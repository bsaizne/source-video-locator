# FINDINGS — 对齐链（单调 DP / DTW）用作候选排序信号（A2 探针）

> **GT 版本**：`ground_truth_v4.json` + `ground_truth_test1|2|3.json`（138 条正例进入统计；基于 v4 口径）。
> **日期**：2026-09-25　**性质**：竞品对标探针（研究侧）　**runtime 改动**：零

## 0. 结论

把「序列对齐得分」用于**跨候选/跨实例排序**（我方此前只用于候选窗内 moment 精修）：

- **rank 层面：无增量且整体更差** —— 138 案例中 **改善 18 / 恶化 37 / 持平 83**，平均真值 rank **2.43 → 2.80**；
- **margin 层面：有微弱信号** —— 平均 margin **−0.0495 → −0.0407**；72 个 base 错配（margin<0）案例中 **16 个（22%）被 DTW 纠正**；
- **核心失败族 p08（兄弟机位）两者皆失败** —— 真值 rank 3（两法相同），margin base −0.0482 → dtw_mean **−0.1062（更负）**。

→ **裁决：不把对齐分引入排序层**。我方现有位置（对齐只做候选窗内 moment 精修，见
`EvidenceLocalizer._align_global_moments`）是更稳妥的用法；竞品把 dtw 放进 `fast_timeline` 链路
**不构成我方能力缺口**（本探针口径下反而更差）。

## 1. 竞品口径 vs 我方现状（事实核查，修正前提）

竞品模块图（137 模块）中与对齐相关的有：`matching.alignment.{dtw,timeline,continuity,geometry,offset_refiner}` +
`fast_timeline.{dense_alignment,ordered_search,path_selection,local_refiner}`。

但**我方已有等价能力**：`engine/localization/seq_align.py` 即**单调 DP 对齐**
（`_dp_path`：max Σsim 的单调路径 + `sim_thresh`/`diag_penalty`/`step_penalty`，REUSE research `src/experiments/ta.py`），
**且已接入 runtime**（`EvidenceLocalizer._align_global_moments`：候选窗 ±`seq_pad_s` → 对齐 → 连续段 → moment 收窄 → 双门控）。

⇒ 双方的差异**不在「有没有 DTW」**，而在**「对齐得分是否参与候选/实例排序」**。本探针只隔离这一个变量。

## 2. 方法（`mvp/scripts/research_dtw_rank.py`）

对每条 GT 正例（编辑段 `[ed0,ed1]`，真值窗 `[og0,og1]`）：

1. 编辑段 @8 fps（= `config.edit_fps`）抽帧 → DINOv2 CLS 384d（DirectML）；
2. 原片索引（1 fps，生产 `data/index/<stem>__<hash>.idx`）features/times；
3. 候选锚点 = 编辑段逐帧 best-match 帧时间（1 s 去重）∪ 真值窗中心帧；
4. 每个锚点 `t` → 原片窗 `W = times ∈ [t−half, t+half]`，`half = 段时长/2 + 1 s`：
   - **baseline** `cos(mean(E), mean(W))` ← 现行检索分口径；
   - **dtw_mean** = 单调 DP 路径上的 sim 均值（`sim_thresh=0.40, diag_penalty=0.5, step_penalty=1.0`，与 runtime 同款）；
   - **dtw_norm** = Σpath_sim / |E|；**dtw_cov** = |path| / (|E|+|W|)；
5. 评分：真值锚点在各打分下的 **rank**，以及 真值 − 最强干扰 的 **margin**。

## 3. 结果

### 3.1 全量统计（138 条正例，耗时 260 s）

| 指标 | base（均值余弦） | dtw_mean（对齐路径） |
|---|---|---|
| 平均真值 rank | **2.43** | 2.80 |
| rank 改善 / 恶化 / 持平 | — | **18 / 37 / 83** |
| 平均 margin（真值 − 最强干扰） | −0.0495 | **−0.0407** |
| 错配（margin<0）案例数 | 72 | 其中 **16 例被纠正**（22%） |

### 3.2 逐案例明细（`work/dtw_rank_results.json`，5 例探针）

| 案例 | nq | 候选 | rank base | rank dtw_mean | margin base | margin dtw_mean | 备注 |
|---|---|---|---|---|---|---|---|
| p01（易例） | 10 | 2 | 1 | 1 | +0.0843 | **+0.3059** | 对齐放大优势 |
| p08（兄弟机位） | 14 | 3 | 3 | 3 | −0.0482 | **−0.1062** | 两法皆失败，对齐更差 |
| p09（同场对话戏） | 31 | 5 | 4 | **2** | −0.0985 | **+0.0164** | 唯一 rank 改善 |
| p26（夜读，v4 已消解） | 16 | 4 | 1 | 1 | +0.0616 | **+0.3143** | 对齐放大优势 |
| t3r12（重复镜头） | 12 | 2 | 2 | 2 | −0.3188 | −0.2710 | 两法皆失败 |

读法：**对齐分确实比均值余弦更能「拉开」正确与干扰的差距（margin）**，但
（a）拉开幅度不足以改变排序决策（rank 层面 18 改善 vs 37 恶化）；
（b）核心失败族（兄弟机位）**两者都失败** —— 与项目既有结论一致：该族的缺口在「正确/干扰实例外观近同」，
不在「对齐质量」。

## 4. 诚实边界

1. 候选池是**探针简化口径**（best-match 锚点 + 1 s 去重，典型 2–9 个候选），不是 runtime 的 top-K 证据池
   → 绝对值不可外推到产品指标，只用于**同口径 A/B 对比**。
2. 窗口长度取「编辑段时长/2 + 1 s」，DP 参数取 runtime 默认；**未做参数 sweep**（护栏禁止）。
3. 编辑段 @8 fps 而原片索引 @1 fps（两侧帧率不同，DP 可容忍），与 runtime 密帧查询口径一致。
4. 未测「对齐 + 几何 + patch」组合链（竞品的组合用法）；本研究只隔离**排序用途**这一个变量。
5. 竞品精度仍未知（产品未运行）；本结论只说「把对齐分用于排序在**我方素材与口径**下无增量」。

## 5. 产物

- `mvp/scripts/research_dtw_rank.py`（cases / all 两种模式）
- `work/dtw_rank_results.json`（5 例探针）、`work/dtw_rank_results_all.json`（138 例全量）
- `work/dtw_rank_all.out.log`、`work/dtw_rank.out.log`
