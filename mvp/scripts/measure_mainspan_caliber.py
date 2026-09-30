# -*- coding: utf-8 -*-
"""main-span 同口径(截等长严格)测量 —— fast-global 立项的 77/139 基线口径复算。

判据(与续9~续10m 的"对方 localization 只有主 span ⇒ 公平对照"口径一致):
  每条结果只取主 span, 从起点截到**该段编辑窗等长**(消掉我方 span 偏宽红利),
  再跑 measure_shot_recall.evaluate 的严格判据。子 span / alternatives 全部不参与。

用法:
  python mvp/scripts/measure_mainspan_caliber.py --pattern "work/fastglobal_{case}.results.json" \
      --out work/fastglobal_{case}_caliber.json
"""
from __future__ import annotations

import argparse
import copy
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


def truncate_main(batch: dict) -> dict:
    b = copy.deepcopy(batch)
    for r in b.get("results", []):
        orig = r.get("original") or {}
        ed = r.get("edited_segment") or {}
        w = ed.get("end", 0) - ed.get("start", 0)
        if w > 0 and "candidate_start" in orig:
            orig["candidate_end"] = orig["candidate_start"] + w
        r["original_segments"] = []
        r["alternatives"] = []
    return b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", required=True, help="含 {case} 占位")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    rows, tot = [], {"hit": 0, "n": 0}
    for case, gt_rel in CASES:
        rp = BENCH / args.pattern.format(case=case)
        if not rp.exists():
            continue
        batch = truncate_main(json.loads(rp.read_text(encoding="utf-8")))
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        m = evaluate(gt, batch.get("results", []))
        rows.append({"case": case, "strict": m["strict_hit"], "n": m["n_pos"]})
        tot["hit"] += m["strict_hit"]
        tot["n"] += m["n_pos"]
        print("%-6s main-span截等长严格 %d/%d" % (case, m["strict_hit"], m["n_pos"]))
    print("合计 %d/%d" % (tot["hit"], tot["n"]))
    if args.out:
        (BENCH / args.out).write_text(json.dumps({"rows": rows, "total": tot},
                                                 ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
