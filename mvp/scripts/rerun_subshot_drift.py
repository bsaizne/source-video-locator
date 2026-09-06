# -*- coding: utf-8 -*-
"""montage 主定位漂移触发判据修复后的四片回归（2026-09-05 HANDOFF_SUBSHOT_QUERY §4）。

与 rerun_runtime_twopass_flash.py 同生产路径（seg_twopass_enabled=True），仅输出
独立结果文件 work/rerun_<case>_subshotdrift.results.json（历史结果不覆盖约定；
基线批 = work/_backup_pre_subshot_rescue/）。

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
from infrastructure.logging import configure_logging  # noqa: E402

configure_logging(stream=sys.stdout)

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
    print("seg_twopass_enabled =", cfg.pipeline.seg_twopass_enabled,
          "subshot_enabled =", cfg.pipeline.subshot_enabled,
          "subshot_drift_gap_s =", cfg.pipeline.subshot_drift_gap_s, flush=True)
    for name, paths in CASES.items():
        if only and name != only:
            continue
        out = BENCH / "work" / f"rerun_{name}_subshotdrift.results.json"
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print(f"  {name}: skip (result exists)", flush=True)
            continue
        print(f"\n=== {name} subshot drift ===", flush=True)
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
