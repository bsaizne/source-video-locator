# -*- coding: utf-8 -*-
"""build_backend_mac — macOS 版后端打包（CI 用, 在 macOS ARM64 runner 上运行）。

与 build_backend.py（Windows）同构:
  PyInstaller onedir（backend.spec, 产物二进制名 `backend`）→ 装配 ui/resources/backend/
  （backend + _internal/ + ffmpeg + ffprobe——取 runner PATH 上的媒体二进制）→
  DINOv2 权重装配到 ui/resources/models/dinov2_vits14/（MPS 后端经
  SVL_DINOV2_WEIGHTS 引用; mac 无 DML, 不装 onnx）。

依赖: pip install torch numpy opencv-python fastapi uvicorn pyinstaller rapidocr-onnxruntime
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]                # benchmark
MVP = ROOT / "mvp"
SCRIPTS = MVP / "scripts"
BACKEND_DIR = MVP / "ui" / "resources" / "backend"
MODELS_DIR = MVP / "ui" / "resources" / "models"
DIST = SCRIPTS / "dist_backend"
WORK = SCRIPTS / "build_backend_work"

PRUNE_DIRS = ["scipy", "scipy.libs", "pandas", "pandas.libs", "onnx", "onnxscript"]


def _which(name: str) -> Path:
    p = shutil.which(name)
    if not p:
        raise SystemExit(f"missing required binary on PATH: {name} (macOS runner 自带)")
    return Path(p)


def main() -> None:
    ffmpeg = _which("ffmpeg")
    ffprobe = _which("ffprobe")
    weights = Path(os.environ.get("SVL_DINOV2_WEIGHTS", "")) \
        if os.environ.get("SVL_DINOV2_WEIGHTS") else \
        ROOT / ".cache" / "dinov2_weights" / "dinov2_vits14_pretrain.pth"
    if not weights.exists():
        raise SystemExit(f"missing DINOv2 weights: {weights}")

    # 1) PyInstaller onedir
    if DIST.exists():
        shutil.rmtree(DIST)
    if WORK.exists():
        shutil.rmtree(WORK)
    cmd = [sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
           str(SCRIPTS / "backend.spec"), "--distpath", str(DIST), "--workpath", str(WORK)]
    print(">>> running PyInstaller:", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)

    # 2) 装配 resources/backend（mac 二进制名无 .exe; ffmpeg/ffprobe 取 PATH）
    built = DIST / "backend"
    binary = built / "backend"
    if not binary.exists():
        raise SystemExit(f"PyInstaller did not produce backend binary under {built}")
    if BACKEND_DIR.exists():
        shutil.rmtree(BACKEND_DIR)
    shutil.copytree(built, BACKEND_DIR)
    shutil.copy2(ffmpeg, BACKEND_DIR / "ffmpeg")
    shutil.copy2(ffprobe, BACKEND_DIR / "ffprobe")

    # 3) prune（与 Windows 版同一清单）
    internal = BACKEND_DIR / "_internal"
    for name in PRUNE_DIRS:
        for t in list(internal.glob(name)) + list(internal.glob(f"{name}-*.dist-info")):
            shutil.rmtree(t, ignore_errors=True)

    # 4) DINOv2 权重（MPS 后端用）→ resources/models/dinov2_vits14/
    wdir = MODELS_DIR / "dinov2_vits14"
    wdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(weights, wdir / "dinov2_vits14_pretrain.pth")

    total = sum(f.stat().st_size for f in BACKEND_DIR.rglob("*") if f.is_file())
    print(f">>> assembled {BACKEND_DIR} ({total / 1024 / 1024:.0f} MiB)", flush=True)


if __name__ == "__main__":
    main()
