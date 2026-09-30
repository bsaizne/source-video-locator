# -*- coding: utf-8 -*-
"""对比两份 measure_four_results --out 产物, 列出逐 ID 命中翻转。

用法: python mvp/scripts/diff_two_metrics.py work/fastglobal_on_metrics.json work/fastglobal_on_min2_metrics.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")


def marks(mp: dict) -> dict:
    out = {}
    for row in mp["rows"]:
        for p in row.get("per_pos", []):
            out[f"{row['label']}/{p['id']}"] = p["mark"]
    return out


def main() -> int:
    a = json.loads((BENCH / sys.argv[1]).read_text(encoding="utf-8"))
    b = json.loads((BENCH / sys.argv[2]).read_text(encoding="utf-8"))
    ma, mb = marks(a), marks(b)
    flips = [(k, ma.get(k), mb.get(k)) for k in sorted(set(ma) | set(mb))
             if ma.get(k) != mb.get(k)]
    for k, x, y in flips:
        arrow = "IMPROVE" if y == "HIT" and x != "HIT" else ("REGRESS" if x == "HIT" else "change")
        print("%-18s %s -> %s  [%s]" % (k, x, y, arrow))
    if not flips:
        print("(no per-id flips)")
    print("totals: A strict %s/%s  B strict %s/%s" % (
        sum(r.get("strict_hit", r.get("strict", 0)) for r in a["rows"]),
        sum(r["n_pos"] for r in a["rows"]),
        sum(r.get("strict_hit", r.get("strict", 0)) for r in b["rows"]),
        sum(r["n_pos"] for r in b["rows"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
