# -*- coding: utf-8 -*-
"""②③ 单调弱先验落地后重跑: 用新代码(含 timeline_prior)重跑 2.mkv + test1-3 分析。

结果批保存到 work/rerun_<case>_timelineprior.results.json(不覆盖历史 cases/)。
随后用新 GT(test1-3 正式版 + v4) 跑 measure_shot_recall, 对比旧基线:
  2.mkv v4: 32/39 | test1: 32/43 | test2: 9/20 | test3: 31/37
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
    srv = SourceLocatorService(config=load_config())
    for name, paths in CASES.items():
        if only and name != only:
            continue
        print(f"\n=== {name} rerun (timeline_prior) ===", flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"])
            out_dir = Path(os.environ.get("SVL_RUN_OUT", str(Path(os.environ.get("TEMP", "/tmp")))))
            out_dir.mkdir(parents=True, exist_ok=True)
            out = out_dir / f"rerun_{name}_timelineprior.results.json"
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(batch.to_dict(), f, ensure_ascii=False, indent=1)
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            n_tp = sum(1 for r in batch.results
                       if "temporal_outlier_repair" in r.confidence.reasons)
            n_cr = sum(1 for r in batch.results if "conflict_rerank" in r.confidence.reasons)
            n_seq = sum(1 for r in batch.results if "sequence_rerank" in r.confidence.reasons)
            print(f"  {name}: {len(batch.results)} 段 HIGH={n_high} "
                  f"repair={n_tp} conflict={n_cr} seq={n_seq} "
                  f"elapsed={time.monotonic()-t0:.1f}s -> {out.name}", flush=True)
        except Exception as exc:
            print(f"  {name} FAILED: {type(exc).__name__}: {exc}", flush=True)
    print("\nALL DONE", flush=True)

if __name__ == "__main__":
    main()
