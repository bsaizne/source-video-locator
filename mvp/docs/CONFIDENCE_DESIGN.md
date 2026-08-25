# Confidence Design — 工程化置信度（Source Video Locator）

> 阶段：MVP Design（Stage 0）。设计不依赖 GT、不把 cosine 当概率的**工程化 Confidence**：输入是检索/定位层真实信号，输出 HIGH/MEDIUM/LOW + score + reasons。**阈值/权重需在 H1 用真实数据标定**（本文给出初始公式与降级规则 + 标定计划）。禁止把 `score` 展示成具统计意义的模型概率。

## 1. 为什么不能只用 cosine（产品第一原则）

实测：**错误场景的 CLS similarity 可能高于真正来源**。
- s2：错误候选（暗室内男子）sim 0.726 > 正确区 0.558。
- s0/s1：正确区深 rank6/5，被暗色相似场景压过。
- 因此"相似度高"≠"定位可信"。Confidence 必须综合**时序结构与定位稳定性**等多信号，而非单一外观相似度。

## 2. 可用信号（运行时无 GT，全部来自检索/定位层）

| 信号 | 来源 | 定义/说明 |
|---|---|---|
| `rank` | ranking | n_reps rerank 后候选排名（1=最佳） |
| `n_reps` | ranking | 候选窗覆盖的 distinct edited 帧数（查询时序覆盖度）。连续镜头段更高 |
| `score` | ranking | `mean*sqrt(hit)*(0.5+0.5*cons)*n_reps^alpha`（alpha=0.5，冻结） |
| `margin` | ranking | `score_best - score_2nd`。margin 大→可信；margin 小→竞争 |
| `consistency` | clustering | 候选窗内 query 命中一致性（=cons） |
| `coverage` | retrieval | `best_cover` = 候选窗对查询内容的覆盖出（rank 无关） |
| `mean_sim`/`peak_sim` | retrieval | 候选窗窗口内相似度均值/峰值 |
| `finloc_stability` | localization | 精定位轨迹：`run_len_s`、是否落在候选窗内、是否退化成点、per-orig coverage 是否单峰 vs 多岛 |
| `montage_suspicion` | localization | 多岛 per-orig coverage、query 覆盖分散、margin 低、窗口异常（≥60s 上限命中） |
| `source_window_anomaly` | clustering | width 异常大/异常小、窗口超出可解释范围 |

> 注意：`start_err/end_err/IoU` **运行时不可用**（依赖 GT），Confidence 不得使用它们。

## 3. 决策阶梯（flag → min-rule → 档位）

分两级：**硬 flag（直接定 LOW）** 与 **软信号加权（定 MEDIUM/HIGH）**。

### 3.1 硬 flag（命中任一 → 至少 LOW，并计入 reasons）
- `montage_flag`：多岛 coverage（≥2 个显著高匹配 run 且中间 gap 需桥接，如 s4 的 [1376,1382]+[1390,1396]）
- `low_margin`：`score_best - score_2nd` 低于阈值（候选相互竞争）
- `multiple_similar_candidates`：>N 个候选 score 落在最佳 score 的 X% 内
- `source_window_anomaly`：width 触及 60s 上限、或 width 小到不可解析
- `finloc_unstable`：longest_run 退化（run_len 过短 / 轨迹点 / 越过候选窗）
- `query_coverage_dispersed`：n_reps 低且 qcov 分散（query 被多个相似场景吸走，如 s1 蒙太奇食物特写 beat 不在正确区）

### 3.2 软信号（无硬 flag 时，用加权合成分选档）
初始工程分（建议起始权重，待标定）：
```
confidence_score = w1*rank_norm + w2*margin_norm + w3*n_reps_norm
                   + w4*coverage_norm + w5*consistency_norm + w6*finloc_stability_norm
```
- `rank_norm`：rank=1 → 1.0；rank>1 递减。
- `margin_norm`：margin 归一化到 [0,1]（用候选集内 min-max 或固定锚）。
- `n_reps_norm` / `coverage_norm` / `consistency_norm` / `finloc_stability_norm`：各自归一化。
- 初值 `w`（占位，需标定）：例如 `[0.30, 0.25, 0.15, 0.15, 0.08, 0.07]`。

**档位映射**（示例阈值，待标定）：
- `HIGH`：score ≥ 0.75 且无硬 flag
- `MEDIUM`：score ∈ [0.55, 0.75) 且无硬 flag
- `LOW`：score < 0.55 **或命中任一硬 flag**

### 3.3 输出
```json
{ "confidence": "HIGH", "score": 0.87,
  "reasons": ["rank1","high_query_coverage","stable_temporal_localization","large_candidate_margin"] }
{ "confidence": "LOW", "score": 0.42,
  "reasons": ["multiple_similar_candidates","low_candidate_margin","possible_montage"] }
```

## 4. Reasons 词汇表（机器可读，UI 翻译成人话）

| reason key | 文本 | 说明 |
|---|---|---|
| rank1 / rankN | "最优候选/候选 #N" | 候选秩 |
| high_query_coverage | "查询覆盖充分" | n_reps 高 |
| low_query_coverage | "查询覆盖不足" | n_reps 低 |
| stable_temporal_localization | "时间定位稳定" | finloc run 稳健 |
| large_candidate_margin | "与第二候选差距大" | margin 大 |
| low_candidate_margin | "与第二候选差距小" | margin 小 |
| multiple_similar_candidates | "存在多个相似候选" | 竞争 |
| possible_montage | "疑似多镜头蒙太奇" | montage_flag |
| dark_scene_semantic_confusion | "暗色内容语义可能混淆" | DINOv2 CLS 已知局限（s2/s4 类）→ 降置信 |
| source_window_anomaly | "来源窗口异常" | 超 60s/过窄 |
| finloc_unstable | "精定位不稳定" | 轨迹退化 |
| manual_override | "人工修正" | 来源=manual |

## 5. 暗内容语义混淆的显式降险

DINOv2 CLS 对"暗色+人物+军事纹理"判别有限（Phase15 C）。因此当候选含该类内容特征（可通过 mean_sim 偏高但 coverage/时序结构异常、或窗口命中已知困难模式）时，**显式降低置信**并加入 reason `dark_scene_semantic_confusion`。目标：避免"拿一个看似高置信、实际错的结果"。

## 6. 标定计划（H1 必做，非虚构）

1. **输入**：real 7 段（corrected GT）+ 更广的标注集（连续镜头若干 + montage 若干，人工标注真值区间与"是否可自动确定"）。
2. **target**：让 HIGH 段的边界误差 ≤ 预期（用 GT 核），LOW 段确实难自动；同时**不打爆**连续镜头的档位。
3. **对照**：先 with-GT 验证 confidence 分排序与 GT 一致性（研发期），再 no-GT 产出。
4. **口径**：记录每档 precision（该档中对的比例）与 recall（该档覆盖率）。目标：HIGH 高 precision（宁缺勿滥）、LOW 高 recall of hard cases（该降的降）。

**诚实声明**：上述 `w` 与阈值只是结构占位，**不代表已标定**；上线前必须以实际结果校准并记录，不得凭感觉填数。

## 7. 禁止事项

- 禁止把 `score`/`confidence` 展示为百分比概率、或具统计显著性误读。
- 禁止仅用 `mean_sim`/`cosine` 直接作 confidence。
- 禁止在 montage/多岛情形输出"精确单边界"并标 HIGH。
