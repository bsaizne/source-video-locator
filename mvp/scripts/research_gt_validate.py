"""研究验证 — 蒙太奇原型 vs 基线，在 GT（ground_truth_corrected.json）上的 recall 校检。

对每个 GT 段（edited 区间 视觉确认的 original 区间）：
  1. 找到与该 GT edited 区间重叠最大的 App 段。
  2. 基线（user_results.json 的单 span）在该 App 段上对 GT original 的覆盖率。
  3. 原型（montage_localize.json 的子 span）在该 App 段上对 GT original 的最大覆盖率。
  4. 统计 recall（cover>=0.5）baseline vs 原型。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_gt_validate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
U = BENCH / "mvp" / "benchmark" / "user_case"
GT = BENCH / "datasets" / "real" / "ground_truth_corrected.json"
BASELINE = U / "user_results.json"
PROTO = U / "montage_research" / "montage_localize.json"
COVER_THRESH = 0.5


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def cover(span, g0, g1):
    if not span:
        return 0.0
    return overlap(span[0], span[1], g0, g1) / max(g1 - g0, 1e-6)


def main():
    gt = json.loads(GT.read_text(encoding="utf-8"))["segments"]
    proto = {s["idx"]: s for s in json.loads(PROTO.read_text(encoding="utf-8"))["segments"]}
    base = json.loads(BASELINE.read_text(encoding="utf-8"))["results"]

    print("=== GT 段 校检（cover>=%.1f 记命中）===" % COVER_THRESH)
    print(f"{'GT':4} {'edited':>14} {'orig':>16} | {'基线span':>18} cov | {'原型最大子span':>18} cov")
    rows = []
    for g in gt:
        ge0, ge1 = g["edited_start"], g["edited_end"]
        go0, go1 = g["original_start"], g["original_end"]
        # 找与该 GT edited 重叠最大的 App 段
        best_idx, best_ov = None, -1.0
        for idx, seg in proto.items():
            e0, e1 = seg["edited"]
            ov = overlap(ge0, ge1, e0, e1)
            if ov > best_ov:
                best_ov, best_idx = ov, idx
        seg = proto[best_idx]
        # 基线单 span（App 段 idx == results 顺序）
        br = base[best_idx]
        bspan = (br["original"]["candidate_start"], br["original"]["candidate_end"])
        bcov = cover(bspan, go0, go1)
        # 原型子 span 最大覆盖
        pcov = max((cover(s["span"], go0, go1) for s in seg["sub_spans"] if s["span"]), default=0.0)
        rows.append({"id": g.get("test", "?"), "edited": (ge0, ge1), "orig": (go0, go1),
                     "idx": best_idx, "bspan": bspan, "bcov": bcov, "pcov": pcov})
        print(f"{g.get('test','?'):4} ({ge0:6.1f},{ge1:6.1f}) ({go0:7.1f},{go1:7.1f}) | "
              f"({bspan[0]:7.1f},{bspan[1]:7.1f}) {bcov:.2f} | "
              f"{'--':>18} {pcov:.2f}")

    b_hit = sum(1 for r in rows if r["bcov"] >= COVER_THRESH)
    p_hit = sum(1 for r in rows if r["pcov"] >= COVER_THRESH)
    print(f"\nGT recall 基线={b_hit}/{len(rows)} ({b_hit/len(rows):.0%})  "
          f"原型={p_hit}/{len(rows)} ({p_hit/len(rows):.0%})")
    print("\n=== 原型子 span 明细（每个 App 段 覆盖哪些 GT original）===")
    for idx in sorted(proto):
        seg = proto[idx]
        gts = [(r["id"], r["orig"], round(r["pcov"], 2)) for r in rows if r["idx"] == idx]
        if gts:
            print(f"[{idx:2}] edited={seg['edited']} 命中GT: {gts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
