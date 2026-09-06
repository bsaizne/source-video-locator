"""镜头级 GT 评估——per-shot recall / 负例误报 / 结果 span 支撑率。

对 GT 文件的每条正例:存在某个结果 span(主 span 或 original_segments 子 span),
编辑侧重叠 ≥50% 且原片侧重叠 ≥50%(或包含 GT 中点)→ 召回。
对每条负例:任何结果 span 的编辑侧与之重叠 ≥50% → 误报(把非源片内容也定位了)。
对每个结果 span:原片侧与任一正例重叠 → 有 GT 支撑,否则 = 无支撑定位。

运行(单片):
  "D:/claudework/video-dedup-tool/.venv/scripts/python.exe" mvp/scripts/measure_shot_recall.py \
      [--gt datasets/real/ground_truth_v3.json] [--results mvp/benchmark/user_case/user_results.json]

四片基线一键复跑见 mvp/scripts/measure_baseline.py(调用本模块 evaluate)。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]


def overlap_frac(a0, a1, b0, b1) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    denom = max(1e-6, a1 - a0)
    return inter / denom


def result_spans(r: dict) -> list[tuple[str, float, float]]:
    out = [("main", r["original"]["candidate_start"], r["original"]["candidate_end"])]
    for s in r.get("original_segments") or []:
        out.append(("sub", s["candidate_start"], s["candidate_end"]))
    return [x for x in out if x[2] - x[1] > 0.01]  # 空 span(not_in_source/未定位)不算定位


def _union_covers(spans: list[tuple[float, float]], o0: float, o1: float,
                  min_frac: float = 0.5) -> bool:
    """多个结果 span 的并集是否覆盖 GT 原片区间的 min_frac(细切分管线的复合 GT 口径)。"""
    inter_total = 0.0
    for a0, a1 in spans:
        inter_total += max(0.0, min(a1, o1) - max(a0, o0))
    # 重叠不去重的并集上界即可(保守方向是高估,但重叠 span 已被 IoU 去重)
    return (inter_total / max(1e-6, o1 - o0)) >= min_frac


def evaluate(gt: dict, res: list[dict], *, label: str = "") -> dict:
    """评估一个 GT↔结果批对,返回结构化指标(CLI 打印与 measure_baseline 共用同一口径)。

    返回 dict: {label, n_pos, n_neg, strict_hit, verified_hit, loose_hit, scene_hit,
                fp, sup, tot, per_pos, offenders}
    """
    if label:
        print(f"=== 镜头级评估: {label} ===")
    print(f"=== {len(res)} 段结果 vs GT "
          f"({len(gt['positives'])} 正例 / {len(gt['negatives'])} 负例) ===\n")

    hit = verified_hit = loose_hit = scene_hit = 0
    per_pos = []
    for p in gt["positives"]:
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        covering = []  # (a, b) 原片侧与 GT 有交集的 span(联合覆盖用)
        ed_intervals = []  # 编辑侧与 GT 有交集的区间(联合编辑覆盖用)
        best = None
        best_scene = None
        for i, r in enumerate(res):
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            ed_inter = max(0.0, min(e1, re1) - max(e0, re0))
            if ed_inter <= 0:
                continue
            ed_intervals.append((max(e0, re0), min(e1, re1)))
            for kind, a, b in result_spans(r):
                conf = f"{r['confidence']}({kind})"
                within = (a >= o0 - 2.0) and (b <= o1 + 2.0)
                mid_in = a <= (o0 + o1) / 2 <= b   # 修复:GT 中点须落在 span 内
                cov = overlap_frac(o0, o1, a, b) >= 0.4
                if best is None and (within or mid_in or cov):
                    best = (i, kind, a, b, conf)
                if a <= o1 and b >= o0:
                    covering.append((a, b))
                # 场景级口径:结果中点落在 GT span ±15s 内
                m = (a + b) / 2
                if o0 - 15.0 <= m <= o1 + 15.0 and best_scene is None:
                    best_scene = (i, kind, a, b, conf)
        # 编辑侧联合覆盖:多结果并集计入(细切分管线与复合 GT 的口径对齐)
        ed_union = _union_covers(ed_intervals, e0, e1, 0.5) if ed_intervals else False
        if best is None and covering and ed_union and _union_covers(covering, o0, o1):
            best = ("union", "joint", covering[0][0], covering[-1][1], "joint")
        if p["tier"] == "verified":
            verified_hit += best is not None
        elif p["tier"] == "loose":
            loose_hit += best is not None
        hit += best is not None
        scene_hit += best_scene is not None
        mark = "HIT " if best else ("part" if best_scene else "MISS")
        per_pos.append({"id": p["id"], "tier": p["tier"], "mark": mark.strip()})
        det = (f"s{best[0]}({best[1]} {best[2]:.0f}-{best[3]:.0f} {best[4]})" if best else
              (f"s{best_scene[0]}({best_scene[1]} {best_scene[2]:.0f}-{best_scene[3]:.0f} ~场景级)" if best_scene else "-"))
        print(f"[{mark}] {p['id']} ed{e0:6.1f}-{e1:6.1f} -> og{o0:6.1f}-{o1:6.1f} "
              f"[{p['tier']:8s}] {det}")

    n_ver = sum(1 for p in gt["positives"] if p["tier"] == "verified")
    n_loo = sum(1 for p in gt["positives"] if p["tier"] == "loose")
    print(f"\n正例召回: 严格 {hit}/{len(gt['positives'])} "
          f"(verified {verified_hit}/{n_ver}, loose {loose_hit}/{n_loo}) | "
          f"场景级(±15s) {scene_hit}/{len(gt['positives'])}")

    print("\n=== 负例误报(编辑侧非源片内容被定位;not_in_source 结果=正确拒绝,不计) ===")
    fp = 0
    offenders = []
    for n in gt["negatives"]:
        e0, e1 = n["edited"]
        off = []
        for i, r in enumerate(res):
            if r.get("not_in_source"):
                continue  # 正确拒绝
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            if overlap_frac(e0, e1, re0, re1) >= 0.5:
                for kind, a, b in result_spans(r):
                    off.append(f"s{i}({kind} {a:.0f}-{b:.0f} {r['confidence']})")
        fp += bool(off)
        offenders.append({"id": n["id"], "fp": bool(off)})
        print(f"[{'FP  ' if off else 'OK  '}] {n['id']} ed{e0:6.1f}-{e1:6.1f} "
              f"{n['reason'][:40]} -> {' ; '.join(off) if off else '-'}")
    print(f"负例误报: {fp}/{len(gt['negatives'])}")

    print("\n=== 结果 span 支撑率(定位是否有 GT 依据;空 span/正确拒绝不计) ===")
    sup = tot = 0
    for i, r in enumerate(res):
        if r.get("not_in_source"):
            continue
        for kind, a, b in result_spans(r):
            tot += 1
            supported = any(
                overlap_frac(a, b, p["original"][0], p["original"][1]) >= 0.3
                or (p["original"][0] - 15.0 <= (a + b) / 2 <= p["original"][1] + 15.0)
                for p in gt["positives"])
            sup += supported
            if not supported:
                print(f"  [无支撑] s{i}({kind} {a:.0f}-{b:.0f}) ed"
                      f"{r['edited_segment']['start']:.1f}-{r['edited_segment']['end']:.1f}")
    print(f"有支撑 span: {sup}/{tot}\n")
    return {
        "label": label,
        "n_pos": len(gt["positives"]),
        "n_neg": len(gt["negatives"]),
        "strict_hit": hit,
        "verified_hit": verified_hit,
        "loose_hit": loose_hit,
        "scene_hit": scene_hit,
        "fp": fp,
        "sup": sup,
        "tot": tot,
        "per_pos": per_pos,
        "offenders": offenders,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=str(BENCH / "datasets/real/ground_truth_v3.json"))
    ap.add_argument("--results", default=str(BENCH / "mvp/benchmark/user_case/user_results.json"))
    args = ap.parse_args()

    gt = json.loads(Path(args.gt).read_text(encoding="utf-8"))
    res = json.loads(Path(args.results).read_text(encoding="utf-8"))["results"]
    evaluate(gt, res)
    return 0


if __name__ == "__main__":
    sys.exit(main())