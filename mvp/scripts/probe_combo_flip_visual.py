# -*- coding: utf-8 -*-
"""五环组合探针 翻转出图(test1, 2026-09-26 续10c).

对双口径评估(probe_combo_dual_caliber.py 产物)中 A(four-ring) 与 B(five-ring+G5) 两臂的
差异条目出四行对照图: ED(GT) / OG(G5臂) / OG(A臂) / OG(GT) —— 沿用 review_proxy_loc_visual.sheet()。
出图桶: C1名次变化 / C2严格翻转 / G5平滑修复 / 一致抽样(防虚高)。

用法: python mvp/scripts/probe_combo_flip_visual.py --eval work/combo_probe_test1.json \
        --loc-a <...comboA...json> --loc-b <...comboG5...json> --case test1
产物: work/combo_probe_review/*.png + manifest.json
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from pathlib import Path

import cv2

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(B / "mvp" / "scripts"))
from review_proxy_loc_visual import CASES, sheet  # noqa: E402

OUT = B / "work" / "combo_probe_review"


def load_rows(loc_path: Path) -> dict:
    """qid -> results-schema 简化行(供 sheet 用)。"""
    d = json.loads(loc_path.read_text(encoding="utf-8"))
    rows = {}
    for q in d.get("queries", []):
        sp = q.get("source_span") or {}
        rows[q["query_id"]] = {
            "edited_segment": {"start": q["ed"]["start_ms"] / 1000.0, "end": q["ed"]["end_ms"] / 1000.0},
            "original": {"candidate_start": sp.get("start_ms", 0) / 1000.0,
                         "candidate_end": sp.get("end_ms", 0) / 1000.0},
            "confidence": q.get("score"),
            "not_in_source": bool(q.get("not_in_source")) or not q.get("source_span")}
    return rows


def best_row_for_gt(rows: dict, gt_ed: tuple, matched_only: bool = True):
    e0, e1 = gt_ed
    best, bo = None, -1.0
    for r in rows.values():
        if matched_only and r.get("not_in_source"):
            continue
        o = min(e1, r["edited_segment"]["end"]) - max(e0, r["edited_segment"]["start"])
        if o > bo:
            best, bo = r, o
    return best if bo > 0 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default=str(B / "work/combo_probe_test1.json"))
    ap.add_argument("--loc-a", required=True)
    ap.add_argument("--loc-b", required=True)
    ap.add_argument("--case", default="test1")
    ap.add_argument("--max-consistent", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20260926)
    args = ap.parse_args()
    random.seed(args.seed)

    ev = json.loads(Path(args.eval).read_text(encoding="utf-8"))
    ed, om, gt_name = CASES[args.case]
    gt = json.loads((B / "datasets" / "real" / gt_name).read_text(encoding="utf-8"))
    gt_by_id = {p["id"]: p for p in gt["positives"]}
    rows_a = load_rows(Path(args.loc_a))
    rows_b = load_rows(Path(args.loc_b))
    OUT.mkdir(parents=True, exist_ok=True)

    f = ev["flips_A_vs_G5"]
    jobs = []  # (bucket, gid)
    for x in f["c1_rank_changes"]:
        jobs.append(("C1名次变化", x["id"]))
    for x in f["c2_hit_flips"]:
        jobs.append(("C2严格翻转", x["id"]))
    for gid in f["g5_smoothed_entries"][:8]:
        jobs.append(("G5平滑修复", gid))
    consistent = [p["id"] for p in ev["A_four_ring"]["c1"]["per"]
                  if p["rank"] is not None and p["rank"] == dict(
                      (q["id"], q["rank"]) for q in ev["B_five_ring_g5"]["c1"]["per"]).get(p["id"])]
    for gid in random.sample(consistent, min(args.max_consistent, len(consistent))):
        jobs.append(("E一致抽样", gid))

    manifest, csv_rows = [], []
    for bucket, gid in jobs:
        g = gt_by_id.get(gid)
        if g is None:
            continue
        gt_ed = tuple(map(float, g["edited"]))
        gt_og = tuple(map(float, g["original"]))
        c1a = next((x for x in ev["A_four_ring"]["c1"]["per"] if x["id"] == gid), {})
        c1b = next((x for x in ev["B_five_ring_g5"]["c1"]["per"] if x["id"] == gid), {})
        c2a = next((x for x in ev["A_four_ring"]["c2"]["per"] if x["id"] == gid), {})
        c2b = next((x for x in ev["B_five_ring_g5"]["c2"]["per"] if x["id"] == gid), {})
        va = "c1r%s/c2%s" % (c1a.get("rank"), "HIT" if c2a.get("hit") else "MISS")
        vb = "c1r%s/c2%s" % (c1b.get("rank"), "HIT" if c2b.get("hit") else "MISS")
        # A 臂作 baseline 位, G5 臂作 proxy 位
        img = sheet(args.case, gid, bucket, ed, om, gt_ed, gt_og,
                    best_row_for_gt(rows_b, gt_ed), best_row_for_gt(rows_a, gt_ed), vb, va)
        fp = OUT / ("%s_%s_%s.png" % (args.case, gid, bucket[:2]))
        cv2.imwrite(str(fp), img)
        manifest.append({"case": args.case, "gt_id": gid, "bucket": bucket,
                         "A_verdict": va, "G5_verdict": vb, "png": fp.name})
        csv_rows.append({"png": fp.name, "gt_id": gid, "bucket": bucket,
                         "A_v": va, "G5_v": vb, "verdict_A": "", "verdict_G5": "",
                         "verdict_GT": "", "notes": ""})
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    if csv_rows:
        with open(OUT / "verdicts_template.csv", "w", newline="", encoding="utf-8-sig") as fh:
            w = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()))
            w.writeheader()
            w.writerows(csv_rows)
    print("出图 %d 张 -> %s (桶分布: %s)" % (len(manifest), OUT,
          {b: sum(1 for m in manifest if m["bucket"] == b) for b in set(m["bucket"] for m in manifest)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
