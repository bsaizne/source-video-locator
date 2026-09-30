# -*- coding: utf-8 -*-
"""eval_backbone_swap — 「换 backbone 四片回归」评估 harness（2026-09-26 固化，零 mvp/src 改动）。

背景: ViT-B 全量索引回归(FINDINGS_VITB_FULL_INDEX.md)证明的评估基建, 固化为一键编排,
供未来 H4(CUDA)/DINOv3/其他 backbone 评估直接复用(2026-09-25 待拍板第 ① 项, 2026-09-26 用户批准固化)。

四阶段(每个 backbone 一个注册表项 + 一个 rerun 模块):
  1. asset   检查 ONNX 资产在位; 缺失时打印导出命令(不自动下载权重)。
  2. locate  调该 backbone 的 rerun 模块逐片跑生产管线(隔离 SVL_DATA_DIR, 不碰产品索引)。
  3. measure 调 measure_four_results.py 出三指标(严格/场景/负例/支撑)。
  4. compare 与基线批(work/rerun_{case}_perfopt.results.json)逐片对照, 打印差值表。

用法:
  python mvp/scripts/eval_backbone_swap.py --backbone vitb            # 全流程(资产在位时)
  python mvp/scripts/eval_backbone_swap.py --backbone vitb --phase locate   # 单跑某阶段
  python mvp/scripts/eval_backbone_swap.py --list                     # 列出已注册 backbone

诚实边界(继承 rerun_vitb_runtime):
  * CLS=新基座 / patch=ViT-S 的混合口径(patch 重排资产不变); 对「是否换基座」结论不构成偏置(基线同配置);
  * 正式接入 runtime 需另做 dim 参数化(索引 schema/validate)与其回归测试——本 harness 只做评估;
  * 新 backbone 接入 = 在 BACKBONES 加一项 + 写一个 rerun_<name>_runtime.py(照 rerun_vitb_runtime.py
    改 fv/onnx/维度修正), 本脚本零改动。
"""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

B = Path(__file__).resolve().parents[2]
PY = sys.executable

# 注册表: 新 backbone 在此加一项; rerun 模块放 mvp/scripts/ 并提供 main(case|None)。
BACKBONES = {
    "vitb": {
        "desc": "DINOv2 ViT-B/14 CLS-768 (2026-09-25 评估批, 已关闭——无增益, 仅作 harness 参考实现)",
        "onnx": B / "work" / "vitb_asset" / "dinov2_cls_768.onnx",
        "rerun_module": "rerun_vitb_runtime",
        "pattern": "work/vitb_{case}.results.json",
        "metrics_out": "work/vitb_four_metrics.json",
        "export_hint": 'python mvp/scripts/export_dml_model_vitb.py  (权重 work/dinov2_weights/dinov2_vitb14_pretrain.pth)',
    },
    # "vits384": {...}  # 示例: 未来条目
}

BASELINE_PATTERN = "work/rerun_{case}_perfopt.results.json"  # 三指标基线批(perfopt, 全 ViT-S)
CASES = ["2mkv", "test1", "test2", "test3"]


def run_phase_asset(cfg: dict) -> int:
    if cfg["onnx"].exists():
        print("[asset] OK %s (%.1f MB)" % (cfg["onnx"], cfg["onnx"].stat().st_size / 1e6))
        return 0
    print("[asset] 缺失: %s" % cfg["onnx"])
    print("[asset] 导出: %s" % cfg["export_hint"])
    return 1


def run_phase_locate(cfg: dict, case: str | None) -> int:
    sys.path.insert(0, str(B / "mvp" / "scripts"))
    mod = importlib.import_module(cfg["rerun_module"])
    # 各 rerun 模块约定: main() 自读 sys.argv[1] 作单案例过滤
    sys.argv = [str(B / "mvp" / "scripts" / ("%s.py" % cfg["rerun_module"]))] + ([case] if case else [])
    rc = mod.main()
    return int(rc or 0)


def run_phase_measure(cfg: dict) -> int:
    pattern = cfg["pattern"]
    out = B / cfg["metrics_out"]
    cmd = [PY, str(B / "mvp" / "scripts" / "measure_four_results.py"),
           "--pattern", pattern, "--out", str(out.relative_to(B))]
    print("[measure] %s" % " ".join(cmd))
    return subprocess.call(cmd)


def run_phase_compare(cfg: dict) -> int:
    def load(pattern, out=None):
        tmp = B / (out or "work/_ebs_tmp.json")
        subprocess.check_call([PY, str(B / "mvp" / "scripts" / "measure_four_results.py"),
                               "--pattern", pattern, "--out", str(tmp.relative_to(B))],
                              stdout=subprocess.DEVNULL)
        return json.loads(tmp.read_text(encoding="utf-8"))

    new = load(cfg["pattern"], cfg["metrics_out"])
    base = load(BASELINE_PATTERN, "work/_ebs_baseline_tmp.json")
    new_rows = {r["label"]: r for r in new["rows"]}
    base_rows = {r["label"]: r for r in base["rows"]}
    tag = cfg["pattern"].split("/{case}")[0].split("/")[-1]
    print("\n== 与基线对照(严格 | 场景级 | 负例误报 | 支撑) ==")
    print("| 片 | 基线(perfopt) | %s | Δ严格 |" % tag)
    print("|---|---|---|---|")

    def fmt(r):
        return "%d/%d · %d/%d · %d/%d · %d" % (r["strict_hit"], r["n_pos"], r["scene_hit"],
                                               r["n_pos"], r["fp"], r["n_neg"], r["sup"])
    for c in CASES:
        bn, nn = base_rows.get(c), new_rows.get(c)
        if not bn or not nn:
            print("| %s | %s | %s | (缺结果批) |" % (c, fmt(bn) if bn else "?", fmt(nn) if nn else "?"))
            continue
        print("| %s | %s | %s | %+d |" % (c, fmt(bn), fmt(nn), nn["strict_hit"] - bn["strict_hit"]))
    bt, nt = base["total"], new["total"]
    print("| **合计** | **%d/%d · %d/%d · %d/%d** | **%d/%d · %d/%d · %d/%d** | **%+d** |" % (
        bt["strict"], bt["n_pos"], bt["scene"], bt["n_pos"], bt["fp"], bt["n_neg"],
        nt["strict"], nt["n_pos"], nt["scene"], nt["n_pos"], nt["fp"], nt["n_neg"],
        nt["strict"] - bt["strict"]))
    print("\n(支撑总数见 measure 输出; 基线批 = %s)" % BASELINE_PATTERN)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="backbone 四片回归评估 harness")
    ap.add_argument("--backbone", default="vitb", choices=sorted(BACKBONES))
    ap.add_argument("--phase", default="all", choices=["all", "asset", "locate", "measure", "compare"])
    ap.add_argument("--case", default=None, help="locate 阶段单片跑: 2mkv|test1|test2|test3")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()

    if args.list:
        for k, v in BACKBONES.items():
            print("%-10s %s\n           onnx=%s" % (k, v["desc"], v["onnx"]))
        return 0
    cfg = BACKBONES[args.backbone]
    rc = 0
    if args.phase in ("all", "asset"):
        rc = rc or run_phase_asset(cfg)
        if rc:
            return rc
    if args.phase in ("all", "locate"):
        rc = rc or run_phase_locate(cfg, args.case)
    if args.phase in ("all", "measure"):
        rc = rc or run_phase_measure(cfg)
    if args.phase in ("all", "compare"):
        rc = rc or run_phase_compare(cfg)
    return rc


if __name__ == "__main__":
    sys.exit(main())
