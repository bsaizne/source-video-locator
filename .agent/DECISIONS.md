# DECISIONS

## Phase 11 最终技术选型（2026-08-24）

- **Decision**：加权评分（Accuracy 35/Robustness 20/Speed 15/Long-video 10/Integration 10/Cross-platform 5/License 5）：VCSL 思路 6.00 > VDF 5.46 > TransVCL 2.63。结论 A 无合格纯算法引擎（real 全败）；结论 B VDF 工程最省但 AGPL 风险 / VCSL 自研底座 license 安全；结论 C 推荐自研视觉核心 + VDF 音频指纹辅助。
- **Reason**：real 素材三引擎全 recall=0；VCSL 思路 synthetic recall 76% 方向对但 precision 25%（46 FP）需去 FP。
- **Alternatives**：直接用 VDF / 直接用 TransVCL。
- **Rejected**：VDF 在真实解说素材直接 error、画面型变换 recall 0；TransVCL 本机 ORB-BOW 无有效输出（特征不匹配，非模型问题）。
- **文档**：`TECHNOLOGY_SELECTION.md`

## Phase 12 双基线实验路线（用户任务书，2026-08-24）

- **Decision**：不做 VCSL 简单特征升级，改为两个干净基线——Experiment A（DINOv2 + 自研单调 DP 时间对齐，0.5fps）+ Experiment B（官方 ISC21 特征 + TransVCL，1fps）。
- **Reason**：32x32 灰度在真实解说素材系统性失效；TransVCL 需官方特征才能真实评估，不能用 ORB-BOW 判定其能力。
- **Alternatives**：ORB-BOW 直接喂 TransVCL（已证明 recall=0，特征不匹配）。
- **Rejected**：把自训 ISC 变体标为"官方 TransVCL"；两实验融合；改 GT。
- **约束**：不开发 GUI、不删 benchmark/GT、不研究音频指纹、不淘汰 TransVCL、不改 GT、实验完成前不宣布结论。

## DINOv2 权重来源（2026-08-24）

- **Decision**：从 `dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth`（**带 `dinov2_vits14/` 子路径**）下载；落盘校验大小 88,283,115B + torch.load 结构。
- **Reason**：无子路径的 URL 实测 403；该子路径 URL Range GET 实测返回真实 torch pickle。HuggingFace / Google Drive 本机不可达。
- **Alternatives**：HuggingFace / GitHub 镜像。
- **Rejected**：官方无子路径 URL（403）；HuggingFace（连接失败）。

## Experiment A 特征口径（2026-08-24）

- **Decision**：DINOv2 vits14 手写 ViT-S/14 前向（torchvision 无 DINOv2 类），取 CLS token 384 维 + L2 归一化；0.5fps 采样。
- **Reason**：官方权重为裸 state_dict（无 `model` 键），load_state_dict 需精确结构匹配（已修正 ls1/ls2 gamma、mlp fc1/fc2、mask_token 1 维、patch_embed 无 norm）。
- **Alternatives**：torch.hub.load（默认 URL 指向被拦的 fbaipublicfiles）。
- **Rejected**：依赖 torch.hub 的默认权重加载路径。

## 当前未决：real GT 准确性存疑（2026-08-24）

- **Issue**：DINOv2 对每个编辑帧的 top 匹配集中在原片 1130~1580s（随编辑时间单调递增），而 GT 声称在原片 6350/6598s 附近，该处相似度仅 0.04~0.24；决定性测试 edited 20s vs orig 6599s 余弦≈-0.002、ORB 仅 1 匹配（两帧非同一画面）。
- **Status**：**待确认**。需 ORB 独立交叉验证（edited 20s → 1296s vs 6599s）判断 GT 是否准确。在证据充分前**不修改 GT**（任务书铁律），需用户决策。

## Phase 14C 查询密度实验结论（2026-08-24）

- **Decision**：**不采纳"提高查询采样率(fps)能救 s3/s4/s6"**。固定查询窗口下，edited 查询 2→4→8fps 对候选召回零增益（n_recall_B 恒 6/7、coverage 逐段逐 bit 相同），且更高 fps 对 fine localization 略有害（s2 iou .368→.226、s6 .75→.5、s5 .455→.353）。**真正把 recall 3/7→6/7 的杠杆是查询窗口 span（pad 0→±4s，编辑上下文变宽）**，靠查询帧把 orig 区命中填满成连续块、基础时间聚类即可融合（s4 两碎片→[1374,1404]、s6 →[1550,1610]），无需 12s 连续性桥。
- **Reason**：14A.1 假说"查询密度不足"指的是**编辑上下文 span / 不同编辑帧数**，不是**帧采样率**。pad 增加不同编辑帧数（20 vs 4 个 rep），使连续性 rep 轨迹变密；再增大 fps 只是重复采样相同内容，无新增判别信息，反而引入噪音命中。
- **s3 判定**：唯一 miss（cov 恒 0.375）。s3 的 2s 剪辑与 s2 同内容，映射到共享区 [1296,1346]，候选只擦到 GT[1340,1356] 的 6s。**是内容歧义/判别极限，非采样密度可解**——任何 gap/fps/pad 都 ≤0.375。
- **Alternatives**：换判别特征（局部 patch/区域特征）；更高层边界建模区分 s2/s3；候选阶段加场景一致性排序惩罚 s2 的错误高分场景 [1212,1234]（mean 0.726，压过 correct rank2）。
- **Rejected**：靠加 fps 增加"查询密度"；放宽聚类 gap。
- **约束**：本阶段未改 GT/特征/检索/聚类参数，只改查询采样率与窗口 pad。完成后停止，未进 14B/15。

## Phase 15 视觉诊断结论（2026-08-25）

- **Decision**：**先复核 s3 的 GT 边界，而非直接换特征**。Agent 视觉诊断显示 s3 的 GT[1340,1356] 是区间估计、与 s2 重叠、尾段混入异构镜头（老年女性肖像），且 edited 是蒙太奇（直升机→s2 共享区、士兵走开→s4 区）。这是 **GT 边界/不确定（E）**，非"特征无法判别"。收缩 GT 让 s3 cover≥0.5 是 recall→7/7 的最省力路径，无需换特征。
- **真正需要换特征的是 s2/s4（C）**：整帧 CLS 把"暗色+军人/人物+纹理"的高外观相似场景混同——s2 暗室内男子 sim0.726 反超正确区[1296,1346] 0.558；s4 暗色军事画面（森林营地/掩体/控制面板）不可分，fine loc 仅 iou0.273。方向=局部 patch/区域特征或候选阶段场景一致性排序。
- **s0/s1 = 相似场景混淆（B）**：正确区深 rank6/5，top3 全是暗色迷彩/室内军人（sim0.62~0.756 但 cover0）。**s6 = 编辑证据不足（F, 已解决）**：pad=0 稀疏，14C 加 span 后 cover1.0/iou0.75。**s5 = 干净命中**（correct rank1 cover1.0；distracter sim 低于正确区）。
- **贯穿主因**：**"相似外观（暗色+军人/人物+纹理）掩盖语义身份"**——整帧 CLS 对这类军旅素材全局判别力有限。这也是 s2/s4/s0/s1 的共同根源；s3 例外（GT 边界）。
- **Agent 多模态定位**：只是开发期诊断工具（解释"为何失败"），**不接入最终 runtime**；DINOv2/Localization 才是最终引擎。Agent 不自动改算法，只写 diagnosis.json 供人工决策。
- **约束**：本阶段未改 DINOv2/模型/GT/指标/产品架构，未把 Agent/VLM 接入 runtime。Phase 15 结束即停，未进 Phase 16。

## Phase 16B 排序/特征决策（2026-08-25）

- **Decision**：**采纳 ExpA（`n_reps` 查询时序覆盖度 rerank），不采纳 ExpB（patch pooling）/ ExpC（multi-scale）**。
- **ExpA**：把候选得分改为 `mean*sqrt(hit)*(0.5+0.5*cons) * n_reps^0.5`，其中 `n_reps` = 候选窗代表的 distinct edited 帧数（查询时序覆盖度）。α=0.5（∈[0.4,0.8] 宽稳定平台）使 **s2 best_rank 2→1**（正确区[1296,1346] n_reps=10 反超错窗暗室内男[1212,1234] n_reps=5），其余段不变，recall_B 恒 7/7，finloc 不变（`best_cover` 与 rank 无关）。4fps 下 s0 6→4、s1 5→4（更优）。
- **为什么是它**：错窗是**均质暗场景**，`qcov`(=1.0)/`sim_std`(0.016, 反比正确区的 0.064)/`scene_diversity` 三项经数据证明**方向全反、无法区分**；只有"候选覆盖编辑剪辑的时序广度"这一**结构**信号能分开——错窗只命中 query 的暗色子集(5 帧)，正确区覆盖更宽时序(10 帧)。一条原则性规则（真匹配应覆盖整个编辑剪辑内容），非过拟合；一致性幂需 k>1.83 才翻转但会摧毁 s0/s1（12/7），sim_std 惩罚需 c<0（奖励方差，不合理）。
- **ExpB/C 为何失败**：错窗暗室内男在 **CLS 与 pooled-patch 空间都编码得比正确区更近**（patch 后差距 0.168→0.10 仍未翻盘；错窗 sim 0.726→0.758 反升）——pooled-patch 是 1369 patch 的全局均值，仍属"全局外观"描述子，无法判别语义身份。s4 的 shot-boundary 问题（暗色掩体/森林/控制台/蓝屏），patch/multi-scale 只把 IoU 从 0.333 抬到 0.429/0.529 但 traj 过度延伸（end_err +24/+16），精度更差；且连环伤 s3(0.75→0.0)、s0(cover 1.0→0.667)、s6(0.75→0.5)、s5(0.455→0.353)、s2(0.5→0.226)。
- **Alternatives**：若坚持修 s4 shot-boundary，方向应为局部 patch↔patch **correspondence**（shot 边界匹配）或场景身份模型，均超出"只测 A/B/C"范围；或接受 s4 finloc 0.333 为已知极限。
- **Rejected**：采用 pooled-patch / multi-scale 信号进入排序或 finloc；提高 `n_reps` 幂到一致性-k 类过拟合。
- **约束**：未改 backbone / GT / benchmark 口径 / 检索-finloc 主流程，只在排序层加一项；`2@0.5fps_patch.npy` 为新增只读缓存。Phase 16B 结束即停，未进 Phase 17。

## Phase 17A / 18 / 19 finloc 决策（2026-08-25）

- **Decision**：**finloc 三方向（只改 Fine Localization 层，其余全部复用 query_density_14c）均不采纳**。每方向都在"修好 s4（多-shot montage）"与"退化干净段"之间不可调和，净收益为负。
- **17A multi-segment（per-query argmax）**：s4 0.333→1.0 验证"longest_run 单连续 run 对 montage 过严"假设**成立**；但 s0/s2→None、s1/s3/s6 过窄、s5 反向跨段；gap 2/4/6 逐段全同（无 gap 可调）。**根因：per-query 单帧 argmax 太脆**（跨 shot 抖动 + monotonic/teleport 校验整条拒绝）。
- **18 temporal neighborhood voting（per-query 邻域投票）**：s4 0.333→0.889、s2 0.5→0.667、0 None；但 s0/s3/s6 静态塌缩成点、s1 过窄、s5 w3 仍反向跨段。**根因：per-query consensus 单 bin 众数丢弃区间；单调路径永不断段使并集+cut 门成死路径；cut 过度检测**。
- **19 cut-aware coverage（per-orig coverage 主信号 + run 级 source-cut 切分）**：s0/s1 稳定、0 None、s5 不再反向跨段；但 s4 仍 0.333（[1383,1389] 的 8s coverage 洞 > gap_merge 4s）、s2/s3/s6 明显退化（cut 段内误检 + 无-cut-merge 门控截断）。**根因：0.5fps 下相邻内容距离几乎处处高（d 0.6~0.94），无法区分"段内 montage 洞"vs"跨段真 cut"**；s5 cross=F 是 coverage 信号+分数巧合非 cut 功。
- **三轮共识**：**per-orig max-over-query coverage 是对的主定位信号（保留区间/稳定性来源）**；run 级 cut 切分反例成立；per-query 位置信号做不了主定位。**"保留区间"只能靠 per-orig 覆盖信号。**
- **约束**：未改 DINOv2/检索/ExpA/GT/cosine/指标；研究代码保留。各 Phase 完成即停，未自动进下一 Phase。

## Phase 20 架构决策（2026-08-25）

- **Decision**：**不启动新的算法研究阶段**。把已验证栈（DINOv2→检索→聚类→ExpA n_reps→longest_run finloc→Confidence→FFmpeg）直接产品化（P0）；仅当产品目标域蒙太奇/多-shot 素材占比高时才做 **s4 单类定向验证**（P1：DINOv2 稠密 + VCSL/VTA 序列对齐），成功才接入二级定位器，失败则确认 s4 为固有难例。
- **s4 定性**：**可接受的困难边界案例**，非必须攻克核心（主问题已被 recall_B 7/7 回答；2–2.5s 编辑跨 3–4 来源 shot 本质欠定；三轮框架内优化均伤及 3–5 段）。
- **sequence-level model 引入条件**（不默认换模型）：①frame-level 优化到顶（已满足）②产品域蒙太奇占比高（需产品决策）③s4 单类 sequence-level 定向验证正面（未满足，可低成本做）。VCSL/VTA（MIT）是贴合"multi-shot montage source localization"的现成候选，但 real 未证 + dinov2_ta blocked → 只能"二级定位器+定向验证"接入，不得整体替换。
- **约束**：不写代码/不改 GT/不重跑 benchmark/不调参/不加模型；数据冲突（s4 根因诊断、序列级方向 vs 可行性、s5 改好稳健性、召回 vs 深 rank）如实记录，不强行单一结论。

## MVP 产品化决策（2026-08-25）

- **Decision**：进入 MVP 产品化（Source Video Locator）。**产品第一原则 = Confidence Engineering**（不把 cosine 当置信度/概率；综合 rank/n_reps/score/margin/consistency/coverage/finloc_stability/竞争性/montage/窗口异常 → HIGH/MEDIUM/LOW + reasons）。montage/多岛 = 低置信 + 候选范围 + 人工修正；**宁可提示人工确认，不输出虚假精确高置信**。
- **技术栈**：**Python + PySide6（LGPL）**。理由：引擎已是 Python/PyTorch，单进程免 IPC；DINOv2 的 AMD/MPS/CUDA backend 进程内切换；FFmpeg 子进程；用户已有 PySide6 经验；LGPL 商用友好。**不选 Avalonia/Electron**（UI 极轻、瓶颈在引擎，跨进程无收益）。
- **硬件路线**：严格 **H1 Windows CPU → H2 Windows AMD → H3 macOS Apple Silicon**，不并行。6750 GRE 的 ROCm/Windows 可用性**需实机验证**，不稳标 `AMD_GPU_BACKEND_BLOCKED` 继续 CPU；macOS 需实机验证、不支持 Intel。
- **研究代码处理**：REUSE=手写 ViT-S/14 模型+预处理+前向、longest_run、cosine_similarity、检索/聚类算法、v2_score 公式；REFACTOR=feature extraction 入 DeviceBackend、narrow 定位流程去 GT/TransVCL 依赖、检索/聚类 I/O 去 benchmark 全局；REWRITE=frame 采样→FFmpeg、FFmpeg 工具集中化、FeatureStore、ConfidenceEngine、engine/segment；RESEARCH_ONLY=ta._dp_path、query_density_14c 整脚本、17A/18/19 变体、patch/multi-scale、ORB-BOW/TransVCL/VDF。
- **无 GT 落差点**：研究用 GT 窗口定义查询段，产品无 GT → 新增 `engine/segment` 做 edited shot 切分。**约束**：不改冻结算法；products 代码与研究代码物理隔离。

## MVP Stage 1 第 1~4 项决策（2026-08-25，产品化编码）

- **FFmpegIO 替代 cv2**：所有时间定位走 ffmpeg/ffprobe subprocess，**禁 cv2.CAP_PROP_POS_MSEC**（MKV 可致从头解码）。mkv 流 duration=N/A → metadata 只信 `format.duration`、fps 只信 `avg_frame_rate`。
- **clip 提取用精确重编码**：`-ss <start> -i ... -t <len> -c:v libx264`（`-ss before -i` 快 seek + 重编码 = 帧精确首帧）。**stream copy 是 keyframe 对齐、不精确**，产品价值点拒绝。libx264 是 GPL 编码器，打包时评估 LGPL 构建（见 TECH_STACK §6）。
- **采样约定改时间基**：产品 `iter_frames(fps=f)` 用 ffmpeg `fps` 过滤器，`t=i/fps`（时间驱动），**不复刻研究 cv2 `idx%step` 帧索引基**。理由：产品是全新 runtime（不重跑研究 benchmark），时间基对齐 FeatureStore `t=row/fps`、跨源 fps 稳定。因此 MVP 索引不会与 `work/dinov2_feats` 逐字节一致（预期，无害）。
- **FeatureStore 落盘/失效**：`<index_root>/<stem>__<hash8>.idx/{index.json,features.npy,times.npy}`（times 与 features 行对齐，绝对秒）。失效判定 size→duration→model/dim/fps/version→hash 硬检；旧索引进 `.stale` 隔离命名空间（不静默覆盖，可恢复）。`validate_index` 每次对原片做内容哈希（快检优先，但 hash 是 INDEX_SPEC §4 最硬判据，1GB≈0.9s 可接受）。
- **检索/排序冻结参数**：`retrieval_top_k`=20（Phase 14A 冻结，config 占位 100→20）、`v2_score` alpha=0.5（Phase 16B ExpA 冻结）。**仅当**聚类/排序的 base_gap=10 / bridge=15 / max_window=60 / sim_floor=0.45 等为模块级冻结默认（不 sweep）。
- **定位信号分层**：`best_cover`（per-orig max-over-query coverage）是 finloc 计算量，**由第 5 项 longest_run 回填**；第 4 项 Candidate 的 `best_cover` 暂时留 0.0 占位。`domain.Candidate` 增 `scene_div`（内部 orig 桥接段数+1，montage 指示供 Confidence）。
- **研究代码 RESEARC_H_ONLY 边界**：`ta._dp_path`/`temporal_align`（TA/DTW）、`query_density_14c.localize`/`edited_window_feats`/`best_cover(GT)`、`_recall`(GT overlap)、14A `ffmpeg_frames`/`dinov2_batch`、17A/18/19 变体、patch/multi-scale、ORB-BOW/TransVCL/VDF——全部不进入 MVP runtime，保留溯源。
- **已知数据属性（交接必读）**：合成图案场景（source.mp4 的多色 drawbox）DINOv2 CLS 语义易混淆，`v2_score` 会把覆盖更宽的非 GT 窗口排在真 GT 区之前（第 4 项冒烟实测）。这是 **冻结公式 + 合成图案**的属性；研究在真实影片数据上 v2_score 正确分离（Phase 16B：s2 正确区[1296,1346] n_reps=10 反超错窗[1212,1234] n_reps=5）。若真实数据同样混淆 → 属 Confidence 应显式降险情形（第 5 项），**非 retrieval 改动，也不回退冻结公式**.

## MVP Stage 1 第 5~6 项决策（2026-08-25，产品化编码）

- **第 5 项 localization+confidence 要点**：finloc = per-orig max-over-query coverage + 3 帧平滑 + mask(0.4 冻结) + longest_run → 精确 span；montage 只用 `multi_island` **检测与标记**（不自动解）；`pipeline.localize_segment` = 候选→finloc 最佳→回填 `best_cover`→confidence→`RefinedSegment`，montage/无 span/run 过短时 original **退化为候选窗范围**（不输出虚假精确边界）。Confidence 是对低置信（weights/threshold 全部占位，入 `ConfidenceConfig` 供 H1 标定）；`engine/localization/__init__` 不 import 编排避免 `confidence<->localization` 循环（pipeline 作为显式子模块）。禁 per-query argmax/voting/cut-aware/TA/改 similarity·ranking。
- **第 6 项 `engine/segment` 关键决策**：`ShotSegment` 放 **engine 层**（domain 禁 numpy；先例 `Hits`/`LocalizationResult`）；切分**判别用局部 z-score**（`z=(s-局部均值)/max(局部σ,floor)`，边界需 `z>=2` 且 `s>=cut_abs=0.30`）——**非裸绝对阈值**（研究证绝对 d 不可靠），且**弃了"相对基线 `max(cut_abs, cut_rel*local_baseline)`"**——那是死代码（cut_rel*base ≤ 0.5 < cut_abs，永远选 cut_abs，退化为纯绝对阈值=被证伪做法）；`cut_abs` 仅作下限安全垫（挡近零 σ 静态段微尖峰）。**默认平滑窗=1**（不平滑保留单帧 cut——分析：平滑窗 3 会把单帧边界拉平，块边界 z≈1.15<2 漏检；且相邻双尖峰会互相抬高局部统计）。**整体偏向下切分**（产品约束：过长可接受、过短/碎片化更危险），NMS(min_gap=max(1,round(min_shot_s*fps))) + merge(过短段并入更弱边界一侧) 保底；无边界/单帧/空 → 回退整段 1 查询单元（=现状行为）。切分参数是**产品化占位**（非冻结 finloc 阈值），入 `PipelineConfig.seg_*`（3 接线点 + JSON 覆盖）供 H1 真实数据标定，**不做 sweep**。segment 属产品胶水，**不触碰任何冻结算法**；避免把 Phase19 原片侧 cut-aware 逻辑重新引入。

## MVP Stage 1 第 7 项决策（2026-08-25，产品化编码，application service）

- **层次归属**：shot 切分 + per-segment 管线循环放 **app service 层**（按 STATE.md Next Actions，直接复用 `detect_shots`/`produce_candidates`/`localize_segment` 现有函数，**不新建** engine 层 `LocalizationEngine` 类）。App Service = UI 唯一入口，三职责：编排 / Result 持久化 / 会话状态；不写视觉算法、不触碰冻结语义。
- **编排**：`build_original_index`(validate→MISSING/INVALID→create→load) → `analyze_edited_video`(iter_frames@edited_segment_fps→embed_frames→detect_shots, 空帧→ApplicationError) → 逐 segment `produce_candidates` + `localize_segment` → 拼 `domain.Result`(edited=shot.span)。`_locate_features(shots,bundle,cfg)` 拆出**纯管线（无 IO）**供 deterministic 测试直注构造特征。
- **失败隔离**：单 segment 失败（produce/localize 异常）→ unresolved `Result`(LOW + `failure_reason` + 日志完整 exception) + **继续后续 segment**，不让整个 edited task 失败。**cancellation 的 `ApplicationError` 不落入段级隔离**（`except ApplicationError: raise` 穿透）。
- **ffmpeg/backend/FeatureStore 惰性构建**：仅做纯编排（如 `_locate_features`）或未配置二进制时**不强制解析**（避免构造即因缺 ffprobe 失败）。
- **Progress**：显式 7 阶段 `ProgressStage` + `ProgressEvent{stage,current,total,message}` 逐事件回调；GUI 用状态机/进度条，不做细粒度逐帧。
- **Cancellation**：`CancellationToken`(threading.Event 封装)，在 index build / edited feature extraction / segment loop / export 检查；取消抛 `ApplicationError`。
- **错误模型**：`infrastructure/errors.py` 补 `IndexError`/`FeatureExtractionError`/`LocalizationError`/`ApplicationError`（均 `LocatorError` 子类）；service 把底层异常翻译为可处理类型，GUI `except LocatorError` 即可，不解析原始 exception string。
- **Result 持久化（用户拍板）**：JSON 单文件批信封 `schema_version/original_video/edited_video/results[]`（`*.results.json`，`<edited_stem>__<hash8>.results.json`，落 `paths.export_root()`）；复用 `Result.to_dict()/from_dict()`，保留 auto/manual 双轨（`manual_override` 时 `auto_result`/`manual_timestamp` 不丢）；`domain.Result` 增可选 `failure_reason`；当前不引入 SQLite。
- **修复的 app 级 bug**：`_result_from_refined` 曾传 `shot` 而非 `shot.span` → `Result.edited` 被塞进整个 ShotSegment；已改为 `_result_from_refined(shot.span, refined)`。
- **真素材结果仅观察**：冒烟报告 segment/result/HIGH·MEDIUM·LOW/unresolved/candidate/各阶段耗时/内存，只记录不调算法（除非确定性 app bug）。
