# -*- coding: utf-8 -*-
"""apply_gt_version_headers — 2026-10-01 批量补 GT 版本标注头（用户拍板「32 份补齐」）。

依据 = mvp/benchmark/user_case/semantic_signal/GT_VERSION_REGISTER_PROPOSAL_20260928.md
（A/B/C/E/F/G 类 29 份按提案建议头，H 类 3 份读文后判定）+ 提案后新增 12 份（续29~35，
代际由档案直接确证）。同时把登记行追加到 FINDINGS_GT_CONTAMINATION_AUDIT.md §八 表格。
不改任何正文技术结论；已含「GT 版本/GT 口径」头的文档自动跳过（幂等）。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # mvp/
UC = ROOT / "benchmark" / "user_case"

D139 = ("现行 139 条 verified（ground_truth_v4.json + test1-3.json，2026-09-02 定案；"
        "2026-09-30 重锚定 12 行后仍为现行基准）")
STALE = "文内引用的旧基线属当时现役口径、现已过时，引用数字须注明口径代际（现行基线见 .agent/STATE.md）。"
INFER = "〔推断级：按成文日期推定，依据 GT_VERSION_REGISTER_PROPOSAL_20260928.md〕"

HEADERS = {
    # ---- A 类：竞品判据对照，不适用（6） ----
    "competitor_cutmatch/FINDINGS_BOUNDARY_REFINER_COMPARISON.md":
        "不适用——竞品边界精修判据对照（227 条现行边界 + 44 例人工盲判），不与我方 GT 做召回判定。",
    "competitor_cutmatch/FINDINGS_CAPABILITY_GAP.md":
        "不适用——竞品组合链能力差距分析，无 GT 判定。",
    "competitor_cutmatch/FINDINGS_CUTMATCH_CONSTANTS_ADOPTION.md":
        "不适用——竞品常量绑定核对；但文内引用我方基线 117/139 为当时现役口径已过时，" + STALE,
    "competitor_cutmatch/FINDINGS_CUTMATCH_POSTPROCESS_REPLAY.md":
        "不适用——竞品 probs 后处理重放（24/24 逐帧几何复现）。",
    "competitor_cutmatch/FINDINGS_DOCSTRING_BREAKTHROUGH.md":
        "不适用——竞品 docstring/常量语义挖掘（纯竞品数据）。",
    "competitor_cutmatch/FINDINGS_COMPETITOR_FULL_SWEEP.md":
        "不适用——竞品 282 blob 全量扫穿（纯竞品数据）。",
    # ---- B 类：GT 建设本体（1） ----
    "gt_review/FINDINGS_TEST1-3_GT_BUILD.md":
        "本文件即 test1-3 GT 建设记录（draft→正式版 2026-09-02 定案，139 条 verified 的由来），"
        "不适用「按某版 GT 重验」。⚠️ 现行 GT 已于 2026-09-30 重锚定（12 行修正 + 2 同源注释），"
        "见 semantic_signal/FINDINGS_GT_TICKET_ADJUDICATION_20260930.md。",
    # ---- C 类：现行 139 条（7，推断级） ----
    "competitor_cutmatch/FINDINGS_COMBO_FIVE_RING_TEST1.md":
        D139 + "（test1 43 条子集）。" + INFER,
    "competitor_cutmatch/FINDINGS_P0_DENSE_START_TEST1.md":
        D139 + "；文内基线 117/139 = vote_prior 移植前口径，" + STALE + INFER,
    "competitor_cutmatch/FINDINGS_FAST_GLOBAL_REPRO.md":
        D139 + "；文内 117 与 119 并存（vote_prior 前后双臂），引用须注明臂，且均早于 09-30 重锚定。" + INFER,
    "competitor_cutmatch/FINDINGS_PROXY_B_STAGE_REVIEW.md":
        "不适用——TN 代理切分几何对照 + 44 例人工盲判；文内 v4 提及为历史引用。",
    "competitor_cutmatch/FINDINGS_PROXY_D_STAGE_REVIEW.md":
        D139 + "；文内基线 117/121/124 系当时口径，" + STALE + INFER,
    "competitor_cutmatch/FINDINGS_QUERY_UNIT_SWAP.md":
        D139 + "；文内 114→104 系当时口径，" + STALE + INFER,
    "competitor_cutmatch/FINDINGS_PATCH_FUSION_PROBE.md":
        D139 + "（探针真值窗取自 v4/test3，rank/margin 口径不涉三指标）。" + INFER,
    # ---- E 类：v4 重跑确证（3） ----
    "semantic_signal/FINDINGS_M4_V4.md":
        "v4（2026-09-01 修正）重跑版✅（CHANGELOG 2026-09-04）；对应旧口径版 FINDINGS_M4.md 已作废留档。"
        "现行基准已再经 2026-09-30 重锚定。",
    "semantic_signal/FINDINGS_M8_V4.md":
        "v4（2026-09-01 修正）重跑版✅（CHANGELOG 2026-09-04，纯 numpy 真值/干扰互换）；"
        "对应旧口径版 FINDINGS_M8.md 已作废留档。",
    "semantic_signal/FINDINGS_P28P36_RECALL_VERIFY.md":
        "v4（2026-09-01 修正）+ 2026-09-04 rerun 批复核✅（同日基于 v4）。",
    # ---- F 类：v3 时代（4） ----
    "semantic_signal/FINDINGS_M1.md":
        "原版基于 v3（2026-09-01 成文，同日 GT 大修正）；v4 后由 M1-v2 复审覆盖"
        "（14 案例本模型直看帧，TODO 2026-09-06(XII)），引用以复审为准。",
    "semantic_signal/FINDINGS_M6.md":
        "原版基于 v3，数字已作废——v4 重算见同目录 FINDINGS_M6_REVISED.md（RESCUE 1/41→0/39，方向彻底关闭）。",
    "semantic_signal/FINDINGS_P3.md":
        "v3（p 系列真值窗，2026-09-01 成文）；「序列上下文证伪」方向由 09-05 时序单调性探针独立同向维持，"
        "数字口径旧（早于 v4/test1-3 与 09-30 重锚定）。",
    "semantic_signal/RESEARCH_PROPOSAL_CONTEXT_RERANK.md":
        "提案时代口径 v3（2026-09-01 成文）；执行结果见 CHANGELOG 2026-09-06(VII/X/XIV)——patch v2 已落地翻案。",
    # ---- G 类：现行 139 条（8，推断级） ----
    "semantic_signal/FINDINGS_C_ITEM_8FPS.md":
        D139 + "；文内 112/118/125/127 属当时基线，" + STALE + INFER,
    "semantic_signal/FINDINGS_SUBSHOT_QUERY.md":
        D139 + "；另见 §八登记行：蒙太奇子镜头线真值另有 ground_truth_corrected.json（7 段视觉确认）来源。" + INFER,
    "semantic_signal/FINDINGS_TEMPORAL_MONOTONICITY.md": D139 + "。" + INFER,
    "semantic_signal/FINDINGS_TIMELINE_PRIOR.md": D139 + "。" + INFER,
    "semantic_signal/FINDINGS_LENIENT_V4_METRICS.md":
        "ground_truth_v4.json（脚本直读，✅ 确证非推断；2026-09-04 评测口径澄清）。",
    "semantic_signal/RESEARCH_PROPOSAL_PATCH_RECALL_V2.md": D139 + "。" + INFER,
    "semantic_signal/RESEARCH_PROPOSAL_SECOND_SIGNAL.md": D139 + "。" + INFER,
    "semantic_signal/RESEARCH_PROPOSAL_TRAINING.md": D139 + "。" + INFER,
    # ---- H 类：读文判定（3） ----
    "montage_research/FINDINGS.md":
        "ground_truth_corrected.json（v2 代际，早于 v4/test1-3 正式化）；本篇为查询轴聚类原型验证，"
        "结论由 2026-09-04/05 蒙太奇子镜头查询线接续（FINDINGS_SUBSHOT_QUERY.md），数字口径旧。",
    "scene_recall/FINDINGS.md":
        "v3（41 条镜头级，2026-08-28 定案；早于 v4/test1-3 与 09-30 重锚定）。"
        "场景扩池层已产品化默认开（scene_recall_enabled），现行基线见 .agent/STATE.md。",
    "second_signal/FINDINGS.md":
        "v3（41 条 + 4 负例，2026-08-28）；Phase 24-0 预研，结论由 2026-09-05 第二信号重启线"
        "（事件身份 P1/P2 等）覆盖，本篇数字未见 v4 重跑。",
    # ---- 提案后新增（12，续29~35，代际由档案直接确证） ----
    "competitor_cutmatch/FINDINGS_CAPABILITY_MAP_20260928.md":
        "不适用——竞品 103 叶子模块能力对照 + 我方实现映射；文内引用我方基线 117/139 为当时口径，" + STALE,
    "competitor_cutmatch/FINDINGS_COMBO_CALIBER_ALL_CASES.md":
        "重锚定前 GT（2026-09-29 成文，基线 127/截等长 105 时代）；⚠️ 本篇提出的 14 条口袋测试集已按"
        "重锚定后口径重推（8 条真口袋，probe_pocket_retest_gt130），引用口袋集须用新版。",
    "competitor_cutmatch/FINDINGS_DEGRADATION_LEGS_AND_DUP_CLAIM_WARN.md":
        "重锚定前 GT（2026-09-29 成文，严格 127 时代双臂）；结论（拒识门维持默认关 + LOC-2002 安全形态默认开）"
        "不依赖具体代际，数字引用须注明。",
    "competitor_cutmatch/FINDINGS_E3_ECC_PROBE.md":
        "判据探针口径（44 例已裁锚点 36 真/5 假 + ECC 结构相关腿），不套 GT 三指标；"
        "锚点属重锚定前代际，负结果（不进 runtime、通道关闭）与代际无关。",
    "competitor_cutmatch/FINDINGS_ORDERED_SEARCH_M0.md":
        "重锚定前 GT（2026-09-29 成文，截等长 105 基线时代）；判负结论（不进 runtime、不留通道）与代际无关，"
        "数字引用须注明口径。",
    "competitor_cutmatch/FINDINGS_RETRO_MULTIMODAL_REVIEW_20260930.md":
        "历史判负结论的跨代际补复核（续27 夹具缺陷更正等）；更正结论与代际无关。",
    "competitor_cutmatch/FINDINGS_SOURCE_MERGE_PORT.md":
        "现行（2mkv GT，合并片定位对照 36/39 逐 ID 零翻转验收）；mkvmerge 路由/字幕轨口径差异与 GT 无关。",
    "competitor_cutmatch/FINDINGS_VIDEO_RENDER_PORT.md":
        "不适用——成片渲染能力移植，验收 = 帧数严格校验 + 帧距 + 逐张读图，无 GT 判定。",
    "semantic_signal/FINDINGS_GT_TICKET_ADJUDICATION_20260930.md":
        "本文件即 2026-09-30 GT 重锚定的裁决记录（18 条工单逐帧裁决 → 12 行重锚定 + 2 同源注释，"
        "现行基准的由来），不适用「按某版 GT 重验」。",
    "semantic_signal/FINDINGS_INSCENE_REFINE_PROBE_20260930.md":
        D139.split("；")[0] + "（重锚定后 130/107 基线时代执行，(E) 影响面统计 23 行可救池同口径）。",
    "semantic_signal/FINDINGS_SPLIT_PATCH_PROD_ACCEPT_20260930.md":
        "现行（重锚定后基线：严格 130→132 · 导出实得 107→119，生产路径双臂验收）。",
    "semantic_signal/FINDINGS_SPLIT_PATCH_GRAB_PERF_20261001.md":
        "不适用——纯耗时归因 + 零语义逐位一致验证（整条 locate 全字段一致），不改任何判定数字。",
}

TABLE_ROWS = {
    # 简表：文档 → 表格两列（基于哪版 GT / 状态）
    "competitor_cutmatch/FINDINGS_BOUNDARY_REFINER_COMPARISON.md":
        ("不适用（44 例人工盲判）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_CAPABILITY_GAP.md":
        ("不适用（能力差距分析）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_CUTMATCH_CONSTANTS_ADOPTION.md":
        ("不适用；基线引用 117 已过时", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_CUTMATCH_POSTPROCESS_REPLAY.md":
        ("不适用（几何复现 24/24）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_DOCSTRING_BREAKTHROUGH.md":
        ("不适用（竞品数据）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_COMPETITOR_FULL_SWEEP.md":
        ("不适用（竞品数据）", "✅ 2026-10-01 已加头"),
    "gt_review/FINDINGS_TEST1-3_GT_BUILD.md":
        ("本体即 GT 建设记录（09-02 定案）", "✅ 2026-10-01 已加头（注明 09-30 重锚定）"),
    "competitor_cutmatch/FINDINGS_COMBO_FIVE_RING_TEST1.md":
        ("verified-139（推断级）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_P0_DENSE_START_TEST1.md":
        ("verified-139；基线 117 已过时", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_FAST_GLOBAL_REPRO.md":
        ("verified-139；117/119 双臂并存", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_PROXY_B_STAGE_REVIEW.md":
        ("不适用（几何+盲判）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_PROXY_D_STAGE_REVIEW.md":
        ("verified-139；基线引用已过时", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_QUERY_UNIT_SWAP.md":
        ("verified-139；基线引用已过时", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_PATCH_FUSION_PROBE.md":
        ("verified-139（真值窗 v4/test3）", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_M4_V4.md": ("v4 重跑", "✅ 已在表（E 类）"),
    "semantic_signal/FINDINGS_M8_V4.md": ("v4 重跑", "✅ 已在表（E 类）"),
    "semantic_signal/FINDINGS_P28P36_RECALL_VERIFY.md": ("v4 + 09-04 rerun 批", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_M1.md": ("v3；M1-v2 复审覆盖", "✅ 2026-10-01 已加头（指向复审）"),
    "semantic_signal/FINDINGS_M6.md": ("v3；数字作废", "✅ 2026-10-01 已加头（指向 M6_REVISED）"),
    "semantic_signal/FINDINGS_P3.md": ("v3（方向维持）", "✅ 2026-10-01 已加头"),
    "semantic_signal/RESEARCH_PROPOSAL_CONTEXT_RERANK.md":
        ("v3 提案口径；已由 patch v2 落地翻案", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_C_ITEM_8FPS.md": ("verified-139；基线已过时", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_SUBSHOT_QUERY.md": ("verified-139 + corrected.json 窗", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_TEMPORAL_MONOTONICITY.md": ("verified-139（推断级）", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_TIMELINE_PRIOR.md": ("verified-139（推断级）", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_LENIENT_V4_METRICS.md": ("v4（脚本直读）", "✅ 2026-10-01 已加头"),
    "semantic_signal/RESEARCH_PROPOSAL_PATCH_RECALL_V2.md": ("verified-139（推断级）", "✅ 2026-10-01 已加头"),
    "semantic_signal/RESEARCH_PROPOSAL_SECOND_SIGNAL.md": ("verified-139（推断级）", "✅ 2026-10-01 已加头"),
    "semantic_signal/RESEARCH_PROPOSAL_TRAINING.md": ("verified-139（推断级）", "✅ 2026-10-01 已加头"),
    "montage_research/FINDINGS.md":
        ("ground_truth_corrected.json（v2 代际）", "✅ 2026-10-01 读文判定并加头"),
    "scene_recall/FINDINGS.md": ("v3（41 条，08-30 成文）", "✅ 2026-10-01 读文判定并加头"),
    "second_signal/FINDINGS.md": ("v3（41+4，08-30 成文）", "✅ 2026-10-01 读文判定并加头"),
    "competitor_cutmatch/FINDINGS_CAPABILITY_MAP_20260928.md":
        ("不适用；基线引用 117 已过时", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_COMBO_CALIBER_ALL_CASES.md":
        ("重锚定前（127/105 时代）", "✅ 2026-10-01 已加头（口袋集指向新版）"),
    "competitor_cutmatch/FINDINGS_DEGRADATION_LEGS_AND_DUP_CLAIM_WARN.md":
        ("重锚定前（127 时代双臂）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_E3_ECC_PROBE.md": ("判据探针口径", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_ORDERED_SEARCH_M0.md": ("重锚定前（105 时代）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_RETRO_MULTIMODAL_REVIEW_20260930.md":
        ("跨代际补复核", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_SOURCE_MERGE_PORT.md": ("现行（2mkv GT）", "✅ 2026-10-01 已加头"),
    "competitor_cutmatch/FINDINGS_VIDEO_RENDER_PORT.md": ("不适用（渲染验收）", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_GT_TICKET_ADJUDICATION_20260930.md":
        ("本体即 09-30 重锚定记录", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_INSCENE_REFINE_PROBE_20260930.md":
        ("现行（重锚定后 130/107 时代）", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_SPLIT_PATCH_PROD_ACCEPT_20260930.md":
        ("现行（130→132 双臂验收）", "✅ 2026-10-01 已加头"),
    "semantic_signal/FINDINGS_SPLIT_PATCH_GRAB_PERF_20261001.md":
        ("不适用（零语义性能归因）", "✅ 2026-10-01 已加头"),
}


def insert_header(rel: str, text: str) -> str:
    """返回 'written' / 'skipped:<原因>'。"""
    p = UC / rel
    if not p.is_file():
        return f"skipped:missing {rel}"
    raw = p.read_text(encoding="utf-8")
    if "GT 版本" in raw[:600] or "GT 口径" in raw[:600]:
        return f"skipped:already {rel}"
    lines = raw.split("\n")
    head = lines[0].rstrip("\r")
    rest = "\n".join(lines[1:]).lstrip("\n")
    new = f"{head}\n\n> **GT 版本**（2026-10-01 补登记，批量执行）：{text}\n\n{rest}"
    p.write_text(new, encoding="utf-8", newline="\n")
    return f"written {rel}"


def append_registry() -> str:
    audit = UC / "semantic_signal" / "FINDINGS_GT_CONTAMINATION_AUDIT.md"
    raw = audit.read_text(encoding="utf-8")
    if "2026-10-01 批量补登记" in raw:
        return "skipped:registry already updated"
    rows = ["",
            "**2026-10-01 批量补登记（44 份，用户拍板；依据 GT_VERSION_REGISTER_PROPOSAL_20260928.md "
            "+ 续29~35 新增 12 份）**：", ""]
    for rel, (gt, st) in TABLE_ROWS.items():
        rows.append(f"| `{rel}` | {gt} | {st} |")
    rows.append("")
    marker = "**登记规则**"
    idx = raw.index(marker)
    new = raw[:idx] + "\n".join(rows) + "\n\n" + raw[idx:]
    audit.write_text(new, encoding="utf-8", newline="\n")
    return "registry updated"


def main() -> int:
    results = [insert_header(rel, h) for rel, h in HEADERS.items()]
    written = sum(1 for r in results if r.startswith("written"))
    print(append_registry())
    print(f"headers written={written} skipped={len(results) - written} total={len(results)}")
    for r in results:
        if not r.startswith("written"):
            print(" ", r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
