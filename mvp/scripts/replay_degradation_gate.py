# -*- coding: utf-8 -*-
"""退化拒绝门 + 场景覆盖门槛 离线重放 A/B（2026-09-28 续19, T1-1 验收）。

竞品 results.validation 的两条硬停门（确证值 0.8 / 0.2）在我方**现有结果批**上离线重放：
门只看已落盘的主 span / 子 span cover, 不需要重跑 GPU, 因此双臂对照是同一段结果、同一 GT、
同一判据（`measure_shot_recall.evaluate`），唯一差别 = 门开没开。

被拒段在 gated 批里写成「零宽主 span + 无子 span」= 产品语义上的"未给出答案"
（评估层只看 span, 不看 failure_reason, 所以必须真的抹掉答案, 否则等于偷偷保留了定位）。

用法:
  PY="D:/claudework/video-dedup-tool/.venv/Scripts/python.exe"
  $PY mvp/scripts/replay_degradation_gate.py \
      --pattern "work/rerun_{case}_perfopt.results.json" \
      --out-pattern "work/gateon_{case}.results.json" \
      --max-dup 0.8 --min-cover 0.2

产物: work/degradation_gate_ab.json（逐片三指标双臂 + 翻转清单 + dup 比例分布）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from domain import ResultBatch                                    # noqa: E402
from engine.localization.degradation_gate import apply_degradation_gate  # noqa: E402
from measure_shot_recall import evaluate                          # noqa: E402

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json"),
    ("test1", "datasets/real/ground_truth_test1.json"),
    ("test2", "datasets/real/ground_truth_test2.json"),
    ("test3", "datasets/real/ground_truth_test3.json"),
]


def _blank(r: dict) -> dict:
    """把一段写成"未给出答案"（零宽主 span + 清空子 span）。"""
    r = dict(r)
    r["original"] = {"candidate_start": 0.0, "candidate_end": 0.0}
    r["original_segments"] = []
    r["failure_reason"] = "degenerate_duplicate"
    r["confidence"] = "LOW"
    r["confidence_score"] = 0.0
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="work/rerun_{case}_perfopt.results.json")
    ap.add_argument("--out-pattern", default="work/gateon_{case}.results.json")
    ap.add_argument("--max-dup", type=float, default=0.8)
    ap.add_argument("--min-cover", type=float, default=0.2)
    ap.add_argument("--write", action="store_true", help="落盘 gated 批（供 measure_four_results 复算）")
    ap.add_argument("--report", default="work/degradation_gate_ab.json",
                    help="A/B 报告落盘路径（跑新批次时必须换新名，勿覆盖历史留痕）")
    args = ap.parse_args()

    report = {"max_duplicate_scene_ratio": args.max_dup, "min_scene_coverage": args.min_cover,
              "cases": []}
    totals = {k: 0 for k in ("base_strict", "gate_strict", "base_scene", "gate_scene",
                             "base_fp", "gate_fp", "base_sup", "gate_sup", "n_pos", "n_neg")}
    for case, gt_rel in CASES:
        rp = BENCH / args.pattern.format(case=case)
        if not rp.exists():
            print("MISSING results: %s" % rp)
            continue
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads(rp.read_text(encoding="utf-8"))
        batch = ResultBatch.from_dict(raw)
        stats = apply_degradation_gate(batch.results, enabled=True,
                                       max_duplicate_scene_ratio=args.max_dup,
                                       min_scene_coverage=args.min_cover)
        gated = list(raw["results"])
        for i in stats.rejected:
            gated[i] = _blank(gated[i])
        # 子 span 被覆盖门槛丢弃的段也如实反映（cover < 门槛的 sub 从 gated 里剔除）
        for i, r in enumerate(batch.results):
            if i in stats.rejected:
                continue
            kept = [(s.start, s.end) for s in r.original_segments]
            rows = [x for x in gated[i].get("original_segments") or []]
            if len(rows) != len(kept):
                gated[i] = dict(gated[i])
                gated[i]["original_segments"] = [x for x in rows
                                                 if float(x.get("cover") or 0.0) >= args.min_cover]

        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            base = evaluate(gt, raw["results"], label=case)
            gate = evaluate(gt, gated, label=case)
        flips = [{"id": b["id"], "from": b["mark"], "to": g["mark"]}
                 for b, g in zip(base["per_pos"], gate["per_pos"]) if b["mark"] != g["mark"]]
        case_row = {
            "case": case,
            "rejected": [[i, round(stats.dup_ratios.get(i, 0.0), 3)] for i in stats.rejected],
            "subs_dropped": stats.subs_dropped, "subs_kept": stats.subs_kept,
            "base": {"strict": f"{base['strict_hit']}/{base['n_pos']}",
                     "scene": f"{base['scene_hit']}/{base['n_pos']}",
                     "fp": f"{base['fp']}/{base['n_neg']}", "sup": f"{base['sup']}/{base['tot']}"},
            "gate": {"strict": f"{gate['strict_hit']}/{gate['n_pos']}",
                     "scene": f"{gate['scene_hit']}/{gate['n_pos']}",
                     "fp": f"{gate['fp']}/{gate['n_neg']}", "sup": f"{gate['sup']}/{gate['tot']}"},
            "flips": flips,
        }
        report["cases"].append(case_row)
        totals["base_strict"] += base["strict_hit"]; totals["gate_strict"] += gate["strict_hit"]
        totals["base_scene"] += base["scene_hit"]; totals["gate_scene"] += gate["scene_hit"]
        totals["base_fp"] += base["fp"]; totals["gate_fp"] += gate["fp"]
        totals["base_sup"] += base["sup"]; totals["gate_sup"] += gate["sup"]
        totals["n_pos"] += base["n_pos"]; totals["n_neg"] += base["n_neg"]

        print("[%s] rejected=%d subs_dropped=%d  strict %s -> %s | scene %s -> %s | fp %s -> %s" % (
            case, len(stats.rejected), stats.subs_dropped,
            case_row["base"]["strict"], case_row["gate"]["strict"],
            case_row["base"]["scene"], case_row["gate"]["scene"],
            case_row["base"]["fp"], case_row["gate"]["fp"]), flush=True)
        for f in flips:
            print("      flip %-10s %-5s -> %-5s" % (f["id"], f["from"], f["to"]), flush=True)
        if args.write:
            out = BENCH / args.out_pattern.format(case=case)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps({"schema_version": 1,
                                       "original_video": raw.get("original_video"),
                                       "edited_video": raw.get("edited_video"),
                                       "results": gated}, indent=2, ensure_ascii=False),
                           encoding="utf-8")

    report["totals"] = {**totals,
                        "strict_delta": totals["gate_strict"] - totals["base_strict"],
                        "scene_delta": totals["gate_scene"] - totals["base_scene"],
                        "fp_delta": totals["gate_fp"] - totals["base_fp"]}
    out_json = BENCH / args.report
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("=" * 78)
    print("合计 严格 %d/%d -> %d/%d (%+d) | 场景 %d -> %d (%+d) | 负例误报 %d -> %d (%+d)" % (
        totals["base_strict"], totals["n_pos"], totals["gate_strict"], totals["n_pos"],
        report["totals"]["strict_delta"],
        totals["base_scene"], totals["gate_scene"], report["totals"]["scene_delta"],
        totals["base_fp"], totals["gate_fp"], report["totals"]["fp_delta"]), flush=True)
    print("产物: %s" % out_json, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
