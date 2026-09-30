# FINDINGS — 快速模式全局层完整复现（第三阶段「第二套复现」）：偏移投票锚定 +11, 复现链 100/139 新高；同口径下我方 main span 落后 +23（2026-09-27 续10m）

> **触发**：用户拍板「竞品对标继续深挖全层，看看全链闭环后我们和竞品还差在哪」——即续10j 遗留两条路中的
> ①「在沙盒完整重建快速模式候选生成」。
> **定级**：代理复现（推断级），非竞品实测。语义来源 = `FINDINGS_DOCSTRING_BREAKTHROUGH.md` §9（docstring + 字节确证常量）；
> 罚斜率/质量权重形状/锁定细节未确证（见产物 manifest params 登记）。**护栏说明**：本阶段全部在外部仓沙盒（研究侧），零 `mvp/src` 改动。
> **产物链**：`cutmatch-analysis/sandbox/run_fast_repro.py`（新）+ `run_localization.py` 加 `start_override` 种子参数（默认 None=交付口径逐字节不变）
> → 判据复用 `probe_combo_dual_caliber.py`（候选层 top-k + main span 截查询等长严格，争议 GT 双计）。

## 1. 实现内容（F1-F4）

| 层 | 竞品语义（docstring） | 复现形式 |
|---|---|---|
| F1 commentary_sampler | 3fps 连续采样 + 亮度/对比度/清晰度质量权重 | ED 全片 3fps CLS（test1 407 帧）+ 三分量 min-max 加权 0.2/0.3/0.5（形状未确证） |
| F2 coarse_retrieval | 逐样本 top-k → 0.05s 分桶加权偏移投票 → OffsetCandidate | 支持者（top-1 落该场景的样本）命中投影回 ED 场景起点 → 0.05s 分桶 → 共识簇(±1 桶)加权质心 = source_start；输出 {coarse, support_count, support_ratio, dispersion} |
| F3 select_refined_candidate_path | 四项加权 0.55 local+0.2 consistency+0.2 coarse+0.05 support；转移罚 grace 2.0s/max 0.12/backward 0.05；恢复候选（1.0s ∧ 0.45） | 两遍 DP + path-prev/next 恢复候选；主线锁定仅记诊断（N1 值未绑定） |
| F4 起点精确对齐 | 粗定位 → 10fps 起点对齐 | 投票共识起点作为 `start_override` 种子交给既有精修管线（±30 窗 + offset ±2 + P0 终版门 + DTW + AKAZE 全不动） |
| 池纪律 | — | **候选池 = 既有检索 top-20 不扩池**（collect_candidates 同数学）——差异可归因于「排序+锚定」本身 |

## 2. 三臂归因（test1，截查询等长严格，争议 GT 双计）

| 臂 | 严格 | vs p0f | 结论 |
|---|---|---|---|
| p0f 终版（无全局层） | 13/43 | — | 基准 |
| **DP 选路 only**（winner 换成两遍 DP+恢复候选） | **5/43** | **−8** | ❌ **路径 DP/恢复候选有害**——「全局层选择语义推断级不可下沉」第三次证实（继投票 graft 三连败后） |
| DP + 投票种子 | 16/43 | +3 | 种子 +11 但被 DP −8 抵消 |
| **种子叠加贪心**（winner 不动，只投投票共识起点） | **23/43** | **+10 全部 MISS→HIT 零退化** | ✅ **胜出形态**：全局层价值全在「锚定」，不在「选择」 |

- 种子命中即赢：增益例（t1r00/03/04/06/07a/10b/13b/28 等）种子起点距 GT 内容起点普遍 **<1s**（例：t1r00 种子 2154.2 vs GT 2153.3）。
- 候选层所有臂 top1 42/43 饱和、名次变化 0——增益 100% 来自位置层。

## 3. 四片全量（胜出形态 seed-on-greedy vs p0f）

| 片 | p0f | +全局锚定 | Δ | 备注 |
|---|---|---|---|---|
| test1 | 13/43 | **23/43** | **+10** | 零退化；18/35 查询种子生效 |
| 2mkv | 31/39 | 30/39 | **−1** | p19/p20 HIT→MISS、p26 MISS→HIT（2mkv 场景内多实例，种子偶发偏置） |
| test2 | 14/20 | 14/20 | 0 | 剩余 MISS 是蒙太奇/特征层型，锚定层无从发力 |
| test3 | 31/37 | **33/37** | **+2** | t3r00/t3r28，零退化 |
| **合计** | **89/139** | **100/139** | **+11** | **复现管线历史最高**（此前 P0+P1a=91） |

负例误报：7/9（2mkv 3/4 · test1 1/1 · test2 1/1 · test3 2/3），与基线同级。matched_on（akaze on）：test1 31/35 · 2mkv 68/72 · test2 63/67 · test3 —；一致性两遍全同（四片全部 diff=0）。

## 4. 同口径对照（main span 截查询等长严格）——「全链闭环后还差在哪」的定量回答

用**完全相同的判据**（main span 截到查询等长 → within±2s / mid-in / cov≥0.4，负例 ED 重叠≥0.5 计误报）评我方生产基线批
（`work/rerun_*_perfopt.results.json`，main span only；脚本内联，产物 `work/ours_mainspan_truncated_caliber.json`）：

| 管线 | test1 | 2mkv | test2 | test3 | **合计** |
|---|---|---|---|---|---|
| 我方生产 main span（同判据） | 22/43 | 20/39 | 10/20 | 25/37 | **77/139** |
| 复现链 p0f（单层精修） | 13 | 31 | 14 | 31 | 89/139 |
| **复现链 + 全局锚定（新）** | 23 | 30 | 14 | 33 | **100/139** |
| （参考）我方生产完整批三指标 | — | — | — | — | 117/139（口径不同物，含子 span/事件扩池） |

### 逐层差距定位（全链闭环后的剩余差距）

1. **main span 单发起起点精度：我方落后 +23（100 vs 77）——这是当前唯一的大差距项。**
   根因有据：竞品链有「3fps 逐样本偏移投票」这个**跨查询全局共识先验**给起点锚定；我方生产的起点精修全是**局部**信号
   （CLS 窗内精修/密集复核——P0 移植实测零增益），全局共识信号完全没有。复现链 100 里的增益例，起点普遍距 GT <1s。
2. **负例误报：同级（双方 7~8/9）**——CLS 内容混叠上限，双方都没有解，非差距项。
3. **候选层：双方饱和**（test1 42/43 · 2mkv 37/39；test3 5 never=蒙太奇段，双方同类）——非差距项。
4. **整体三指标**：我方 117 依赖子 span 枚举/事件扩池/冲突重排的「广度兜底」；竞品链靠「单发精度」。
   两条路线的差距已收窄为单点：**起点锚定的全局信号**。

## 5. 移植落地（2026-09-27 续11, 用户拍板「立项吧」）= 生产 117 -> 119/139（+2 零回退）✅

- **实现**: `engine/localization/offset_vote_prior.py`（纯函数, 采纳门 = support>=0.2 + max_shift<=4s 生产安全附加）
  + PipelineConfig 五旋钮（`vote_prior_enabled` 默认关）+ `locator_service._apply_offset_vote_prior`
  （挂接在 P0 密集复核之前, 镜像「粗种子 -> 密集对齐」; 复用索引特征零解码开销）+ 单测 7 项（全套 279 全绿）。
- **生产四片双臂回归**（`rerun_vote_prior.py`, GPU DirectML）:
  基线（denserecheck_off）117/139 · 137 · 4/9 → **投票先验臂 119/139 · 137 · 4/9**（test1 +2: t1r07a/t1r10b
  part→HIT, 经 main span 直接转正, 与沙盒种子修复例一致; 其余三片逐位不变）; **投票+密集复核臂 119/139 同臂 1**
  （种子落位后 P0 密集复核零增量, 与 P0 单独零增益一致）。
- **诚实边界**: 生产三指标只兑现 +2（沙盒同口径 +23 的差距）——因为三指标判据宽松（GT 中点入 span, 且子 span
  可兜底）, 沙盒截等长口径的大部分增益在生产里本就被子 span/part 认领; 真实价值 = **main span 单发精度**提升
  （与用户可见的「第一条定位就准」直接相关）, 以及新增了「全局共识」这一信号通道（未来定位劣化时的第二条腿）。
  耗时增量可忽略（每段一次 [n,384]×[N,384] 矩阵乘, 无新解码）。
- **默认关维持**: 按 DECISIONS 2026-09-26 移植纪律, UI/导出验收（需打包授权）通过后才翻默认开。
- 产物: `work/voteprior_{case}.results.json` / `work/voteprior_dense_{case}.results.json` +
  `work/voteprior_metrics.json` / `work/voteprior_dense_metrics.json`（对照 `work/voteprior_baseline_metrics.json`）。

## 5b. 原始拍板材料（移植前, 留档）

把 F2 偏移投票作为「起点先验」移植进 mvp 生产：对每个定位段的 winner 区域，用编辑侧逐样本（我方 2fps 采样）对源库
独立检索 → 0.05s 分桶投票 → 共识起点作为密集复核/精修的种子。**与 P0 移植（零增益）的本质区别**：P0 是局部窗内重找，
投票是跨查询全局共识——本轮数据首次给出了生产可能缺这个信号的直接证据（77 vs 100）。
须按惯例走立项 + 三指标回归 + UI 验收；风险 = 2mkv 型场景内多实例的种子偏置（本轮回退 1 例）。

## 6. 产物与登记

- 外部仓：`sandbox/run_fast_repro.py`（F1-F4 + 三臂旗标）+ `run_localization.py` start_override 参数（默认不变）+
  `out/localization_{fast,fastw,fasts}_{case}.json` 全系 + `manifest_fast*_*.json` + ed3fps 缓存。
- 判卷侧：`work/fasts_probe_{test1,test2,2mkv,test3}.json` / `work/fast_probe_test1.json` / `work/fastw_probe_test1.json` +
  `work/ours_mainspan_truncated_caliber.json`。
- 未竟（按需）：2fps 主档/AKAZE loose/top_k 28 档未跑（复现方接口在）；主线锁定（ordered_search 完整形态）仅诊断未实现；
  罚斜率/质量权重形状未确证（推断级，manifest 已登记）。
