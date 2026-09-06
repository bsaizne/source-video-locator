"""诊断: montage 段「主定位 vs 最佳 span gap」分布 + 子镜头触发判据命中集(研究侧, 零 runtime)。

背景(HANDOFF_SUBSHOT_QUERY §4): 现行 montage 弱命中触发用 all_spans max sim < 0.62,
被高 sim 附加 span 掩盖主定位漂移(p10 型触发不了)。候选新判据 = 主定位与最佳 span
gap 大。本脚本在基线批(work/_backup_pre_subshot_rescue)上统计:
  - 每个 montage_flag 结果: 主定位 mid / 最佳 montage span mid / gap / 主定位 sim / 最佳 sim
  - 按 GT(v4/test1-3) 标 verdict(HIT/part/MISS) + 主定位与 GT 中点偏移
输出每片 montage 段明细表, 用于选 gap 阈值。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/diag_subshot_trigger.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate, overlap_frac  # noqa: E402

BASE = BENCH / "work" / "_backup_pre_subshot_rescue"
FILMS = [
    ("2mkv", BENCH / "datasets/real/ground_truth_v4.json", BASE / "rerun_2mkv_runtime_twopassflash.results.json"),
    ("test1", BENCH / "datasets/real/ground_truth_test1.json", BASE / "rerun_test1_runtime_twopassflash.results.json"),
    ("test2", BENCH / "datasets/real/ground_truth_test2.json", BASE / "rerun_test2_runtime_twopassflash.results.json"),
    ("test3", BENCH / "datasets/real/ground_truth_test3.json", BASE / "rerun_test3_runtime_twopassflash.results.json"),
]


def montage_spans(r: dict) -> list[dict]:
    return [s for s in (r.get("original_segments") or [])
            if not s.get("from_scene_pool") and not s.get("from_event_pool")
            and s.get("score") is not None]


def main() -> int:
    for label, gt_p, res_p in FILMS:
        gt = json.loads(Path(gt_p).read_text(encoding="utf-8"))
        res = json.loads(Path(res_p).read_text(encoding="utf-8"))["results"]
        ev = evaluate(gt, res, label=label)
        # GT 正例 -> (e0,e1,o0,o1,verdict)
        pos = [(p["edited"][0], p["edited"][1], p["original"][0], p["original"][1], p["id"])
               for p in gt["positives"]]
        verdict = {d["id"]: d["mark"] for d in ev["per_pos"]}

        print(f"\n########## {label}: montage_flag 段明细 ##########")
        print(f"{'seg':>4} {'ed':>15} {'primary_mid':>11} {'best_mid':>9} {'gap':>7} "
              f"{'psim':>6} {'bsim':>6} {'gt_id':>8} {'gt_mid':>8} {'p_off':>7} {'b_off':>7} verdict")
        for i, r in enumerate(res):
            if not r.get("montage_flag"):
                continue
            ms = montage_spans(r)
            if not ms:
                continue
            p0 = r["original"]["candidate_start"]
            p1 = r["original"]["candidate_end"]
            pmid = (p0 + p1) / 2.0
            # 主定位 sim = 与 original 最重叠的 montage span 的 score
            psim, pspan = None, None
            best_ov = -1.0
            bsim, bmid = -1.0, None
            for s in ms:
                a, b = s["candidate_start"], s["candidate_end"]
                ov = overlap_frac(a, b, p0, p1) if (b - a) > 0 else 0.0
                if ov > best_ov:
                    best_ov, psim, pspan = ov, s["score"] or 0.0, (a, b)
                if (s["score"] or 0.0) > bsim:
                    bsim = s["score"] or 0.0
                    bmid = (a + b) / 2.0
            gap = abs(pmid - bmid)
            # 编辑侧匹配 GT 正例(重叠>=50%)
            e0, e1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            gt_hit = None
            for ge0, ge1, go0, go1, gid in pos:
                if overlap_frac(ge0, ge1, e0, e1) >= 0.5:
                    gt_hit = (gid, (go0 + go1) / 2.0)
                    break
            gtid = gt_hit[0] if gt_hit else "-"
            gmid = gt_hit[1] if gt_hit else float("nan")
            p_off = abs(pmid - gmid) if gt_hit else float("nan")
            b_off = abs(bmid - gmid) if gt_hit else float("nan")
            v = verdict.get(gtid, "-") if gt_hit else "(neg/none)"
            print(f"s{i:>3} {e0:7.1f}-{e1:6.1f} {pmid:11.1f} {bmid:9.1f} {gap:7.1f} "
                  f"{psim:6.3f} {bsim:6.3f} {gtid:>8} {gmid:8.1f} {p_off:7.1f} {b_off:7.1f} {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
