# -*- coding: utf-8 -*-
"""方案1补臂 — 两级切分 + 8fps 查询（同采样比切分器，钉死 TN 有无净增量）。

与 rerun_tn_fed.py 的 tnfed_8（TN+8fps）同口径（都关 shot_split/patch_refine、索引1fps、
edited_cache 关、查询 8fps），唯一差异 = 切分器（两级 vs TN）。两者直接对比即「同采样下
TN 是否胜过我方两级切分」。配合 off（两级+2fps 单片）看「喂饱对我方切分是否也有用」。

跑：D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/rerun_twofed.py
测：python mvp/scripts/measure_four_results.py --pattern "work/twofed_8_{case}.results.json" --out work/_four_twofed8.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import rerun_transnet_runtime as a1  # noqa: E402  复用 CASES/_Progress/env（不 patch TN）
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from infrastructure.logging import configure_logging  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402

BENCH = Path(r"D:\claudework\benchmark")


def run(fps: float, case: str, paths: dict) -> None:
    out = BENCH / "work" / ("twofed_%d_%s.results.json" % (int(fps), case))
    if out.exists():
        print("  %s fps=%g: skip (exists)" % (case, fps), flush=True)
        return
    cfg = load_config()
    cfg.pipeline.edited_segment_fps = fps
    cfg.pipeline.shot_split_enabled = False
    cfg.pipeline.patch_refine_enabled = False
    cfg.pipeline.edited_cache_enabled = False
    srv = SourceLocatorService(config=cfg)
    t0 = time.monotonic()
    batch = srv.locate(paths["edited"], paths["original"], on_progress=a1._Progress())
    out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
    unresolved = sum(1 for r in batch.results if r.failure_reason)
    print("  %s fps=%g: %d 段 HIGH=%d unresolved=%d elapsed=%.1fs -> %s"
          % (case, fps, len(batch.results), n_high, unresolved,
             time.monotonic() - t0, out.name), flush=True)


def main() -> int:
    configure_logging(stream=sys.stdout)
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    del srv
    fps = float(sys.argv[1]) if len(sys.argv) > 1 else 8.0
    print("两级切分(生产默认) + %gfps 查询 + 关 shot_split/patch_refine" % fps, flush=True)
    for case, paths in a1.CASES.items():
        run(fps, case, paths)
    print("ALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
