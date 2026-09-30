# -*- coding: utf-8 -*-
"""gt_impact_scan — GT 修正时自动列出受影响结论 (2026-09-26, 审计 §八 机制的自动化半边)。

背景: FINDINGS_GT_CONTAMINATION_AUDIT.md —— 本项目已因「GT 修正后未重验旧结论」亏三次;
登记规则②要求 GT 修正后"执行者更新本表并标注受影响文档", 此前依赖人工比对。本脚本把
「发现受影响文档」自动化: 用 GT 文件内容哈希快照检测变更, 再把变更映射到 §八登记表中的结论文档;
同时扫描 user_case 下未登记 GT 版本的 FINDINGS/提案文档。

用法:
  python mvp/scripts/gt_impact_scan.py --init    # 建立当前 GT 哈希快照(首次/GT 更新核对后重建)
  python mvp/scripts/gt_impact_scan.py --check   # 检测 GT 变更 → 列受影响文档; 未登记文档清单
退出码: 0 = 无未确认变更且无未登记文档(或仅提示); 1 = 有 GT 变更待人工核对。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

B = Path(__file__).resolve().parents[2]
GT_DIR = B / "datasets" / "real"
MANIFEST = B / "work" / "gt_version_manifest.json"
AUDIT = B / "mvp" / "benchmark" / "user_case" / "semantic_signal" / "FINDINGS_GT_CONTAMINATION_AUDIT.md"
SCAN_DIRS = [B / "mvp" / "benchmark" / "user_case"]
GT_PATTERN = re.compile(r"ground_truth[\w\-]*\.json")

# §八登记表里「文档 → 依赖 GT 文件」的映射(人工维护, 与审计 §八 同步);
# 变更检测 = 该 GT 文件哈希变化 ⇒ 列出映射到的文档。
AFFECTED_MAP = {
    "ground_truth.json": ["(v1, 已证伪留档, 勿用于评估)"],
    "ground_truth_v2.json": ["FINDINGS_SUBSHOT_QUERY.md", "FINDINGS_REVIEW_M1M8.md(部分)"],
    "ground_truth_v3.json": ["feature_upgrade/FINDINGS.md", "phase24_1/FINDINGS.md",
                             "semantic_signal/FINDINGS_M5.md", "(v3 基线历史批)"],
    "ground_truth_v4.json": ["feature_upgrade/FINDINGS_FEATURE_UPGRADE_V4.md",
                             "feature_upgrade/FINDINGS_VITB_FULL_INDEX.md",
                             "phase24_1/FINDINGS_V4.md", "semantic_signal/FINDINGS_M5_V4.md",
                             "semantic_signal/FINDINGS_TIMELINE_V4_QUANT.md",
                             "semantic_signal/FINDINGS_EVENT_IDENTITY_P1_P2.md",
                             "semantic_signal/FINDINGS_P36_FINESEG.md",
                             "semantic_signal/FINDINGS_AMBIGUITY_PROTOTYPE.md",
                             "semantic_signal/FINDINGS_LOWINFO_STRIP.md",
                             "semantic_signal/FINDINGS_IFRAME_CUT.md(回归护栏)"],
    "ground_truth_test1.json": ["gt_review/GT_BASELINE_test1-3.md", "(test1 域全部结论)"],
    "ground_truth_test2.json": ["gt_review/GT_BASELINE_test1-3.md", "(test2 域全部结论; t2r07c 2026-09-06 修正留痕)"],
    "ground_truth_test3.json": ["gt_review/GT_BASELINE_test1-3.md", "(test3 域全部结论; r14/r15 负例)"],
    "ground_truth_corrected.json": ["semantic_signal/FINDINGS_SUBSHOT_QUERY.md"],
}


def gt_hashes() -> dict:
    out = {}
    for p in sorted(GT_DIR.glob("ground_truth*.json")):
        out[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    return out


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def scan_unregistered() -> list:
    missing = []
    for d in SCAN_DIRS:
        for p in sorted(d.rglob("*.md")):
            text = p.read_text(encoding="utf-8", errors="replace")
            if "FINDINGS" not in p.name and "RESEARCH_PROPOSAL" not in p.name:
                continue
            if re.search(r"GT 版本|GT 污染|作废|已重跑|不依赖 GT|不套 GT", text[:2000]):
                continue
            missing.append(str(p.relative_to(B)))
    return missing


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true", help="重建 GT 哈希快照")
    ap.add_argument("--check", action="store_true", help="检测变更并列受影响文档")
    args = ap.parse_args()

    cur = gt_hashes()
    if args.init or not MANIFEST.exists():
        old = load_manifest()
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps(cur, ensure_ascii=False, indent=1), encoding="utf-8")
        print("快照已写 %s (%d 个 GT 文件)" % (MANIFEST.relative_to(B), len(cur)))
        if old and old != cur:
            changed = [k for k in cur if old.get(k) != cur[k]]
            print("本次快照相对旧快照变更: %s" % changed)
        if args.init:
            return 0

    old = load_manifest()
    changed = [k for k in cur if old.get(k) != cur[k]]
    removed = [k for k in old if k not in cur]
    rc = 0
    print("== GT 变更检测 ==")
    if not changed and not removed:
        print("无变更(%d 个 GT 文件, 基准快照 %s)" % (len(cur), MANIFEST.relative_to(B)))
    else:
        rc = 1
        for k in changed:
            print("⚠️ GT 变更: %s (%s → %s)" % (k, (old.get(k) or "-")[:12], cur[k][:12]))
            for doc in AFFECTED_MAP.get(k, ["(未登记映射——请补 AFFECTED_MAP)"]):
                print("   受影响: %s" % doc)
        for k in removed:
            print("⚠️ GT 移除: %s" % k)
        print("→ 按审计 §八规则: 逐文档重验/标注, 完成后重跑 --init 固化新快照。")

    print("\n== 未登记 GT 版本的文档(前 2000 字符无 GT 版本/作废标注) ==")
    miss = scan_unregistered()
    if miss:
        for m in miss:
            print("  - %s" % m)
        print("  (共 %d 份; 历史已闭环文档可忽略, 新文档应按登记规则①加头)" % len(miss))
    else:
        print("  无")
    return rc


if __name__ == "__main__":
    sys.exit(main())
