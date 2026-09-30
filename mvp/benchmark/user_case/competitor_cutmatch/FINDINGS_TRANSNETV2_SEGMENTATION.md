# FINDINGS — TransNetV2 场景切分 替换编辑侧两级切分（A1 单点实验）

> **GT 版本**：2.mkv → `datasets/real/ground_truth_v4.json`（39 正例 / 4 负例）；
> test1/2/3 → `datasets/real/ground_truth_test1|test2|test3.json`（100 正例 / 5 负例）。
> **基于 v4 口径，未使用 v3**。
> **日期**：2026-09-25　**性质**：竞品对标单点实验（研究侧）　**runtime 改动**：零（`mvp/src` 未改）

## 0. 结论（一句话）

把编辑侧两级像素切分换成竞品所用的 **TransNetV2（a01）**，四片生产管线回归 =
**严格 117/139 → 101/139（−16）**、**场景级 137/139 → 120/139（−17）**、负例 4/9 → 3/9。
翻转明细：**退化 32 例 / 改善 12 例**（净负、且方向系统性偏负，非抖动）。

TransNetV2 的边界与我方切分**高度重合**（双向 recall 0.76–0.98、中位距离 <0.1 s），
差异不在「谁看得更准」，而在**切分粒度**：模型偏向把快剪解说段切得更碎，
与我方「查询单元要偏大、防碎片化」的产品约束直接冲突。
→ **不接入（有据）**；「竞品多一个学习式场景切分」**不构成能力缺口**。

## 1. 动机（竞品对标）

竞品 CutMatch V7.1.0 逆向（独立项目 `D:/claudework/cutmatch-analysis`，137 模块图）：

- `cutmatch.matching.scene_detection.*`（`detector` / `boundary` / `boundary_refiner` /
  `decode` / `input_preparation` / `models` / `predictions` / `scene_engine_runtime` / `supervisor`）
  对应 `a01 = TransNetV2`（容器级确证：90 张量 / 7,618,056 元素 / 明文 30,509,621 B）；
- 基座双方一致：`a02 = DINOv2 ViT-S/14` 且与 `dinov2_vits14_pretrain.pth` **SHA256 逐字节一致**
  → 竞品**未微调**基座 ⇒ 不存在「他们模型更强」的解释空间（与「换更大基座关闭」互为旁证）。

我方全仓 grep `TransNet` = **0 命中**（`src/` 与所有 `.md`），许可矩阵亦未登记
→ 这是**从未评估过的组件**，不是「试过不行」。

## 2. 方法与可复现性

| 环节 | 做法 | 证据 |
|---|---|---|
| 模型代码 | 官方 soCzech/TransNetV2 `inference-pytorch/transnetv2_pytorch.py` | `work/transnetv2/`，sha256 `f7c1d437465579a8ec28a5ad…` |
| 权重 | 官方 `transnetv2-pytorch-weights.pth`（30,508,183 B） | state_dict 90 张量 / **7,618,056 元素** == a01 明文计数（逐位一致） |
| 推理 | ONNX `work/transnetv2/probe_transnetv2.onnx`，对拍官方 PyTorch | sigmoid 后 **max&#124;diff&#124; = 6.1e-8**（输出 534=single / 535=many_hot） |
| 速度 | DML 0.032 s/窗口 vs CPU 0.295 s/窗口（100 帧窗，step 50） | `work/transnetv2/bench_speed.py` |
| 阈值 | 官方口径：single>0.5 判 cut，重叠窗累加取均值，末窗末帧重复补齐 | `mvp/scripts/tn_transnetv2.py` |
| 采样 | 编辑片**原生 fps**（28–30）抽 48×27 RGB；编辑片 69–156 s ⇒ 全片推理 2–4 s | 同上 |

零 `mvp/src` 改动的 harness `mvp/scripts/rerun_transnet_runtime.py`：
monkey-patch `SourceLocatorService._segment_twopass_flash` → `_segment_transnet`
（TransNetV2 边界 → 最短镜头保护 0.5 s → 2 fps 特征切片 → `card_guard`），
其余生产管线（索引/检索/事件扩池/patch v2/文本锚/置信）**完全不变**；
编辑缓存关闭以免命中旧 shots；结果写 `work/tn_<case>.results.json`（不覆盖历史批）。

## 3. 结果 A：编辑侧边界三方对比（`mvp/scripts/probe_transnet_bounds.py`，纯离线）

命中口径：边界到对面最近边界距离 ≤ 0.5 s。recall = GT 边界被覆盖比例；
precision = 检测边界贴近 GT 的比例（GT 只标注「需要定位的段」而非全片切点 → precision 天然偏低）。

| 案例 | GT 段/边界 | 基线段/边界 | TN 边界 | GT vs 基线 R/P | GT vs TN R/P | 基线 vs TN R/P |
|---|---|---|---|---|---|---|
| 2mkv | 43 / 58 | 69 / 70 | 71 | 0.810 / 0.586 | **0.862 / 0.662** | 0.857 / 0.873 |
| test1 | 44 / 77 | 41 / 42 | 33 | **0.545 / 0.738** | 0.481 / 0.788 | 0.762 / 0.970 |
| test2 | 21 / 23 | 54 / 55 | 66 | **0.913 / 0.364** | 0.826 / 0.258 | 0.982 / 0.818 |
| test3 | 40 / 71 | 67 / 68 | 87 | 0.704 / 0.456 | **0.746 / 0.425** | 0.897 / 0.713 |

**读法**：基线 vs TN 的 recall 0.76–0.98、中位距离 <0.1 s ⇒ 两套切分判的是**同一批画面边界**；
差异集中在**粒度**（test2 66 vs 54、test3 87 vs 67：TN 更碎；test1 33 vs 41：TN 更少）。

## 4. 结果 B：四片三指标（生产管线，仅切分不同）

口径 `mvp/scripts/measure_four_results.py`（严格 = GT 中点落在某 span 内；场景级 = ±15 s；负例 = 误报）。
基线 = `work/rerun_<case>_perfopt.results.json`（两级切分 + 白闪守卫）；实验 = `work/tn_<case>.results.json`。

| 案例 | 基线 严格 | TN 严格 | Δ | 基线 场景 | TN 场景 | Δ | 基线 负例 | TN 负例 | 段数 基线→TN | 耗时 TN |
|---|---|---|---|---|---|---|---|---|---|---|
| 2mkv | 35/39 | **25/39** | **−10** | 39/39 | 33/39 | −6 | 3/4 | 2/4 | 69 → 69 | 439 s |
| test1 | 34/43 | **32/43** | **−2** | 42/43 | 39/43 | −3 | 0/1 | 0/1 | 41 → 41 | ~370 s |
| test2 | 14/20 | **13/20** | **−1** | 19/20 | **14/20** | **−5** | 0/1 | 0/1 | 54 → 66 | 607 s |
| test3 | 34/37 | **31/37** | **−3** | 37/37 | 34/37 | −3 | 1/3 | 1/3 | 67 → 86 | 762 s |
| **合计** | **117/139** | **101/139** | **−16** | **137/139** | **120/139** | **−17** | 4/9 | 3/9 | | |

负例 4→3 **不是改善**：切碎使部分段更保守（拒绝），代价是正例大量掉档。

### 4.1 逐案例翻转（`mvp/scripts/diff_four_batches.py`）

- **2mkv（退化 12 / 改善 1）**：HIT→MISS `p02 p03 p08 p26 p36`；HIT→part
  `p05 p23 p32 p34 p40 p41`；part→MISS `p30`；唯一改善 `p20` part→HIT。
- **test1（退化 8 / 改善 5）**：HIT→MISS `t1r12a t1r30a t1r31`；HIT→part
  `t1r00 t1r07b t1r10a t1r13b t1r30b`；改善 `t1r02 t1r07a t1r10b t1r14d t1r26`（part→HIT）。
- **test2（退化 7 / 改善 4；场景级 −5 最重）**：HIT→MISS `t2r01c t2r02b t2r07a t2r07c`；
  HIT→part `t2r03a`；part→MISS `t2r04a t2r05a`；改善 `t2r03b t2r03c t2r05b t2r06a`。
  ⚠️ 场景级从 19 → 14 说明**定位偏移被放大**（不只是丢命中）。
- **test3（退化 5 / 改善 2）**：HIT→MISS `t3r01 t3r02c t3r04c`；HIT→part `t3r02b t3r18`；
  改善 `t3r06b t3r29`。
- 支撑 span：592/1141 → **572/1129**（略降）。

## 5. 机制：不是「切得不准」，是「切得太碎」

- 典型退化链（2mkv）：`p02`(ed 1.2–2.0) 与 `p03`(2.0–3.7) 在基线中同属 `s0` 大段，
  靠 **sub span 枚举**命中；TN 在这两处切出独立单元后**双双 MISS**（TN 的 s2 已漂到 og 2442–2444）。
  同型：`p26`/`p30`/`p36` 由 HIT 变 MISS。
- test2 的 `t2r02b`（多子镜头蒙太奇段）与 `t2r07c` 由 HIT 变 MISS —— 与项目既有结论一致：
  这类段需要「整段 + 子 span / 蒙太奇子镜头」策略，切碎反而破坏证据。
- 与我方模块设计注释一致（`engine/segment/segment.py` 头部）：
  > 「目标不是精确还原每个摄影机 shot，而是生成**适合独立定位的 Edited 查询单元**……
  > 过长 segment 可接受；过短/碎片化 segment 更危险 → 整体**偏向下切分**」

  TransNetV2 是**镜头/场景边界检测器**，训练目标 ≠「查询单元」目标；在解说型快剪素材上
  它把「语义上应整体检索的连续块」切开，使单段证据不足以独立定位
  （本管线依赖「段内多帧 + span 枚举 + patch 事件扩池」）。

## 6. 诚实边界

1. **只替换编辑侧切分**；未测 TransNetV2 用于**原片侧**场景表/事件表（竞品可能在原片侧用它），
   也未与 `boundary_guard` 等我方等价守卫做对照。
2. 单模型单阈值（官方 100/50/0.5 + 我方 0.5 s 最短保护），**未做阈值 sweep**（项目护栏禁止）。
3. 我方管线其余部分（patch v2 / 事件扩池 / 置信）未重标定——对两侧**同等**生效，不构成偏置。
4. 竞品**精度仍未知**（产品未运行，C1 对标实验未做）；本结论只说「同素材上 TN 切分更差」，
   不说「竞品整体更差」。
5. TransNetV2 许可证 = **MIT**（官方 `LICENSE`，Tomáš Souček 2020；已存 `work/transnetv2/LICENSE`）——
   本项目 `ENGINE_LICENSE_MATRIX.md` **仍未登记**该模型（建议补登记；本次未改该文件）。
6. 复现提示：本实验在**生产 data 目录**跑；长任务须用可脱离 shell 的进程启动方式
   （本次用 WMI `Win32_Process.Create`），否则会被会话清理中断（记录：前三次 2mkv/test 批
   曾因进程被中断而误判为「卡住」）。

## 7. 产物

- `mvp/scripts/tn_transnetv2.py`（共享推理：session/predict/cuts/boundaries）
- `mvp/scripts/probe_transnet_bounds.py`（边界三方对比，纯离线）
- `mvp/scripts/rerun_transnet_runtime.py`（四片生产管线 harness，monkey-patch 切分 + 进度回调）
- `work/transnetv2/`（官方权重/代码/ONNX 对拍/速度标定）
- `work/tn_bounds_summary.json`、`work/tn_{2mkv,test1,test2,test3}.results.json`、
  `work/tn_four_metrics.json`、`work/tn_*.out.log`
