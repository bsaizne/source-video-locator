# -*- coding: utf-8 -*-
"""isc_refine 生产路径四片双臂验收（2026-10-02 续44 立项后置验收）。

用途：为「ISC 第二意见局部重排」（pipeline.isc_refine_enabled，默认关）提供生产路径
证据——走完整 srv.locate()（现役默认：shot_split/patch_refine 均开，fast_global 开），
唯一变量 = isc_refine_enabled。

arm OFF: 现役默认（isc 关）  -> work/isc_refine_arms/off_{case}.results.json
arm ON : isc_refine_enabled  -> work/isc_refine_arms/on_{case}.results.json
产物目录独立（防「输出路径无区分度」覆写事故再犯）。

验收门（FINDINGS_ORTHOGONAL_BACKBONE_PROBE_20261002 §9.3）:
  严格/导出实得/负例 三指标零回退（硬门）| MISS6 + t2r03b 逐案例核对（必验收，如实报告）
  | 翻转行逐张读图 | feature_version 零变更。
不达标 => isc_refine 维持默认关，不作为产品行为启用。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/rerun_isc_refine.py both
  （单臂: ... rerun_isc_refine.py on [case] ; SVL_FORCE_RERUN=1 强制重跑）
  指标:
  python mvp/scripts/measure_four_results.py --pattern "work/isc_refine_arms/{off|on}_{case}.results.json"
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

OUT = BENCH / "work" / "isc_refine_arms"


def main() -> int:
    arm = sys.argv[1] if len(sys.argv) > 1 else "both"
    only = sys.argv[2] if len(sys.argv) > 2 else None
    arms = ["off", "on"] if arm == "both" else [arm]
    if arm == "v2":
        arms = ["v2"]
    if arm == "ladder":
        arms = ["ladder"]
    for a in arms:
        assert a in ("off", "on", "v2", "ladder"), "arm 只能是 off/on/v2/ladder/both, 收到 %r" % a
    cases = [only] if only else list(CASES)
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    cfg = srv.config.pipeline
    assert cfg.fast_global_enabled is True, "基线要求 fast_global_enabled=True（现役默认）"
    assert cfg.shot_split_enabled and cfg.patch_refine_enabled, \
        "基线要求两旋钮默认开（现役）"
    OUT.mkdir(parents=True, exist_ok=True)

    for a in arms:
        cfg.isc_refine_enabled = (a in ("on", "v2", "ladder"))
        cfg.isc_refine_scan_radius_s = (90.0 if a in ("v2", "ladder") else 0.0)
        cfg.isc_refine_ladder_s = (30.0 if a == "ladder" else 0.0)
        print("=" * 74, flush=True)
        print("[arm %s] isc=%s radius=%s ladder=%s margin=%s"
              % (a, cfg.isc_refine_enabled, cfg.isc_refine_scan_radius_s,
                 cfg.isc_refine_ladder_s, cfg.isc_refine_margin), flush=True)
        for name in cases:
            out = OUT / ("%s_%s.results.json" % (a, name))
            if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
                print("[skip] %s" % out.name, flush=True)
                continue
            paths = CASES[name]
            t0 = time.monotonic()
            print("[arm %s | case %s] locate start" % (a, name), flush=True)
            batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
            data = batch.to_dict()
            out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
            print("[arm %s | case %s] done %.1fs (%d segments) -> %s"
                  % (a, name, time.monotonic() - t0, len(data["results"]), out.name), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
