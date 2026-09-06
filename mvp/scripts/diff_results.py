"""对比两份 results JSON(基线 vs 场景扩展),输出每段主定位/子span/置信 diff 与三指标。

用法:
  python mvp/scripts/diff_results.py baseline.json new.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))["results"]


def brief(r):
    spans = [(round(s["candidate_start"], 1), round(s["candidate_end"], 1))
             for s in r.get("original_segments") or []]
    conf = r.get("confidence") or "LOW"
    nis = "NIS" if r.get("not_in_source") else ""
    fr = r.get("failure_reason") or ""
    return (f"main=({r['original']['candidate_start']:.1f},{r['original']['candidate_end']:.1f}) "
            f"conf={conf} sub={spans} {nis}{fr}")


def main() -> int:
    base, new = load(sys.argv[1]), load(sys.argv[2])
    print(f"baseline {len(base)} results vs new {len(new)} results\n")
    n_changed = 0
    for i, (b, n) in enumerate(zip(base, new)):
        bb, nb = brief(b), brief(n)
        ed = f"ed {b['edited_segment']['start']:.1f}-{b['edited_segment']['end']:.1f}"
        if bb != nb:
            n_changed += 1
            print(f"[CHANGED] s{i} {ed}\n  - {bb}\n  + {nb}")
        else:
            print(f"[same   ] s{i} {ed} {bb}")
    print(f"\nchanged: {n_changed}/{min(len(base), len(new))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
