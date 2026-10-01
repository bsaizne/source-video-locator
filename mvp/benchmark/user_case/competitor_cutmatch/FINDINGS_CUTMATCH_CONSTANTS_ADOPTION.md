# FINDINGS —— 竞品常量绑定（09）的采纳评估 + 两级采样保真度实测

> **GT 版本**（2026-10-01 补登记，批量执行）：不适用——竞品常量绑定核对；但文内引用我方基线 117/139 为当时现役口径已过时，文内引用的旧基线属当时现役口径、现已过时，引用数字须注明口径代际（现行基线见 .agent/STATE.md）。

> **输入（对方产出）**：`D:\claudework\cutmatch-analysis\FINDINGS\09_CONSTANT_BINDING.md`（2026-09-26 01:29）
> —— 27 项确证绑定 + 2 处更正 + 1 个否定结论（线性对齐证伪）。
> **我方现值来源**：`mvp/src/infrastructure/config.py`（2026-09-26 实读，非记忆）。
> **性质**：采纳评估 + 1 项新探针　**runtime 改动**：零（探针脚本 `mvp/scripts/audit_retrieval_ceiling.py` 加 `--coarse-stride`）。

---

## 0.0 证据分级与自我核查（2026-09-26 追加，回应"这些是真数据吗"）

本文件此前把若干**推断**写成了结论。以下按证据等级重排，并附本轮**独立字节复核**（benchmark 侧第一次自己碰二进制，
脚本 `mvp/scripts/verify_cutmatch_bindings.py`，产物 `work/verify_cutmatch_bindings.json` + `work/binding_occurrence_stats.json`）：

**A 类 · 已核实（可复现，= 真数据）**

| 项 | 复核方式 | 结果 |
|---|---|---|
| 09 表格 26 项绑定 | 从 09 的 md 表格正则抽 (name, value, name_off, val_off) 后**逐项读字节** | **26/26**：名字串确在该偏移、**零间隔**紧跟一个数值元素、数值与表一致 |
| 绑定是否"随机相邻" | 穷举 `data.find` 统计每个名字的全部出现 | 每个名字在二进制出现 **3–9 次**；**24/26 只有唯一一个"名字后紧跟数字"的位置**；2 项（`offset_refine_min_support`、`offset_refine_min_score`）各有两个数值落点，但**两处数值完全相同**（2/2 与 0.55/0.55） |
| 常量流布局 | 顺序解析名字前后各元素 | 19/26 = `name→value→name`（序列化字段记录）；4 = `name→value→value`；2 = `value→tuple`；1 = `value→string`。区段内 **5359 个属性名位置中仅 280 个（5.2%）后跟数字** ⇒ 相邻不是普遍拓扑现象 |
| 我方全部指标 | 本文件与 `FINDINGS_METRIC_CALIBER_V5.md` 的所有数字 | 均由 `work/*.json` 计算得出，命令见 §6 / 各文件"复现命令" |

**B 类 · 未核实（对方自报或无法验证）**

- 数值的**语义归属**：字节只证明"常量池里存在这个默认值落点"，**不证明运行期使用该值**（可能被 env/配置覆盖，或位于未被调用的分支）；
- A1/A2 家族（dual/visual/structure/motion/flash）**仍未绑定**（09 §5 自述）；
- 09 的"语义自洽"筛选本身是**人工判断**（同区段确有 `ceil→1e-06`、`arange→0.5`、`runtime_vision_vits14→5` 这类校验器/关键字伪影）。

**C 类 · 我的推断（此前写得过强，现降级/撤回）**

| 此前的表述 | 现状 | 反证/依据 |
|---|---|---|
| 「`180 帧 = 6 s @30fps`（强推断）」 | **降级为假设** | 值 180 是真的，但帧率口径 `_scene_range_fps` 未绑定；本轮亲眼看到同区段 `source_global_fps` 值位后**紧邻两个浮点**（0.1 与 30.0，前一元素还是约束类型名 `d_float`）⇒ "哪个数字属于哪个名字"在该区段**存在歧义**，不能由"180 + 有个 6 秒参数"推出单位 |
| 「作用阶段 = 匹配粒度 vs 输出粒度」 | **假设** | 我方 `raw_merge` 覆盖崩塌只说明"我们按输出粒度合并会崩"，**不证明**他们的用途 |
| 「0.1 fps 粗筛 + `long_scene_*` 密验 = 组合拳」 | **降级为叙事** | 实测只有"stride=10 时正确区跌出粗池 top-100 的有 12/139"；把他们存在 `long_scene_*` 与这 12 例**因果绑定是我的猜测** |
| 对照表里"我方缺 X"（`offset_bucket_seconds` 缺分桶、`dense_early_weight` 缺加权…） | **由名字推断** | 不构成功能缺失证据，只能算"待确认的机制差异" |
| 「竞品 `source_global_fps = 0.1`」当作既定值用于探针设计 | **有歧义，需降级表述** | 该值位紧随 30.0；探针结论应表述为"**stride=10 的敏感性实验**"，而非"复现竞品口径" |

> 结论：**字节层的绑定是真的**（A 类，我已独立复核）；**由绑定推出的"意图/单位/作用阶段/我方缺口"大多还是假设**（C 类）。
> 本文件下文若与本节冲突，以本节为准。

---

## 0.1 09 增量版（2026-09-26 02:14）独立复核 —— 我方再读一次字节

对方在本轮**接受了我方 §0.0 的质疑**，并把 09 从 147 行扩到 280 行（新增 §8 增量、§9 重分级 + 文法修订）。
我方用 `mvp/scripts/verify_cutmatch_bindings_v2.py`（含修订文法：**0x6e = 隐式 1 元组**）**逐条再核字节**，结果：

| 09 增量主张 | 我方独立复核 | 判定 |
|---|---|---|
| §8.1：边界精修 7 项（min_segment_frames 32 / min_side_frames 10 / near_cut_frames 16 / absolute_diff_min 45 / mad_multiplier 4 / max_move_frames 16 / max_additions_per_segment 1） | 7/7：名字在偏移处 + 零间隔 + 数值一致 | ✅ **我方 A7 临时绑定升级为确证** |
| §8.2：`offset_refine_dtw_topk_rerank_max_candidates=10`、`..._min_scene_coverage=0.8`、`actual_refine_score_threshold=0.65`、`ordered_search_max_seconds=1800.0`【2026-09-26 更正：原记 7200 系相邻配对假象，见 `reconcile_cutmatch_bindings.py`】 | 4/4 通过（`actual_refine_score_threshold` 首检被我方 kind 过滤误判，实为 `_` 类限定名 + `f 0.65`，字节成立） | ✅ 值成立；⚠️ 该名邻域全是 `balanced_*` 限定名 ⇒ **需确认它属默认 profile 还是 balanced profile** |
| §8.3：`runtime_vision_vits14 → 224` 是伪绑定（名字表 + 值块交界） | **复核成立且量级更大**：从 `0x174bcbd2` 起解出连续纯数值块 `224, 1.0, 3.0, 10, 5, 10, 3, 15, 315, 2, 300, 900, 1800, 0.55, 0.35, 0.62, 0.55, 0.03, 1.0, 2.0, 3.0, 3.0, 10.0, 5.0, 10.0, 3` | ✅ **陷阱确认**：凡"名字表末尾 + 值块首元素"一律不可取 |
| §9.2：`source_global_fps` 歧义 [0.1, 30]、`feature_image_size` 歧义 [224,32,1024]、`runtime_vision_vits14` 两处 | 全部复现（含 runtime_vision 第二处 `[5,512,20,100]`） | ✅ 我方上一轮的降级判断被对方确认 |
| §9.3：`_scene_range_fps` 数据段无字面值（3 处出现，紧随均非数值） | 3/3 出现，紧随元素为 tuple / 限定名，**确无数值** | ✅ 我方"180 = 6 s @30fps"**静态不可判定**（保留为假设） |
| §9.4：代码对象记录形状 = (qualname, [co_consts…, filename], co_varnames)，`global_weight/patch_weight` 的 0.45/0.55 出现在 `retrieval.py` 的 co_consts | **独立解出** `0x174db053`：qualname `match_commentary_scenes`；co_consts `[0.45, 0.55]`；filename `cutmatch\\matching\\feature_index\\retrieval.py`；varnames `['item']` | ✅ **本文件唯一升级到"代码级"的一项**：权重值不再只是数据段相邻 |

**对我方的直接结论更新**

1. **可采纳清单从 0 变为 11 项已字节省略级确证**（边界精修 7 + topk_rerank 2 + ordered_search_max_seconds 1 + proxy 96×54 等在 §1 表内），
   且 `global_weight 0.45 / patch_weight 0.55` 有 **co_consts 互证**（使用位置 = `matching/feature_index/retrieval.py` 的 `match_commentary_scenes`）。
2. 但**融合形式仍未知**（0.45/0.55 是加权求和？归一化？门控前/后？）⇒ 仍是假设，不能直接照抄实现。
3. **数据段已挖尽**（对方自述：剩余 59 项——N1 全部 `ordered_search_*`、N4 全部 `path_*`、各类 `*_enabled` 与 gain 门——
   每一次出现后面都不是数值而是 `T[1][自身名字]`）⇒ 只能走 **code object 常量索引（反汇编）**，这是我方可预期的最长等待项。
4. `_scene_range_fps` 静态拿不到 ⇒ "180 的单位"与"两级采样的真实口径"都**不能**靠静态结论，必须等运行日志。

> 复核产物：`work/verify_cutmatch_v2.json`（逐项 name/紧随元素/数值）+ `mvp/scripts/verify_cutmatch_bindings_v2.py`。

---

## 0.2 ⚠️ 08/09 的邻接绑定已被 FINDINGS/10 证伪 —— 权威来源切换（2026-09-26 追加）

对方已产出 `FINDINGS/10_NUITKA_CONSTANT_BLOB_BREAKTHROUGH.md»（Nuitka 常量块破解）+ **机器可读口径**
`data/competitor_profile_v1.json»（943 行，每条 = `value / level(确证|强推断) / source = code object@offset#index»）。
⇒ **我方此前的"邻接绑定"表（08/09）作废，一律以 FINDINGS/10 与该 profile 为准。**

**两处直接影响我方记录的更正**

| 参数 | 08/09 记 | FINDINGS/10 更正 | 我方独立复核（`work/_verify10.py»，读字节） |
|---|---|---|---|
| `source_global_fps» | 0.1 | **1.0** | 名字共 5 处出现，唯一数值落点为 `f 0.1» 后紧邻 `f 30.0»（**两个浮点并排**）⇒ 邻接口径确实定不了值；**但我在同区段找到产品自述字符串 `原子保存 1fps 原片全局索引及其身份 metadata。»（0x174b043d）** ⇒ 与「1.0」互证 |
| `commentary_short_scene_min_frames» | 180 | **8** | 180 处（0x174e0cca）紧随 `T[1]['scene_proxy_height']»（依赖/描述符形态），更像**约束**而非默认值；同区存在 `i 8»（0x174e1894）⇒ 与「8」不矛盾，但我**未能独立定值**（需 code object 侧证据） |

**由此作废/降级的我方记录**
1. 我此前的"**stride=10 模拟竞品 0.1 fps 粗筛**"表述 **作废** —— 他们的原片全局索引与我们**同为 1 fps**（那条 stride 敏感性实验本身仍有效，只是不能叫"竞品口径"）。
2. "**180 帧 = 6 s @30fps**" 及一切基于它的"匹配粒度"推论 **作废**。
3. 本文 §1 对照表中 `source_global_fps»、`commentary_short_scene_min_frames» 两行以 FINDINGS/10 为准；其余行若与 `competitor_profile_v1.json» 冲突，也以后者为准。

**新增：代理复现通道（运行期已被明确排除）**
- 对方 `RUNBOOK_CUTMATCH_PROXY_REPRO.md»：**不跑他们产品**（无合法激活码 + 模型为 AES-256-GCM 密文、密钥走服务器 lease ⇒ 做了也解不开），
  改用**公开权重**（TransNetV2 ONNX + DINOv2 ViT-S/14 官方权重）+ **确证参数**在我方沙盒复现其"场景切分 + 定位口径"，
  产出 `scene_split.json» / `localization.json» 交我方对照。
- **定级纪律**：产物是「**代理复现（推断级）**」，**不是竞品实测输出**；与 117/139 的对比只能写成「**口径差异分析**」。
- 我方已备好导入与对照：`mvp/scripts/import_competitor_proxy.py»
  ① 把 `localization.json» 转成我方 results schema → 直接喂 `measure_four_results.py» 同口径评估；
  ② 把 `scene_split.json» 与我方边界做 ±0.5 s 几何对照（匹配/双方独有/最近距离分位 → JSON+CSV），**谁是真切换仍由人工/多模态逐条裁决**。

---

## 0. 结论（四条，证据等级见 §0.0）

1. **可直接采纳项：原为 0，经 09 增量版（02:14）后为 11 项字节级确证**（边界精修 7 + `topk_rerank` 2 + `ordered_search_max_seconds` 1 + proxy 尺寸 96×54），
   其中 7 项同时**复核了我方 A7 临时绑定（一致）**；`global_weight 0.45 / patch_weight 0.55` 另有 **co_consts 互证**（见 §0.1）。
   但**融合形式**（0.45/0.55 如何组合）与**使用位置**（默认 profile vs balanced profile）仍需确认；
   真正缺的仍是 A1/A2 家族与 `ordered_search_*` / `path_*`（对方自述：数据段已挖尽，须走 code object 常量索引）。
2. 【**假设，非数据**】`commentary_short_scene_min_frames = 180` 的**单位与作用阶段未定论**。
   值 180 已复核为真（§0.0 A 类），但"180 帧 = 6 s @30 fps"依赖**未绑定**的 `_scene_range_fps`；
   同区段 `source_global_fps` 值位后紧邻两个浮点（0.1 / 30.0，前置元素为约束类型名 `d_float`）⇒ 数字归属存在歧义。
   "它属匹配粒度而非输出粒度"同样只是**假设**（我方 `raw_merge` 覆盖 .862→.172 只证明"我们按输出粒度合并是灾难"）。
   ⇒ 需要 `_scene_range_fps` 的值或一段运行日志才能定论。
3. **"抄池大小"对我方没有价值（有据）**：竞品 `global_top_k=100` / `scene_top_k=10` 对应的召回缺口在我方不存在 ——
   本轮 139 例审计中，22 例非 HIT 里有 **19 例的真值帧全片 rank ≤3**（本就落在我们 `retrieval_top_k=28` 的池内），
   真正跌出 top-20 的只有 `t2r05a` 一例。⇒ 要抄的是**选择/门控/精修**（`ordered_search_*`、`offset_refine_*`、路径一致性），
   不是池容量。
4. **两级采样敏感性已实测（A 类数据）**：复用生产索引（零重建）把索引抽稀 ——
   `stride 2 (0.5 fps)` 粗筛 **139/139 保真**；`stride 10 (0.1 fps)` 粗筛 **127/139（91.4%）**，
   漏掉的 12 例在密集索引里 rank 全为 1–3（都是短时刻案例）。
   ⇒ **可陈述的事实**：抽稀到 0.1 fps 会丢 8.6%，且这些损失肉眼可定位（12 例已列名）。
   ⇒ **不能陈述的**："竞品就是靠 `long_scene_*` 补回这 12 例"是我的**猜测**（C 类）；且 `source_global_fps` 的值本身
   在字节层有歧义（§0.0 C 类）⇒ 本探针应表述为"**抽稀敏感性实验**"，而非"复现竞品口径"。

---

## 1. 27 项绑定 ∶ 我方现值对照表

| 竞品常量（09 §4） | 值 | 我方对应 | 现值 | 判断 |
|---|---|---|---|---|
| `source_global_fps` | **0.1** | `pipeline.index_sampling_fps` | **1.0** | 我方密 10×；见 §3 实测（0.1 会漏 12/139） |
| `commentary_sample_fps` | **3.0** | `edited_segment_fps` 2.0 / 两级切分粗步长 6 帧 | 2.0 / ≈3 fps@30 | **接近**（口径可比） |
| `dense_sample_fps` | **10.0** | `seq_align.edit_fps` | **8.0** | 接近（我方 DP 重采样） |
| `balanced_coarse_sample_fps` | **5.0** | —（无对应档位） | — | 缺：我方无"平衡档"概念 |
| `feature_image_size` | **224** | 特征输入尺寸 | **518** | **不抄**（已实测 4/5 难例 518 更强：p08 −0.157）；需其 proxy 用途（N11） |
| `scene_proxy_height` | **720** | 切分/精修用原生分辨率 | 原生 | 不可比（我方无 proxy 层） |
| `dense_early_weight` | **1.5** | —（无对应） | — | 缺：密验早停/加权项 |
| `continuity_tiebreak_bonus` | **0.02** | 部分对应 `seq_dp_order_lambda` 0.001（罚，非赏） | 0.001 | **语义不同**（他赏连续，我罚倒退） |
| `global_weight` / `patch_weight` | **0.45 / 0.55** | patch 仅门控重排：`patch_rerank_enabled`、`keep_near` 8.0、`patch_v2_margin` 0.075、`radius` 30 / `stride` 4 | — | **我方缺"加权融合打分"**（值已知，融合形式未知 = N5） |
| `scene_top_k` | **10** | `scene_top_k` | **5** | 差 2×，但非瓶颈（§0.3） |
| `global_top_k` | **100** | `retrieval_top_k`（硬上限 `FROZEN_TOP_K`） | **28** | 同上：非瓶颈 |
| `offset_refine_min_score` / `min_support` | **0.55 / 2** | `patch_v2_margin` 0.075（近场）＋置信门 | — | 口径不可直接比（他在 offset 空间，我在 patch 空间） |
| `offset_refine_dtw_max_samples` | **64** | `seq_align.max_query_frames` | **64** | **完全一致（巧合但值得留档）** |
| `offset_refine_dtw_min_score` | **0.1** | `seq_align.global_mean_sim_min` | **0.20** | 我方门更紧 2× |
| `offset_refine_dtw_start_window_radius_frames` / `min_improvement` | **30 / 0.04** | `seq_align.window_max_s` 45 / 无 improvement 门 | — | **我方缺 start-window 门**（N3） |
| `commentary_boundary_refine_proxy_w/h` | **96 / 54** | 两级精修在**原生分辨率**上做 | — | 我方更贵更准；可作为**成本探针**候选 |
| `long_scene_min_seconds` | **6** | `seg_max_shot_s` 8.0 | 8.0 | 近似（他 6 s 场景 vs 我 8 s 长块细分） |
| `long_scene_max_keyframes` | **16** | `seq_align.max_query_frames` 64 / 每簇密帧 | 64 | 我方预算更大 |
| `long_scene_probe_window_seconds` / `stride` | **3 / 1.5** | `montage_cluster_gap_s` 15 / `subshot_cut_thresh` 0.5 | — | **机制最接近我方"蒙太奇子镜头"**（已被研究侧验证 POSITIVE 但 runtime 零变化） |
| `min_candidate_margin` | **0.1** | `margin_low` 0.08 | **0.08** | **接近，可对齐**（影响置信档，不改定位） |
| `offset_bucket_seconds` | **0.5** | —（1 fps 索引 ⇒ 时间粒度 1 s） | — | 缺：offset 分桶（对我方 1 fps 口径意义有限） |
| `commentary_short_scene_min_frames` | **180**（= 6 s @30fps，强推断） | `seg_min_shot_s` 0.8 / `seg_twopass_min_shot_s` 0.5 | — | **作用阶段不同**（他=匹配粒度，我=输出粒度），见 §0.2 |
| `local_sample_fps`（强推断） | **0.1** | — | — | 未定论（09 §4 注明等级弱） |

## 2. 09 的更正项对我方的直接作用

| 09 的更正 | 对我方影响 |
|---|---|
| `0.55 / 0.35 / 0.62` **不是** `commentary_scene_dual_*` | 纠正 `HANDOFF_CUTMATCH_AND_METRIC_AUDIT` §2 的前提；我方 A1 的"共现候选"绑定的证据等级仍为"中"，**不可用于实现** |
| `commentary_short_scene_min_frames = 180` **绑定正确、语义待修正** | 见 §0.2：作用阶段假设（匹配粒度）已在 `raw_merge` 实验中获得反证支持（按输出粒度合并 → 覆盖崩塌） |
| 线性对齐**证伪**（93 名 vs 93 值硬对齐 → 4/4 抽样全错） | A1/A2 家族只能走 code object `co_consts` 常量索引；**不能**再用"紧随其后的字面量块"，避免把噪声写成结论 |

## 3. 新探针：两级采样保真度（复用生产索引，217 s，零重建）

脚本：`mvp/scripts/audit_retrieval_ceiling.py --coarse-stride "2,10"`（对同一批 139 例、同一批 GT 引导查询点，
把生产 1 fps 索引抽帧成更粗索引，取"窗 ±(stride/2+0.5s) 内最佳粗帧在**粗池**里的 rank"）。

| 粗索引 | 等效 fps | 可判例数 | 正确区落在 粗池 top-100 | rank 分位 p50 / p90 / p99 |
|---|---|---|---|---|
| stride 1（生产） | 1.0 | 139/139 | 139（参照，全片 rank ≤3 者 19 例） | — |
| stride 2 | 0.5 | 139/139 | **139 / 139（100%）** | 1.0 / 2.2 / 25.3 |
| stride 10（**竞品 source_global_fps**） | 0.1 | 139/139 | **127 / 139（91.4%）** | 1.0 / 39.4 / **448.6** |

**0.1 fps 粗筛漏掉的 12 例**（括号内为它们在密集索引里的全片 rank）：

- 2mkv：p16(1)、p26(1)、p41(1)
- test1：t1r07b(1)
- test2：t2r00(1)、t2r02c(1)、t2r03a(1)
- test3：t3r03a(1)、t3r07(1)、t3r10(3)、t3r13(1)、t3r31(1)

⇒ 特征：**全部是"短时刻/短场景"案例**——正确内容在密集索引里几乎都是 rank 1，但 10 s 网格上的最近粗帧
（最远偏离 ±5 s）匹配到了别的画面。这与竞品 `long_scene_*`（长场景 3 s 窗 / 1.5 s 步长密探）的**存在理由完全吻合**。
⇒ 可复用结论：**两级采样是"索引成本 ÷10 + 局部密验兜底"的组合拳，单抄前半段 = −8.6% 召回**。

## 4. 由本轮可以立即关闭/推进的事项

| 事项 | 结论 |
|---|---|
| 抄 `global_top_k=100` / `scene_top_k=10` | **关闭**（我方非 HIT 的真值帧本就 rank ≤3；池容量不是瓶颈） |
| 抄 `feature_image_size=224` | **保持关闭**（518 实测更强），改为索取其 proxy 口径（N11） |
| `margin_low` 0.08 → 0.1 对齐 `min_candidate_margin` | 可做，但只影响**置信档**（不改定位），优先级低于定位层 |
| 两级采样（0.1 fps 粗 + long_scene 密验） | **可立项探针**：预期索引成本 ÷10，需把 12 例兜住（设计要点 = `long_scene_probe_window_seconds/strides`） |
| `offset_refine_dtw_max_samples = 64` 与我方一致 | 留档（旁证：双方在 DP 采样预算上收敛到同一量级） |

## 5. 仍需等对方（对应 `INTEL_REQUESTS_CUTMATCH.md` 2026-09-26 增量节）

- **N1–N4**（`ordered_search_*` 采纳门 / `offset_refine_*` 残留项 / `offset_refine_dtw_topk_rerank_*` / `select_scene_match_path` 目标函数）
  —— 对应我方定位层 19/139，**仍是最高优先**；
- **N5**（`global_weight/patch_weight` 的融合形式）—— 值已到手，缺的是算法形状；
- **N6**（两级采样的窗口/步长/切换条件）+ **N7**（180 的作用阶段确认）+ **N8**（多判据组合方式）；
- **N16**（运行期日志）—— 一份日志可一次性给出 N1–N6 大半实际取值，仍被"卡密 + 服务器 lease"挡住。

## 6. 产物

| 文件 | 内容 |
|---|---|
| `work/coarse_sampling_audit.json` | 139 例 × 3 档粒度（1.0/0.5/0.1 fps）的检索 rank 与粗池判定 |
| `mvp/scripts/audit_retrieval_ceiling.py` | 新增 `--coarse-stride` / `--coarse-k`（两级采样保真度探针） |
| 本文件 | 27 项绑定对照 + 180 语义推断 + 两级采样实测 + 关闭项 |

## 7. 待拍板

1. 是否立项「两级采样（0.1 fps 粗 + long_scene 密验）」探针（目标：索引成本 ÷10 且四片召回不回退）。
2. 是否把 `margin_low` 对齐到 `min_candidate_margin = 0.1`（置信档口径对齐，非定位改动）。
3. 是否向对方追加一项请求：**`_scene_range_fps` 的值**（决定 180 的帧率口径是否 = 30 fps；若 = 3 fps 则 180 帧 = 60 s，§0.2 的推断需改写）。
