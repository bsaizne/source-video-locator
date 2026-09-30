# -*- coding: utf-8 -*-
"""fast_global 翻默认开后的默认态四片验收批（2026-09-29 用户拍板 ②）。

零环境注入、零配置覆写 —— 纯出厂 load_config()（fast_global_enabled=True）全链路,
验收 = 复现 M1 ON 臂数字（严格 127/139 · 场景 137 · 负例 4/9 · 口径 105/139）。
产物: work/fastglobal_default_{case}.results.json
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
from rerun_fast_global import CASES, _Progress  # noqa: E402


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cases = [only] if only else list(CASES)
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(srv.backend).__name__}"
    cfg = srv.config.pipeline
    assert cfg.fast_global_enabled is True, "默认态验收要求 fast_global_enabled=True"
    assert not getattr(cfg, "fast_global_quality_weights_enabled", False), "腿 c 必须默认关"
    assert int(getattr(cfg, "fast_global_vote_top_k", 1)) == 1, "腿 a 必须默认关"
    assert float(getattr(cfg, "fast_global_wide_std_max_s", 0.0)) == 0.0, "腿 b 必须默认关"
    print("BACKEND_SELECTED type=%s fast_global_enabled=%s (pure default)" %
          (type(srv.backend).__name__, cfg.fast_global_enabled), flush=True)
    for name in cases:
        out = BENCH / "work" / ("fastglobal_default_%s.results.json" % name)
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print("[skip] %s" % out.name, flush=True)
            continue
        paths = CASES[name]
        t0 = time.monotonic()
        print("[case %s default] locate start" % name, flush=True)
        batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
        out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                       encoding="utf-8")
        print("[case %s default] done %.1fs (%d segments)"
              % (name, time.monotonic() - t0, len(batch.results)), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
