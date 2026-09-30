# -*- coding: utf-8 -*-
"""TN 双判据仲裁探针 Stage 1（2026-09-26，纯 numpy，零 runtime）。

背景（全部有据）：
  - 我方 6 处已裁决假切点在 TN 概率上非峰（cut_swap_probe.json）；
  - 但 29 处已裁决真切点在 TN 概率上也非峰（中位 0.0012，与 TN 切点相距 0.6-5.0s = 另一处真切换）
    ⇒ TN 概率单判据不能否决（会连真一起杀）；
  - 故仲裁规则必须是双判据：TN 无支持（±窗内无 TN 峰）∧ 像素帧差无峰（H-CM1 判据未通过）
    才允许把该边界降级为「合并候选」。
本脚本三步：
  ① 在 44 例已裁决锚点上搜索可行工作点（目标 = 6/6 假切点全命中 ∧ 真切点零误伤）；
  ② 把最优（或最接近目标的）规则套到全部 227 条现行边界，输出合并候选清单；
  ③ 一致性自检：6 处已知假切点必须在候选内；test3 两处「相邻真切换各选其一」（16.29/40.07，帧差强证据）
     必须不在候选内。
产物 work/tn_arbitration_probe.json。不套 GT；裁决真值只用 44 例人工盲判。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

B = Path(r"D:\claudework\benchmark")
PROXY = Path(r"D:\claudework\cutmatch-analysis\sandbox\out")
WORK = B / "work"

CASES = {"2mkv": ("1.mp4", 29.0), "test1": ("test1-ed.mp4", 30.0),
         "test2": ("tset2-ed.mp4", 30.0), "test3": ("test3-ed.mp4", 28.0)}


def load_all():
    verd = json.loads((WORK / "proxy_blind_disputes" / "verdicts_44_enriched.json").read_text(encoding="utf-8"))
    tags = {}
    for v in verd:
        tags.setdefault((v["case"], int(round(v["ours_s"] * 100))), v["ours_v"])  # 兜底
    cut_swap = json.loads((WORK / "cut_swap_probe.json").read_text(encoding="utf-8"))
    refiner = json.loads((WORK / "boundary_refiner_probe.json").read_text(encoding="utf-8"))
    return verd, cut_swap, refiner


def tn_win_max(prob: np.ndarray, f: int, half: int) -> float:
    lo, hi = max(0, f - half), min(len(prob), f + half + 1)
    seg = np.nan_to_num(prob[lo:hi], nan=-1.0)
    return float(seg.max()) if len(seg) else 0.0


def main() -> int:
    verd, cut_swap, refiner = load_all()
    # 锚点真值（44 例人工盲判）：键 = (case, frame)；裁决值 cut/nocut/unsure → true/false/unsure
    remap = {"cut": "true", "nocut": "false", "unsure": "unsure"}
    anchor = {}
    for v in verd:
        case = v["case"]
        fps = CASES[case][1]
        f = int(round(v["ours_s"] * fps))
        anchor.setdefault((case, f), remap.get(v["ours_v"], v["ours_v"]))

    rows = []  # 每条现行边界一行
    for case, (clip, fps) in CASES.items():
        prob = np.load(PROXY / ("%s.probs.npy" % clip))
        cs = {b["frame"]: b for b in cut_swap["cases"][case]["bounds"]}
        rf = {r["frame"]: r for r in refiner["cases"][case]["rows"]}
        half_a = max(1, int(round(0.25 * fps)))
        half_b = max(1, int(round(0.50 * fps)))
        frames = sorted(set(cs) | set(rf))
        for f in frames:
            cb, rb = cs.get(f), rf.get(f)
            t = cb["t"] if cb else rb["boundary_s"]
            rows.append({
                "case": case, "frame": f, "t": round(float(t), 3),
                "tn_at": cb["tn_prob"] if cb else None,
                "tn_win025": round(tn_win_max(prob, f, half_a), 4),
                "tn_win050": round(tn_win_max(prob, f, half_b), 4),
                "fd_reason": rb["reason"] if rb else None,
                "fd_peak": round(rb["peak"], 2) if rb else None,
                "fd_thr": round(rb["thr"], 2) if rb else None,
                "fd_shift": rb["shift_frames"] if rb else None,
                "tag": anchor.get((case, f)),
            })

    tagged = [r for r in rows if r["tag"]]
    n_tag = {"true": 0, "false": 0, "unsure": 0}
    for r in tagged:
        n_tag[r["tag"]] = n_tag.get(r["tag"], 0) + 1
    print("锚点对上: true=%d false=%d unsure=%d (共 %d/%d)" % (
        n_tag["true"], n_tag["false"], n_tag["unsure"], len(tagged), len(rows)))

    # ---- ① 在 44 例上搜工作点 ----
    print()
    print("== 工作点搜索（目标: 假 6/6 全命中 ∧ 真 0 误伤）==")
    print("| 规则 | 假命中 | 真误伤 | 未定命中 | 真误伤清单 |")
    print("|---|---|---|---|---|")
    best = None
    combos = []
    for th_a_name, th_a in (("w25<0.1", ("tn_win025", 0.1)), ("w25<0.2", ("tn_win025", 0.2)),
                            ("w25<0.3", ("tn_win025", 0.3)), ("w50<0.3", ("tn_win050", 0.3)),
                            ("w50<0.5", ("tn_win050", 0.5))):
        for th_b_name, pred_b in (("below_thr", lambda r: r["fd_reason"] == "below_threshold"),
                                  ("peak<thr", lambda r: (r["fd_peak"] or 0) < (r["fd_thr"] or 45)),
                                  ("peak<45", lambda r: (r["fd_peak"] or 0) < 45)):
            ff = [r for r in tagged if r["tag"] == "false" and pred_b(r) and r[th_a[0]] < th_a[1]]
            ft = [r for r in tagged if r["tag"] == "true" and pred_b(r) and r[th_a[0]] < th_a[1]]
            fu = [r for r in tagged if r["tag"] == "unsure" and pred_b(r) and r[th_a[0]] < th_a[1]]
            lst = ", ".join("%s@%.2f" % (r["case"], r["t"]) for r in ft) or "-"
            print("| %s ∧ %s | %d/6 | %d | %d | %s |" % (th_a_name, th_b_name, len(ff), len(ft), len(fu), lst))
            score = (len(ff), -len(ft))  # 先假命中多，再真误伤少
            if best is None or score > best[0]:
                best = (score, (th_a_name, th_a[0], th_a[1], th_b_name, pred_b))
    print()
    print("最优工作点: %s ∧ %s" % (best[1][0], best[1][3]))

    # ---- ② 最优规则套全部 227 条 ----
    _, key_a, th_a, _, pred_b = best[1]
    cands = [r for r in rows if pred_b(r) and r[key_a] < th_a]
    per_case = {}
    for case in CASES:
        cc = [r for r in cands if r["case"] == case]
        per_case[case] = {"n_boundaries": sum(1 for r in rows if r["case"] == case),
                          "n_merge_candidates": len(cc),
                          "candidates": [{"t": r["t"], "frame": r["frame"], "tag": r["tag"],
                                          "tn_win": r[key_a], "fd_peak": r["fd_peak"],
                                          "fd_thr": r["fd_thr"]} for r in cc]}
        tagged_flagged = sum(1 for r in cc if r["tag"] == "false")
        print("  %s: 边界 %d 条, 合并候选 %d 条 (含已裁决假切点 %d/%d)" % (
            case, per_case[case]["n_boundaries"], len(cc), tagged_flagged,
            n_tag["false"] if case != "test1" else 3))

    # ---- ③ 一致性自检 ----
    print()
    known_false = [("2mkv", 113.17), ("test1", 2.53), ("test1", 44.73), ("test1", 73.93),
                   ("test3", 49.14), ("test3", 27.79)]
    cand_keys = {(r["case"], round(r["t"], 0)) for r in cands}
    cand_keys2 = {(r["case"], round(r["t"], 1)) for r in cands}
    ok = []
    for case, t in known_false:
        hit = any(abs(r["t"] - t) <= 0.05 for r in cands if r["case"] == case)
        ok.append((case, t, hit))
    print("已知 6 假切点是否全部入候选:", all(h for _, _, h in ok), ok)
    disp = [r for r in rows if r["case"] == "test3" and abs(r["t"] - 16.286) < 0.2 or
            (r["case"] == "test3" and abs(r["t"] - 40.07) < 0.2)]
    for r in disp:
        print("  相邻真切换对照 test3@%.2f: tn_win025=%.3f fd_peak=%.1f fd_thr=%.1f → 入候选=%s" % (
            r["t"], r["tn_win025"], r["fd_peak"] or -1, r["fd_thr"] or -1,
            r in cands))

    out = {"note": "TN 双判据仲裁探针 Stage 1（ TN 无支持 ∧ 帧差无峰 → 合并候选）",
           "anchors": {"true": n_tag["true"], "false": n_tag["false"], "unsure": n_tag["unsure"]},
           "best_rule": {"tn": best[1][0], "fd": best[1][3]},
           "per_case": per_case,
           "known_false_check": ok,
           "rows": rows}
    (WORK / "tn_arbitration_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("saved work/tn_arbitration_probe.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
