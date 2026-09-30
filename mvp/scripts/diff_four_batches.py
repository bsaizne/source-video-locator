"""四片结果批逐案差异(A/B 两批对比: 哪些 GT 案例翻转)。

用法:
  python mvp/scripts/diff_four_batches.py \
      --a "work/rerun_{case}_perfopt.results.json" \
      --b "work/vitb_{case}.results.json"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402

CASES = [("2mkv", "datasets/real/ground_truth_v4.json"),
         ("test1", "datasets/real/ground_truth_test1.json"),
         ("test2", "datasets/real/ground_truth_test2.json"),
         ("test3", "datasets/real/ground_truth_test3.json")]


def run(pattern: str):
    out = {}
    for case, gt_rel in CASES:
        rp = BENCH / pattern.format(case=case)
        if not rp.exists():
            continue
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        res = json.loads(rp.read_text(encoding="utf-8"))["results"]
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out[case] = evaluate(gt, res, label=case)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="A 批(通常=基线)结果路径模板")
    ap.add_argument("--b", required=True, help="B 批(通常=新批)结果路径模板")
    args = ap.parse_args()
    a, b = run(args.a), run(args.b)
    print("case   A strict / scene / fp   ->   B strict / scene / fp")
    tot = {"a": [0, 0, 0, 0, 0, 0], "b": [0, 0, 0, 0, 0, 0]}
    for case, _ in CASES:
        ra, rb = a.get(case), b.get(case)
        if not ra or not rb:
            print("%-6s (missing)" % case)
            continue
        print("%-6s %d/%d/%d/%d -> %d/%d/%d/%d" % (
            case, ra["strict_hit"], ra["scene_hit"], ra["fp"], ra["sup"],
            rb["strict_hit"], rb["scene_hit"], rb["fp"], rb["sup"]))
        ma = {p["id"]: p["mark"] for p in ra["per_pos"]}
        mb = {p["id"]: p["mark"] for p in rb["per_pos"]}
        for pid in ma:
            if ma.get(pid) != mb.get(pid):
                print("    FLIP %-8s %-4s -> %-4s" % (pid, ma.get(pid), mb.get(pid)))
        for key, r in (("a", ra), ("b", rb)):
            tot[key][0] += r["strict_hit"]; tot[key][1] += r["n_pos"]
            tot[key][2] += r["scene_hit"]; tot[key][3] += r["fp"]
            tot[key][4] += r["sup"]; tot[key][5] += r["tot"]
    print("\n合计  A 严格 %d/%d 场景 %d/%d 负例 %d 支撑 %d/%d" % (
        tot["a"][0], tot["a"][1], tot["a"][2], tot["a"][1], tot["a"][3], tot["a"][4], tot["a"][5]))
    print("      B 严格 %d/%d 场景 %d/%d 负例 %d 支撑 %d/%d" % (
        tot["b"][0], tot["b"][1], tot["b"][2], tot["b"][1], tot["b"][3], tot["b"][4], tot["b"][5]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
