# -*- coding: utf-8 -*-
"""②③ 单调弱先验重跑后评估: 新代码结果批(work/rerun_*) vs 新 GT。

对比旧基线(旧代码结果批 cases/*_results.json):
  2.mkv v4: 32/39 | test1: 32/43 | test2: 9/20 | test3: 31/37
"""
import json
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import overlap_frac, result_spans, _union_covers  # noqa: E402

def evaluate(results, gt):
    hit = verified_hit = loose_hit = scene_hit = 0
    rows = []
    for p in gt["positives"]:
        e0, e1 = p["edited"]; o0, o1 = p["original"]
        covering, ed_intervals, best, best_scene = [], [], None, None
        for i, r in enumerate(results):
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            if max(0.0, min(e1, re1) - max(e0, re0)) <= 0: continue
            ed_intervals.append((max(e0, re0), min(e1, re1)))
            for kind, a, b in result_spans(r):
                within = (a >= o0 - 2.0) and (b <= o1 + 2.0)
                mid_in = a <= (o0 + o1) / 2 <= b
                cov = overlap_frac(o0, o1, a, b) >= 0.4
                if best is None and (within or mid_in or cov): best = (i, kind, a, b)
                if a <= o1 and b >= o0: covering.append((a, b))
                m = (a + b) / 2
                if o0 - 15.0 <= m <= o1 + 15.0 and best_scene is None: best_scene = (i, kind, a, b)
        ed_union = _union_covers(ed_intervals, e0, e1, 0.5) if ed_intervals else False
        if best is None and covering and ed_union and _union_covers(covering, o0, o1):
            best = ("union", "joint", covering[0][0], covering[-1][1])
        if p["tier"] == "verified": verified_hit += best is not None
        elif p["tier"] == "loose": loose_hit += best is not None
        hit += best is not None; scene_hit += best_scene is not None
        rows.append((p["id"], best is not None, best_scene is not None))
    fp = 0
    for n in gt["negatives"]:
        e0, e1 = n["edited"]
        off = False
        for r in results:
            if r.get("not_in_source"): continue
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            if overlap_frac(e0, e1, re0, re1) >= 0.5: off = True
        fp += off
    n_ver = sum(1 for p in gt["positives"] if p["tier"] == "verified")
    n_loo = sum(1 for p in gt["positives"] if p["tier"] == "loose")
    return {"hit": hit, "n": len(gt["positives"]), "ver": verified_hit, "n_ver": n_ver,
            "loo": loose_hit, "n_loo": n_loo, "scene": scene_hit, "fp": fp, "rows": rows}

CASES = [
    ("2mkv",  "datasets/real/ground_truth_v4.json",        "user_results.json",                   "work/rerun_2mkv_timelineprior.results.json"),
    ("test1", "datasets/real/ground_truth_test1.json",     "cases/test1_results.json",            "work/rerun_test1_timelineprior.results.json"),
    ("test2", "datasets/real/ground_truth_test2.json",     "cases/test2_results.json",            "work/rerun_test2_timelineprior.results.json"),
    ("test3", "datasets/real/ground_truth_test3.json",     "cases/test3_results.json",            "work/rerun_test3_timelineprior.results.json"),
]
UC = BENCH / "mvp" / "benchmark" / "user_case"
print(f"{'case':6s} {'旧严格':>7s} {'新严格':>7s} {'旧场景':>6s} {'新场景':>6s} {'旧FP':>4s} {'新FP':>4s}")
for name, gtf, oldf, newf in CASES:
    gt = json.loads((BENCH / gtf).read_text(encoding="utf-8"))
    old = json.loads((UC / oldf).read_text(encoding="utf-8"))["results"]
    try:
        new = json.loads((BENCH / newf).read_text(encoding="utf-8"))["results"]
    except FileNotFoundError:
        print(f"{name:6s} 新结果批未生成"); continue
    evo = evaluate(old, gt); evn = evaluate(new, gt)
    print(f"{name:6s} {evo['hit']:3d}/{evo['n']:<3d} {evn['hit']:3d}/{evn['n']:<3d} "
          f"{evo['scene']:3d}/{evo['n']:<3d} {evn['scene']:3d}/{evn['n']:<3d} "
          f"{evo['fp']}/{len(gt['negatives'])} {evn['fp']}/{len(gt['negatives'])}")
    # 逐条差异
    oldmap = dict((r[0], r[1]) for r in evo["rows"])
    newmap = dict((r[0], r[1]) for r in evn["rows"])
    for pid in oldmap:
        if oldmap[pid] != newmap[pid]:
            print(f"    {pid}: 旧{'HIT' if oldmap[pid] else 'MISS'} -> 新{'HIT' if newmap[pid] else 'MISS'}")
