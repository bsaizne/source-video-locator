# -*- coding: utf-8 -*-
"""偏移投票起点先验 四片生产回归（2026-09-27 续11; 立项=用户拍板, mvp 移植验收）。

走生产 SourceLocatorService.locate 全链路（默认资产/默认索引, feature_version 不变）:
  SVL_VOTE_PRIOR=0  仅基线复跑（默认关, 应与 denserecheck_off 逐位一致）
  SVL_VOTE_PRIOR=1  vote_prior ON（dense off）           -> work/voteprior_{case}.results.json
  SVL_VOTE_PRIOR=2  vote_prior + dense_recheck 双开（全链）-> work/voteprior_dense_{case}.results.json
基线 = work/denserecheck_off_{case}.results.json（2026-09-26 续10l, 与 perfopt 基线逐位一致）。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/rerun_vote_prior.py [case]
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
    mode = os.environ.get("SVL_VOTE_PRIOR", "1")
    cfg = load_config()
    cfg.pipeline.vote_prior_enabled = mode in ("1", "2")
    cfg.pipeline.dense_recheck_enabled = mode == "2"
    suffix = {("0"): "voteprior_off", ("1"): "voteprior", ("2"): "voteprior_dense"}[mode]
    print("cfg: vote_prior=%s dense_recheck=%s support>=%.2f max_shift=%.1fs bucket=%.2fs"
          % (cfg.pipeline.vote_prior_enabled, cfg.pipeline.dense_recheck_enabled,
             cfg.pipeline.vote_prior_min_support, cfg.pipeline.vote_prior_max_shift_s,
             cfg.pipeline.vote_prior_bucket_s), flush=True)
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
            print("[skip] %s exists (%s)" % (out.name, time.strftime("%m-%d %H:%M", time.localtime(out.stat().st_mtime))),
                  flush=True)
            continue
        t0 = time.monotonic()
        print("[case %s] locate start (%s)" % (name, suffix), flush=True)
        try:
            batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            print("[case %s] done %.1fs -> %s (%d segments)"
                  % (name, time.monotonic() - t0, out.name, len(batch.results)), flush=True)
        except Exception as exc:
            import traceback
            print("[case %s] FAILED: %s: %s" % (name, type(exc).__name__, exc), flush=True)
            traceback.print_exc()
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
