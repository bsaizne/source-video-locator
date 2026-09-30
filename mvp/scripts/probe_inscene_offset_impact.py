# -*- coding: utf-8 -*-
"""(E) 场景内稠密局部位置信号立项 · 影响面统计（2026-09-30，续32 后续）。

纪律（续21-E1 + 续31 补二 §4.4）：先影响面统计，再谈形态改造，不做 GT 反标。

口径 = **导出实得**（仅主 span、全长、无子 span/alternatives，与 export_project
include_subs=False 一致）。先复现基线 100/139，再对每条未命中行做机制分诊：

  - overlap_but_outside : 主 span 与 GT 窗有重叠但未满足 within（⊆±2s）——半Inside
  - gap_<=7s            : 间隙 ≤7s（同场景 2–7s 偏移族，复现链口袋的主族）
  - gap_7_30s           : 7–30s（同场景偏移延伸族，conf_v2 曾点名 18–21s）
  - gap_30_120s         : 30–120s（跨场景/邻接场景，位置信号难救）
  - gap_>120s           : 远端（候选层/特征层问题，位置信号无关）
  - no_segment          : 该编辑区无结果段
另逐行标注 16 条 GT 疑错工单行（这些不是真未命中）。

零 GPU / 零 runtime / 零 GT 改动。产物 work/inscene_offset_impact.json。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_inscene_offset_impact.py
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "inscene_offset_impact.json"
CASES = [("2mkv", "datasets/real/ground_truth_v4.json"),
         ("test1", "datasets/real/ground_truth_test1.json"),
         ("test2", "datasets/real/ground_truth_test2.json"),
         ("test3", "datasets/real/ground_truth_test3.json")]
OURS = {"2mkv": "work/fastglobal_default_2mkv.results.json",
        "test1": "work/fastglobal_default_test1.results.json",
        "test2": "work/fastglobal_default_test2.results.json",
        "test3": "work/fastglobal_default_test3.results.json"}
# 导出实得 = 仅主 span：剥掉子 span 与 alternatives，主 span 保持全长
EXPORT_CALIBER_PATCH = {"original_segments": [], "alternatives": []}

# 16 条 GT 疑错工单行（probe_gt_tickets_retrieval.py 2026-09-30 判别，读图 18/18 复核一致）
GT_TICKET_ROWS = {("2mkv", "p10"), ("2mkv", "p31"), ("2mkv", "p33"),
                  ("test1", "t1r08a"), ("test2", "t2r01b"), ("test2", "t2r02a"),
                  ("test2", "t2r03a"), ("test2", "t2r05a"), ("test2", "t2r05b"),
                  ("test2", "t2r07a"), ("test3", "t3r03a"), ("test3", "t3r04b")}
# 14 条真口袋（FINDINGS_COMBO_CALIBER_ALL_CASES.md §3，剔 p14 / t2r01c 容差漏洞）
POCKET_ROWS = {("2mkv", "p02"), ("2mkv", "p03"), ("2mkv", "p20"), ("2mkv", "p30"),
               ("2mkv", "p34"), ("test1", "t1r14c"), ("test2", "t2r02a"),
               ("test2", "t2r05a"), ("test2", "t2r05b"), ("test2", "t2r06c"),
               ("test3", "t3r01"), ("test3", "t3r02c"), ("test3", "t3r05"),
               ("test3", "t3r26")}


def export_caliber_results(raw: dict) -> dict:
    b = copy.deepcopy(raw)
    for r in b.get("results", []):
        for k, v in EXPORT_CALIBER_PATCH.items():
            r[k] = copy.deepcopy(v) if isinstance(v, list) else v
    return b


def classify(gap: float, overlap: float) -> str:
    if overlap > 0:
        return "overlap_but_outside"
    if gap <= 7.0:
        return "gap_<=7s"
    if gap <= 30.0:
        return "gap_7_30s"
    if gap <= 120.0:
        return "gap_30_120s"
    return "gap_>120s"


def main() -> int:
    census, rows_out = {}, []
    tot = {"hit": 0, "n": 0}
    for case, gt_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / OURS[case]).read_text(encoding="utf-8"))
        src = Path(raw["original_video"])
        _ = src  # 主 span 已是原片时间轴，无需再取帧
        m = evaluate(gt, export_caliber_results(raw)["results"])
        tot["hit"] += m["strict_hit"]
        tot["n"] += m["n_pos"]
        our_by_pid = {}
        for x in m["per_pos"]:
            our_by_pid[x["id"]] = x
        for p in gt["positives"]:
            pid = p["id"]
            e0, e1 = p["edited"][0], p["edited"][1]
            o0, o1 = p["original"][0], p["original"][1]
            # 我方与该 GT 编辑窗重叠最多的结果段（同 probe_combo_pocket_visual 映射法）
            best, span = 0.0, None
            for r in raw["results"]:
                re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
                ov = min(e1, re1) - max(e0, re0)
                if ov > best:
                    best = ov
                    orig = r.get("original") or {}
                    if "candidate_start" in orig:
                        span = (orig["candidate_start"], orig["candidate_end"])
            mark = our_by_pid.get(pid, {}).get("mark")
            hit = (mark == "HIT")
            if hit or span is None:
                mech = "hit" if hit else "no_segment"
                gap = overlap = 0.0
            else:
                overlap = min(span[1], o1) - max(span[0], o0)
                gap = max(o0 - span[1], span[0] - o1, 0.0)
                mech = classify(gap, overlap)
            rows_out.append({
                "case": case, "id": pid, "mark": mark, "hit": hit,
                "gt_og": [o0, o1], "our_main_span": list(span) if span else None,
                "gap_s": round(gap, 2), "overlap_s": round(overlap, 2),
                "mechanism": mech,
                "gt_ticket_suspect": (case, pid) in GT_TICKET_ROWS,
                "pocket": (case, pid) in POCKET_ROWS,
            })
        print("[%s] 导出实得 %d/%d" % (case, m["strict_hit"], m["n_pos"]), flush=True)

    from collections import Counter
    miss = [r for r in rows_out if not r["hit"]]
    c_all = Counter(r["mechanism"] for r in miss)
    c_clean = Counter(r["mechanism"] for r in miss if not r["gt_ticket_suspect"])
    inscene = {"gap_<=7s", "gap_7_30s", "overlap_but_outside"}
    print("\n=== 基线复现: 导出实得 %d/%d (期望 100/139) ===" % (tot["hit"], tot["n"]))
    print("未命中 %d 行机制分诊(全量): %s" % (len(miss), dict(c_all)))
    print("未命中机制分诊(剔 %d 条 GT 疑错工单行): %s" % (
        sum(1 for r in miss if r["gt_ticket_suspect"]),
        dict(c_clean)))
    print("同场景族(overlap/≤7s/7–30s) 剔疑错后 = %d 行" % (
        sum(v for k, v in c_clean.items() if k in inscene)))
    print("口袋命中核对: 14 条真口袋中未命中 = %d" % (
        sum(1 for r in rows_out if r["pocket"] and not r["hit"])))
    OUT.write_text(json.dumps({"baseline": tot, "census_all": dict(c_all),
                               "census_ex_ticket": dict(c_clean),
                               "rows": rows_out}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print("产物: %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
