# -*- coding: utf-8 -*-
"""iframecut 探针 vs 基线 三指标对比（2026-09-05）。

对照表:
  - 基线: 2mkv->rerun_2mkv_twopass_flash, test1-3->rerun_*_twopass (严格 112/139, 场景 136/139, 负例 4/9)
  - 探针: rerun_*_iframecut.results.json
运行: python mvp/scripts/compare_iframecut.py
"""
import json, sys
from pathlib import Path
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402

CASES = [
    ("2mkv",  BENCH / "datasets/real/ground_truth_v4.json",
     BENCH / "work/rerun_2mkv_twopass_flash.results.json",
     BENCH / "work/rerun_2mkv_iframecut.results.json"),
    ("test1", BENCH / "datasets/real/ground_truth_test1.json",
     BENCH / "work/rerun_test1_twopass.results.json",
     BENCH / "work/rerun_test1_iframecut.results.json"),
    ("test2", BENCH / "datasets/real/ground_truth_test2.json",
     BENCH / "work/rerun_test2_twopass.results.json",
     BENCH / "work/rerun_test2_iframecut.results.json"),
    ("test3", BENCH / "datasets/real/ground_truth_test3.json",
     BENCH / "work/rerun_test3_twopass.results.json",
     BENCH / "work/rerun_test3_iframecut.results.json"),
]

def main():
    rows = []
    tot = {"strict":0,"n_pos":0,"scene":0,"fp":0,"n_neg":0,"sup":0,"tot":0}
    tot_p = dict(tot)
    print("=" * 100)
    print(f"{'片':<8s} {'基线 严格/场景/负例':<26s} {'iframecut 严格/场景/负例':<26s} {'严格Δ':<8s} {'场景Δ':<8s} {'负例Δ':<8s}")
    print("-" * 100)
    for label, gtp, basep, probep in CASES:
        gt = json.loads(Path(gtp).read_text(encoding="utf-8"))
        rb = json.loads(Path(basep).read_text(encoding="utf-8"))["results"]
        rp = json.loads(Path(probep).read_text(encoding="utf-8"))["results"]
        eb = evaluate(gt, rb, label=label + " 基线")
        ep = evaluate(gt, rp, label=label + " iframecut")
        for t, r in ((tot, eb), (tot_p, ep)):
            t["strict"] += r["strict_hit"]; t["n_pos"] += r["n_pos"]
            t["scene"] += r["scene_hit"]; t["fp"] += r["fp"]; t["n_neg"] += r["n_neg"]
            t["sup"] += r["sup"]; t["tot"] += r["tot"]
        d_strict = ep["strict_hit"] - eb["strict_hit"]
        d_scene = ep["scene_hit"] - eb["scene_hit"]
        d_fp = ep["fp"] - eb["fp"]
        b = f"{eb['strict_hit']}/{eb['n_pos']}  {eb['scene_hit']}/{eb['n_pos']}  {eb['fp']}/{eb['n_neg']}"
        p = f"{ep['strict_hit']}/{ep['n_pos']}  {ep['scene_hit']}/{ep['n_pos']}  {ep['fp']}/{ep['n_neg']}"
        print(f"{label:<8s} {b:<26s} {p:<26s} {d_strict:>+3d}      {d_scene:>+3d}      {d_fp:>+3d}")
    print("-" * 100)
    b = f"{tot['strict']}/{tot['n_pos']}  {tot['scene']}/{tot['n_pos']}  {tot['fp']}/{tot['n_neg']}"
    p = f"{tot_p['strict']}/{tot_p['n_pos']}  {tot_p['scene']}/{tot_p['n_pos']}  {tot_p['fp']}/{tot_p['n_neg']}"
    print(f"{'合计':<8s} {b:<26s} {p:<26s} {tot_p['strict']-tot['strict']:>+3d}      {tot_p['scene']-tot['scene']:>+3d}      {tot_p['fp']-tot['fp']:>+3d}")
    print("=" * 100)
    return 0

if __name__ == "__main__":
    sys.exit(main())
