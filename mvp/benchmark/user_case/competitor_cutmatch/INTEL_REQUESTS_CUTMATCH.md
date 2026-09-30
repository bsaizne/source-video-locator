# INTEL REQUESTS — 为对标实验需要的竞品情报清单

> 提出方：benchmark 侧（Source Video Locator）2026-09-25
> 目标项目：`D:/claudework/cutmatch-analysis`（CutMatch V7.1.0 静态逆向）
> 需求方已完成的实验：见 `FINDINGS_TRANSNETV2_SEGMENTATION.md`（A1）与 `FINDINGS_ALIGNMENT_RANKING.md`（A2）

## 0. 背景：我们已知什么 / 为什么还要这些

**已确证（可直接引用）**
- `a02 = DINOv2 ViT-S/14`（与官方权重 SHA256 逐字节一致 ⇒ 未微调）；`a01 = TransNetV2`（90 张量 / 7,618,056 元素）。
- 我方实验 A1：把**裸官方 TransNetV2**（single>0.5 + 0.5s 最短保护）替换我方编辑侧两级切分 → 四片严格 **117→101/139**、场景 **137→120/139**（更差）。
- 我方实验 A2：把「对齐得分」用于候选排序 → rank 改善 18 / 恶化 37（无增量）。
- 结论：**用原料硬替换不等于复现他们的能力**，需要他们的**参数与判据组合**。

**从 AOT 字符串里挖到的竞品符号名（证据等级 = 符号名级，仅证明存在）**
`commentary_scene_dual_single_min` / `dual_many_min` / `dual_combined_min` /
`commentary_scene_flash_luminance_min|jump_min` / `commentary_scene_motion_ecc_similarity_max` /
`commentary_scene_motion_histogram_distance_max` / `commentary_scene_structure_distance_min` /
`commentary_scene_visual_score_min|visual_strong_score_min|visual_peak_ratio_min` /
`merge_short_commentary_scene_ranges` / `commentary_short_scene_min_frames` /
`refine_commentary_scene_split_with_frame_diff` / `refine_scene_match_boundaries` /
`build_scene_feature_index_{standard,low_memory,streaming}` / `source_scene_index` / `commentary_scene_index` /
`build_source_timeline_index` / `save_fast_global_index` / `source_global_fps` / `global_weight` /
`collect_dtw_topk_rerank_source_scenes` / `rerank_scene_match_offsets_with_dtw_topk` /
`refine_scene_match_offsets` / `resolve_consecutive_scene_offsets` / `select_scene_match_path` /
`describe_scene_path_quality` / `path_consistency_weight` / `path_transition_max_penalty` /
`path_backward_max_penalty` / `path_transition_grace_seconds` / `path_{coarse,local,support}_weight` /
`offset_refine_dtw_{enabled,max_samples,min_score,sample_interval_seconds,start_window_enabled,start_window_radius_frames,start_window_min_improvement,topk_rerank_enabled,topk_rerank_max_candidates,topk_rerank_min_scene_coverage}` /
`offset_refine_max_shift_{frames,seconds}` / `offset_refine_{min_score,min_support}` /
`long_scene_{min_seconds,max_keyframes,keyframe_interval_seconds,probe_window_seconds,probe_stride_seconds}` /
`scene_sensitivity` / `detect_scene_ranges[_with_backend]` / `_scene_range_fps`

**当前假设（需要情报来验证/落地）**
- **H1 粒度层**：他们输出的是 **scene（场景，多镜头聚合）**，我们按 shot 边界用 ⇒ 需要短段合并/场景聚合阈值。
- **H2 判据层**：他们用 **TN 双头 + 白闪/运动/结构/视觉多判据 + 帧差精修**，我们只用了 single>0.5。
- **H3 双侧索引**：他们**两侧**都建场景索引（source + commentary），我们只在编辑侧切分。
- **H4 路径层**：他们做**场景级 DTW offset 路径选择**（一致性权重 + 倒退惩罚），我们逐段独立定位 + 事后修补。

---

## P0 — 决定 H1/H2 能否落地（最想要）

| # | 想要什么 | 用途 | 建议方法 |
|---|---|---|---|
| 1 | `commentary_scene_dual_single_min` / `dual_many_min` / `dual_combined_min` 的**默认数值** | 复现双头判定（H2 核心） | Nuitka 常量池：在 `data/sidecar_crypto_region_strings.txt` 找到这些名字，**在二进制里定位其所属常量结构附近的 float/double**（dataclass/options 默认值常成片出现）；或找 `fast_timeline.options` 对应的 kwargs 名值对 |
| 2 | `commentary_short_scene_merge_enabled` / `commentary_short_scene_min_frames` / `merge_short_commentary_scene_ranges` 的**合并判据** | H1 场景聚合（粒度层） | 同上；另看 `diagnostics/public_messages` 里的用户可见文案（常把规则写成句子） |
| 3 | `commentary_scene_flash_luminance_min` / `jump_min` 的**量纲与阈值**（0-255 均值？亮像素比例？帧间差？） | H2 白闪判据对齐（我方已有 flash_guard，可直接换口径） | 同一常量区；或找 `flash` 相关日志模板 |
| 4 | `visual_score_min` / `visual_strong_score_min` / `visual_peak_ratio_min` / `structure_distance_min` / `motion_ecc_similarity_max` / `motion_histogram_distance_max` 的**组合方式**（哪些是硬门、哪些加分、先后顺序） | 理解他们"切得准"的真正判据 | 符号名共现顺序 + 日志模板；若 `diagnostics` 有 `*_reason` 字段名，可反推分支 |
| 5 | `refine_commentary_scene_split_with_frame_diff` 的**窗口/步长/阈值** | H2 精修阶段 | 同上 |
| 6 | `_scene_range_fps`（喂 TN 的采样 fps）与 `_scene_runtime_input_windows` 的**窗口/步长** | 校准我的输入口径（我现用原生 fps + 48×27 + 100/50） | 常量区 + `_count_scene_runtime_windows` 附近 |

## P0 — 输出层（回答"用户可见的镜头切分为什么更好"）

| # | 想要什么 | 用途 | 建议方法 |
|---|---|---|---|
| 7 | `exporting/segments/builder.py`、`timing/video_timing.py`、`jianying/fcpxml_generator.py`、`premiere/xml_generator.py` 的**输出字段与时间码精度** | 对齐"片段边界"口径 | 字符串池里的标签名/格式串；若能拿到样例文件最好 |
| 8 | **任何他们的真实输出样例**（剪映草稿 / PR XML / 片段列表 / 截图，含时间码） | 直接逐条对照我们的结果定位差距 | 由用户提供（若手上已有） |

## P1 — 决定 H3（原片侧场景索引）

| # | 想要什么 | 用途 |
|---|---|---|
| 9 | `build_scene_feature_index_{standard,low_memory,streaming}` 的**索引粒度与特征来源**（DINOv2 CLS？多尺度？帧率？） | 我们原片侧目前是 1 fps 特征聚合的 `scenes.npy`，需知道他们的口径 |
| 10 | `source_global_fps` / `global_weight` / `local_global_similarities` / `build_source_timeline_index` | 他们**全局索引 + 局部索引融合**的权重与 fps（我们是单一索引） |
| 11 | `_load_scene_runtime_tensorflow_model` 与 `_load_scene_runtime_tensor_runtime_model` 的**关系**；`_convert_scene_runtime_tensor_runtime_weights` 的作用 | 确认 a01 的推理路径与权重来源（是否与我们本地复现的官方 .pth 完全一致） |
| 12 | `detect_scene_ranges_with_backend` 的 **backend 选择逻辑**（CUDA/DML/CPU？） | 若他们只跑 CUDA，说明其场景切分在我们 AMD 环境上未必可用（商业面的差异） |

## P1 — 决定 H4（场景级路径选择，价值最高）

| # | 想要什么 | 用途 |
|---|---|---|
| 13 | `select_scene_match_path` / `resolve_consecutive_scene_offsets` / `describe_scene_path_quality` 的**目标函数**：`path_consistency_weight`、`path_transition_max_penalty`、`path_backward_max_penalty`、`path_coarse_weight`、`path_local_weight`、`path_support_weight`、`path_transition_grace_seconds` 如何组合（DP / Viterbi？） | 复现"全局自洽"的路径选择（我们只有事后 temporal_repair） |
| 14 | `offset_refine_*` 与 `offset_refine_dtw_*` 的**默认值全集**（min_score / min_support / max_shift_seconds / max_shift_frames / sample_interval_seconds / start_window_radius_frames / start_window_min_improvement / topk_rerank_* ） | H4 的搜索窗与采纳门（我方 patch v2 是 offset≤30s + margin 门，需要对照） |
| 15 | `long_scene_{min_seconds,probe_window_seconds,probe_stride_seconds,max_keyframes,probe_base_rank,probe_base_score}` | 对应我方"蒙太奇子镜头查询"（已探针验证 16/16 救回，但 runtime 接入零变化）的阈值设计 |

## P2 — 运行期情报（最硬，需 VM；价值最高但成本高）

| # | 想要什么 | 用途 |
|---|---|---|
| 16 | VM 内用**同一四片素材**（`D:/video/1.mp4`+`2.mkv`、test1-3）跑一次竞品，产出：① 完整输出片段列表（含时间码）；② 缓存文件（`*scene_split_cache`、`scenes_file`、`frame_patches_offsets_path`、`sample_offsets_path`）；③ 日志（其中 `offset_refine_*`、`dtw_*`、`topk_*`、`commentary_scene_*` 的诊断字段通常会**直接打印实际取值**） | C1 端到端对标；日志能反推 P0/P1 的**真实取值**，比静态挖数值省力得多 |
| 17 | lease 后 dump 解密模型：a02 的 `image_size`（224/518？）与 a01 是否被等规模微调 | 校准我们的输入口径与特征语义 |
| 18 | Tauri 前端资源（HTML/JS）：`scene_sensitivity` 等 UI 设置的**取值集合与默认值** | UI 常把阈值直接写在 JS 里 |

## 方法论备注（给执行方）

1. **字符串池 vs 数值常量**：`data/sidecar_crypto_region_strings.txt` 是字符串；**数值**需要另挖（Nuitka 的 `PyFloatObject`/`PyLongObject` 常量区，或 `.rdata` 中的连续 8 字节 IEEE754）。
2. **优先级判断**：静态挖默认值很费劲；**P2#16（VM 跑一次 + 日志/缓存）通常能一次性给出 P0/P1 里的大半答案**，建议并行启动。
3. **证据等级务必标注**：符号名（存在性）/ 常量值（推断用途）/ 运行日志（实测）。不要把推断写成结论。
4. **交付形式**：在 `cutmatch-analysis` 侧新增 `FINDINGS/08_*.md` + 原始产物（dump 文本/JSON），benchmark 侧只读引用，不改动对方项目。
5. 已知可用的现成产物：`data/sidecar_crypto_region_strings.txt`（1 MB 字符串全集）、`sidecar_scene_model.txt`、`sidecar_transnetv2_keys.txt`、`sidecar_keymgmt_strings.txt`、`data/file_inventory.csv`、`data/cutmatch_module_map.txt`。

## 收到情报后我方会做什么（对应关系）

- P0#1/#3/#5 → 改造 H2（双头 + 白闪 + 帧差精修），四片回归；
- P0#2 → 改造 H1（短段合并 / 场景聚合），四片回归（**当前最高优先**）；
- P1#13/#14 → H4 探针的目标函数与门限；
- P1#9/#10 → H3（原片侧场景索引）设计；
- P2#16 → C1 端到端同口径对标（唯一能定论"他们好在哪"的路径）。

---

## 2026-09-26 增量需求 —— 按「定位层瓶颈」重排优先级（覆盖上文 P0/P1 次序）

> 依据（benchmark 侧本轮新增，均为可复算产物，非判断）：
> 1. `FINDINGS_METRIC_CALIBER_V5.md`：四片 139 例中运行期非 HIT = 22，机制分诊 = **口径 2 / 定位层 19 / 特征层 1**；
>    定位层 19 例的检索天花板 rank 全部 ≤7（17 例 ≤3）⇒ **缺口在"选时刻/选实例/查询单元"，不在特征容量、也不在切分**。
> 2. `FINDINGS_TRANSNETV2_SEGMENTATION.md`：**裸官方 TransNetV2 替换我方编辑侧两级切分 = 严格 −16（七组判据下 −16~−17）**
>    ⇒ 我方切分层不是当前主缺口；竞品能力若存在，应在**后处理/判据组合**与**候选生成→精修→路径选择**链路上。
> 3. `cutmatch-analysis/FINDINGS/09_CONSTANT_BINDING.md`（对方产出）：已确证 27 项绑定；**A1/A2 核心阈值家族仍未绑定**
>    （两张独立表，映射在机器码里，需读 co_consts 常量索引）。

### 一、最高优先（直接对应定位层 19/139）

| # | 需要的数据 | 现状 | 用途（我方缺口） | 取证路径 |
|---|---|---|---|---|
| N1 | `ordered_search_coarse_min_score` / `ordered_search_coarse_min_support_ratio` / `ordered_search_refined_min_score` / `ordered_search_consistency_min_score` / `ordered_search_candidate_margin` 的**默认值与作用阶段** | 未绑定（名字已见） | 14 例"池/选择"：候选**采纳门**决定"选哪个时刻/实例" | `fast_timeline/options` code object 的 co_consts 索引（09 §5 指定路线） |
| N2 | `offset_refine_*` **剩余项**：`enabled` / `max_shift_frames` / `max_shift_seconds` / `sample_interval_seconds` / `sample_points` | 已绑 6 项（min_score 0.55 / min_support 2 / dtw_max_samples 64 / dtw_min_score 0.1 / start_window_radius_frames 30 / start_window_min_improvement 0.04） | 我方 p30（差 8 s）、t2r03b（差 29 s）属"同场景内选错时刻"→ 需要其**搜索窗与采纳门** | 同上 |
| N3 | `offset_refine_dtw_topk_rerank_*`（`enabled` / `max_candidates` / `min_scene_coverage`）+ `actual_refine_min_score_gain` / `actual_refine_score_threshold` / `leading_score_gain_threshold` / `recovery_local_score_threshold` | 全未绑定 | 我方 A2 探针只测了"对齐分参与排序"（−）但**未测他们的门控版**（gain 门 + score 门） | 同上 |
| N4 | `select_scene_match_path` / `resolve_consecutive_scene_offsets` / `describe_scene_path_quality` 的**目标函数**：`path_consistency_weight` / `path_transition_max_penalty` / `path_backward_max_penalty` / `path_coarse_weight` / `path_local_weight` / `path_support_weight` / `path_transition_grace_seconds`；**是否 DP/Viterbi、代价单位（帧/秒）** | 未绑定 | 我方仅"事后 temporal_repair"；跨段全局自洽是唯一能同时纠正多例"同场景错时刻"的机制 | 同名 code object + 若不可得，退而求其次：`diagnostics` 文案/字段名反推 |
| N5 | `global_weight 0.45 / patch_weight 0.55` 的**融合形式**（加权求和？归一化？在门控前还是后？）与 `scene_top_k 10` / `global_top_k 100` / `min_candidate_margin 0.1` / `offset_bucket_seconds 0.5` 的**使用位置** | 值已绑（09 §4），**语义/位置未定** | 我方 patch 只做池内重排门控，**没有** patch×global 加权融合（竞品配方里我方完全没有的机制） | 反汇编该模块分支顺序；或用 `fast_timeline` 段日志模板交叉验证 |
| N6 | 两级采样的**组合规则**：`source_global_fps 0.1`（粗筛）与 `dense_sample_fps 10.0` / `commentary_sample_fps 3.0` / `balanced_coarse_sample_fps 5.0` 的**切换条件、窗口、步长**；`local_sample_fps`（强推断 0.1）的归属 | 值已绑，**组合未定** | 5 例"查询单元稀释"（运行期编辑段 ≥2× GT 段）；同时影响索引成本 | 读 `_count_*_windows` / `build_*_index` 系列 code object 常量索引 |

### 二、次高（切分侧：要"判据组合"而非模型）

| # | 需要的数据 | 现状 | 用途 |
|---|---|---|---|
| N7 | `commentary_short_scene_min_frames = 180` 的**真实语义**（方向/单位/生效阶段/是否只在精修后合并） | 值+绑定已确证，**语义未定论**（按字面合并实测灾难：GT 覆盖 .862→.172） | H1 粒度层唯一未解项 |
| N8 | A2 多判据的**组合方式**：`visual_score_min` / `visual_strong_score_min` / `visual_peak_ratio_min` / `structure_distance_min` / `structure_strong_distance` / `motion_ecc_similarity_max` / `motion_histogram_distance_max` / `flash_luminance_min` / `flash_luminance_jump_min`——**谁是硬门、谁加分、先后顺序、是否有投票/加权** | 全未绑定 | 我方已有 TW 双头与白闪守卫，缺的是**判据编排** |
| N9 | A3 几何剩余：`commentary_scene_descriptor_width|height` / `move_radius_frames` / `candidate_snap_radius_frames` / `visual_context_frames` / `min_side_frames` / `max_additions_per_segment` / `prediction_support_radius` | 部分（proxy 96×54 已得） | 边界吸附/上下文窗口径 |
| N10 | A4 边界精修剩余：`min_segment_frames` / `min_side_frames` / `near_cut_frames` / `max_move_frames` / `absolute_diff_min` / `mad_multiplier`；并**复核我方 A7 临时绑定**（32/10/16/45.0/4.0/16/1） | 部分 | 帧差精修口径 |
| N11 | A6 开关：`use_scene_proxy` / `fast_hwaccel_enabled` / `boundary_backshift_enabled`+`max_seconds` / `commentary_scene_refine_enabled` / `runtime_vision_vits14` | 部分 | 是否走 proxy 决定"224 为何够用"（我方实测 518 更强） |

### 三、原片侧（H3）与产品面

| # | 需要的数据 | 现状 | 用途 |
|---|---|---|---|
| N12 | `build_scene_feature_index_{standard,low_memory,streaming}` 的粒度/特征来源/维度/fps；`save_fast_global_index` / `load_fast_global_index` / `build_source_timeline_index` 参数；`local_global_similarities` 融合公式 | 部分（source_global_fps 0.1 / global_weight 0.45 / scene_top_k 10 / global_top_k 100） | H3 原片侧索引设计 |
| N13 | `detect_scene_ranges_with_backend` 的 backend 选择逻辑（CUDA-only？有无 CPU/DML 回退） | 未得 | 商业面差异（我方 H2 = DirectML 已跑通） |
| N14 | 导出层字段与时间码精度（`exporting/segments/builder.py` / `timing/video_timing.py` / `jianying/fcpxml_generator.py` / `premiere/xml_generator.py`），是否携带场景 id / offset | 未开始（任务 D） | 产品对齐（我方导出验收已有 PR CEP 通道） |
| N15 | UI 侧 `scene_sensitivity` 等设置的取值集合与默认值 | 未得 | 校准默认档位 |

### 四、运行期（唯一能定论，当前被授权挡住）

| # | 需要的数据 | 阻塞 |
|---|---|---|
| N16 | 同四片素材跑一次的产物：① 片段列表（含时间码）② 缓存（`*scene_split_cache` / `scenes_file` / `frame_patches_offsets_path` / `sample_offsets_path`）③ 日志中 `offset_refine_*` / `dtw_*` / `topk_*` / `ordered_search_*` / `commentary_scene_*` 的**实际取值** | 用户本机实测"需卡密"；且模型走服务器 lease（a01/a02 为 AES-256-GCM 密文，密钥由服务器 P-256 ECDH+HKDF 下发）⇒ 即使绕过授权也拿不到模型 |
| N17 | lease 后 dump：a02 的 `image_size`（224/518）；a01 推理路径（`_convert_scene_runtime_tensor_runtime_weights` 作用）是否与我们本地官方权重一致 | 同上 |

> **N16 仍是性价比最高的一项**：一份运行日志通常能一次性给出 N1–N6 的大半实际取值（诊断字段会打印实际生效值）。
> 若运行期确认不可行，请只在 `FINDINGS/09` 续写常量索引结果，不必重复尝试运行路线（任务 E 可一并回填该结论）。

### 五、明确**不再需要**/降级

| 项 | 原因 |
|---|---|
| TransNetV2 权重、模型识别、a02 是否微调 | 已确证（官方权重 SHA256/元素数逐位一致；我方 ONNX 对拍 6.1e-8） |
| `feature_image_size = 224` 的**取值** | 已实测对照：518 在 4/5 难例更强（p08 兄弟机位 −0.157）⇒ 需要的是**预处理/代理口径**（N11），不是数值本身 |
| 单看 `dual_single_min / dual_many_min / dual_combined_min` 三值 | 我方 A1 已证"裸 TN 判据替换更差"；单值价值低于**组合方式**（N8） |
| 竞品功能面清单（06 Q4） | 与当前瓶颈（定位层）无关，降为 P2 |

---

### 2026-09-26 02:20 回执 —— 对方 09 增量版已收到并复核（我方独立读字节）

**已闭环**

| 需求 | 状态 |
|---|---|
| N10 边界精修（`commentary_boundary_refine_*»） | ✅ **完成**：7 项全部字节确证（32/10/16/45/4/16/1），且**与我方 A7 临时绑定 7/7 一致** → A7 由"强推断"升为"确证" |
| N3 门控（部分） | 🟡 **部分**：`offset_refine_dtw_topk_rerank_max_candidates=10»、`..._min_scene_coverage=0.8»、`actual_refine_score_threshold=0.65»、`ordered_search_max_seconds=1800.0»（**2026-09-26 更正：原 7200 系相邻配对假象**）；仍缺 `*_enabled»、`actual_refine_min_score_gain»、`leading_score_gain_threshold»、`recovery_local_score_threshold» |
| N11 proxy | 🟡 部分：96×54 已确证；`use_scene_proxy»/`fast_hwaccel_enabled» 未得（且对方已警告 `runtime_vision_vits14→224» 为**伪绑定**，我方复核成立） |
| N7 `180» 语义 | ✅ **结论确定**：`_scene_range_fps» 在数据段**无字面值**（3 处出现紧随均非数值）⇒ 静态不可判定；我方已把"6 s @30fps"降为**假设** |

**新增/细化的请求（按价值排序）**

1. **`actual_refine_score_threshold = 0.65» 的归属 profile**：其字节邻域全是 `balanced_*» 限定名（`balanced_actual_refine_margin_seconds» 等）
   ⇒ 请确认它属**默认 profile** 还是 **balanced profile**（能否直接用作默认门）。
2. **`select_scene_match_path» / `path_*» 目标函数**（N4，保留最高优先）：定位层 19/139 的机制性解药是"跨段全局自洽"。
3. **`ordered_search_*» 全部**（N1）：候选采纳门；对方自述这些是 code object 常量索引可达、数据段不可达。
4. **各类 `*_enabled» / gain 门**（N3 残留）：`offset_refine_enabled»、`..._dtw_topk_rerank_enabled»、`actual_refine_min_score_gain»、
   `leading_score_gain_threshold»、`recovery_local_score_threshold»。
5. **A1/A2 阈值家族 + 组合方式**（N8，保留）：我方已证"裸 TN 判据硬替换更差"（七判据 −16~−17）⇒ 需要的是**编排方式**，不是单值。
6. **`_scene_range_fps» 的值**：静态确认不可得 ⇒ 只能靠**运行日志**或 code object 常量索引。

**我方承诺**：对方产出的每一项，我方都会像本轮一样**自己再读一次字节**（脚本 `mvp/scripts/verify_cutmatch_bindings_v2.py»）
后再写入结论；凡未复核的一律标注"未核实"。09 §9 的自述与我方复核一致。
---

### N18（2026-09-26 追加，最高优先）—— 竞品**成品**运行期取证：可行性判断 + 交付清单

**为什么现在问**：我方已完成四片基线（严格 117/139 · 场景 137/139 · 负例 4/9）与三轮对标（A1 切分替换 −16、A2 对齐排序、
B patch×global 融合探针）。**唯一从未做过的事 = 跑他们的成品**：我们所有结论都建立在"用他们的原料（TN 权重 / 常量值）做的重建"上，
所以"竞品端到端到底更准在哪"在我方档案里至今是 **未测**。若你那边授权/模型有进展，这一条第一次变得可测。

**§1 先回一个判断性问题（决定后面全部）**
- 现在是否**已有可用授权**（正版/试用）能让他们产品正常启动并跑完一次分析？
  - 有 → 按 §2 取证（最高价值）；没有 → 只回报"授权状态 + 你判断的可达路径"，不要为此额外投入，我们走 §3。

**§2 若运行期可行：请在我方四片（与 benchmark 同源）上跑一次**
素材：\`D:\video\1.mp4\` + \`D:\video\2.mkv\`；\`D:\ProjectXIXI\test1|2|3\` 的 ed/om（若只支持单原片，先跑 1.mp4+2.mkv）。
按价值排序的交付项：
1. **他们的镜头/场景切分列表**（编辑片每条起止时间码 + 类型）——**唯一能与我方边界做真值级几何对照**的东西；
   JSON/CSV/剪映草稿/PR XML/缓存文件皆可，UI 列表截图也行。
2. **定位结果**：每条编辑片段的原片起止时间码 + 置信/评分（若有）。
3. **缓存/中间产物**：\`*scene_split_cache\` / \`scenes_file\` / \`frame_patches_offsets_path\` / \`sample_offsets_path\` 等（按实际文件名）。
4. **日志**：含实际生效值的字段（\`commentary_scene_*\` / \`offset_refine_*\` / \`dtw_*\` / \`topk_*\` / \`ordered_search_*\`）
   —— 这一项能一次性补上我方 N1–N6 的大半实际取值。
5. **导出文件**（剪映草稿 / PR XML）—— 对齐"用户可见的切分与时间码精度"。

**§3 若运行期仍不可行：请优先这两条替代**
1. **解密模型本体**（a01/a02 或任一推理期可用权重/ONNX）→ 我方可在本机复现他们的场景切分与特征栈，
   用自己的四片做几何对照。**比常量值有用得多**（常量只能当先验，模型能当对照组）。
2. **任意素材的产品输出样例**（截图/导出即可）→ 只能定性对照粒度与切分风格；此类证据我方只写"观察"，不进指标。

---

### N18 补充登记（2026-09-26 续8）—— `D:\dsh-work` 授权逆向工作区：存在确认 + 处置口径（**不推进绕过**）

- **存在确认**：`D:\dsh-work\` 为竞品**授权体系逆向**工作区（与 `cutmatch-analysis` 的 B/D 段产物不同源）：
  静态还原（Tauri 外壳 + Nuitka sidecar / 授权服务器 `https://401.cutmatch.com` / ECDSA P-256 验签 / TPM 设备绑定 /
  `license-v2.json` 状态文件）+ 一次动态验证（注入 `AUTOCLIP_LICENSE_SERVER_URL` 等环境变量启动竞品、扫运行内存、
  本地 8765 观察端仅收到 1 次 `/_selftest`）。
- **核心发现（仅作情报记录）**：竞品发行构建保留调试覆盖通道——授权服务器地址 / 验签公钥 / 签名强制开关
  **三要素均可被环境变量或程序目录文件覆盖**，Tauri 外壳不过滤、原样透传给 sidecar；授权服务器缺省回退 `127.0.0.1:8765`。
- **对我方既有论据的影响**：N16 的技术论据「即使绕过授权也拿不到模型」**不再可靠**（验签公钥可被替换 ⇒ 信任链根可被接管）。
- **处置口径（维持 2026-09-26 拍板）**：**不绕授权**——不定位门禁机器码、不搭伪造授权服务器、不验证状态文件伪造、
  不完成其"破解待办清单"任何一项。规避他人商业软件技术保护措施不做；与可行性无关。
  （2026-09-26 用户复核：不引申任何衍生动作，此条仅作存在与边界登记。）

**§4 我方收到后的口径承诺**
- 切分几何：用人工/多模态标注的**真切换**做 precision/recall（我方边界 vs 他们的边界），给出双向数字；
- 定位：把他们的定位结果套进**我方评估器**（同 GT、同 \`measure_shot_recall\` 口径），与我方 117/139 直接对照；
- 所有外部数据**独立复核后**才写入结论，未复核的标注"未核实"。

---

### 2026-09-26（续）回执 —— B 段（代理复现场景切分）判卷侧复核完毕：**我方撤回 2 条旧异议 + 认下 1 条裁决 + 2 条文档订正**

> 完整报告：本仓 `user_case/competitor_cutmatch/FINDINGS_PROXY_B_STAGE_REVIEW.md`（含几何对照全表、盲判抽检、自证数据）。

**A. 我方撤回的两条旧异议（本轮自证，根因在我方读法，不在你们的文档）**

| 旧异议 | 本轮自证结论 | 证据 |
|---|---|---|
| `source` 指针「粒度不可独立复现」（我方按 `@0x174e0158#116` 这种**序号**形式找不到 `8`） | **撤回**。profile v2 的约定就是**字节偏移**（`key_off`/`val_off`/`raw`）；我按此写独立验证器，对 162 条：**raw 162/162 逐字节一致**、数值自证 162/162、**名表↔值表名次零颠倒**（3 个 blob：95/61/6 条）⇒ 顺序映射成立且**可独立复现** | `mvp/scripts/verify_cutmatch_profile_pairing.py` → `work/verify_cutmatch_profile_pairing.json` |
| `offset_refine_dtw_min_score` 0.1 vs 0.55「内部不一致」 | **撤回，0.55 成立**。`val_off 0x174e18c8` = `66 9a 99 99 99 99 99 e1 3f` = **0.55**；**0.1 属邻键 `offset_refine_dtw_sample_interval_seconds`**（`0x174e18d1`，紧邻 +9 字节）；我上轮引的 `0x174e04c1` 在**另一个区域**，其后紧跟 `T 01 aoffset_refine_dtw_sample_interval_seconds` ⇒ 是早期「相邻配对」取到了邻键值位。你们 `FINDINGS/09` §296 与 `FINDINGS/10` §247 早已订正为 0.55 | 同上脚本 "争议常量" 段 |

**B. 我方认下的裁决：`test1-om.mkv` 锚点 197,305 → 197,106**

我用**自己的 ffprobe**（`-count_packets`，与你们不同的调用路径）独立数了 6 片：1.mp4 3,677 / 2.mkv 183,837 / test1-ed 4,070 /
**test1-om 197,106** / tset2-ed 2,083 / test3-ed 4,357 —— 与你们 `frame_counts.json` **逐片一致**。
⇒ 两条独立工具链同结论，**以 197,106 为准，不要求重跑该片**。

**C. 我方独立复核确认的三件事**

1. **模型字节级同一**：你们 manifest 的 `model_sha256 c4d54a68…8e0c` = 我方导出 `work/transnetv2/probe_transnetv2.onnx`（31,250,929 B）的 SHA256，**逐字符一致**。
2. **三处规范偏差全部认可**，其中「raw 0..255 而非 /255」**是我方任务书笔误**：我方 `mvp/scripts/tn_transnetv2.py` 第 11 行输入约定原文即「值域 0-255(RGB)」，你们的实测纠正与我的实现一致。
3. **双实现交叉验证（本轮最有价值的一条）**：同一 ONNX、**互不共享后处理代码**的两条实现，在 ±0.5 s 内
   **test1 32/32、test2 65/66（98.5%）**覆盖，2mkv 67/76、test3 84/93，中位距离 **0.10–0.17 s**
   ⇒ 你们 B 段链路**可信**，后文差异可归因到切分策略而非复现走样。

**D. 几何对照主结果（我方现行生产切分 vs 你们四阈值切点；切点=段 start，±0.5 s）**

| 片 | 0.3 | 0.4 | 0.5 | 0.6 | 画像 |
|---|---|---|---|---|---|
| 2mkv（1.mp4） | 仅代理 12 / 仅我方 3 | 12 / 4 | 11 / 8 | 9 / 8 | 混合 |
| test1 | 2 / 7 | 1 / 7 | 1 / 7 | 1 / 7 | **我方过切** |
| test2 | **13 / 0** | 13 / 0 | 13 / 0 | 13 / 0 | **我方漏切（四阈值全稳）** |
| test3 | 34 / 3 | 31 / 4 | 27 / 6 | 23 / 8 | 我方偏粗 |

代理侧阈值稳定性：test2 **100%**、test1 97.1%、2mkv 80.5%、test3 77.5%。
盲判抽检 6/44：**4 例双方都是真切换**（相邻两真切换各选其一）⇒ 分歧主机制是**粒度**，不是任一方造假切点。

**E. 两条文档订正（小，但会制造复现噪声）**

1. **profile 1/162 名字不符**：`/feature_extraction/image_size` 的 `key_off 0x174bc0cd` 解出的是 **`feature_image_size`**（值 224 正确）⇒ 请订正键名或指针。
2. **`197,305` 还有四处未同步**：runbook §5.1 表（帧数列）、`PROMPT_FOR_EXECUTOR.md` 帧数清单、`sandbox/run_scene_split.py` `ANCHORS`、`sandbox/verify_proxy_output.py` `ANCHOR_ORDER`
   ⇒ 不一起改，下一轮复现会继续报 FAIL/停跑。另：`FINDINGS/09` §82 那张旧表行建议标注「已被 §296 取代」（我方上轮就是踩了它）。

**F. 下一步（D 段）**

我方接收侧**已就绪**、等产物即可开跑：`mvp/scripts/import_competitor_proxy.py --loc <localization.json> --case <2mkv|test1|test2|test3>`
→ `work/proxy_<case>.results.json`（我方 results schema）→ `mvp/scripts/measure_four_results.py` 同 GT 同口径对照（基线 严格 117/139 · 场景 137/139）。
D 段请按你们 §4.1 的分步落盘走；**AKAZE on/off 两版都要**（N18-2 硬要求）。

**G. （同日追加）我方对 44 个分歧切点做了逐张盲判（44/44，判卷侧读图 + 帧差旁证）**
- **你们的 29 个独有切点，读图下 0 个是假切点**（27 真 / 2 未定），且 44/44 例都落在跨点帧差峰上（r 中位数 3.10）
  ⇒ **你们多出来的切点是「更细」，不是「切错」**，与 §4 双实现交叉验证互相印证。
- **我方有 6 处假切点**（test1 2.53 / 44.73 / 73.93、2mkv 113.17、test3 49.14 / 27.79），机制 = 镜头内运动 / 字幕换行诱发的 CLS 距离峰；
  我方 44 例中有 14 例不在跨点帧差峰上（你们 0 例）。**test2 我方零假切点、但整段漏切 13 处**。
- 请 D 段照原计划推进；另：若你们的 TN 后处理里 **trim 25:75 + group_midpoint + min_gap 8** 有更细的说明（例如 group 合并的判定边界、是否用 many_hot 通道），
  欢迎一并给出 —— 我方正在评估「输出/展示层换更准切点」的可选方案，这一项直接影响输出粒度。
- 明细：`work/proxy_blind_disputes/verdicts_44.csv`、`frame_diff_sidechannel.json`。

---

### 2026-09-26（续二）回执 —— 11 已收到并**做到逐帧级复现**；附 D 段提示词复核意见（P0 7 条）

**A. 我方独立重放你们的后处理规则 = 24/24 逐帧完全一致**

我用你们的 `sandbox/out/*.probs.npy` 自己实现了一遍后处理（只读，未改你们任何文件），在 **6 片 × 4 阈值 = 24 组**上
**切点集合逐帧 100% 一致**，`groups_t*.json` 也 **24/24** 一致。你们的「trim/stride 互补、无内部空洞」也独立验证通过（6 片覆盖区间内部 NaN 全为 0）。

**B. 11 §3 的「未知 1/2」已被解掉（请改等级）**

| 11 的未知 | 实际规则（我方复现确证） |
|---|---|
| 1. 组中点取整 | **上取整**：闭区间 `(a+b+1)//2`（等价 half-open `(s+e)//2`）；下取整只能复现 10/24 |
| 2. min_gap 保留谁 | **都不保留**：按「**切点之间**间距 < 8」**迭代**合并（会级联），最后取**合并后跨距的中点**（同样上取整） |
| 3. sensitivity | **不参与切点生成**（我完全没用它也能 24/24）；是否作用于别处仍未知 |
| 4. many_hot 展示层 | 未触及（B 段无展示层产物） |

> 上面两条是"按 group 空隙贪心合并"实现不出来的（那种只能到 18–22/24），差别就在**判据是切点间距**且**迭代**。

**C. 关于 11 §4 的「峰值检测更稳」：本批材料上不成立（实测）**

我按你的建议实现了「`prob > th` 且 k 邻域局部极大 + min_gap 去重」，结果是**切点数与你们交付的 0.50 档逐片相等**
（2mkv 71 / test1 34 / test2 66 / test3 87），th=0.3 时等于 0.30 档（77/35/66/97）。
原因：你们的激活组**绝大多数是单帧**（0.50 阈值下多帧组占比 ≤7%，test1-ed/test2-ed 为 0%），**组中点本身即局部极大**。
⇒ 真正的自由度是**阈值**与**min_gap**，不是取点方式（取整/合并规则我这边已可复现，不需要额外自由度）。

**D. 「输出层换切点」我方探针结论（供你们参考，不要求动作）**

把 `probs.npy` 拿来打我方现行切点（锚点 = 已裁决 44 例）：

- 我方 **6 处已裁决假切点**在 TN 概率上**既不是峰也没有值**（0.0001–0.021）⇒ 用 TN 概率口径换切点会**天然剔除这 6 处**；
- 但我方**已裁决为真的 29 处切点**在 TN 概率上也**不是峰**（中位数 0.0012）——因为盲判已证它们与你们的切点**相距 0.6–5.0 s、是另一处真切换**；
⇒ 因此**「换切点」≠「替换」，而是「并集 + 仲裁」**（这与我方 A1 实测「直接换成 TN 切分 → 严格 117→101」方向一致）。

**E. D 段提示词复核 = 认可执行，但请补 7 条 P0**

完整意见见本仓 `user_case/competitor_cutmatch/REVIEW_PROMPT_FOR_EXECUTOR_D.md`（可直接转给执行对话）。摘要：

1. **每段一行，含未匹配行**（我方 GT 有负例，只交命中行会让 FP 不可比）；
2. 每条给 `query_id` + 对应 B 段 `scene_index`；
3. **时间码双写**（ed/om 各自 `frame` + `ms`，用各自 `fps_rational`）；
4. **候选表落盘**（top-k + score + 通道）——我方 19/139 的瓶颈是"池内选错/未进池"，只看 argmax 无法分诊；
5. **`ordered_search_max_seconds=1800.0`（**2026-09-26 更正：原 7200 系相邻配对假象**） 的适用性说明**：本次 **4 部原片全部超过 1800 s**（2.mkv 7667 / test1-om 8229 / test3-om 10177 / test2-om 5051），若实现做截断会系统性漏掉尾部 = 最大假差异源；
6. AKAZE/RANSAC 固定 seed + 重复跑一致性；
7. 原片侧索引口径明写（我方现行 `index_sampling_fps=1.0`，与竞品 `source_global_fps=1.0` **同档**，无需额外对齐）。

另有 5 条**口径混杂因素**必须登记（224 vs 我方 518 / 编辑侧 2fps 均匀 vs 你们 5 关键帧每场景 / 候选池 28 vs 100+20 / AKAZE 我方无此通道 / GT 与判据）——见该文件 §2。

---

### 2026-09-26（续三）回执 —— D 提示词 v2 已核对；**你们纠正了我方一处错记录（7200 → 1800.0）**，我方独立字节复核确认并已全面更正

**A. 我方撤回并更正：`ordered_search_max_seconds` 默认值 = 1800.0（不是 7200）**

| 量 | 值 |
|---|---|
| profile v2 条目 | `/fast_options/ordered_search_max_seconds` = **1800.0**（`level=确证`） |
| 键偏移 | `key_off 0x174bc26a` → 解码即该键名（名字自证通过） |
| 值偏移 | `val_off 0x174bcc1f` → raw `66 00 00 00 00 00 20 9c 40` → **1800.0** |
| 名次配对 | 同 blob 内 名表名次 = 17，值表名次 = 17（同序） |
| 我方旧读数 | `verify_cutmatch_bindings_v2.py` §8.2 读到的 7200.0 实际是**键名之后的相邻字节**（其后紧跟下一个键名 `min_supp…`）⇒ **相邻配对假象** |

⇒ **我方错、你们对**。已把**全部历史相邻绑定**与 profile v2 的 `val_off` 值做系统对账（脚本 `mvp/scripts/reconcile_cutmatch_bindings.py`）：**11 条里只有这 1 条真错**，其余 10 条一致
（其中 `commentary_boundary_refine_max_move_frames` 的 `<<PREV>>` 解析后 = 前一条 `..._near_cut_frames = 16`，与我方读数相同）。

**风险重估（比 v1 更严重，故 v2 的处置我方完全同意）**：上限 = **1800 s = 30 min**，四部原片**全部超限**：
2.mkv 7,667 s / test1-om 8,229 s / test3-om 10,177 s / **test2-om 5,051 s**（v1 按 7200 估时它被误判为"安全"）。
⇒ 请务必在 manifest 写明「是否生效 / 按段还是全局 / 超限如何处理」，**建议不施加全片上限**。

**B. 我方档案内的 7200 已全部更正**（`INTEL_REQUESTS` §8.2 / `FINDINGS_CUTMATCH_CONSTANTS_ADOPTION` / `.agent/STATE.md` / `.agent/TODO.md` / `.agent/CHANGELOG.md`），并记录方法论教训：
`FINDINGS/09` 式"键名相邻字节 = 该键的值"在 Nuitka 常量块里**不可靠**（键名表与值表分离 + 存在 `<<PREV>>` 复用），迄今已造成 **3 例**取值归位错误（0.1/0.55、180/8、7200/1800）。
我方今后统一走「`key_off`/`val_off` 字节偏移 + 名字自证 + 名表↔值表名次配对」。

**C. v2 的 7 条 P0 + 5 条 P1 = 判卷侧确认收到并认可**；完整逐条回执见本仓 `REVIEW_PROMPT_FOR_EXECUTOR_D.md`。

**D. 新增 1 条待澄清（P0-8，不阻塞开跑）**：profile v2 里 `source_sample_rate` = **2**、`commentary_sample_rate` = **2**（`<<PREV>>` 语义），
与 `fast_options.source_global_fps = 1.0` 并存。请说明这两个 `*_sample_rate` 的**单位与作用阶段**（帧步长？采样频率？是否只作用于 precise 阶段？），
并在 manifest 写明 D 段实际用了哪一个 —— 它直接影响"查询帧密度"与"源侧候选密度"，是继 `ordered_search_max_seconds` 之后第二个会制造假差异的口径项。
