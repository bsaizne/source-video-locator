"""mAP@δ 边界尺子（2026-10-28 批次1，调研③「边界时刻精度无尺子」的落地）。

参照 SoccerNet Action Spotting 的 mAP@δ（多容差平均精度），适配到本项目的
「编辑片段 → 原片素材起点」任务：

口径（全部为生产可得信号，无 GT 泄漏进排序）：
- **被量化的时刻 = 素材起点**：GT 用 ``positives[*]["original"][0]``（原片窗起点），
  预测用主 span 的 ``original.candidate_start``（导出工程实际拿到的素材起点，
  include_subs=False 口径）。起点是本产品核心输出，故不做中点变体。
- 预测集 = 各片 results.json 的非 not_in_source 行的主 span（空 span 不计）。
- **编辑侧关联守卫**：预测行的 edited_segment 与 GT 行 edited 窗重叠 ≥50%（同负例
  口径）才允许匹配——防止其它编辑段的行在原片侧巧合命中。
- 匹配：|pred_start − gt_start| ≤ δ，每条 GT 在排序序里至多被认领一次。
- 排序：``confidence_score`` 降序 → 置信档降序（HIGH>MEDIUM>LOW）→ 行号升序（稳定）。
- AP@δ：排序序上每个 TP 处的 precision 累加 ÷ 正例数；对 δ ∈ {0.1,0.25,0.5,1,2}s
  逐档计算，另给 recall@δ（每条 GT 取编辑侧关联主 span 的最小 |Δstart| ≤ δ 占比）。
- 汇总：per-film AP/recall + 四片合并池化（GT 逐条独立，预测按同序合并）。

用法（四片现役批）：
  python mvp/scripts/measure_boundary_map.py \
      --pattern "work/ab_xfeat_start_{case}.results.json" \
      --out work/batch1_20261028/boundary_map_baseline.json

纯标准库实现，零第三方依赖；零 runtime 改动。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json"),
    ("test1", "datasets/real/ground_truth_test1.json"),
    ("test2", "datasets/real/ground_truth_test2.json"),
    ("test3", "datasets/real/ground_truth_test3.json"),
]

DELTAS = (0.1, 0.25, 0.5, 1.0, 2.0)
_CONF_RANK = {"HIGH": 2, "MEDIUM": 1, "LOW": 0}


def _edited_overlap(a0, a1, b0, b1) -> float:
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    return inter / max(1e-6, min(a1 - a0, b1 - b0))


def load_predictions(res_rows: list[dict]) -> list[dict]:
    """主 span 预测（导出实得口径），带生产排序键。"""
    preds = []
    for idx, r in enumerate(res_rows):
        if r.get("not_in_source"):
            continue
        o = r.get("original") or {}
        a, b = o.get("candidate_start"), o.get("candidate_end")
        if a is None or b is None or b - a <= 0.01:
            continue
        e = r.get("edited_segment") or {}
        preds.append({
            "row": idx,
            "start": float(a),
            "end": float(b),
            "e0": float(e.get("start", 0.0)),
            "e1": float(e.get("end", 0.0)),
            "score": float(r.get("confidence_score") or 0.0),
            "tier": _CONF_RANK.get(r.get("confidence"), 0),
        })
    preds.sort(key=lambda p: (-p["score"], -p["tier"], p["row"]))
    return preds


def evaluate_case(gt: dict, res_rows: list[dict], *, label: str = "") -> dict:
    """单片 AP@δ / recall@δ。"""
    preds = load_predictions(res_rows)
    positives = [(p["edited"][0], p["edited"][1], float(p["original"][0]))
                 for p in gt["positives"]]
    n_pos = len(positives)

    per_delta = {}
    for delta in DELTAS:
        # ---- AP@δ：排序序扫描，GT 至多被认领一次 ----
        claimed = [False] * n_pos
        tp = 0
        prec_at_tp = []
        for p in preds:
            for j, (e0, e1, o_start) in enumerate(positives):
                if claimed[j]:
                    continue
                if _edited_overlap(p["e0"], p["e1"], e0, e1) < 0.5:
                    continue
                if abs(p["start"] - o_start) <= delta:
                    claimed[j] = True
                    tp += 1
                    prec_at_tp.append(tp / (len(prec_at_tp) + 1))
                    break
        ap = (sum(prec_at_tp) / n_pos) if n_pos else 0.0

        # ---- recall@δ：每条 GT 的最小 |Δstart|（编辑侧关联的主 span）----
        hit = 0
        for e0, e1, o_start in positives:
            errs = [abs(p["start"] - o_start) for p in preds
                    if _edited_overlap(p["e0"], p["e1"], e0, e1) >= 0.5]
            hit += bool(errs) and min(errs) <= delta
        per_delta[delta] = {"ap": round(ap, 4), "recall": round(hit / n_pos, 4) if n_pos else 0.0}
    return {"label": label, "n_pos": n_pos, "n_pred": len(preds), "per_delta": per_delta}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", required=True,
                    help="结果文件路径模板, 用 {case} 占位(相对 repo 根)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    rows, pooled_preds, pooled_gt = [], [], []   # 池化：GT 带片前缀, 预测带片标签
    for case, gt_rel in CASES:
        res_p = BENCH / args.pattern.format(case=case)
        gt_p = BENCH / gt_rel
        if not res_p.exists():
            print(f"MISSING results: {res_p}")
            continue
        gt = json.loads(gt_p.read_text(encoding="utf-8"))
        res = json.loads(res_p.read_text(encoding="utf-8"))["results"]
        r = evaluate_case(gt, res, label=case)
        rows.append(r)
        off = len(pooled_gt)
        pooled_gt.extend([(e0, e1, o0) for e0, e1, o0 in
                          ((p["edited"][0], p["edited"][1], float(p["original"][0]))
                           for p in gt["positives"])])
        for p in load_predictions(res):
            q = dict(p)
            q["film"] = case
            pooled_preds.append(q)
        del off
        print(f"  {case:7s} n_pos={r['n_pos']:3d} n_pred={r['n_pred']:3d}  " +
              "  ".join(f"δ{d}s AP={r['per_delta'][d]['ap']:.3f} R={r['per_delta'][d]['recall']:.3f}"
                        for d in DELTAS))

    # ---- 四片池化 AP@δ ----
    pooled = {}
    for delta in DELTAS:
        claimed = [False] * len(pooled_gt)
        tp = 0
        prec = []
        for p in pooled_preds:
            for j, (e0, e1, o_start) in enumerate(pooled_gt):
                if claimed[j]:
                    continue
                if _edited_overlap(p["e0"], p["e1"], e0, e1) < 0.5:
                    continue
                if abs(p["start"] - o_start) <= delta:
                    claimed[j] = True
                    tp += 1
                    prec.append(tp / (len(prec) + 1))
                    break
        pooled[delta] = round(sum(prec) / len(pooled_gt), 4) if pooled_gt else 0.0

    print("=" * 88)
    print("四片池化 mAP@δ（素材起点 |Δ|≤δ, confidence_score 排序, GT 一次认领）:")
    print("  " + "  ".join(f"δ={d}s AP={pooled[d]:.4f}" for d in DELTAS))
    print("=" * 88)

    if args.out:
        out = {"pattern": args.pattern, "deltas": list(DELTAS),
               "caliber": "main-span start vs GT original-start, edited-overlap>=0.5 guard",
               "rows": rows, "pooled_ap": pooled}
        Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"saved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
