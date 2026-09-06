# -*- coding: utf-8 -*-
"""方向 A 事件扩池 四片回归评估（2026-09-05 立项完整阶段）。

对 rerun_<case>_runtime_twopassflash.results.json（evt1 事件表 + 事件扩池全链路重跑）
用 measure_shot_recall.evaluate 同口径算三指标, 对照基线:
  严格 112/139 · 场景级 136/139 · 负例 4/9（2026-09-05 twopass+flash 进 runtime 验证值）
并输出逐片对照 + 合计。p08（兄弟机位失败族）若被事件扩池救回, 2.mkv 严格应 +1。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/measure_event_regression.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402

# 基线（2026-09-05 twopass+flash 验证值）: 严格 / 场景 / 负例误报
BASELINE = {
    "2.mkv (v4 GT)": (34, 39, 39, 39, 3, 4),
    "test1": (34, 43, 42, 43, 0, 1),
    "test2": (12, 20, 18, 20, 0, 1),
    "test3": (32, 37, 37, 37, 1, 3),
}
TOTAL_BASE = (112, 139, 136, 139, 4, 9)

CASES = [
    ("2.mkv (v4 GT)",
     BENCH / "datasets/real/ground_truth_v4.json",
     BENCH / "work/rerun_2mkv_runtime_twopassflash.results.json"),
    ("test1",
     BENCH / "datasets/real/ground_truth_test1.json",
     BENCH / "work/rerun_test1_runtime_twopassflash.results.json"),
    ("test2",
     BENCH / "datasets/real/ground_truth_test2.json",
     BENCH / "work/rerun_test2_runtime_twopassflash.results.json"),
    ("test3",
     BENCH / "datasets/real/ground_truth_test3.json",
     BENCH / "work/rerun_test3_runtime_twopassflash.results.json"),
]


def event_span_widths(res_p: Path) -> dict:
    """统计结果批里 from_event_pool=True 的 span 宽度分布（精度量化）。"""
    if not res_p.exists():
        return {"n_event_spans": 0, "widths": [], "median": None, "max": None}
    res = json.loads(Path(res_p).read_text(encoding="utf-8"))["results"]
    widths = []
    for r in res:
        for s in r.get("original_segments") or []:
            if s.get("from_event_pool"):
                w = s["candidate_end"] - s["candidate_start"]
                if w > 0:
                    widths.append(round(w, 1))
    if not widths:
        return {"n_event_spans": 0, "widths": [], "median": None, "max": None}
    widths.sort()
    n = len(widths)
    med = widths[n // 2] if n % 2 else (widths[n // 2 - 1] + widths[n // 2]) / 2
    return {"n_event_spans": n, "widths": widths,
            "median": round(med, 1), "max": round(widths[-1], 1)}


def main() -> int:
    rows = []
    print("=" * 96)
    for label, gt_p, res_p in CASES:
        if not res_p.exists():
            print(f"  {label}: results missing -> {res_p.name}")
            continue
        gt = json.loads(Path(gt_p).read_text(encoding="utf-8"))
        res = json.loads(Path(res_p).read_text(encoding="utf-8"))["results"]
        r = evaluate(gt, res, label=label)
        rows.append(r)

    print("=" * 96)
    print("四片回归（evt1 事件表 + 事件扩池, 生产路径直跑）vs 基线 112/139 · 136/139 · 4/9")
    print("-" * 96)
    t = {"strict": 0, "n_pos": 0, "scene": 0, "fp": 0, "n_neg": 0}
    for r in rows:
        label = r["label"]
        base = BASELINE.get(label)
        strict_d = (r["strict_hit"] - base[0]) if base else None
        scene_d = (r["scene_hit"] - base[2]) if base else None
        fp_d = (r["fp"] - base[4]) if base else None
        d1 = f"({strict_d:+d})" if strict_d is not None else ""
        d2 = f"({scene_d:+d})" if scene_d is not None else ""
        d3 = f"({fp_d:+d})" if fp_d is not None else ""
        print(f"  {label:<18s} 严格 {r['strict_hit']}/{r['n_pos']}{d1:<6s} "
              f"场景 {r['scene_hit']}/{r['n_pos']}{d2:<6s} 负例 {r['fp']}/{r['n_neg']}{d3}")
        t["strict"] += r["strict_hit"]; t["n_pos"] += r["n_pos"]
        t["scene"] += r["scene_hit"]; t["fp"] += r["fp"]; t["n_neg"] += r["n_neg"]
    print("-" * 96)
    print(f"  合计: 严格 {t['strict']}/{t['n_pos']} (基线 {TOTAL_BASE[0]}/{TOTAL_BASE[1]}, "
          f"{(t['strict']-TOTAL_BASE[0]):+d}) | 场景 {t['scene']}/{t['n_pos']} "
          f"(基线 {TOTAL_BASE[2]}/{TOTAL_BASE[3]}, {(t['scene']-TOTAL_BASE[2]):+d}) | "
          f"负例 {t['fp']}/{t['n_neg']} (基线 {TOTAL_BASE[4]}/{TOTAL_BASE[5]}, "
          f"{(t['fp']-TOTAL_BASE[4]):+d})")
    print("=" * 96)
    if args.event_widths:
        print("事件扩池 span 宽度分布（from_event_pool, 精度量化）")
        for label, gt_p, res_p in CASES:
            w = event_span_widths(res_p)
            if w["n_event_spans"]:
                print(f"  {label:<18s} {w['n_event_spans']} 个事件 span, "
                      f"宽度中位数 {w['median']}s, 最大 {w['max']}s")
            else:
                print(f"  {label:<18s} 无事件 span")
    print("=" * 96)
    return 0


if __name__ == "__main__":
    sys.exit(main())