# -*- coding: utf-8 -*-
"""索引密度 ÷2 敏感度探针（2026-10-03 续49，零 runtime 改动 / 零 GPU / 纯 JSON+GT）。

动机：TODO P0 ④「两级采样索引探针」= 把源片索引从 1.0fps 抽稀到 0.5fps（建索引成本 ÷2、
索引体积 ÷2），需 feature_version bump + 四片全回归（≈3~4h）才能拿真实读数。
本探针先做**结构账**（续48 教训：先做结构账再决定实跑）：在**不改 runtime** 的前提下，
用现役默认批的结果 span 做「2s 网格化 / ±1s 收缩 / ±1s 平移」三类扰动，交给**同一评估器**
（measure_shot_recall.evaluate）重算三指标，得到「提案网格粗化 ±1s」的**精度敏感度包络**。

口径（必须随结论一起引用）：
- 这是**最终 span 的敏感度包络**，不是 0.5fps 索引链路的模拟。真实链路里 span 端点由
  patch/ISC 局部细化给出（实测端点落在 0.25s 步长上，非索引网格），故真实损失可能更小；
  反之若粗网格让**提案本身换地方**，损失可能更大——本探针不覆盖后者。
- 扰动只作用于原片侧 span（main + original_segments），编辑侧不动（与本议题无关）。

用法:
  python mvp/scripts/probe_index_fps_sensitivity.py \
      --pattern work/isc_refine_arms/v2_{case}.results.json \
      --out work/index_fps_probe/sensitivity_20261003.json
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from measure_shot_recall import evaluate  # noqa: E402

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json"),
    ("test1", "datasets/real/ground_truth_test1.json"),
    ("test2", "datasets/real/ground_truth_test2.json"),
    ("test3", "datasets/real/ground_truth_test3.json"),
]

# 生产索引元数据（只读）：给成本账提供真实帧数/时长/体积
INDEX_DIR = Path(r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data\index")
INDEX_SUBDIR = {
    "2mkv": "2__4c6d4ab2.idx",
    "test1": "test1-om__5d4fdc2b.idx",
    "test2": "test2-om__35b9a58f.idx",
    "test3": "test3-om__074e2dcc.idx",
}
DML_FPS_INDEX = 13.6   # 续17 实测：H2 DirectML 建索引 13.5~13.8 fps（10/60/128min 三档）


def _grid(v: float, step: float = 2.0) -> float:
    return round(v / step) * step


def perturb(rows: list, mode: str) -> list:
    out = copy.deepcopy(rows)
    for r in out:
        targets = [r["original"]]
        for s in r.get("original_segments") or []:
            targets.append(s)
        for t in targets:
            a, b = float(t["candidate_start"]), float(t["candidate_end"])
            if b - a <= 0.01:
                continue
            if mode == "grid2":                     # 最近 2s 网格（|Δ| ≤ 1s）
                a, b = _grid(a, 2.0), _grid(b, 2.0)
                if b - a <= 0.01:
                    b = a + 2.0
            elif mode == "shrink1":                 # 两端各缩 1s（网格取整的最坏覆盖损失）
                b0 = b
                a = a + 1.0
                b = max(a + 0.01, b0 - 1.0)
            elif mode == "shift_minus1":            # 整体提前 1s
                a, b = max(0.0, a - 1.0), max(0.01, b - 1.0)
            elif mode == "shift_plus1":             # 整体推后 1s
                a, b = a + 1.0, b + 1.0
            else:
                raise ValueError(mode)
            t["candidate_start"], t["candidate_end"] = round(a, 3), round(b, 3)
    return out


def metrics(gt: dict, res: list, label: str) -> dict:
    with contextlib.redirect_stdout(io.StringIO()):
        return evaluate(gt, res, label=label)


def markmap(rep: dict) -> dict:
    return {p["id"]: p["mark"] for p in rep["per_pos"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pattern", default="work/isc_refine_arms/v2_{case}.results.json")
    ap.add_argument("--out", default=str(BENCH / "work" / "index_fps_probe"
                                         / "sensitivity_20261003.json"))
    args = ap.parse_args()
    modes = ["base", "grid2", "shrink1", "shift_minus1", "shift_plus1"]

    report = {"pattern": args.pattern, "modes": modes, "cases": {}, "total": {},
              "index_cost": {}, "caliber": (
                  "最终 span 的敏感度包络（非 0.5fps 链路模拟）；扰动只作用原片侧 span；"
                  "评估器 = measure_shot_recall.evaluate")}
    tot = {m: {"strict": 0, "main": 0, "scene": 0, "fp": 0, "n_pos": 0, "n_neg": 0}
           for m in modes}
    flips = {}
    for case, gt_rel in CASES:
        res_p = BENCH / args.pattern.format(case=case)
        if not res_p.exists():
            print("MISSING results: %s" % res_p, flush=True)
            continue
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        base_res = json.loads(res_p.read_text(encoding="utf-8"))["results"]
        row = {}
        base_marks = None
        for m in modes:
            res_m = base_res if m == "base" else perturb(base_res, m)
            rep = metrics(gt, res_m, case + "_" + m)
            row[m] = {"strict": rep["strict_hit"], "main": rep["main_hit"],
                      "scene": rep["scene_hit"], "fp": rep["fp"],
                      "n_pos": rep["n_pos"], "n_neg": rep["n_neg"]}
            for k in ("strict", "main", "scene", "fp", "n_pos", "n_neg"):
                tot[m][k] += row[m][k]
            mk = markmap(rep)
            if m == "base":
                base_marks = mk
            else:
                flips.setdefault(m, {})[case] = {
                    k: [base_marks.get(k), v] for k, v in mk.items()
                    if base_marks.get(k) != v}
        report["cases"][case] = row
        print("%-7s " % case + " | ".join(
            "%s 严%d 主%d 场%d FP%d" % (m, row[m]["strict"], row[m]["main"],
                                        row[m]["scene"], row[m]["fp"]) for m in modes), flush=True)

    # ---- 索引成本账（真实元数据 + 续17 实测吞吐） ----
    for case, sub in INDEX_SUBDIR.items():
        p = INDEX_DIR / sub / "index.json"
        if not p.exists():
            continue
        meta = json.loads(p.read_text(encoding="utf-8"))
        frames = int(meta.get("num_frames", 0))
        size = sum(f.stat().st_size for f in (INDEX_DIR / sub).glob("*") if f.is_file())
        report["index_cost"][case] = {
            "sampling_fps": meta.get("sampling_fps"), "num_frames": frames,
            "duration_s": round(float(meta.get("duration", 0.0)), 1), "bundle_bytes": size,
            "est_build_s_at_13.6fps": round(frames / DML_FPS_INDEX, 1),
            "feature_version": meta.get("feature_version")}
    report["total"] = tot
    report["flips"] = flips

    print("\n=== 四片合计（现役默认批 = work/isc_refine_arms/v2_*) ===")
    b = tot["base"]
    for m in modes:
        t = tot[m]
        print("  %-12s 严格 %3d/%d (%+d) | 导出实得 %3d (%+d) | 场景 %3d (%+d) | 负例 %d/%d (%+d)"
              % (m, t["strict"], t["n_pos"], t["strict"] - b["strict"],
                 t["main"], t["main"] - b["main"], t["scene"], t["scene"] - b["scene"],
                 t["fp"], t["n_neg"], t["fp"] - b["fp"]))
    print("\n=== 翻转明细（相对 base）===")
    for m in modes[1:]:
        n = sum(len(v) for v in flips.get(m, {}).values())
        print("  %-12s %d 行: %s" % (m, n, json.dumps(flips.get(m, {}), ensure_ascii=False)))
    print("\n=== 索引成本账（四片真实索引）===")
    tf = ts = 0.0
    tbytes = 0.0
    for c, v in report["index_cost"].items():
        tf += v["num_frames"]; ts += v["est_build_s_at_13.6fps"]; tbytes += v["bundle_bytes"]
        print("  %-6s %6d 帧 源片 %8.1f s 体积 %6.1f MB  建索引估 %6.1fs"
              % (c, v["num_frames"], v["duration_s"], v["bundle_bytes"] / 1e6,
                 v["est_build_s_at_13.6fps"]))
    print("  合计   %6d 帧 建索引估 %.1fs (%.1f min)；÷2 后省 %.1f min / 体积省 %.1f MB"
          % (tf, ts, ts / 60.0, ts / 120.0, tbytes / 2e6))

    out_p = Path(args.out)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    out_p.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved %s" % out_p)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
