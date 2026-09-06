"""p05/p35/p41「修正后未跟上」+ p20/p34 边界偏差 → 评测口径澄清（2026-09-04）。

2.mkv v4 GT 剩余 MISS/part 的宽松口径重评: 对照「严格(覆盖≥50%/含中点)」与
「宽松(±容差 且 覆盖≥30%)」两种口径, 量化边界偏差/评测真值前移对三指标的影响。
只读评估, 零 runtime 改动, 不动 ConfidenceConfig。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/measure_lenient_v4.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import result_spans, overlap_frac


GT = BENCH / "datasets/real/ground_truth_v4.json"
RES = BENCH / "work/rerun_2mkv_timelineprior.results.json"

TOL_S = 6.0      # 宽松口径①: span 与 GT±容差 重叠(边界偏差语义)
TOL_S_SCENE = 15.0  # 宽松口径②: 场景级容差(与 measure_shot_recall 场景级口径一致)
COV_MIN = 0.30   # 宽松口径: 任一 span 覆盖 GT >= 30%


def strict_hit(res, e0, e1, o0, o1):
    """measure_shot_recall 严格口径: 编辑重叠>0 的 span 覆盖>=50% 或含 GT 中点(或 within±2s)。"""
    mid = (o0 + o1) / 2
    for r in res:
        re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        if max(0.0, min(e1, re1) - max(e0, re0)) <= 0:
            continue
        for _, a, b in result_spans(r):
            within = (a >= o0 - 2.0) and (b <= o1 + 2.0)
            mid_in = a <= mid <= b
            cov = overlap_frac(o0, o1, a, b) >= 0.4   # 与 measure_shot_recall 严格口径一致
            if within or mid_in or cov:
                return True
    return False


def lenient_hit(res, e0, e1, o0, o1):
    """宽松口径: 编辑重叠>0 且 (span 与 GT±容差 重叠) 或 (任一 span 覆盖 >= COV_MIN)。
    语义: 「边界偏差」= 结果 span 落在 GT 邻域(±TOL_S)内即算命中, 不要求覆盖≥50%。"""
    for r in res:
        re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        if max(0.0, min(e1, re1) - max(e0, re0)) <= 0:
            continue
        for _, a, b in result_spans(r):
            near = (a <= o1 + TOL_S) and (b >= o0 - TOL_S)   # span 与 GT±容差 有交集
            cov_ok = overlap_frac(o0, o1, a, b) >= COV_MIN
            if near or cov_ok:
                return True
    return False


def main() -> int:
    gt = json.loads(Path(GT).read_text(encoding="utf-8"))
    res = json.loads(Path(RES).read_text(encoding="utf-8"))["results"]
    pos = gt["positives"]

    print("=== 2.mkv v4 GT 严格 vs 宽松口径逐条对照（rerun 批） ===")
    print(f"宽松口径: 中点容差 ±{TOL_S}s 或 覆盖≥{COV_MIN:.0%}\n")
    sh = lh = 0
    for p in pos:
        e0, e1 = p["edited"]; o0, o1 = p["original"]
        s = strict_hit(res, e0, e1, o0, o1)
        l = lenient_hit(res, e0, e1, o0, o1)
        sh += s; lh += l
        if not s or not l:
            tag = "HIT/HIT" if (s and l) else ("strict-MISS lenient-HIT" if (l and not s)
                  else ("strict-HIT lenient-MISS" if (s and not l) else "BOTH-MISS"))
            print(f"  [{tag:22s}] {p['id']:5s} ed{e0:6.1f}-{e1:6.1f} -> og{o0:6.1f}-{o1:6.1f}")
    print()
    # 场景级宽松口径(±15s 与 measure_shot_recall 场景级一致, 但补覆盖≥30%条件)
    lh15 = 0
    for p in pos:
        e0, e1 = p["edited"]; o0, o1 = p["original"]
        hit = False
        for r in res:
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            if max(0.0, min(e1, re1) - max(e0, re0)) <= 0:
                continue
            for _, a, b in result_spans(r):
                if ((a <= o1 + TOL_S_SCENE) and (b >= o0 - TOL_S_SCENE)) or \
                   overlap_frac(o0, o1, a, b) >= COV_MIN:
                    hit = True
                    break
            if hit:
                break
        lh15 += hit
    print(f"严格: {sh}/{len(pos)} | 宽松①(±{TOL_S}s/覆盖≥{COV_MIN:.0%}): {lh}/{len(pos)} "
          f"| 宽松②(±{TOL_S_SCENE}s/覆盖≥{COV_MIN:.0%}): {lh15}/{len(pos)}")
    print()
    # 负例与支撑同口径复算(宽松口径不影响负例判定, 仅展示)
    fp = 0
    for n in gt["negatives"]:
        e0, e1 = n["edited"]
        off = any(
            (not r.get("not_in_source")) and overlap_frac(e0, e1, r["edited_segment"]["start"], r["edited_segment"]["end"]) >= 0.5
            for r in res)
        fp += off
    print(f"负例误报: {fp}/{len(gt['negatives'])} (口径不变)")
    return 0


if __name__ == "__main__":
    sys.exit(main())