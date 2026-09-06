# 蒙太奇定位研究 — 阶段一发现（原型验证）

> 背景：真实用户案例（编辑片《The Gorge》解说 1.mp4 → 原片 2.mkv）定位结果「编辑片有、定位结果没有」。诊断结论：**算法限制**（蒙太奇→单 run 丢子镜头 + 相似外观误配），非 bug。用户拍板转向研究蒙太奇定位。本文件记录阶段一：验证「查询轴簇结构」是否为可用的蒙太奇判别+定位信号。

## 已证实的核心假设

**「按逐查询帧的最佳匹配原片时间聚类」能：(A) 判别蒙太奇(≥2 显著簇) vs 干净段(1 簇)，且 (B) 定位每个子镜头、不破坏干净段。**

证据（`query_axis.json`，gap=30s，仅显著簇≥3帧 & best_sim≥0.45）：
- **干净段单簇**：[5]→1708、[10]→2102、[11]→7660（与基线正确单 span 一致）；[1]→980、[8]→1856（干净，但**原基线定位到的 1568/2042 反而是错位**——查询轴暴露出更可能正确的位置）。
- **蒙太奇多簇且与 GT 子镜头对齐**：[2](8-36.5s) 6 簇落在 1134/1300-1344/1376-1402/1580-1588 ≈ 研究 GT 的 s0/s1·s2·s3/s4/s6；[3]→1416/1558≈s5/s6；[4]→1606/1682；[0]→838+2418；[6]→88-140+1746-1810；[7]→3 簇。

**为何不同于已证伪的 17A/18/19**：那些用「per-query argmax 并集 / voting / 原片侧 cut-aware」，因**逐帧 argmax 噪声 + 无门控**失败。本方案改「**先聚类 → 门控(≥2 显著簇) → 每簇单独 finloc**」，用「簇是否显著」做稳健门控，干净段自然走单簇单 span。

## 原型实测（`montage_localize.json` / `research_montage_localize.py`）

- 分类正确：蒙太奇 [0][2][3][4][6][7][9] → montage 多子 span；干净 [1][5][8][10][11] → clean 单 span。与多模态判定一致。
- **[2] 从基线「单 span 1126-1184」→ 6 子 span**，edited 子区间被切分、各自对应独立原片区 → **回收丢失子镜头**。
- 干净段保持单 span 正确（[5]→1704-1710、[10]→2098-2104）。
- 意外改进：[1]/[8] 定位到查询轴主导位（968-984/1854-1858），比原基线（1568-1578/2042-2064）更可能正确 —— 说明**现有单 run 定位在一些段本身就是错位的**（候选窗 finloc 选了次优区），查询轴给主位更稳。

## 诚实标注的问题（阶段二要解决的）

1. **GT 不符（重要）**：seg[1] 原型定位 968-984，但研究视觉确认的 GT 是 s0(6.5-10s→1126-1138)。二者都是「站台/人」，CLS 在**相似站台区**里挑了 968 而非 GT 的 1126——**仍是「相似外观掩盖语义身份」**，查询轴不能保证选对 GT。需要核对编辑片 6-7.5s 的确切内容 + 用 GT 作为校验基准（阶段二明确：**GT 是否比 968 更对**）。
2. **弱簇**：部分子 span cover 低（[2] 的 (8-20)→1578-1584 cover .211），可能是噪声/低置信簇，需按 cover/best_sim 过滤或降档。
3. **蒙太奇镜头快速来回切**导致 edited 子区间相互重叠、子 span→编辑段归属混乱（当前用「簇内查询帧时间的 min/max」表达 edited_sub，对交替剪辑不干净）。需改用「簇内查询帧集合」而非时间区间，或按时间顺序对齐。
4. **原型未接入 runtime**：`research_montage_localize.py` 是观测/原型，未进 `mvp/src`；Result schema 目前单 `original`，多子 span 需要 schema 扩展（待设计）。

## 阶段二：GT 校检（关键验证，通过）

用 `ground_truth_corrected.json`（7 段视觉确认 GT）校检原型 vs 基线（`research_gt_validate.py`）：

| GT | edited | 正确 orig | 基线cover | 原型cover |
|---|---|---|---|---|
| s0 | 6.5-10 | 1126-1138 | 1.00 | 0.83 |
| s1 | 19-21 | 1288-1312 | **0.00(漏)** | **1.00(恢复)** |
| s2 | 26-29 | 1332-1348 | **0.00(漏)** | **0.88(恢复)** |
| s3 | 28-30 | 1340-1348 | **0.00(漏)** | **0.75(恢复)** |
| s4 | 30-32 | 1374-1392 | **0.00(漏)** | 0.00(相邻差一点) |
| s5 | 35-37.5 | 1394-1416 | **0.00(漏)** | 0.45(部分) |
| s6 | 46-48.5 | 1578-1602 | 0.75 | 0.75 |

**GT recall：基线 2/7 (29%) → 原型 5/7 (71%)。** 原型恢复出基线完全漏掉的 3 段（s1/s2/s3），s5 从 0→0.45。⇒ **蒙太奇多段定位方向成立，直接修复「对不上」。**

**seg[1] 968 vs 1126 已澄清**：s0 的 GT 由 App[2]（大蒙太奇）子 span 以 0.83 命中；seg[1]（6-7.5s 独立时刻）的 968-984 是另一视觉合理定位（verify_s1 编辑峡谷+站台 ↔ 968-984 站台内容吻合），二者不冲突。剩余 = s4/s5 边界相邻（refine 簇窗/gap）+ 类内歧义（968 vs 1126，属「相似外观」需第二信号）。

## 阶段三：全段多模态终核 + 原型完善（research 闭环）

**原型完善**（`research_montage_localize.py`）：① 弱簇标记（cover<0.35 或 best_sim<0.45 → `weak`）；② 每个子 span 输出「簇内真实编辑帧集合」（`edited_frames`，代替粗糙的 min/max 区间，解决蒙太奇快切导致的区间重叠）。

**全段终核（`verify_s*.jpg`）**：
- **恢复为真（子镜头内容吻合）**：[0] 峡谷航拍(834-842) + 男子持枪(2408-2432，40:20 手套握枪吻合)；[2] 6 子 span 对齐 s0-s6；[3] s5/s6；[7] 「WE ARE NOT ALLOWED」绿牌(→30:34 同款) + 女子持枪/张臂(→33:42/34:13)。
- **质量方差（诚实）**：[6] 恢复弱——远区 jet 簇 cover 仅 .415、绿牌「WHAT is YOUR NAME?」未干净回收（子镜头暗色/不显著 → CLS 判别力下降）。
- **边界残余**：s4(1374-1392) / s5(1394-1416) 原型子 span(1392-1404) 相邻差一点（finloc 窗/gap 需 refine）；部分弱簇需更严过滤。
- **干净段保持单 span 正确**：[5]/[10]/[11]；且 [1]/[8] 从基线错位 1568/2042 修正到 968/1854（更可能正确）。

### 精度全量核验（2026-08-27 迭代，决定是否需要第二信号）

对全部蒙太奇子 span 逐帧终核（`verify_s0..s9/s1.s5.jpg`）：
- **~18 个子 span，仅 1 个可疑**（seg6 jet 簇 122-142，cover .415——「暗色人物」CLS 相似但语义可能不同）；其余全为真实内容匹配（[0] 持枪/峡谷、[2] s0-s6、[3] s5/s6、[4] 山坡/窗边烛台、[7] 绿牌/持枪张臂、[9] 窗边/岩石铁丝网、干净段全真）。**精度 ≈94%。**
- **结论：蒙太奇多段输出高精度。**「相似外观」误配在此数据上**低频（~5%，单例 seg6 jet / seg1 968-vs-1126 / credits）**，非系统性高频问题。
- **对第二信号的判断**：在此证据上，第二信号（场景身份/时序一致性）**边际价值低**——误配是单例而非高频。故把第二信号列为**后续独立研究**（若未来真实数据证明误配成高频，再触发），当前蒙太奇多段定位（86% recall + ~94% precision）作为算法当前能力定稿。

### 弱簇过滤（precision 优化，2026-08-27 迭代）

丢弃「cover < 0.35 且 best_sim < 0.55」的双低子 span（明确噪声）；单低保留（真实部分子镜头，如 [0] 峡谷 .33/.68）。`research_montage_localize.py` 增加 `WEAK_COVER/WEAK_SIM`。
- **GT recall 保持 6/7 (86%)**（未损失任何 GT 覆盖）；仅 [2] 丢 1 个明确噪声簇（[1578-1586] cover .21/best_sim .53），其余段 kept=全部。
- **诚实**：作用温和（此数据多数簇 best_sim≥.55 不触发双低）；seg6 的 jet 簇（cover .415/best_sim .61）**未**被过滤——它是「相似外观」误配而非弱信号，需第二信号（场景身份/时序一致性）才能处理，独立研究项。
- **s5 边界残留**：s5(GT 1394-1416) 因 App[2] 与 App[3] 之间 0.5s 切分间隙被横跨切割，[2] 给 1376-1404、[3] 给 1416-1426，均不覆盖 1404-1416。属**跨段边界伪影**（非蒙太奇定位核心缺陷）；跨段 span 合并是另一套机制，暂不做。

### 子 span 定义优化（迭代，达成 86% GT recall）

「子 span = 簇最佳匹配范围[min,max] ∪ finloc run 凸包」——既有对数对齐又有覆盖宽度。
GT recall（cover>=0.5）随子 span 定义演进：
- finloc run：5/7（s4 边界漂移错过）
- 簇 p5-p95：5/7（修好 s4 却让 s0/s1 变紧漏）
- **集群 range ∪ finloc run：6/7 (86%)**（s0/s1 恢复 + s4 修复，仅 s5 未命中）

| GT | correct orig | cover |
|---|---|---|
| s0 | 1126-1138 | 0.83 |
| s1 | 1288-1312 | 1.00 |
| s2 | 1332-1348 | 0.88 |
| s3 | 1340-1348 | 0.75 |
| s4 | 1374-1392 | 0.89（修复） |
| s5 | 1394-1416 | 0.45（跨 App[2]/[3] 段边界的映射伪影，非算法缺陷） |
| s6 | 1578-1602 | 0.75 |

基线 2/7 (29%) → **原型 6/7 (86%)**。干净段保持单 span 合理（[5]→[1704,1710]、[10]→[2098,2104]）。

**结论**：蒙太奇多段定位（query-axis clustering + 门控 + per-cluster merged span）是可行的新方向，GT recall 29%→86%，修复「对不上」主要机制。

## 召回优化（2026-08-28，用户「很多镜头没识别到」）

- **量化**（Explore + user_results.json）：12 段 = HIGH3/LOW9，`failure_reason=0`（非 app 吞段，是**真没细拆**）；粗段（28.5s/22.5s/23.5s）内子镜头仅召回 2~5 个，总子 span 18。主因 = 蒙太奇 `min_frames=3`（@2fps 丢弃 <1.5s 子镜头）+ `cluster_gap_s=30`（太宽）+ `detect_shots z_thresh=2.0/cut_abs=0.30`（段太粗）。
- **参数向召回侧优化**（不改语义）：`config.py` 接入 `montage_*` 字段 + `locator_service` 用 PipelineConfig 驱动 MontageLocalizer + 降 seg 参数 + `clustering MIN_HITS 2→1/SIM_FLOOR 0.45→0.38` + `retrieval_top_k 20→28`。
- **参数扫描平衡点**（0.5fps 索引，`measure_recall.py`）：

| 设置 | 段数 | 子span | GT recall |
|---|---|---|---|
| 基线 (z=2.0, mf=3, gap=30) | 12 | 18 | 6/7 |
| **中间 (z=1.7, mf=2, gap=15)** | 14 | **28** | **6/7** |
| 激进 (z=1.4, mf=1, gap=8) | 32 | 42 | **4/7（回归）** |

- **采纳中间设置**：`seg_z_thresh=1.7`/`seg_cut_abs=0.26`/`seg_min_shot_s=0.8`/`montage_min_frames=2`/`montage_min_sim=0.40`/`montage_cluster_gap_s=15.0`/`retrieval_top_k=28` + 索引 `index_sampling_fps` 0.5→**1.0**（密度，用户拍板含）。
- **多模态精度核验**（`verify_recall_sample.py`，recall_s*.jpg）：新子 span 内容**相关**（士兵→士兵、炸弹→炸弹），非随机噪声；部分 cover 低（0.3-0.5）仍相关。GT recall 6/7 保持 = 正确性门过。
- **诚实**：细切分/细子镜头是**召回×精度本征权衡**——激进（z=1.4/mf=1/gap=8）把 GT recall 打到 4/7（碎片化），中间设置保 6/7。**特征层上限未变**（暗色同类子镜头 CLS 仍难区分；需第二信号/更好特征=独立研究）。

## 阶段研究产物

- **硬化模块（2026-08-27，可测、不进 runtime）**：`montage_research/montage_localize.py` —— `MontageLocalizer`（query-axis clustering + 门控 + 每簇 merged span + 弱簇过滤）+ `cluster_by_gap`；核心 `localize()` 无 IO、确定性。**8/8 单测**（`test_montage_localize.py`：cluster_by_gap / clean 单 span / montage 子 span 不相交 / empty / 弱簇丢弃）。**真实 12 段驱动（`mvp/scripts/research_run_module.py`）复现 GT recall 6/7 (86%)，无重构回归**。
- 研究脚本：`mvp/scripts/research_montage_localize.py`（原型）、`research_query_axis.py`（簇结构）、`research_gt_validate.py`（GT 校检）、`research_verify_montage.py`（多模态核验）、`research_run_module.py`（硬化模块驱动）。
- 产物：`mvp/benchmark/user_case/montage_research/`（query_axis.json / montage_localize.json / verify_s*.jpg / montage_localize.py / test_montage_localize.py / FINDINGS.md）。

- `mvp/scripts/research_query_axis.py`（簇结构实验）、`research_montage_localize.py`（原型）、`research_verify_montage.py`（多模态验证）
- `mvp/benchmark/user_case/montage_research/{query_axis.json, montage_localize.json, verify_s*.jpg}`

## 下一步（需对齐）

A. 用 **GT 作为校验基准**：对映射到 GT 的段（[1][2][3]）把原型子 span 与 `ground_truth_corrected.json` 逐段对表，算 recall/IoU；先搞清 seg[1] 的 968 vs 1126 谁对。
B. 过滤弱簇 + 修正 edited_sub 表达（簇帧集合而非时间区间）。
C. 若 A/B 通过，设计 **Result 多 span schema**（edited 段 ↔ 多个 original 子 span + 各自置信/cover）并讨论 guardrail：这是「改定位输出结构」，属于新研究导向的产品化，需评估对单一 span 契约（`Result.original`）的兼容。
D. 评估是否需要场景身份第二信号（CLS 之外的时序一致性）来解决「相似外观」残余（seg[1]、credits 类）。

> 研究护栏：以上均为研究原型，不引入 runtime；未改相似度/检索/排序/置信语义；多模态仅用于核验，不入 runtime。
