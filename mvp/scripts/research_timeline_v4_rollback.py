# -*- coding: utf-8 -*-
"""④ 时序重排 v4 量化（精确回滚）—— 只回滚带 temporal_outlier_repair/conflict_rerank/
sequence_rerank 标记的段，还原修复前主定位（original_segments 首条 cover=0 score=null 留痕）。
数「修复前 MISS/part -> 修复后 HIT」纠正条数（NEXT_STEPS ① 目标）。
"""
import json
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import overlap_frac, result_spans, _union_covers

GT = BENCH / "datasets" / "real" / "ground_truth_v4.json"
RES = BENCH / "mvp" / "benchmark" / "user_case" / "user_results.json"
MARKS = ("temporal_outlier_repair", "conflict_rerank", "sequence_rerank")

def evaluate(results, gt):
    hit = verified_hit = loose_hit = scene_hit = 0
    rows = []
    for p in gt["positives"]:
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        covering, ed_intervals, best, best_scene = [], [], None, None
        for i, r in enumerate(results):
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            ed_inter = max(0.0, min(e1, re1) - max(e0, re0))
            if ed_inter <= 0:
                continue
            ed_intervals.append((max(e0, re0), min(e1, re1)))
            for kind, a, b in result_spans(r):
                within = (a >= o0 - 2.0) and (b <= o1 + 2.0)
                mid_in = a <= (o0 + o1) / 2 <= b
                cov = overlap_frac(o0, o1, a, b) >= 0.4
                if best is None and (within or mid_in or cov):
                    best = (i, kind, a, b)
                if a <= o1 and b >= o0:
                    covering.append((a, b))
                m = (a + b) / 2
                if o0 - 15.0 <= m <= o1 + 15.0 and best_scene is None:
                    best_scene = (i, kind, a, b)
        ed_union = _union_covers(ed_intervals, e0, e1, 0.5) if ed_intervals else False
        if best is None and covering and ed_union and _union_covers(covering, o0, o1):
            best = ("union", "joint", covering[0][0], covering[-1][1])
        if p["tier"] == "verified":
            verified_hit += best is not None
        elif p["tier"] == "loose":
            loose_hit += best is not None
        hit += best is not None
        scene_hit += best_scene is not None
        rows.append((p["id"], best is not None, best_scene is not None, best))
    return {"hit": hit, "verified": verified_hit, "loose": loose_hit, "scene": scene_hit,
            "n": len(gt["positives"]), "rows": rows}

gt = json.loads(GT.read_text(encoding="utf-8"))
res = json.loads(RES.read_text(encoding="utf-8"))["results"]

# 识别带标记的段
marked = []
for i, r in enumerate(res):
    marks = [x for x in (r.get("reasons") or []) if x in MARKS]
    if not marks:
        continue
    main = (r["original"]["candidate_start"], r["original"]["candidate_end"])
    legacy = None
    for s in (r.get("original_segments") or []):
        sp = (s["candidate_start"], s["candidate_end"])
        if s.get("score") is None and s.get("cover") == 0 and \
                (abs(sp[0]-main[0]) > 0.5 or abs(sp[1]-main[1]) > 0.5):
            legacy = sp
            break
    marked.append((i, marks, main, legacy))

print("带修复标记的段:")
for i, marks, main, legacy in marked:
    print(f"  s{i} {marks} main={main} 修复前={legacy}")

cur = evaluate(res, gt)
print(f"\n[current 修复后] 严格 {cur['hit']}/{cur['n']} (ver {cur['verified']}, loose {cur['loose']}) | 场景 {cur['scene']}/{cur['n']}")

rollback = list(res)
for i, marks, main, legacy in marked:
    if legacy is not None:
        rollback[i] = {**res[i], "original": {"candidate_start": legacy[0], "candidate_end": legacy[1]}}
rb = evaluate(rollback, gt)
print(f"[回滚时序修复后] 严格 {rb['hit']}/{rb['n']} (ver {rb['verified']}, loose {rb['loose']}) | 场景 {rb['scene']}/{rb['n']}")

cur_map = dict((r[0], r) for r in cur["rows"])
rb_map = dict((r[0], r) for r in rb["rows"])
print("\n=== 逐条变化（修复前 -> 修复后）===")
fixed = 0
for pid in cur_map:
    ch, cs = cur_map[pid][1], cur_map[pid][2]
    rh, rs = rb_map[pid][1], rb_map[pid][2]
    def m(h, s): return "HIT" if h else ("part" if s else "MISS")
    m1, m2 = m(ch, cs), m(rh, rs)
    if m1 != m2:
        print(f"  {pid}: {m2} -> {m1}")
        if m1 != "MISS" and m2 == "MISS":
            fixed += 1
        elif m1 == "HIT" and m2 != "HIT":
            pass
print(f"\n纠正条数（修复前 MISS/part -> 修复后 HIT，严格口径）: {fixed}")
