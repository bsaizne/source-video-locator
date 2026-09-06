"""build_backend — 编排：PyInstaller 打包生产后端 + 装配到 mvp/ui/resources/backend。

用法（在 benchmark 目录，用 venv 的 python 运行）：
  ../video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/build_backend.py

产物：
  resources/backend/
    backend.exe          # PyInstaller onedir 单进程入口（uvicorn 启动 FastAPI）
    _internal/           # Python 运行时 + 冻结栈 + torch/cv2/onnx 等依赖
    ffmpeg.exe           # 媒体二进制（Electron 用 MEDIA_FFMPEG 指向）
    ffprobe.exe
    README.md

不动 ``mvp/src``。build/dist 中间产物留在 scripts/ 下（gitignore）。
"""
import shutil
import subprocess
import sys
from pathlib import Path

# tools/ 下的 ffmpeg + venv static_ffmpeg 的 ffprobe（与 AGENTS.md 记录的路径一致）
FFMPEG = Path(__file__).resolve().parents[2] / "tools" / "ffmpeg.exe"
ROOT = Path(__file__).resolve().parents[2]                # benchmark
MVP = ROOT / "mvp"
SCRIPTS = MVP / "scripts"
BACKEND_DIR = MVP / "ui" / "resources" / "backend"
DIST = SCRIPTS / "dist_backend"
WORK = SCRIPTS / "build_backend_work"

# 显式 ffprobe 路径（venv 位于 benchmark 的兄弟目录 video-dedup-tool 下）
FFPROBE = ROOT.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages" \
    / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe"


def _ensure(name: Path) -> None:
    if not name.exists():
        raise SystemExit(f"missing required binary: {name}")


# PyInstaller torch/onnx 钩子过度收集、但运行时从未 import 的包。已用打包后端做
# 真实 DINOv2 索引 + 预览验证：剔除后推理/预览正常（见 bundle_optimization_report.md）。
# 注意：不要剔除 torch/cv2/onnxruntime/numpy（必需）。
# PIL 不可剪:rapidocr(OCR 文字锚点第二信号)依赖它(2026-08-29 修复)
PRUNE_DIRS = ["scipy", "scipy.libs", "pandas", "pandas.libs", "onnx",
              "onnxscript"]


def _prune_unused(internal: Path) -> None:
    for name in PRUNE_DIRS:
        targets = list(internal.glob(name))
        targets += list(internal.glob(f"{name}-*.dist-info"))
        for t in targets:
            shutil.rmtree(t, ignore_errors=True)
    print(">>> pruned unused: " + ", ".join(PRUNE_DIRS))


def main() -> None:
    _ensure(FFMPEG)
    _ensure(FFPROBE)

    # 1) PyInstaller onedir -> DIST/backend/
    if DIST.exists():
        shutil.rmtree(DIST)
    if WORK.exists():
        shutil.rmtree(WORK)
    cmd = [
        sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
        str(SCRIPTS / "backend.spec"),
        "--distpath", str(DIST),
        "--workpath", str(WORK),
    ]
    print(">>> running PyInstaller:", " ".join(cmd))
    subprocess.run(cmd, check=True)

    # 2) 装配 resources/backend（onedir + 媒体二进制）
    built = DIST / "backend"
    if not (built / "backend.exe").exists():
        raise SystemExit(f"PyInstaller did not produce backend.exe under {built}")
    if BACKEND_DIR.exists():
        shutil.rmtree(BACKEND_DIR)
    shutil.copytree(built, BACKEND_DIR)
    shutil.copy2(FFMPEG, BACKEND_DIR / "ffmpeg.exe")
    shutil.copy2(FFPROBE, BACKEND_DIR / "ffprobe.exe")

    # 3) 剔除钩子过度收集、运行时未使用的包（PyInstaller excludes 对钩子收集不生效）。
    _prune_unused(BACKEND_DIR / "_internal")

    total = sum(f.stat().st_size for f in BACKEND_DIR.rglob("*") if f.is_file())
    print(f">>> assembled {BACKEND_DIR} ({total / 1024 / 1024:.0f} MiB)")


if __name__ == "__main__":
    main()
