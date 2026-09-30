# -*- coding: utf-8 -*-
"""五环组合链 四片双口径评估（2026-09-29 续31，用户令「从 1 开始」）。

回答一个从未回答过的问题：**把竞品那套链路整套复现出来，四片合计的天花板到底是多少**，
以及它与我方现役生产（完整口径 127/139、main-span 截等长 105/139）在**同一判据**下怎么比。

续10d 只在 test1 一片上做过（"单片先行"），档案里从未扩到四片 ⇒ 本脚本补这一步。
零 runtime 改动、零 GPU、零 GT 改动（纯离线判卷）。

三方读数（每片 + 合计）：
  R1 复现链 完整 span 严格        —— 已知被 TN 场景 span 装配效应抬高，只作留档不作结论
  R2 复现链 span 截查询等长 严格   —— 公平读数（口径2，与 R4 同判据）
  R3 复现链 候选层名次             —— 粒度无关，回答「找没找到」
  R4 我方 main-span 截等长 严格    —— `measure_mainspan_caliber.truncate_main` 同款协议
  R5 我方 完整口径 严格/场景/负例  —— 现役生产基线批

用法:
  PY="D:/claudework/video-dedup-tool/.venv/Scripts/python.exe"
  $PY -X utf8 mvp/scripts/probe_combo_caliber_all_cases.py \
      --out work/combo_caliber_all_cases.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
SANDBOX_OUT = Path(r"D:\claudework\cutmatch-analysis\sandbox\out")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from measure_mainspan_caliber import truncate_main          # noqa: E402
from measure_shot_recall import evaluate, overlap_frac      # noqa: E402
from probe_combo_dual_caliber import caliber1, caliber2, load_rows  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# 争议 GT（双侧独立定位同内容区、GT 窗画面与 ED 不符）—— 仅 test1 有，双计留档
DISPUTED = {"test1": ["t1r08b", "t1r12a"]}

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json", "localization_2mkv.json",
     "work/fastglobal_default_2mkv.results.json"),
    ("test1", "datasets/real/ground_truth_test1.json", "localization_comboA_test1.json",
     "work/fastglobal_default_test1.results.json"),
    ("test2", "datasets/real/ground_truth_test2.json", "localization_test2.json",
     "work/fastglobal_default_test2.results.json"),
    ("test3", "datasets/real/ground_truth_test3.json", "localization_test3.json",
     "work/fastglobal_default_test3.results.json"),
]


def _quiet(fn, *a, **kw):
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        return fn(*a, **kw)


def _full_span_strict(rows, gt):
    """R1：复现链按**未截断**的主 span 跑我方严格判据（把行转成我方 results 形态）。"""
    res = [{"edited_segment": {"start": r["e0"], "end": r["e1"]},
            "original": ({"candidate_start": r["s0"], "candidate_end": r["s1"]}
                         if (r["matched"] and r["s0"] is not None)
                         else {"candidate_start": 0.0, "candidate_end": 0.0}),
            "original_segments": [], "alternatives": [], "confidence": "HIGH",
            "not_in_source": not r["matched"]}
           for r in rows]
    m = _quiet(evaluate, gt, res, label="")
    return {"strict": "%d/%d" % (m["strict_hit"], m["n_pos"]),
            "scene": "%d/%d" % (m["scene_hit"], m["n_pos"]),
            "fp": "%d/%d" % (m["fp"], m["n_neg"])}


def run_case(case, gt_rel, loc_name, ours_rel):
    gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
    loc_path = SANDBOX_OUT / loc_name
    if not loc_path.exists():
        print("MISSING %s" % loc_path)
        return None
    rows = load_rows(loc_path)
    c1 = caliber1(rows, gt["positives"])
    c2 = caliber2(rows, gt["positives"], gt["negatives"])
    keep = [p for p in gt["positives"] if p["id"] not in DISPUTED.get(case, [])]
    c2x = caliber2(rows, keep, gt["negatives"]) if len(keep) != len(gt["positives"]) else None

    ours_path = BENCH / ours_rel
    ours, n_ours = {}, 0
    if ours_path.exists():
        raw = json.loads(ours_path.read_text(encoding="utf-8"))
        n_ours = len(raw["results"])
        full = _quiet(evaluate, gt, raw["results"], label="")
        trunc = _quiet(evaluate, gt, truncate_main(raw)["results"], label="")
        ours = {"full": {"strict": "%d/%d" % (full["strict_hit"], full["n_pos"]),
                         "scene": "%d/%d" % (full["scene_hit"], full["n_pos"]),
                         "fp": "%d/%d" % (full["fp"], full["n_neg"])},
                "trunc": "%d/%d" % (trunc["strict_hit"], trunc["n_pos"])}

    fs = _full_span_strict(rows, gt)
    print("\n===== %s (复现 %d 行 / matched %d · 我方 %d 段 · GT %d 正例 + %d 负例) =====" % (
        case, len(rows), sum(1 for r in rows if r["matched"]), n_ours,
        len(gt["positives"]), len(gt["negatives"])))
    print("  R1 复现链 完整 span 严格   %s   (场景 %s, 负例 %s)  ← 装配效应抬高，仅留档" %
          (fs["strict"], fs["scene"], fs["fp"]))
    print("  R2 复现链 截查询等长 严格  %d/%d%s" % (
        c2["strict_hit"], c2["n"],
        "" if not c2x else "  (不含争议 GT %d/%d)" % (c2x["strict_hit"], c2x["n"])))
    print("  R3 复现链 候选层          top1 %d / top3 %d / top20 %d / 从未 %d  median rank %s"
          " · 找到但被拒 %s" % (c1["top1"], c1["top3"], c1["top20"], len(c1["never"]),
                                c1["median_rank"], c1["found_but_rejected"]))
    print("  R4 我方   main-span 截等长 %s" % ours.get("trunc", "n/a"))
    print("  R5 我方   完整口径          严格 %s · 场景 %s · 负例 %s" % (
        ours.get("full", {}).get("strict", "-"), ours.get("full", {}).get("scene", "-"),
        ours.get("full", {}).get("fp", "-")))
    return {"case": case, "loc": str(loc_path), "n_rows": len(rows),
            "n_matched": sum(1 for r in rows if r["matched"]),
            "R1_proxy_fullspan": fs,
            "R2_proxy_trunc": "%d/%d" % (c2["strict_hit"], c2["n"]),
            "R2_proxy_trunc_ex_disputed": (None if not c2x else
                                           "%d/%d" % (c2x["strict_hit"], c2x["n"])),
            "R2_proxy_neg_fp": "%d/%d" % (c2["neg_fp"], len(gt["negatives"])),
            "R3_candidate_layer": {"top1": c1["top1"], "top3": c1["top3"], "top20": c1["top20"],
                                   "never": c1["never"], "median_rank": c1["median_rank"],
                                   "found_but_rejected": c1["found_but_rejected"]},
            "R4_ours_trunc": ours.get("trunc"), "R5_ours_full": ours.get("full"),
            "R2_per_pos": c2["per"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="work/combo_caliber_all_cases.json")
    args = ap.parse_args()

    report = {"note": "复现链 = 四片 delivered 四环产物（G5 在 test1 上零翻转，未扩到其余三片）",
              "cases": []}
    tot = {"R2_hit": 0, "R2_n": 0, "R4_hit": 0, "R4_n": 0, "R5_hit": 0, "R5_n": 0,
           "R1_hit": 0, "R1_n": 0}
    for case, gt_rel, loc_name, ours_rel in CASES:
        r = run_case(case, gt_rel, loc_name, ours_rel)
        if not r:
            continue
        report["cases"].append(r)
        a, b = r["R2_proxy_trunc"].split("/")
        tot["R2_hit"] += int(a); tot["R2_n"] += int(b)
        a, b = r["R1_proxy_fullspan"]["strict"].split("/")
        tot["R1_hit"] += int(a); tot["R1_n"] += int(b)
        if r["R4_ours_trunc"]:
            a, b = r["R4_ours_trunc"].split("/")
            tot["R4_hit"] += int(a); tot["R4_n"] += int(b)
        if r["R5_ours_full"]:
            a, b = r["R5_ours_full"]["strict"].split("/")
            tot["R5_hit"] += int(a); tot["R5_n"] += int(b)

    print("\n" + "=" * 78)
    print("四片合计   R1 复现链完整 span %d/%d  |  R2 复现链截等长 %d/%d" % (
        tot["R1_hit"], tot["R1_n"], tot["R2_hit"], tot["R2_n"]))
    print("           R4 我方截等长 %d/%d  |  R5 我方完整口径 %d/%d" % (
        tot["R4_hit"], tot["R4_n"], tot["R5_hit"], tot["R5_n"]))
    print("⇒ 同判据公平读数 = R2 vs R4（两者都是「主 span 截到查询等长 + 同款严格判据」）")
    report["totals"] = tot
    out = BENCH / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("产物: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
