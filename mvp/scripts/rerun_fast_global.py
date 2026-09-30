# -*- coding: utf-8 -*-
"""fast_global_anchor 四片双臂生产回归（PROJECT_FAST_GLOBAL_ANCHOR M1, 2026-09-28）。

arm OFF: 现役默认(vote_prior 开, fast_global 关)  -> work/fastglobal_off_{case}.results.json
arm ON : fast_global 开(替换 vote_prior 应用点)   -> work/fastglobal_on_{case}.results.json
验收门(章程 §3): main-span 同口径净增 >= +8 且三指标零回退 + 翻转逐张读图; 不达标即关闭。

运行: "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/rerun_fast_global.py [case]
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
from device.directml_backend import DirectMLBackend  # noqa: E402
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
        if stage != self.stage or now - self.t_last > 30:
            self.stage = stage
            self.t_last = now
            print("    [%s] %s %s/%s" % (stage, getattr(ev, "message", ""),
                                         getattr(ev, "current", 0),
                                         getattr(ev, "total", 0) or "?"), flush=True)


def _apply_leg_env(cfg) -> None:
    """M2 消融腿旋钮注入（SVL_FG_TOP_K / SVL_FG_WIDE_STD / SVL_FG_MIN_SAMPLES / SVL_FG_QUALITY）。"""
    for env, attr, cast in (("SVL_FG_TOP_K", "fast_global_vote_top_k", int),
                            ("SVL_FG_WIDE_STD", "fast_global_wide_std_max_s", float),
                            ("SVL_FG_MIN_SAMPLES", "fast_global_min_valid_samples", int),
                            ("SVL_FG_QUALITY", "fast_global_quality_weights_enabled", lambda v: v == "1")):
        v = os.environ.get(env)
        if v:
            setattr(cfg, attr, cast(v))
            print("[leg] %s=%s" % (attr, v), flush=True)


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cases = [only] if only else list(CASES)
    arms = set((os.environ.get("SVL_ARMS") or "off,on").split(","))
    srv = SourceLocatorService(config=load_config())
    b = srv.backend
    print("BACKEND_SELECTED type=%s" % type(b).__name__, flush=True)
    assert isinstance(b, DirectMLBackend), f"必须 DirectMLBackend, 实际 {type(b).__name__}"
    tag = os.environ.get("SVL_OUT_TAG")
    _apply_leg_env(srv.config.pipeline)
    for enabled in (False, True):
        suffix = "on" if enabled else "off"
        if suffix not in arms:
            continue
        if tag and suffix == "off":
            continue   # 消融腿只需 ON 臂, OFF 基线复用既有产物
        srv.config.pipeline.fast_global_enabled = enabled
        for name in cases:
            out = BENCH / "work" / ("fastglobal_%s_%s.results.json"
                                    % (tag or suffix, name))
            if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
                print("[skip] %s" % out.name, flush=True)
                continue
            paths = CASES[name]
            t0 = time.monotonic()
            print("[case %s arm %s] locate start" % (name, suffix), flush=True)
            batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            print("[case %s arm %s] done %.1fs (%d segments)"
                  % (name, suffix, time.monotonic() - t0, len(batch.results)), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
