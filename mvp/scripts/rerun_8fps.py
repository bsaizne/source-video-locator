# -*- coding: utf-8 -*-
"""C 项验证:编辑侧 8fps 全量重跑(2026-09-05)。

只改 edited_segment_fps=8.0(其余 config 默认, 同 rerun_timeline_prior.py),
重跑 2.mkv + test1-3 完整管线(analyze→locate), 结果批保存到
work/rerun_<case>_8fps.results.json(不覆盖历史), 供 measure_baseline 对比。
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
    cfg.pipeline.edited_segment_fps = 8.0
    print("edited_segment_fps =", cfg.pipeline.edited_segment_fps, flush=True)
    srv = SourceLocatorService(config=cfg)
    for name, paths in CASES.items():
        if only and name != only:
            continue
        print(f"\n=== {name} rerun (8fps) ===", flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"])
            out = BENCH / "work" / f"rerun_{name}_8fps.results.json"
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            n_repair = sum(1 for r in batch.results if "temporal_outlier_repair" in r.confidence.reasons)
            n_cr = sum(1 for r in batch.results if "conflict_rerank" in r.confidence.reasons)
            n_seq = sum(1 for r in batch.results if "sequence_rerank" in r.confidence.reasons)
            print(f"  {name}: {len(batch.results)} 段 HIGH={n_high} repair={n_repair} "
                  f"conflict={n_cr} seq={n_seq} elapsed={time.monotonic()-t0:.1f}s -> {out.name}", flush=True)
        except Exception as exc:
            print(f"  {name} FAILED: {type(exc).__name__}: {exc}", flush=True)
    print("\nALL DONE", flush=True)

if __name__ == "__main__":
    main()
