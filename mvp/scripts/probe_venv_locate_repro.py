# -*- coding: utf-8 -*-
"""probe_venv_locate_repro — venv 源码树 in-process 复现打包态 E2E 失败（2026-10-05）。

打包态 r8 在 test1 全链的 isc_refine 阶段崩（LOC-9999，worker log 为 no-op 无堆栈）。
本脚本用**同一份数据目录（AppData）+ 同一默认配置（L2 翻默认开）**在源码树直接调
service.locate——异常自然带完整堆栈穿出。若 venv 过 ⇒ 打包特异；若崩 ⇒ 直接得堆栈。
"""
import os
import sys
import time
import traceback

BENCH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("MEDIA_FFMPEG", os.path.join(BENCH, "tools", "ffmpeg.exe"))
os.environ.setdefault(
    "MEDIA_FFPROBE",
    r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, os.path.join(BENCH, "mvp", "src"))
sys.path.insert(0, os.path.join(BENCH, "mvp"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.locator_service import SourceLocatorService  # noqa: E402

EDITED = r"D:\ProjectXIXI\test1\test1-ed.mp4"
ORIGINAL = r"D:\ProjectXIXI\test1\test1-om.mkv"

try:
    srv = SourceLocatorService()
    t0 = time.monotonic()
    batch = srv.locate(EDITED, ORIGINAL)
    print("LOCATE_OK wall=%.1fs segments=%d" % (time.monotonic() - t0, len(batch.results)))
except Exception:
    traceback.print_exc()
    print("LOCATE_FAILED", flush=True)
    sys.exit(1)
