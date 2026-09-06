# backend.spec — PyInstaller onedir 打包生产 Python 后端（MVP 只读全套冻结栈 + FastAPI 桥）。
#
# 产出 dist/backend/backend.exe（+ _internal/）。Electron 生产模式直接 spawn 这个
# exe（见 electron/backend/config.ts 的 prodBackendConfig）。FFmpegIO 的 ffmpeg/ffprobe
# 二进制**不在**本 bundle 内，由 Electron 主进程以 MEDIA_FFMPEG/MEDIA_FFPROBE 环境变量
# 指向 <resources>/backend/ffmpeg.exe|ffprobe.exe 交给运行时 resolve（不改 mvp/src）。
#
# 运行：
#   python -m PyInstaller --clean --noconfirm mvp/scripts/backend.spec \
#     --distpath ... --workpath ...
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

SPEC_DIR = Path(os.path.dirname(os.path.abspath(SPEC))).resolve()   # …/mvp/scripts
SRC = SPEC_DIR.parent / "src"            # …/mvp/src
SRC = str(SRC)
sys.path.insert(0, SRC)

# 桥 + 冻结栈：把 mvp.api 与 mvp/src 的各个顶层包（可被 import mvp.api.main 触达）
# 的模块都收进来。FFmpegIO 走 subprocess（ffmpeg/ffprobe），不 import cv2.VideoCapture。
from PyInstaller.utils.hooks import collect_data_files

hiddenimports = [
    "PIL",  # rapidocr utils 依赖(动态导入路径,PyInstaller 静态分析未捕获,显式声明)
    *collect_submodules("rapidocr_onnxruntime")
    + collect_submodules("mvp.api")
    + collect_submodules("app")
    + collect_submodules("domain")
    + collect_submodules("engine")
    + collect_submodules("device")
    + collect_submodules("infrastructure")
    + collect_submodules("media")
    # uvicorn 的运行时按字符串动态 import 的子模块，静态分析触不到，需显式列出。
    + [
        "uvicorn.logging",
        "uvicorn.loops.auto",
        "uvicorn.loops.asyncio",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.http.h11_impl",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.protocols.websockets.websockets_impl",
        "uvicorn.lifespan.on",
        "cffi",
        "anyio._backends._asyncio",
    ],
]

# console=True + Electron spawn 的 windowsHide（CREATE_NO_WINDOW）：可靠地把
# uvicorn 日志写到 stdout/stderr 管道，又不闪控制台。
a = Analysis(
    [str(SPEC_DIR / "run_backend.py")],
    pathex=[str(SPEC_DIR.parent), SRC],
    binaries=[],
    datas=[
        # rapidocr 自带检测/识别模型与配置(OCR 文字锚点第二信号,打包后可用)
        *collect_data_files("rapidocr_onnxruntime"),
    ],
    hiddenimports=hiddenimports,
    # 明确排除：产品运行时不需要（用 torch/cv2/onnxruntime/numpy；fastapi/uvicorn/pydantic）。
    # scipy/pandas/PIL 是 PyInstaller torch hook 的过度收集——验证过 `import torch;import cv2;
    # import onnxruntime` 均不传递导入它们，且 mvp/src 从未使用。排除后需跑一次真实索引冒烟
    # 确认推理仍正常（见 bundle_optimization_report.md 的 Risk）。
    # PIL 不排除:rapidocr(OCR 文字锚点)依赖它
    excludes=["tkinter", "matplotlib", "IPython", "notebook", "jupyter",
              "torchvision", "PyQt5", "PySide6", "scipy", "pandas",
              "scipy.spatial", "scipy.stats",
              "scipy.special", "scipy.linalg", "scipy.sparse"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="backend",
    console=True,           # console subsystem；由 Electron windowsHide 抑制控制台
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="backend")
