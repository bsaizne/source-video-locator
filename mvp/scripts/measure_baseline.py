"""四片三指标基线一键复跑（2026-09-04 固化）。

对 2.mkv(v4 GT) + test1/2/3(⑤' 正式 GT) 共四片, 用 measure_shot_recall.evaluate 同口径
计算严格召回 / 场景级(±15s) / 负例误报 / 支撑 span, 输出汇总表 + work/baseline_v4.json。

基线口径(与 GT_BASELINE_test1-3.md / FINDINGS_TEST1-3_GT_BUILD.md 一致):
  - 严格: 编辑重叠≥50% 且原片覆盖/中点命中; 场景级: 结果中点落在 GT ±15s;
  - 结果批(默认) = 文档基线批: 2.mkv->user_case/user_results.json, test1-3->cases/*_results.json;
  - --use-rerun 切换到 2026-09-02 单调弱先验重跑批(work/rerun_*_timelineprior.results.json,
    严格/场景/负例一致, 仅 test1 子 span 枚举略异: 103/158 vs 97/152)。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/measure_baseline.py [--out work/baseline_v4.json] [--use-rerun]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402


# (label, gt, results)
BASELINES_DOC = [
    ("2.mkv (v4 GT)",
     BENCH / "datasets/real/ground_truth_v4.json",
     BENCH / "mvp/benchmark/user_case/user_results.json"),
    ("test1",
     BENCH / "datasets/real/ground_truth_test1.json",
     BENCH / "mvp/benchmark/user_case/cases/test1_results.json"),
    ("test2",
     BENCH / "datasets/real/ground_truth_test2.json",
     BENCH / "mvp/benchmark/user_case/cases/test2_results.json"),
    ("test3",
     BENCH / "datasets/real/ground_truth_test3.json",
     BENCH / "mvp/benchmark/user_case/cases/test3_results.json"),
]
BASELINES_RERUN = [
    ("2.mkv (v4 GT)",
     BENCH / "datasets/real/ground_truth_v4.json",
     BENCH / "work/rerun_2mkv_timelineprior.results.json"),
    ("test1",
     BENCH / "datasets/real/ground_truth_test1.json",
     BENCH / "work/rerun_test1_timelineprior.results.json"),
    ("test2",
     BENCH / "datasets/real/ground_truth_test2.json",
     BENCH / "work/rerun_test2_timelineprior.results.json"),
    ("test3",
     BENCH / "datasets/real/ground_truth_test3.json",
     BENCH / "work/rerun_test3_timelineprior.results.json"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BENCH / "work" / "baseline_v4.json"))
    ap.add_argument("--use-rerun", action="store_true",
                    help="用 2026-09-02 单调弱先验重跑批替代文档基线批")
    args = ap.parse_args()

    table = BASELINES_RERUN if args.use_rerun else BASELINES_DOC
    rows = []
    print("=" * 78)
    for label, gt_p, res_p in table:
        gt = json.loads(Path(gt_p).read_text(encoding="utf-8"))
        res = json.loads(Path(res_p).read_text(encoding="utf-8"))["results"]
        r = evaluate(gt, res, label=label)
        r["gt"] = str(gt_p)
        r["results"] = str(res_p)
        rows.append(r)

    print("=" * 78)
    print("四片三指标基线汇总（严格 | 场景级±15s | 负例误报 | 支撑 span）")
    print("-" * 78)
    t = {"strict": 0, "n_pos": 0, "scene": 0, "fp": 0, "n_neg": 0, "sup": 0, "tot": 0}
    for r in rows:
        label = r["label"]
        strict = f"{r['strict_hit']}/{r['n_pos']}"
        scene = f"{r['scene_hit']}/{r['n_pos']}"
        neg = f"{r['fp']}/{r['n_neg']}"
        sup = f"{r['sup']}/{r['tot']}"
        print(f"  {label:<18s} {strict:<12s} {scene:<14s} {neg:<12s} {sup}")
        t["strict"] += r["strict_hit"]; t["n_pos"] += r["n_pos"]
        t["scene"] += r["scene_hit"]; t["fp"] += r["fp"]; t["n_neg"] += r["n_neg"]
        t["sup"] += r["sup"]; t["tot"] += r["tot"]
    print("-" * 78)
    total_line = ("  合计(不含test4)          "
                  + f"{t['strict']}/{t['n_pos']:<7d} {t['scene']}/{t['n_pos']:<9d} "
                  + f"{t['fp']}/{t['n_neg']:<7d} {t['sup']}/{t['tot']}")
    print(total_line)
    print("=" * 78)
    out = {"generated": "2026-09-04",
           "mode": "rerun" if args.use_rerun else "doc",
           "note": "四片基线(v4 GT + ⑤' GT); doc=文档基线批, rerun=2026-09-02 重跑批",
           "rows": rows, "total": t}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())