# Ambiguity Detection 原型 FINDINGS —— 现有置信信号无法分离「正确 HIGH」与「错配 HIGH」

> 日期:2026-09-01 GT 重建专会话 | 性质:**原型实验(零 runtime 改动, 重跑 29 段提取内部信号)**
> 目标: 验证产品层假设「用现有 confidence 信号(margin/similar_band/multiple_similar_candidates)把 AMBIGUOUS 转人工」在当前特征/检索架构下是否可行。
> 方法: 对 user_results.json 全部 29 段重跑 `EvidenceLocalizer`(产品主定位器), 提取 multi-evidence 内部信号
> (mode / n_strong_clusters / qcov / dispersion / primary-secondary best_sim / margin), 对照 v4 GT 判定命中。
> 数据: `work/amb_prototype_signals.json` | 脚本: `work/_amb_proto_run.py`

## 一、核心发现: HIGH 档精度仅 5/13 (38%), 且「错配 HIGH」与「正确 HIGH」信号完全同构

29 段中 **13 段 HIGH**。对照 v4 GT: 严格命中 5 段, 未命中 8 段(含边界偏差/修正前移/真漏)。
重跑提取的内部 multi-evidence 信号(下表), **正确与错配没有任何可分维度**:

| 维度 | 正确 HIGH (5) | 错配 HIGH (8) | 可分? |
|---|---|---|---|
| mode | 全 clean(除 p40 montage) | 多 clean, 少数 montage | ❌ 重叠 |
| n_strong_clusters | 1-3 | 1-3 | ❌ 重叠 |
| qcov | 0.75-1.0 | 0.8-1.0 | ❌ 重叠 |
| dispersion | 0(clean) | 0(clean) | ❌ 重叠 |
| primary best_sim | 0.497-0.684 | 0.49-0.69 | ❌ **完全重叠** |
| secondary best_sim | None(clean) | None(clean) | ❌ 同构 |
| margin | 1.0(secondary=None 饱和) | 1.0(饱和) | ❌ 同构 |

**关键机制**: 这些 HIGH 段几乎全是 **clean(单证据簇)**, `EvidenceResult.secondary=None` →
`_evidence_margin` 返回 1.0(饱和) → `low_candidate_margin` 与 `multiple_similar_candidates`
两个 flag 都要求 `n_strong_clusters >= 2`(代码 `_evidence_flags`), **clean 段结构上不触发任何降险 flag**。
因此: 无论 clean 段定位对错, 置信引擎都给出 HIGH + 相同的 reasons(single_evidence_region / high_query_coverage / stable_temporal_localization)。

## 二、为什么「检索池里没有第二个强簇」才是根因

- 错配 HIGH 的 primary best_sim(0.49-0.69)与正确 HIGH(0.497-0.684)落在同一区间——**不是 sim 高低问题**;
- 而是检索架构下, 兄弟机位/同质场景的真值与干扰在特征空间**几乎同分**, 检索 top 常只浮出「错的那一个」
  作为唯一强簇(secondary=None)→ 引擎内部**无分歧信号**可捕获;
- 这与 M1-M8 结论完全一致(兄弟机位 CLS 混叠、patch 仅 +1/41、VLM 反向)——**AMBIGUOUS 需要的「内部分歧」
  在该特征架构下不存在**, 除非外部引入独立信号(多模态已证伪、OCR 字牌单例)。

## 三、对产品层(校准阶段)的诚实结论

1. **「用 margin/similar_band/multiple_similar_candidates 识别 AMBIGUOUS」对 clean 单证据段不成立**——
   单证据段 secondary 不存在, margin 恒饱和, 相关 flag 不触发, 无论对错都 HIGH。
2. **HIGH 错配无法被任何现有内部信号降档/标记**——这与 2026-08-27 研究证「纯置信度标定只能降档自信答错,
   修不了定位内容对不上」的既有结论**双向闭合**。
3. **AMBIGUOUS 检测的现实选项**:
   - **A. 保守化 HIGH 门槛**(把 best_sim<某阈值的 HIGH 降 MEDIUM/提示): 可降低 38%→更高的 precision,
     但会误伤 p26/p41(正确但 sim 0.51-0.55)型——**需要标定, 收益待测**;
   - **B. 外部分歧信号**(唯一可行方向): 字幕/音频/镜头图, 但 M1-M3/M8 已证伪或单例 → 需新证据才立项;
   - **C. 接受为已知局限**: HIGH 档 38% precision 在「兄弟机位/同质场景」上无法内部分歧检测,
     产品通过「结果页手动替换 + 提示相似候选」兜底(已有 UI 能力)。
4. **校准阶段重定位**: 既然 AMBIGUOUS 无内部信号可用, 校准的价值 = **保守化 HIGH 门槛标定**
   (用 v4 数据把「自信错答」降 MEDIUM/LOW, 提高 HIGH precision), 而非「正确识别 AMBIGUOUS」。

## 四、建议

- **短期(校准)**: 用 v4 的 29 段做 HIGH 门槛标定实验——扫描 best_sim/score 阈值, 找到「precision↑ / 误伤最少」的平衡点;
- **不立项** AMBIGUOUS 检测(无内部信号, 外部已证伪);
- **产品兜底**: HIGH 仍可直出, 但配「相似候选/手动替换」提示(UI 已有), 明确这是已知边界。

## 相关产物
- `work/amb_prototype_signals.json`(29 段内部信号) + `work/_amb_proto_run.py`(脚本)
- 前置: `V4_MISS_RECHECK.md`(8 条未命中复查) + CONFIDENCE_DESIGN.md + 2026-08-27 置信标定研究
