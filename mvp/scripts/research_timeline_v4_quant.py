# -*- coding: utf-8 -*-
"""④ 时序重排 v4 量化（2026-09-01 拍板执行序第 4 项，研究侧快）。

对比各管线版本结果批在 v4 GT 下的纠正量，重点数:
temporal_outlier_repair + seq_dp（+ conflict_rerank）把「修正前 MISS/part → 修正后 HIT」几条。
复用 measure_shot_recall 口径（严格/场景级/负例/支撑），输出逐条正例命中明细差异。
"""
import json
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import overlap_frac, result_spans, _union_covers

GT = BENCH / "datasets" / "real" / "ground_truth_v4.json"
RES_DIR = BENCH / "mvp" / "benchmark" / "user_case"

VERSIONS = [
    ("baseline_p21", "user_results_baseline_p21.json"),  # Phase 21 前（无场景召回/seq_dp?）
    ("pre22a",       "user_results_pre22a.json"),        # Phase 22a 前
    ("pre24",        "user_results_pre24.json"),         # Phase 24 前（无 conflict_rerank）
    ("current",      "user_results.json"),               # 当前（全部修复）
]

def evaluate(results, gt):
    hit = verified_hit = loose_hit = scene_hit = 0
    rows = []
    for p in gt["positives"]:
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        covering = []
        ed_intervals = []
        best = None
        best_scene = None
        for i, r in enumerate(results):
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            ed_inter = max(0.0, min(e1, re1) - max(e0, re0))
            if ed_inter <= 0:
                continue
            ed_intervals.append((max(e0, re0), min(e1, re1)))
            for kind, a, b in result_spans(r):
                conf = f"{r['confidence']}({kind})"
                within = (a >= o0 - 2.0) and (b <= o1 + 2.0)
                mid_in = a <= (o0 + o1) / 2 <= b
                cov = overlap_frac(o0, o1, a, b) >= 0.4
                if best is None and (within or mid_in or cov):
                    best = (i, kind, a, b, conf)
                if a <= o1 and b >= o0:
                    covering.append((a, b))
                m = (a + b) / 2
                if o0 - 15.0 <= m <= o1 + 15.0 and best_scene is None:
                    best_scene = (i, kind, a, b, conf)
        ed_union = _union_covers(ed_intervals, e0, e1, 0.5) if ed_intervals else False
        if best is None and covering and ed_union and _union_covers(covering, o0, o1):
            best = ("union", "joint", covering[0][0], covering[-1][1], "joint")
        if p["tier"] == "verified":
            verified_hit += best is not None
        elif p["tier"] == "loose":
            loose_hit += best is not None
        hit += best is not None
        scene_hit += best_scene is not None
        rows.append((p["id"], best is not None, best_scene is not None, best, best_scene))
    n_ver = sum(1 for p in gt["positives"] if p["tier"] == "verified")
    n_loo = sum(1 for p in gt["positives"] if p["tier"] == "loose")
    # 负例
    fp = 0
    for n in gt["negatives"]:
        e0, e1 = n["edited"]
        offenders = False
        for i, r in enumerate(results):
            if r.get("not_in_source"):
                continue
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            if overlap_frac(e0, e1, re0, re1) >= 0.5:
                offenders = True
        fp += offenders
    return {"hit": hit, "verified": verified_hit, "loose": loose_hit, "scene": scene_hit,
            "n": len(gt["positives"]), "n_ver": n_ver, "n_loo": n_loo, "fp": fp, "rows": rows}

gt = json.loads(GT.read_text(encoding="utf-8"))
summary = {}
for name, fname in VERSIONS:
    res = json.loads((RES_DIR / fname).read_text(encoding="utf-8"))["results"]
    ev = evaluate(res, gt)
    summary[name] = {k: ev[k] for k in ("hit", "verified", "loose", "scene", "fp", "n")}
    print(f"[{name:10s}] 严格 {ev['hit']}/{ev['n']} (ver {ev['verified']}/{ev['n_ver']}, "
          f"loose {ev['loose']}/{ev['n_loo']}) | 场景 {ev['scene']}/{ev['n']} | 负例 FP {ev['fp']}/4")

print()
# 逐版本正例命中差异（相对 current）
# 简单对比：打印每个版本中与 current 命中状态不同的正例
cur_ev = None
for name, fname in VERSIONS:
    if name == "current":
        res = json.loads((RES_DIR / fname).read_text(encoding="utf-8"))["results"]
        cur_ev = evaluate(res, gt)
print("\n=== 正例命中状态差异（相对 current）===")
for name, fname in VERSIONS:
    if name == "current":
        continue
    res = json.loads((RES_DIR / fname).read_text(encoding="utf-8"))["results"]
    ev = evaluate(res, gt)
    cur = dict((r[0], r) for r in cur_ev["rows"])
    diffs = []
    for pid, hit, scene, best, bscene in ev["rows"]:
        c = cur[pid]
        mark = lambda h, s: "HIT" if h else ("part" if s else "MISS")
        m1, m2 = mark(hit, scene), mark(c[1], c[2])
        if m1 != m2:
            det1 = f"s{best[0]}({best[1]} {float(best[2]):.0f}-{float(best[3]):.0f})" if best else "-"
            det2 = f"s{c[3][0]}({c[3][1]} {float(c[3][2]):.0f}-{float(c[3][3]):.0f})" if c[3] else "-"
            diffs.append(f"  {pid}: {m1}({det1}) -> {m2}({det2})")
    print(f"[{name:10s}]")
    print("\n".join(diffs) if diffs else "  (与 current 一致)")
