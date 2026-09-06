# -*- coding: utf-8 -*-
"""两级切分+白闪守卫 进 runtime 后的四片回归（2026-09-05 用户拍板）。

直接用生产 SourceLocatorService（默认 seg_twopass_enabled=True 走
_segment_twopass_flash 路径, 含白闪守卫）跑四片 locate, 结果存
work/rerun_<case>_runtime_twopassflash.results.json, 供 measure_baseline 对照
（基线: 2mkv twopass_flash + test1-3 twopass = 严格 112/139, 场景 136/139, 负例 4/9）。

GPU 约定: 启动打印 BACKEND_SELECTED（DirectML/amd 生效）。
"""
import json
import os
import sys
import time
from pathlib import Path

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

CASES = {
    "2mkv":  {"edited": r"D:\video\1.mp4",            "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",  "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",  "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",  "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
}


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    try:
        b = srv.backend
        print(f"BACKEND_SELECTED type={type(b).__name__} "
              f"device={getattr(b, 'device_name', lambda: '?')()} "
              f"dtype={getattr(b, 'device_type', lambda: '?')()}", flush=True)
    except Exception as bexc:
        print(f"BACKEND_SELECTED ERROR: {bexc}", flush=True)
    print("seg_twopass_enabled =", cfg.pipeline.seg_twopass_enabled, flush=True)
    for name, paths in CASES.items():
        if only and name != only:
            continue
        out = BENCH / "work" / f"rerun_{name}_runtime_twopassflash.results.json"
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print(f"  {name}: skip (result exists)", flush=True)
            continue
        print(f"\n=== {name} runtime twopass+flash ===", flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"])
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            print(f"  {name}: {len(batch.results)} 段 HIGH={n_high} "
                  f"elapsed={time.monotonic()-t0:.1f}s -> {out.name}", flush=True)
        except Exception as exc:
            print(f"  {name} FAILED: {type(exc).__name__}: {exc}", flush=True)
    print("\nALL DONE", flush=True)


if __name__ == "__main__":
    main()
