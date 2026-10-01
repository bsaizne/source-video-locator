# -*- coding: utf-8 -*-
"""shot_split + patch_refine 生产路径四片双臂验收（2026-09-30 续33 尾巴）。

用途：为「两旋钮默认值翻转」（pipeline.shot_split_enabled / patch_refine_enabled）
提供**生产路径**证据——前序验证（validate_split_patch_refine.py）是把 runtime 模块
**离线**套在已有生产结果批上；本脚本走完整 srv.locate()（含切分/检索/定位/门/重排）。

arm OFF: 出厂默认（两旋钮 False） -> work/spl_patch_arms/off_{case}.results.json
arm ON : 两旋钮 True            -> work/spl_patch_arms/on_{case}.results.json
产物目录独立（不复用 work/ 根下既有名字，防「输出路径无区分度」覆写事故再犯）。

指标:
  python mvp/scripts/measure_four_results.py --pattern "work/spl_patch_arms/off_{case}.results.json"
  python mvp/scripts/measure_four_results.py --pattern "work/spl_patch_arms/on_{case}.results.json"

预立门槛（与 validate_split_patch_refine.py 同规格）:
  严格 >=130 且结构性零回退 | FP <=4 | 导出实得 >=107 且净增 > 0 | feature_version 零变更。
若生产路径不达标 => 维持两旋钮默认关，不作为产品行为启用（离线 +12 不自动外推）。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/rerun_split_patch_arms.py both
  （单臂: ... rerun_split_patch_arms.py on [case] ; SVL_FORCE_RERUN=1 强制重跑）
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

OUT = BENCH / "work" / "spl_patch_arms"
ARMS = {"off": (False, False), "on": (True, True)}


def main() -> int:
    arm = sys.argv[1] if len(sys.argv) > 1 else "both"
    only = sys.argv[2] if len(sys.argv) > 2 else None
    arms = ["off", "on"] if arm == "both" else [arm]
    for a in arms:
        assert a in ARMS, "arm 只能是 off/on/both, 收到 %r" % a
    cases = [only] if only else list(CASES)
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    cfg = srv.config.pipeline
    assert cfg.fast_global_enabled is True, "基线要求 fast_global_enabled=True（现役默认）"
    OUT.mkdir(parents=True, exist_ok=True)

    for a in arms:
        split_flag, patch_flag = ARMS[a]
        cfg.shot_split_enabled = split_flag
        cfg.patch_refine_enabled = patch_flag
        print("=" * 74, flush=True)
        print("[arm %s] shot_split_enabled=%s patch_refine_enabled=%s backend=%s"
              % (a, split_flag, patch_flag, type(srv.backend).__name__), flush=True)
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
