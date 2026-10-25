# -*- coding: utf-8 -*-
"""开关矩阵四片生产 A/B（2026-10-25 续94，review 缺口收口）。

背景：config 有 5 个默认关的开关（dense_recheck / degradation_gate / resolve_consecutive /
fast_global_quality_weights / conf_v2），历史欠四片生产回归 ⇒ 默认值一直悬置。
本脚本每轮**单变量**开一个（或若干）开关，走生产 SourceLocatorService.locate 全链
（索引/编辑缓存复用、feature_version 不变），产物 work/ab_{tag}_{case}.results.json，
对照基线 = work/scn4_{case}.results.json，三指标用 measure_shot_recall.py。

运行（矩阵=5 开关 × 4 片，顺序执行）:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe -u mvp/scripts/rerun_toggle_ab.py
  ... rerun_toggle_ab.py dense_recheck_enabled          # 只跑一个开关
  ... rerun_toggle_ab.py "dense_recheck_enabled,degradation_gate_enabled"  # 组合
  SVL_FORCE_RERUN=1 强制重跑。
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
TOGGLES = ["dense_recheck_enabled", "degradation_gate_enabled",
           "resolve_consecutive_enabled", "fast_global_quality_weights_enabled",
           "conf_v2_enabled"]


class _Progress:
    def __init__(self):
        self.t_last, self.stage = 0.0, None

    def __call__(self, ev):
        now = time.monotonic()
        stage = getattr(getattr(ev, "stage", None), "value", "?")
        if stage != self.stage or now - self.t_last > 15:
            self.stage, self.t_last = stage, now
            print("    [%s] %s %s/%s" % (stage, getattr(ev, "message", ""),
                                         getattr(ev, "current", 0),
                                         getattr(ev, "total", 0) or "?"), flush=True)


def run_round(toggles: list[str]) -> None:
    tag = "+".join(t.replace("_enabled", "") for t in toggles)
    cfg = load_config()
    for t in toggles:
        # 开关默认都在 pipeline；conf_v2_* 一组挂在 pipeline.confidence（续95 修：
        # 旧写法 assert hasattr(cfg.pipeline, t) 对 conf_v2_enabled 必炸）。
        target = cfg.pipeline if hasattr(cfg.pipeline, t) else cfg.pipeline.confidence
        assert hasattr(target, t), t
        setattr(target, t, True)
    print("\n######## ROUND %s (%s) ########" % (tag, time.strftime("%H:%M:%S")), flush=True)
    srv = SourceLocatorService(config=cfg)
    b = srv.backend
    print("BACKEND_SELECTED type=%s device=%s" % (type(b).__name__,
                                                  getattr(b, "device_name", lambda: "?")()),
          flush=True)
    for name, paths in CASES.items():
        out = BENCH / "work" / ("ab_%s_%s.results.json" % (tag, name))
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print("  %s: skip (exists)" % name, flush=True)
            continue
        print("\n=== %s : locate ===" % name, flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            n_high = sum(1 for r in batch.results
                         if getattr(getattr(r, "confidence", None), "level", None) is not None
                         and r.confidence.level.value == "HIGH")
            print("  %s: %d 段 HIGH=%d elapsed=%.1fs" %
                  (name, len(batch.results), n_high, time.monotonic() - t0), flush=True)
        except Exception as exc:
            import traceback
            print("  %s FAILED: %s: %s" % (name, type(exc).__name__, exc), flush=True)
            traceback.print_exc()


def main() -> int:
    args = sys.argv[1:]
    rounds = [a.split(",") for a in args] if args else [[t] for t in TOGGLES]
    for r in rounds:
        run_round(r)
    print("\nALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
