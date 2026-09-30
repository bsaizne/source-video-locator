# -*- coding: utf-8 -*-
"""E1 连续重复起点修正 双臂生产回归（2026-09-28; 竞品 resolve_consecutive 语义移植验收）。

走生产 SourceLocatorService.locate 全链路（默认数据目录/默认索引, vote_prior 默认开=现役口径）:
  arm OFF: resolve_consecutive_enabled=False -> work/consec_off_{case}.results.json
  arm ON : resolve_consecutive_enabled=True  -> work/consec_on_{case}.results.json
两臂同进程同缓存, 唯一差异 = 该旋钮。OFF 臂应与 work/voteprior_{case}.results.json 逐位一致
（vote_prior 现役默认开同口径; 若不一致须先归因再谈 ON 臂结论）。

运行（默认 test2+test3=影响面所在片; 传 case 名可单跑）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/rerun_consecutive.py [case]
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
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",
              "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",
              "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
    "2mkv":  {"edited": r"D:\video\1.mp4", "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",
              "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
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


def _run_arm(srv, cfg, *, enabled: bool, cases: list[str]) -> None:
    cfg.pipeline.resolve_consecutive_enabled = enabled
    suffix = "on" if enabled else "off"
    for name in cases:
        paths = CASES[name]
        out = BENCH / "work" / ("consec_%s_%s.results.json" % (suffix, name))
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print("[skip] %s exists" % out.name, flush=True)
            continue
        t0 = time.monotonic()
        print("[case %s arm %s] locate start" % (name, suffix), flush=True)
        batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
        out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print("[case %s arm %s] done %.1fs -> %s (%d segments)"
              % (name, suffix, time.monotonic() - t0, out.name, len(batch.results)),
              flush=True)


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cases = [only] if only else ["test2", "test3"]
    cfg = load_config()
    assert cfg.pipeline.vote_prior_enabled, "现役默认: vote_prior 应为开(续21)"
    srv = SourceLocatorService(config=cfg)
    b = srv.backend
    print("BACKEND_SELECTED type=%s" % type(b).__name__, flush=True)
    # 硬断言后端（记忆教训: 隔离数据目录/环境漂移会静默降级 CPU, 那样数字全部作废）
    assert isinstance(b, DirectMLBackend), f"必须 DirectMLBackend, 实际 {type(b).__name__}"
    _run_arm(srv, cfg, enabled=False, cases=cases)
    _run_arm(srv, cfg, enabled=True, cases=cases)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
