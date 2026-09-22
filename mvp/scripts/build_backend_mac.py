# -*- coding: utf-8 -*-
"""build_backend_mac — macOS 版后端打包（CI 用, 在 macOS ARM64 runner 上运行）。

与 build_backend.py（Windows）同构:
  PyInstaller onedir（backend.spec, 产物二进制名 `backend`）→ 装配 ui/resources/backend/
  （backend + _internal/ + ffmpeg + ffprobe——**静态链接**版, 见 _static_media_binaries）→
  DINOv2 权重装配到 ui/resources/models/dinov2_vits14/（MPS 后端经
  SVL_DINOV2_WEIGHTS 引用; mac 无 DML, 不装 onnx）。

依赖: pip install torch numpy opencv-python fastapi uvicorn pyinstaller rapidocr-onnxruntime static-ffmpeg
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


def _static_media_binaries() -> tuple[Path, Path]:
    """返回**静态链接**的 (ffmpeg, ffprobe)，来自 static_ffmpeg 包。

    不能用 PATH 上的 ffmpeg：macOS runner 的 ffmpeg 来自 Homebrew，是**动态链接**的
    （依赖 /opt/homebrew/Cellar/ffmpeg/<ver>/lib/*.dylib）。只 copy2 可执行文件进 app
    bundle，用户机器上没有那些库 → dyld 直接失败:
      Library not loaded: /opt/homebrew/Cellar/ffmpeg/9.0.1_1/lib/libavdevice.63.dylib
    static_ffmpeg 提供自带全部依赖的静态构建（与 Windows build_backend.py 同源）。
    """
    try:
        import static_ffmpeg.run as _sfr
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("missing static-ffmpeg (pip install static-ffmpeg): "
                         f"it provides statically-linked ffmpeg/ffprobe ({exc})")
    ffmpeg_exe, ffprobe_exe = _sfr.get_or_fetch_platform_executables_else_raise()
    return Path(ffmpeg_exe), Path(ffprobe_exe)


def main() -> None:
    ffmpeg, ffprobe = _static_media_binaries()
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

    # 2) 装配 resources/backend（mac 二进制名无 .exe; ffmpeg/ffprobe 为静态构建）
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
