# -*- coding: utf-8 -*-
"""shot_split+patch_refine 双臂翻转行的**口径机制分解**（2026-09-30 续33 尾巴）。

背景：measure_shot_recall.evaluate 的 main_hit（导出实得口径）由三条判据之一满足
within(±2s 容差) / mid_in(GT 中点落 span 内) / cov(交叠>=0.4)，外加编辑侧联合覆盖
的 union(joint_main) 组装条款。+12 里必须逐行分清"真位置增益"与"装配/容差打折"。

用法: python mvp/scripts/diag_split_patch_flips.py
产物: work/spl_patch_arms/flip_caliber.json + stdout 表
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from measure_shot_recall import _union_covers, overlap_frac, result_spans  # noqa: E402

CASES = [("2mkv", "datasets/real/ground_truth_v4.json", "work/fastglobal_default_%s.results.json"),
         ("test1", "datasets/real/ground_truth_test1.json", "work/fastglobal_default_%s.results.json"),
         ("test2", "datasets/real/ground_truth_test2.json", "work/fastglobal_default_%s.results.json"),
         ("test3", "datasets/real/ground_truth_test3.json", "work/fastglobal_default_%s.results.json")]
ON = "work/spl_patch_arms/on_%s.results.json"


def arm_state(res: list[dict], p: dict) -> dict:
    e0, e1 = p["edited"]
    o0, o1 = p["original"]
    cov_main, ed_intervals = [], []
    mech = None
    for i, r in enumerate(res):
        re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        if max(0.0, min(e1, re1) - max(e0, re0)) <= 0:
            continue
        ed_intervals.append((max(e0, re0), min(e1, re1)))
        for kind, a, b in result_spans(r):
            if kind != "main":
                continue
            within = (a >= o0 - 2.0) and (b <= o1 + 2.0)
            mid_in = a <= (o0 + o1) / 2 <= b
            cov = overlap_frac(o0, o1, a, b) >= 0.4
            if mech is None and (within or mid_in or cov):
                mech = {"kind": "direct", "row": i, "span": [round(a, 2), round(b, 2)],
                        "within": within, "mid_in": mid_in, "cov": cov}
            if a <= o1 and b >= o0:
                cov_main.append((a, b))
    if mech is None:
        ed_union = _union_covers(ed_intervals, e0, e1, 0.5) if ed_intervals else False
        if cov_main and ed_union and _union_covers(cov_main, o0, o1):
            mech = {"kind": "union", "spans": [[round(a, 2), round(b, 2)] for a, b in cov_main]}
    return mech


def main() -> int:
    out = []
    for case, gt_rel, off_pat in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        off = json.loads((BENCH / (off_pat % case)).read_text(encoding="utf-8"))["results"]
        on = json.loads((BENCH / (ON % case)).read_text(encoding="utf-8"))["results"]
        for p in gt["positives"]:
            a, b = arm_state(off, p), arm_state(on, p)
            ha, hb = a is not None, b is not None
            if ha == hb:
                continue
            verdict = "GAIN" if hb else "LOSS"
            mech = (b if hb else a)["kind"]
            out.append({"case": case, "id": p["id"], "verdict": verdict, "mech": mech,
                        "gt_og": p["original"], "off": a, "on": b})
            print("%-6s %-7s %-4s mech=%-6s GT_OG=%s" % (case, p["id"], verdict, mech, p["original"]))
            print("        OFF %s" % json.dumps(a, ensure_ascii=False))
            print("        ON  %s" % json.dumps(b, ensure_ascii=False))
    (BENCH / "work" / "spl_patch_arms" / "flip_caliber.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n共 %d 行翻转；机制分布:" % len(out))
    dist: dict[str, int] = {}
    for r in out:
        k = "%s/%s" % (r["verdict"], r["mech"])
        dist[k] = dist.get(k, 0) + 1
    for k, v in sorted(dist.items()):
        print("   %-16s %d" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
