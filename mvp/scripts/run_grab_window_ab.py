# -*- coding: utf-8 -*-
"""grab_window_decode 全片 A/B（2026-10-03 续46）：零语义证明 + 计时。

arm off: grab_window_decode=False（现役形态, 每帧 spawn 并行4）
arm on : grab_window_decode=True （窗批量解码）
唯一变量 = 该 flag；产物 work/grab_window_ab/{arm}_test1.results.json。
验收：strip(result_id) 后全部确定性字段逐位一致（同 续34 口径）+ 耗时对比。
Run: python mvp/scripts/run_grab_window_ab.py [case]  (默认 test1)
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

OUT = BENCH / "work" / "grab_window_ab"


def main() -> int:
    case = sys.argv[1] if len(sys.argv) > 1 else "test1"
    OUT.mkdir(parents=True, exist_ok=True)
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend)
    paths = CASES[case]
    for arm, flag in (("off", False), ("on", True)):
        srv.config.pipeline.grab_window_decode = flag
        out = OUT / f"{arm}_{case}.results.json"
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print(f"[skip] {out.name}", flush=True)
            continue
        t0 = time.monotonic()
        print(f"[arm {arm} | {case}] locate start (grab_window_decode={flag})", flush=True)
        batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
        data = batch.to_dict()
        out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[arm {arm}] done {time.monotonic()-t0:.1f}s ({len(data['results'])} segs) -> {out.name}",
              flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
