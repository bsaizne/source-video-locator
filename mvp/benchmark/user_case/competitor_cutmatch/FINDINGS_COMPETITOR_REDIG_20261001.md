# FINDINGS — 竞品全量重挖（函数级 varnames + 内联常量）× 精度机制总账（2026-10-01 续37）

> **GT 版本**：v4 + test1/2/3（2026-09-30 重锚定后），基线 = `work/spl_patch_arms/on_*.results.json`
> （两旋钮开，严格 132 · 导出实得 119 · 场景 137 · FP 4）。
> **触发**：用户令「重新挖竞品，全部挖干净」。
> **方法**：不复用旧摘要，把 62 个算法相关模块（`cutmatch.matching.*` + `exporting.segments/timing`，9,850 个常量）
> 逐值转储为文本（`work/cm_redig/dump_blobs.py` → `work/cm_redig/cutmatch.*.txt`）逐个读完。
> 此前 FULL_SWEEP 只用了 docstring + dict 常量；本轮新增两类证据：**每函数 co_varnames 元组**（揭示函数内部变量 =
> 算法结构）与**函数内联数值常量**。纪律不变：只读静态常量，不运行竞品、不碰授权/受保护模型。

## 0. 结论

**竞品侧已无可挖的精度杠杆。** 全部精度相关机制已逐条对账：要么已移植在跑，要么已实测关闭，要么我方有等价物。
本轮新发现 3 项从未测过的差异，全部当场实测：**两项净零、一项净负**。

| 本轮新测 | 竞品证据 | 实测 | 判定 |
|---|---|---|---|
| ① 主 span 改为「1× 等长 + 整段偏移对位」锚定（竞品 `results._segment_payload` / `models._anchored_segment_parts`；我方 seq_align 是峰帧 ±1s） | varnames `start_src/count/flip/speed_percent=100`、`anchor_offset/preferred_start` | 导出实得 119→**119**（+4 −4），严格 132→132，FP 4→4 | 净零，关闭 |
| ② 编辑帧裁黑白边后再提 DINO（`frame_reader._clean_frame_for_features`：gray→inRange(9,246)→boundingRect，内容区<0.4 不裁） | 内联常量 9/246/0.4 + docstring「裁掉稳定黑白边」 | 只影响 2mkv（1.mp4 上下黑边约 24%，其余 3 片 0~1 帧被裁）；检索层 top1 25→23 / top5 29→31；**生产路径端到端 2mkv 严格 37→36、导出 34→33、场景 39→38**（p08、p36 回退） | 净负，关闭 |
| ③ patch_refine「窗内峰位移」（`local_refiner.score_start` 窗内移动起点） | varnames `score_start/starts/global_ranked/deduplicated_patch_starts` | 导出 119→119（两形态） | 净零，关闭（见 CHANGELOG 续37 后续） |

## 1. 精度机制总账（竞品默认 = `standard` 精确管线；`fast` 为可选）

| 竞品机制（模块） | 关键参数（字节/内联确证） | 我方对应 | 状态 |
|---|---|---|---|
| 场景切分 TransNetV2 + 解说帧差复查 + 短镜合并（`scene_detection.*`、`boundary`） | 48×27 / 100 窗 / 50 步；96×54 帧差、abs≥45、MAD×4、≤16 帧移动、补切≤1；短镜<8 帧并邻 | CLS 两级切分 + card/flash guard | 换切分 −16、TN 仲裁、查询单元换竞品切点 −10：**已关** |
| 特征 DINOv2 ViT-S @224 INTER_AREA（`extractor`） | image_size 224 | @518 INTER_LINEAR | 224 vs 518 探针 518 胜：**已关** |
| 场景关键帧 5 + 长镜头自适应（≥6s 每 1s，≤16）（`sampling`） | 5 / 6.0 / 1.0 / 16 | 1fps 逐帧索引（密度更高） | 我方更密：**无需** |
| 长镜头局部 probe（3s 窗 / 1.5s 步 / ≤16）（`retrieval`、`sampling`） | 3.0 / 1.5 / 16 | 1fps 逐帧检索天然覆盖 | **等价** |
| global×0.45 + patch×0.55 全库融合检索（`retrieval`） | 0.45/0.55，scene_top_k 20(精确)/10 | CLS 检索 + 局部 patch 精排 | 全库融合判负（PATCH_FUSION）；局部形态已在 patch_refine：**已覆盖** |
| patch 聚合 = 每 query token 最佳源相似度，取 top-16 均值（`similarity`、`geometry`） | 16（224 → 256 token） | top-100（518 → 1369 token） | 比例 6.3% vs 7.3%，**同口径，非差异** |
| 镜头路径 DP + 倒退罚（`timeline.select_scene_match_path`） | loose 2 / normal 5 / strict 10 | 无 | DP 下沉 −8、时间轴单调性：**已关** |
| 镜头内 offset：关键帧锚点对 + 子序列 DTW（0.1s 采样 ≤64）+ 开场窗 ±30 帧（`offset_refiner`、`dtw`） | 0.55 / 2 / 0.03 / 64 / 30 / 16 / 0.04 | seq_align 单调 DP + 8fps 密帧 | 等价物在跑；DTW 作排序判负（A2）；本轮①偏移锚定净零 |
| 可疑段 TopK DTW 复查（覆盖<0.8 / 锚点弱）（`offset_refiner`、`continuity`） | top10 / cov 0.8 | patch_refine top-K 候选局部精排 | **已覆盖** |
| 连续同源镜头起点去重（`resolve_consecutive_scene_offsets`） | — | `consecutive_offsets.py` | 移植实测无收益 +1 回归：**已关** |
| 入点后移 1 帧（`boundary_refiner`） | 160 宽灰度，≤2 帧 | 无 | 97.4% 边界位移 ≤4 帧，秒级口径不可测：**已关** |
| 结果片段：锚点 1× + ±10% 变速补齐 + 同镜合并（`results.models`） | 90/110 | 主 span 直出 | 本轮①净零；变速补齐属导出体验 |
| 结果验证门（覆盖 / 重复率 0.8 / 单帧碎片）（`validation`、`segments.builder`） | 0.2 / 0.8 | degradation_gate + LOC-2002 + 单帧守卫 | 拒识形态 −2：**已关**，提示形态在跑 |
| 特征帧裁黑白边（`frame_reader`） | 9 / 246 / 0.4 | 无 | 本轮②净负：**关闭** |
| 局部特征 AKAZE/ORB + 单应（`local_matcher`、`geometry`） | 0.78 / 内点×3 | 无 | 只服务旧候选召回，V2 runner 不导入；2026-09-01 探针证伪：**已关** |
| **fast**：3fps 解说采样 + 质量权重（`commentary_sampler`） | 内联 128/0.15/5/80/250/120/0.2/48/0.25/180/0.45/0.3 | `fast_global_quality_weights_enabled` | 严格 −10：**已关** |
| **fast**：0.05s 分桶偏移投票（`coarse_retrieval`） | top10/样本，dispersion 0.35 | `offset_vote_prior`（fast_global 默认开） | **在跑**（+2） |
| **fast**：局部 3fps 序列精排 + 单调性（`local_refiner`） | 0.7/0.3 预筛 top3，0.65/0.35 融合 | patch_refine | 本轮③净零 |
| **fast**：顺序检索 / 两遍 DP + 恢复候选（`ordered_search`、`path_selection`） | 300/315/15/1800s；penalty ÷25 | 无 | M0 判负 / DP −8：**已关** |
| **fast**：10fps 密集起点 + 实际帧复核（`dense_alignment`） | 0.65/0.35，early 线权 1.5，±0.2s | `dense_start_check`（默认关） | 生产零增益：**已关** |
| **fast**：开头串镜 / 尾部硬切守卫（`boundary_guard`） | ≤2s，MAD 8/4，0.5/2.2 | `snap_clips_to_scenes` ±1s + `split_clips_at_boundaries` | 秒级口径内：**部分等价** |
| **fast**：四项加权置信（`confidence`） | 0.3/0.4/0.2/0.1，门 0.6 | conf_v2 通道 | 信号饱和、靶子是假的：**已关** |

## 2. 为什么挖不出东西了（机制层解释）

- 竞品两条管线的精修全部建立在同一组信号上：**DINOv2 CLS/patch 余弦 + 时间对位**。我方同样用了这组信号，
  而且检索密度更高（1fps 逐帧 vs 每场景 5 帧）、输入分辨率更高（518 vs 224）。
- 剩余 20 行导出缺口里，凡是竞品命中、我方没中的（7 行），读图都落在「同场景时刻偏几秒 / 暗景」这一族。
  三种不同的时刻锚定形态（窗内峰、整段偏移对位、1× 起点）结果都在 119 附近来回交换，说明这族的上限
  是**特征判别力**，不是锚定方式。
- 竞品全库 9 条 GT 从未进入候选表，我方只有 1 条 rank>20；全集独家命中我方 43 行、竞品 7 行。

## 3. 产物

- 转储脚本 / 全量文本：`work/cm_redig/dump_blobs.py`、`work/cm_redig/cutmatch.*.txt`（62 模块）
- ① `work/cm_redig/probe_offset_anchor.py`、`work/cm_redig/offset_anchor/`、`probe_span_anchor.py`
- ② `work/cm_redig/probe_crop_signal.py` + `crop_signal.json`；端到端 `run_crop_e2e.py` → `crop_on_2mkv.results.json`（1573s，DML）
- 零 `mvp/src` 改动；`feature_version` 零变更。
