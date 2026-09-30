# FINDINGS — 精修/展示层语义挖掘突破：Nuitka 常量 blob 内嵌中文 docstring（2026-09-26 续10e）

> **触发**：用户拍板「竞品文件数据都有，为什么不去全局搜索精修和展示层」+「自己挖，死命挖」（续10d 后追加）。
> **方法**：不等执行方机器码专项（09 §8.5 / N1-N8）——直接全局搜索执行方已交付的逆向数据
> （`cutmatch-analysis/data/`：option_catalog 1563 键 + profile v1 943 条 + nuitka_blobs.json 282 个解码 blob
> + param_values/dict_bindings/n_list_bindings + 137 模块清单）。
> **突破**：**Nuitka 把每个函数的中文 docstring 原样编进了常量 blob**——不需要机器码反汇编，
> 函数级语义（含公式形状、阈值、判据）直接可读。此前「N1-N8 静态不可得」的判断**过于悲观，本文件正式推翻**。
> **边界维持**：只做静态常量/字符串分析；不绕授权、不解密受保护模型（a01/a02 走服务器 lease，2026-09-26 拍板不变）。

## 0. 一句话结论

**精修链和展示层的语义全部可读**：竞品的"锚不准"问题（本轮五环探针实测的瓶颈）由**至少 6 层精修机制**治理
（路径 DP 罚项 / 连续偏移修正 / 密集 10fps 起点复核 / 局部 3fps 精排 / 开头串镜守卫 / 尾部硬切回退），
其目标函数权重与全部阈值均已字节级确证；展示层 = 真实转场切点在剪映/PR 时间线展开 + 单帧片段稳定性检查。

## 1. G5 真实语义（此前推断级近似的正确形式）——`alignment/timeline.py` + `fast_timeline/path_selection.py`

### 1a. `select_scene_match_path`（镜头路径 DP，docstring 原文）
- 「**时间线镜头选路：使用动态规划按原候选顺序选择弱惩罚倒退的路径。**」
- `_scene_transition_score`：「时间线镜头转移评分：**对源镜头索引或起点发生倒退施加固定惩罚**」
  + 罚值表 `{"loose": 2.0, "normal": 5.0, "strict": 10.0}`（随 `timeline_strictness`=normal 档取 5.0）。
- 我方续10c 近似（winner 相邻 +0.02 加分）**形式不符**：真实是**倒退罚项**（惩罚源场景索引/起点回退），
  且作用于路径 DP 而非贪心逐查询排序。

### 1b. `resolve_consecutive_scene_offsets`（连续偏移修正）
- 「**时间线连续偏移：修正连续命中同一源镜头时重复使用起始帧的问题。**」
- 配套统计 `describe_scene_path_quality`：`total / matched / coverage / duplicate_ratio`（源起点重复比例）。
- `_fits_source_range`：「确认移动后的起点和时长不超过匹配源范围」；修正字段 `source_offset_resolved_shift`。
- **这正是本轮探针发现的"GT 内容距 span 起点中位 14.9s / 同场景重复起点"问题的官方解法。**

### 1c. `align_candidate_path`（逐采样对齐，fast 模式）
- 「时间线采样对齐：**按连续性惩罚从逐采样候选中恢复稳定源帧路径**」；
  `_transition_score`：「按**实际帧差与期望帧差的偏离**扣除连续性分数」（`expected_delta` vs `actual_delta`，
  blob 内常量 **-0.08** = 逐帧连续性扣分权重）。

### 1d. `select_refined_candidate_path`（精修候选路径 DP，fast 模式主目标函数）
- OffsetCandidate 四项加权（**全部字节确证**）：
  **score = 0.55×local + 0.20×consistency + 0.20×coarse + 0.05×support**
  （`path_local_weight` / `path_consistency_weight` / `path_coarse_weight` / `path_support_weight`）。
- DP 转移罚：`path_transition_grace_seconds=2.0`、`path_transition_max_penalty=0.12`、`path_backward_max_penalty=0.05`；
  「用动态规划**压制孤立跳点，同时允许连续多段跳入新的原片章节**」。
- 候选补全：`build_continuity_candidates`「**把上一段最强候选按解说时间差平移**，补入全局召回可能漏掉的位置」；
  `build_path_recovery_candidates`「从初选路径的**前后邻居反推**当前镜头候选起点」（id 前缀 `path-prev-`/`path-next-`）；
  触发判据 = `recovery_neighbor_disagreement_seconds=1.0` ∧ `recovery_local_score_threshold=0.45`
  （「挑出低证据镜头和同时偏离前后路径预测的镜头」）。
- 窗口边距：`local_window_margin_seconds=2.0`、`propagated_local_window_margin_seconds=3.0`。

## 2. 原片侧起点精修链（治"锚不准"的完整武器库）

| 模块 | docstring 关键句 | 已确证参数 |
|---|---|---|
| `alignment/dtw.py` | 「执行子序列 DTW 并验证**支持度、边界、位移和最低置信度**」「在 DTW 粗起点附近按**开场特征窗口**搜索更可信的精确起点」 | dtw_min_score 0.55 / samples 64 / interval 0.1 / start_window ±30 帧·max_points **16**·min_improvement 0.04（max_points 为新增确证） |
| `alignment/offset_refiner.py` | 「使用**缓存帧特征校正每个命中镜头的源片起始帧**」「收集**可疑匹配**进行 TopK DTW 复查」「把胜出的 TopK DTW 候选元数据完整写回」 | topk_rerank 10 / coverage 0.8 / `actual_refine_score_threshold=0.65` / `actual_refine_min_score_gain=0.01` / `actual_refine_query_count=3` / `initial_refine_candidate_count=5` |
| `fast_timeline/dense_alignment.py` | 「使用候选附近 **10fps 网格**和**多帧首段证据**寻找最佳源起点」「**仅在实际帧复核分数有明确增益时**覆盖稳定的 10fps 起点」「让**低分、锚点分歧、边缘命中或开头切点风险**进入实际帧复核」 | `dense_sample_fps=10`、平衡模式 `balanced_coarse_sample_fps=5`（「粗扫只降低采样频率；局部精排仍使用原 10fps」） |
| `fast_timeline/local_refiner.py` | 「在局部窗口内移动候选起点，并用**多帧全局/Patch 证据精排**」「合并校正后**收敛到同一起点**的候选」 | 局部块 10s @3fps；`frame_refine_radius_seconds=0.2`、`path_refine_radius_seconds=0.35`、`frame_refine_query_count=5`、`min_candidate_margin=0.1`、`offset_bucket_seconds=0.5` |
| `fast_timeline/ordered_search.py` | 「按已确认原片位置**增量向后检索**，只回退到未搜索区间」「从可靠递增匹配中**自动识别主线**，并在重排时解除锁定」 | `ordered_search_max_seconds=1800.0` / `ordered_search_refined_min_score=0.62` |
| `fast_timeline/boundary_guard.py`（`adjust_fast_match_boundaries`） | 「修正快速模式**开头串镜**，并在尾部跨镜时**优先使用同镜头画面**」；开头=语义复核（DINO 特征，前 3 个解说样本加权总分，global/patch **0.65/0.35**，`dense_early_weight` 线权 0.05 步进）；采纳判据 `score_gain`/`first_score_gain`/`stronger_post_cut_match`；尾部=`_detect_trailing_cut`「返回结尾前最近的可信硬切首帧」 | `boundary_backshift_enabled=true`、`boundary_backshift_max_seconds=2.0`；硬切判据 `_adaptive_hard_cut_threshold`（尾部正常运动帧差 median + MAD，常量 8.0/4.0）、`_is_hard_cut`（切点前后各一帧稳定性 0.5/2.2，160 宽灰度）、`_is_motion_tolerant_hard_cut`（识别运动镜头单帧硬切） |
| `alignment/geometry.py`（AKAZE/ORB） | 「执行汉明距离比率筛选和**单应性验证**」「**按内点三倍权重计算局部特征分数**」「loose/normal/strict 几何严格度映射到**最少单应性内点数**」 | 修正 AKAZE 理解：min_match_points 作用于**单应内点**（非比值检验后 good 数），内点权重 ×3 |

## 3. ED 侧切分精修（展示层边界质量的来源）

- `scene_detection/boundary_refiner.py`（**入点后移校正**）：「**只在源片段开头明显还是上一镜头尾帧时，才把入点向后校正**。
  这不是固定跳过第一帧：它比较 start-1/start、start/start+1、start+1/start+2。只有…」
  —— 即 `source_boundary_refine_max_shift=2` 帧 + `source_boundary_guard_frames=0` 的语义；
  判据 = 三段相邻帧差（160 宽灰度、平均绝对像素差）。
- `fast_timeline/commentary_scenes.py`（快速分镜复核，ED 侧）：「读取 **SceneRuntime 双预测**（单帧+全帧 TN）并只在快速模式复核解说切点」
  「快速分镜复核完成：**校正 N 个切点，补切 N 个，拒绝 N 个非硬切候选**」。
  机制 = 48×27 低分辨率描述子（LAB 均值+Sobel 边缘+HSV 直方图 `_normalized_correlation`）+ `_locate_visual_cut`（视觉切点定位）
  + ECC 仿射运动校验（`findTransformECC MOTION_AFFINE`，区分运动 vs 切换）+ 白闪判别（`_probable_flash_cut`）。
  全部阈值字节确证：`snap_radius=4` / `move_radius=16` / `min_side_frames=8` / `max_additions=4` / 双预测门 0.02·0.04·0.08 /
  visual 0.15·0.2·1.35 / structure 0.42·0.85 / motion ECC≤0.8 ∧ hist≤0.2 / flash 0.78·0.2。
- `feature_index/sampling.py`：「普通场景均匀取帧，**长原片场景按时间间隔和最大数量自适应增加样本**」+
  「合并普通锚点和可选 DTW 时序采样」——确认 G1 关键帧 + DTW 采样合并的形态。

## 4. 检索层补充发现（此前未登记）

- `feature_index/retrieval.py`：「为每段解说联合全局与 patch top-k 召回原片候选，并应用**长镜头局部提升**后排序」
  + 「为内存索引的**长场景建立局部窗口 probe**，低内存模式则移除」+「报告进入最终 top-k 的长镜头局部窗口、原排名、时间范围和分数提升」
  —— **长场景局部 probe 提升**是此前五环模型没有的一环（对长场景内多候选排序有直接影响）。
- `fast_timeline/coarse_retrieval.py`：「为一个解说镜头汇总**多个采样帧的时间偏移投票**」——时间偏移投票粗召回。
- `fast_timeline/commentary_sampler.py`：「3fps 连续采样」+「亮度/对比度/清晰度组成**质量权重**」+「短镜头内部均匀补点」。

## 5. 展示/导出层（G7 的完整形态）

- `exporting/jianying/fcpxml_generator.py`（FCPXML）+ `exporting/premiere/xml_generator.py`：
  segments `{'start_src', 'count', 'flip'}`；**Premiere 时间重映射**（「计算 Premiere 时间重映射使用的速度百分比」）+ 音轨展开。
- `exporting/segments/builder.py` + 稳定性检查：「N 个是单帧片段。这通常表示画面匹配失败，**继续导出会生成闪烁视频**」——导出前单帧片段守卫。
- `fast_timeline/confidence.py`：「按**采样、偏移支持、局部一致性和候选差距**给出稳定置信度结论」+
  「将精排和密集起点结果组合成**保持原片一倍速**的最终片段」——置信度公式输入面（采样/偏移支持/局部一致/候选差距）首次可读。
- `boundary_guard._record_boundary_split`：「**记录需要在剪映和 Premiere 时间线展开的真实转场切点**」——
  定位 span 内的真实转场在时间线上展开成多段（这就是用户看到的"边界几何正确"的机制）。

## 6. 与本轮五环探针的对账（为什么复现"锚不准"而竞品不）

本轮沙盒只实现了 offset(±2帧)/start-window(±30帧)/DTW 门的**一层**精修；竞品实际有
**密集 10fps 起点复核（多帧首段证据）→ 局部 3fps 多帧精排 → TopK DTW 复查可疑匹配 → 路径 DP（四项加权+倒退罚）→
连续偏移修正（同场景重复起点）→ 开头串镜守卫/尾部硬切回退** 共 6 层。
GT 内容距 span 起点中位 14.9s 的差距，主要就是这 6 层的职责。**"位置层弱"是复现不完整，不是竞品弱**——
上一轮 FINDINGS_COMBO_FIVE_RING_TEST1 §3.4 的推断「优势来自可复现层之外的精修」被本轮 docstring 证据**具体化并证实**。

## 7. 可实现项清单（供下一步拍板，按预期收益排序）

1. **P0 候选：密集 10fps 起点复核**（`dense_alignment` 形态）——在我方复现管线的 matched span 内，
   用 10fps + 多帧首段证据重找起点；直接对症"锚不准"，接口已在沙盒（dense_cls 已有）。
2. **P1：连续偏移修正**（`resolve_consecutive_scene_offsets` 语义已完整）——同场景重复起点检测 + 平移，
   比 G5a/G5b 近似更接近真实形式。
3. **P1：路径 DP 四项加权目标**（0.55/0.2/0.2/0.05 + grace 2.0/penalty 0.12/0.05）——替换我方贪心 rerank。
4. **P2：开头串镜守卫/尾部硬切回退**（fast 模式产物；我方复现走的是 precise 语义，接入需口径对齐）。
5. **P2：长场景局部 probe 提升**（检索层，长场景多候选排序）。
6. **展示层（独立通道，不碰指标）**：真实转场切点时间线展开 + 单帧片段导出守卫 + TN 边界展示（G7）。
7. **不再依赖执行方**：N1-N8 中"路径/精修语义"部分已由 docstring 解决；真正剩余的只有公式内部细节
   （如 `_score_early_alignment` 的 linspace 权重形状、confidence 公式精确权重）——可用探针拟合验证。

## 8. 产物与登记

- 数据源：`cutmatch-analysis/data/`（未改动对方文件，只读检索）；关键 blob：390776090（timeline.py）、
  390780941（boundary_guard.py）、390805752（commentary_scenes.py）、390848752（path_selection.py）、
  390817647（dense_alignment.py）、390988120（pipeline options）。
- 新确证键值（未在执行方 27+7+4 绑定表内的）：`path_*` 四权重 + 三罚值 + 两 recovery 值、
  `continuity_tiebreak_bonus=0.02`（adjacent_pairs 已有,本轮对上语义）、`local/propagated_window_margin 2.0/3.0`、
  `frame/path_refine_radius 0.2/0.35`、`frame_refine_query_count=5`、`initial_refine_candidate_count=5`、
  `actual_refine_query_count=3`、`min_candidate_margin=0.1`、`offset_bucket_seconds=0.5`、
  `commentary_scene_*` 全族 14 键、`boundary_backshift_*`、`source_boundary_refine_max_shift=2`、
  `dense/balanced_coarse_sample_fps=10/5`、`dtw_start_window_max_points=16`。
- 纪律：静态常量/docstring 分析；未运行竞品代码、未绕授权、未解密受保护资产。


## 9. 同日追加（续10j）：全局层挖掘（runner 调用序 / 主线锁定 / 偏移投票 / 置信公式）+ 分散度 graft 负结果

### 9a. 两条管线的完整调用序（docstring 逐字恢复）

**精确模式**（pipeline.runner, 我方沙盒对标口径）：SceneRuntime 双侧切分 → RuntimeVision 特征库 → 全局/patch 召回 →
**「正在选择 V2 镜头级匹配路径」（路径 DP）→「候选复查」（局部精修/TopK DTW 复查）** → 边界调整 → 按 scene boundary 拆分输出。
**快速模式七阶段**（fast_timeline.runner）：读解说 → 分镜复核 → 原片 1fps 索引 → 全局粗定位（3fps+偏移投票）→
候选精排（局部块 + 顺序搜索 + **两遍路径 DP（主线 + 恢复候选重选）**）→ **10fps 起点精确对齐** → 原片边界复查（含拒绝明细）→ 输出。
**结构事实：局部精修永远发生在全局路径选定之后，并被路径约束** —— 我方沙盒逐行独立做密集复核，缺的正是这个上下文。

### 9b. 全局层机制明细（全部 docstring + 常量级证据）

- **主线锁定**（ordered_search.OrderedSearchController）：「从可靠递增匹配中自动识别主线，并在重排时解除锁定」；
  增量向后检索只回退未搜索区间；接受顺序结果须「局部证据、采样支持和候选间隔」三可靠（`reliable_streak`）；
  候选排序 = **local×0.7 + consistency×0.3**（blob 常量），min_score 0.62；粗候选可靠性 = dispersion ≤ **0.35s** + 支持率门；
  候选去重 0.25s；参数族 `ordered_search_{backtrack,chunk,context,candidate_count,candidate_margin,lock_segments}_*`（N1 族，值未绑定）。
- **时间偏移投票**（coarse_retrieval）：每个 3fps 解说样本独立 top-k → **0.05s 分桶加权投票** → OffsetCandidate
  {source_start, coarse_score, support_count, support_ratio, offset_dispersion_seconds} → `continuity_tiebreak_bonus`
  在此处即参与候选构建。
- **两遍路径 DP + 恢复候选**：先常规 DP 选路，再挑「低证据 ∧ 偏离前后路径预测」的镜头，用前后邻居反推候选（path-prev/next）重选。
- **置信公式**（fast confidence）：coarse/local/consistency/margin 四项加权（`confidence_*_weight`）+
  四类低置信原因：`insufficient_samples`（min_valid_samples 2/3）/ `weak_offset_support`（min_support_ratio）/
  `weak_local_consistency`（min_local_score）/ `small_candidate_margin`（0.1）。

### 9c. 分散度门 graft 实验 = 否定（诚实负结果，已降级为诊断字段）

把 `offset_dispersion_seconds ≤ 0.35` graft 到 P0（首段关键帧窗内独立 argmax 的隐含起点标准差）：
test1 10/43（+4 好移动全被拦）、2mkv 30/39（p41 真改善 disp=0.616 被误杀、p01 假移动 disp=0.319 反而达标）——
**窗口局部重算的分散度不分真假**。竞品语义依赖全片 3fps 投票 + 质量权重 + 分桶共识的完整上下文，不可拆解贴用。
**结论：全局层语义是管线级属性，不是局部判据**；要获得它只有两条路——① 在沙盒完整重建快速模式候选生成
（工程量大，等于第二套复现），② 等机器码逆向补全。P0 终版配置（+6 零退化）维持不变，分散度仅留诊断字段。
