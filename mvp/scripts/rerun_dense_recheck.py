# -*- coding: utf-8 -*-
"""P0 密集起点复核 四片生产回归（2026-09-26 续10l; mvp 移植验收）。

走生产 SourceLocatorService.locate 全链路（默认资产/默认索引, feature_version 不变）,
仅 cfg.pipeline.dense_recheck_enabled=True（DECISIONS 2026-09-26 豁免裁决）。
产物 work/denserecheck_{case}.results.json → measure_four_results.py 三指标对照基线 117/139。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/rerun_dense_recheck.py [case]
  (case ∈ 2mkv|test1|test2|test3; 省略=四片全跑; SVL_FORCE_RERUN=1 强制重跑)
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))

sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

CASES = {
    "2mkv":  {"edited": r"D:\video\1.mp4", "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",
              "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",
              "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",
              "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
}


class _Progress:
    def __init__(self):
        self.t_last = 0.0
        self.stage = None

    def __call__(self, ev):
        now = time.monotonic()
        stage = getattr(getattr(ev, "stage", None), "value", "?")
        if stage != self.stage or now - self.t_last > 15:
            self.stage = stage
            self.t_last = now
            print("    [%s] %s %s/%s" % (stage, getattr(ev, "message", ""),
                                         getattr(ev, "current", 0),
                                         getattr(ev, "total", 0) or "?"), flush=True)


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config()
    cfg.pipeline.dense_recheck_enabled = os.environ.get("SVL_DENSE_RECHECK", "1") != "0"
    suffix = "denserecheck" if cfg.pipeline.dense_recheck_enabled else "denserecheck_off"
    print("cfg: dense_recheck_enabled=%s margin=%.1fs gain>=%.2f max_shift=%.1fs fps=%d"
          % (cfg.pipeline.dense_recheck_enabled, cfg.pipeline.dense_recheck_margin_s,
             cfg.pipeline.dense_recheck_min_gain, cfg.pipeline.dense_recheck_max_shift_s,
             cfg.pipeline.dense_recheck_fps), flush=True)
    print("cfg: data_dir=%s index_fps=%s" % (cfg.data_dir, cfg.pipeline.index_sampling_fps),
          flush=True)

    srv = SourceLocatorService(config=cfg)
    b = srv.backend
    print("BACKEND_SELECTED type=%s device=%s dtype=%s"
          % (type(b).__name__, getattr(b, "device_name", lambda: "?")(),
             getattr(b, "device_type", lambda: "?")()), flush=True)

    for name, paths in CASES.items():
        if only and name != only:
            continue
        out = BENCH / "work" / ("%s_%s.results.json" % (suffix, name))
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print("  %s: skip (result exists)" % name, flush=True)
            continue
        print("\n=== %s : locate (dense recheck ON) ===" % name, flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"],
                               on_progress=_Progress())
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            n_high = sum(1 for r in batch.results
                         if getattr(getattr(r, "confidence", None), "level", None) is not None
                         and r.confidence.level.value == "HIGH")
            print("  %s: %d 段 HIGH=%d elapsed=%.1fs"
                  % (name, len(batch.results), n_high, time.monotonic() - t0), flush=True)
        except Exception as exc:
            import traceback
            print("  %s FAILED: %s: %s" % (name, type(exc).__name__, exc), flush=True)
            traceback.print_exc()
    print("\nALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
