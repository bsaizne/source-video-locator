# -*- coding: utf-8 -*-
"""ISC 近场亚门带 A/B（2026-10-06 续57 夜间批终版设计）。

唯一差量 = ``pipeline.isc_refine_margin_near`` 0.05 → **0.035**（near_offset_s=3.0 默认）：
|best_mid − main_mid| ≤ 3s 的近场候选门降到 0.035，远跳候选维持 0.05。设计依据
（2mkv 全量 0.035 臂读图裁决 + FINDINGS_ORTHOGONAL_BACKBONE_PROBE §3/§4）：
  - 真救回全在近场（t1r12a offset 2.0s / 2mkv row23 offset 1.5s 读图=真增益）；
  - 亚门分远跳 = 真损失（2mkv 0.9s 窄段 HIGH 被 56.6s 远跳，读图裁决）⇒ 远跳维持 0.05。
off 臂 = 复用 ``work/defaults_flip_ab/<case>/on.results.json``（同代码态默认旋钮；
本批 isc_refine 改动在 margin_near=0.05 下行为逐位不变，复用成立）。

验收门：严格/导出/场景/负例 零回退 + t1r08c/t1r12a 逐案例核对 + 翻转行逐张读图。
Run: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_isc_subgate_ab.py [--case test1]
输出: work/isc_subgate_ab/<case>.results.json + summary.json
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from rerun_fast_global import CASES, _Progress  # noqa: E402

OUT = BENCH / "work" / "isc_subgate_ab"
MARGIN_NEAR = 0.035


def strip(data: dict) -> dict:
    d = copy.deepcopy(data)
    d.pop("result_id", None)
    for r in d.get("results", []):
        r.pop("result_id", None)
    return d


def _span_str(row: dict) -> str:
    o = row.get("original")
    if isinstance(o, dict):
        return "%.2f-%.2f" % (o.get("start", o.get("candidate_start", -1)),
                              o.get("end", o.get("candidate_end", -1)))
    return str(o)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default=None, choices=sorted(CASES))
    args = ap.parse_args()
    cases = [args.case] if args.case else list(CASES)
    OUT.mkdir(parents=True, exist_ok=True)
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    cfg = srv.config.pipeline
    assert cfg.fast_global_enabled and cfg.shot_split_enabled and cfg.patch_refine_enabled
    assert cfg.isc_refine_enabled and cfg.isc_refine_scan_radius_s == 90.0
    summary = {}
    for case in cases:
        paths = CASES[case]
        cfg.isc_refine_margin_near = MARGIN_NEAR
        print("[subgate %s] margin=%.3f margin_near=%.3f near_offset=%.1f BACKEND=%s"
              % (case, cfg.isc_refine_margin, cfg.isc_refine_margin_near,
                 cfg.isc_refine_near_offset_s, type(srv.backend).__name__), flush=True)
        t0 = time.monotonic()
        batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
        wall = round(time.monotonic() - t0, 1)
        out_p = OUT / ("%s.results.json" % case)
        out_p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                         encoding="utf-8")
        ref_p = BENCH / "work" / "defaults_flip_ab" / case / "on.results.json"
        s_new = strip(json.loads(out_p.read_text(encoding="utf-8")))
        s_ref = strip(json.loads(ref_p.read_text(encoding="utf-8")))
        flips = []
        for i, (a, b) in enumerate(zip(s_ref.get("results", []), s_new.get("results", []))):
            if a != b:
                flips.append(i)
                print("  [FLIP] %s row %d edited=%s\n    ref  main=%s conf=%s\n    sub  main=%s conf=%s"
                      % (case, i, a.get("edited_segment"), _span_str(a), a.get("confidence"),
                         _span_str(b), b.get("confidence")), flush=True)
        identical = s_ref == s_new
        summary[case] = {"wall_s": wall, "strip_identical": identical,
                         "n_flip_rows": len(flips), "flip_rows": flips}
        print("SUMMARY[subgate %s] wall=%.1fs identical=%s flips=%d"
              % (case, wall, identical, len(flips)), flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
