# GT 版本登记表 · 剩余 32 份文档 **推断级提案**（2026-09-28）

> **状态：待用户确认，未生效。** 本表不是「已登记」，而是把 `mvp/scripts/gt_impact_scan.py --check`
> 报出的 32 份「正文无 GT 版本标注」文档，按**可核证据**归类，供你逐条或整批拍板后再写入
> `FINDINGS_GT_CONTAMINATION_AUDIT.md` §八 登记表与各文档头。
> 抽头方式与 2026-09-26 续9「7 份剩余文档逐条核销」同源（头部标注 + 登记表行）。

## 一、方法与其局限（先说清，避免把推断当结论）

**证据来源**（三档可信度）：

| 档 | 含义 | 依据 |
|---|---|---|
| ✅ 有据 | 档案明确记载该结论已用修正 GT 重跑过 | `CHANGELOG.md` 2026-09-04 / 2026-09-25(续) 的 v4 重跑条目 |
| 🔶 推断 | 按文内成文日期落在 GT 时点之前/之后判定 | 文内 `2026-xx-xx`（**不用文件 mtime**——`semantic_signal/*` 有整批 mtime=2026-09-06 的批量 touch 痕迹，mtime 不可作日期证据） |
| ❓ 未知 | 文内无日期、或正文引用的 GT 名不在现行文件集内 | 需执行者读文确认 |

**GT 时点**（用于推定的锚）：v1 证伪留档 → `ground_truth_v3.json` 2026-08-28 → **v4 重建 2026-09-01**
（2.mkv 39 正/4 负）→ **test1-3 正式化 2026-09-02**（合计 139 条 verified）→ t2r07c GT 修正 2026-09-06。

> ⚠️ 本表**不改变**任何技术结论。它只回答「这份文档的结论当时是拿哪版 GT 量的」，
> 这正是本项目已因缺失而亏过三次的信息（审计原文）。

## 二、分类提案

### A. 竞品对标线 · 不使用我方 GT（6 份，建议登记为「不适用」）

成文 2026-09-26/27，评估对象是竞品常量/切分产物，不与我方 GT 做召回判定。

| 文档 | 成文 | 内容判据 | 建议头 |
|---|---|---|---|
| `competitor_cutmatch/FINDINGS_BOUNDARY_REFINER_COMPARISON.md` | 09-26 | 227 条现行边界 + 盲判图裁决，不套 GT | GT 口径：不适用（竞品判据对照，真值=44 例人工盲判） |
| `competitor_cutmatch/FINDINGS_CAPABILITY_GAP.md` | 09-26 | 能力差距分析（组合链），无 GT 判定 | 同上 |
| `competitor_cutmatch/FINDINGS_CUTMATCH_CONSTANTS_ADOPTION.md` | 09-26 | 竞品常量绑定核对（正文引 117/139 作我方基线参照） | GT 口径：不适用；**基线引用已过时**（见 D） |
| `competitor_cutmatch/FINDINGS_CUTMATCH_POSTPROCESS_REPLAY.md` | 09-26 | 竞品 probs 后处理重放 24/24 | GT 口径：不适用（几何/帧号复现） |
| `competitor_cutmatch/FINDINGS_DOCSTRING_BREAKTHROUGH.md` | 09-26 | 竞品 docstring 语义挖掘 | GT 口径：不适用（纯竞品数据） |
| `competitor_cutmatch/FINDINGS_COMPETITOR_FULL_SWEEP.md` | 09-27 | 282 blob 全量扫穿 | 同上 |

### B. GT 建设过程文档（1 份，建议登记为「本体即 GT 记录」）

| 文档 | 成文 | 建议头 |
|---|---|---|
| `gt_review/FINDINGS_TEST1-3_GT_BUILD.md` | 09-02 | GT 口径：本文件即 test1-3 GT 建设记录（draft→正式版 09-02 定案，139 条 verified 的由来），不适用「按某版 GT 重验」 |

### C. 竞品对标线 · 使用我方 GT 评估（7 份，建议登记为「现行 139 条 verified」）

成文 09-26/27，均晚于 v4(09-01) 与 test1-3(09-02)，🔶 推断 = 现行 139 条口径。

| 文档 | 成文 | 文内基线数字 | 建议头 |
|---|---|---|---|
| `FINDINGS_COMBO_FIVE_RING_TEST1.md` | 09-26 | 34/43 · 22/43 · 10/43 | GT：现行 139 条 verified（test1 43 条）🔶 |
| `FINDINGS_P0_DENSE_START_TEST1.md` | 09-26 | 117/139 | GT：现行 139 条 🔶；基线引用已过时（见 D） |
| `FINDINGS_FAST_GLOBAL_REPRO.md` | 09-27 | 117/139 与 119/139 并存 | GT：现行 139 条 🔶；本份已含 vote_prior 后 119，引用时须注明臂 |
| `FINDINGS_PROXY_B_STAGE_REVIEW.md` | 09-26 | — （几何对照为主） | GT：不适用（几何+盲判）；文内 v4 提及为历史引用 |
| `FINDINGS_PROXY_D_STAGE_REVIEW.md` | 09-26 | 117/121/124/128/139 | GT：现行 139 条 🔶；基线引用已过时 |
| `FINDINGS_QUERY_UNIT_SWAP.md` | 09-26 | 114→104/139 | 同上 |
| `FINDINGS_PATCH_FUSION_PROBE.md` | 09-26 | — （rank/margin 口径） | GT：现行 139 条 🔶（探针用真值窗取自 v4/test3） |

### D. 跨类提醒：这 7 份里的「基线 117/139」已不是现役数字

2026-09-27 续11 偏移投票先验使生产基线 **117 → 119/139**（默认关，待 UI 验收后翻默认开）。
上述文档引用 117 处属当时事实，**不得**在后续对话中被当作「现役基线」——建议在头注补一句
「本文基线 117/139 = vote_prior 移植前现役口径，见 `.agent/STATE.md` 2026-09-27(续11)」。

### E. 已有 v4 重跑证据（3 份，✅ 直接登记）

| 文档 | 重跑证据 |
|---|---|
| `semantic_signal/FINDINGS_M4_V4.md` | CHANGELOG 2026-09-04：M4 仅 p26 用 v4 真值重跑，旧「12→43 恶化」判定为错误 GT 假象 |
| `semantic_signal/FINDINGS_M8_V4.md` | CHANGELOG 2026-09-04：M8 纯 numpy v4 重跑（真值/干扰互换） |
| `semantic_signal/FINDINGS_P28P36_RECALL_VERIFY.md` | 2026-09-04 同日基于 v4 + rerun 批复核 |

建议头：`GT 口径：v4（2026-09-01 修正）重跑版；对应旧口径版=<FINDINGS_M4.md/M8.md>，已作废留档`

### F. 成文于 v3 时代、未见 v4 重跑记录（4 份，❓ 需你确认是否加作废警示）

| 文档 | 成文 | 现状判断 | 建议 |
|---|---|---|---|
| `semantic_signal/FINDINGS_M1.md` | 09-01 | 多模态判定探针；同日 GT 大修正发生。09-06 有「M1-v2 本模型直看帧重跑（14 案例）」记录 | 加头：原版基于 v3；v4 后由 M1-v2 复审覆盖（见 TODO 2026-09-06(XII)）✅ |
| `semantic_signal/FINDINGS_M6.md` | 09-01 | **已有 v4 重算** `FINDINGS_M6_REVISED.md`（RESCUE 1/41→0/39） | 加头：原版数字作废，指向 M6_REVISED ✅ |
| `semantic_signal/FINDINGS_P3.md` | 09-01 | 序列上下文证伪，用的 p 系列真值窗 = v3 | 🔶 加头：基于 v3；「证伪」方向维持（09-05 单调性探针独立同向） |
| `semantic_signal/RESEARCH_PROPOSAL_CONTEXT_RERANK.md` | 09-01 | 提案文档；后续 09-06(VII/X) patch v2 已实际落地并翻案 | 🔶 加头：提案时代口径 v3，执行结果见 CHANGELOG 09-06(X/XIV) |

### G. 成文于 test1-3 正式化之后（8 份，🔶 推断=现行 139 条）

`FINDINGS_C_ITEM_8FPS.md`(09-05) · `FINDINGS_SUBSHOT_QUERY.md`(09-04) ·
`FINDINGS_TEMPORAL_MONOTONICITY.md`(09-05) · `FINDINGS_TIMELINE_PRIOR.md`(09-02) ·
`FINDINGS_LENIENT_V4_METRICS.md`(09-04，正文已引 ground_truth_v4.json) ·
`RESEARCH_PROPOSAL_PATCH_RECALL_V2.md`(09-06) · `RESEARCH_PROPOSAL_SECOND_SIGNAL.md`(09-05) ·
`RESEARCH_PROPOSAL_TRAINING.md`(09-06)

建议头统一：`GT 口径：现行 139 条 verified（v4 + test1-3，2026-09-02 定案）；t2r07c 修正见 2026-09-06(XIII)` 🔶
（其中 `FINDINGS_C_ITEM_8FPS.md` 文内 112/118/125/127 属当时基线，同 D 处理）

### H. 无法判定（3 份，❓ 需读文，不建议自动加头）

| 文档 | 障碍 |
|---|---|
| `montage_research/FINDINGS.md` | 文内无日期，且正文引用 `ground_truth_corrected.json`——该文件名不在现行 GT 集（8 个已登记文件）内，需确认它指代哪版 |
| `scene_recall/FINDINGS.md` | 首日期 08-30（早于 v4），但正文未写 GT 文件名，重跑与否无档案记载 |
| `second_signal/FINDINGS.md` | 首日期 08-30；Phase 24-0/24-2 预研，STATE 记录其结论后续由 09-05 事件扩池线接续，但**原探针数字未见 v4 重跑** |

## 三、建议的落地方式（等你选）

1. **整批写入**（快）：A/B/C/E/F/G 共 29 份按上表加头，H 类 3 份留 ❓ 不加头（继续由扫描脚本告警）。
2. **只写有据项**（保守）：仅 E + F 中 M1/M6（✅ 档，5 份）加头，其余留待逐份读文确认。
3. **先补 D 的基线过时提醒**（最小）：只在引用 117/139 的 7 份加「基线已过时」一句，其余不动。

无论选哪种，都不改正文技术结论；H 类若需要我可以逐份读文后单独给结论（成本约 3 轮工具调用）。
