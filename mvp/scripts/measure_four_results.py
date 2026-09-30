"""四片三指标批量评估(任意结果批) —— 基线核对与 ViT-B 回归复用。

用法:
  python mvp/scripts/measure_four_results.py --pattern "work/rerun_{case}_perfopt.results.json"
  python mvp/scripts/measure_four_results.py --pattern "work/vitb_{case}.results.json" --out work/vitb_four_metrics.json

GT(与 measure_baseline.py 一致): 2mkv -> ground_truth_v4.json; test1/2/3 -> ground_truth_test*.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json"),
    ("test1", "datasets/real/ground_truth_test1.json"),
    ("test2", "datasets/real/ground_truth_test2.json"),
    ("test3", "datasets/real/ground_truth_test3.json"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", required=True,
                    help="结果文件路径模板, 用 {case} 占位(相对 repo 根)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows, totals = [], {"strict": 0, "main": 0, "n_pos": 0, "scene": 0, "fp": 0,
                        "n_neg": 0, "sup": 0, "tot": 0}
    for case, gt_rel in CASES:
        res_p = BENCH / args.pattern.format(case=case)
        gt_p = BENCH / gt_rel
        if not res_p.exists():
            print("MISSING results: %s" % res_p, flush=True)
            continue
        gt = json.loads(gt_p.read_text(encoding="utf-8"))
        res = json.loads(res_p.read_text(encoding="utf-8"))["results"]
        r = evaluate(gt, res, label=case)
        r["gt"] = str(gt_p)
        r["results"] = str(res_p)
        rows.append(r)
        for k in ("strict_hit", "main_hit", "n_pos", "scene_hit", "fp", "n_neg", "sup", "tot"):
            key = {"strict_hit": "strict", "main_hit": "main", "scene_hit": "scene"}.get(k, k)
            totals[key] += r[k]

    print("=" * 78)
    print("四片汇总(严格 | 导出实得=仅主 span | 场景级±15s | 负例误报 | 支撑)")
    for r in rows:
        print("  %-7s %-11s %-19s %-13s %-11s %s/%s" % (
            r["label"], "%d/%d" % (r["strict_hit"], r["n_pos"]),
            "%d/%d (差%+d)" % (r["main_hit"], r["n_pos"], r["main_hit"] - r["strict_hit"]),
            "%d/%d" % (r["scene_hit"], r["n_pos"]),
            "%d/%d" % (r["fp"], r["n_neg"]), r["sup"], r["tot"]))
    print("  %-7s %-11s %-19s %-13s %-11s %s/%s" % (
        "合计", "%d/%d" % (totals["strict"], totals["n_pos"]),
        "%d/%d (差%+d)" % (totals["main"], totals["n_pos"],
                           totals["main"] - totals["strict"]),
        "%d/%d" % (totals["scene"], totals["n_pos"]),
        "%d/%d" % (totals["fp"], totals["n_neg"]), totals["sup"], totals["tot"]))
    print("=" * 78)

    if args.out:
        Path(args.out).write_text(json.dumps(
            {"pattern": args.pattern, "rows": rows, "total": totals},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print("saved %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
