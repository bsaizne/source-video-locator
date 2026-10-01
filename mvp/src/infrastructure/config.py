"""infrastructure.config — 产品配置（dataclass 默认值 + JSON 覆盖）。

- ``MediaConfig``：ffmpeg/ffprobe 路径与超时。应用服务用它构造 ``FFmpegIO``，
  让二进制来源由配置驱动（而非调用方硬传），见 Stage 1 第 1 项遗留风险。
- ``PipelineConfig``：冻结流水线常量（采样率/窗口/alpha 等），值对齐 MVP 基线。
  其中 ``confidence`` 的权重/阈值是 **未标定占位**（CONFIDENCE_DESIGN §6 诚实声明），
  需 H1 用真实数据校准后再定稿。
- ``AppConfig``：聚合入口。``load_config(path)`` 用 JSON 覆盖默认值。

MVP 用 stdlib json（TECH_STACK §4），无第三方依赖；持久化留待 app service。
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from .errors import ConfigError


@dataclass
class MediaConfig:
    """FFmpeg 二进制与超时。None -> 由 ``resolve_binaries`` 解析默认。"""

    ffmpeg_path: str | Path | None = None
    ffprobe_path: str | Path | None = None
    timeout_s: float = 600.0


@dataclass
class DeviceConfig:
    """推理后端选择与 DirectML 运行时配置。

    - ``preferred``：``auto``(能力探测) / ``cpu`` / ``directml``。``auto`` 会在本机
      能力探测通过时优先 DirectML，否则 CPU（见 ``device.resolve_backend``）。
    - ``onnx_model``：显式 DirectML ONNX 图路径；None -> 由 ``resolve_dml_model``
      搜索产品 ``models`` 目录 / env ``SVL_DML_MODEL``。
    - ``dml_device_id`` / ``dml_batch_size``：DirectML 默认 device id 与前向 batch。
    """

    preferred: str = "auto"
    onnx_model: str | Path | None = None
    dml_device_id: int = 0
    dml_batch_size: int = 8  # 生产实测 batch=1 建索引 10.1fps < batch8 11.2fps(2026-09-05, M4 探针的 20.5fps 不适用于生产 embed 路径); 全程 batch=8 口径自洽


@dataclass
class ConfidenceConfig:
    """工程化置信度的权重与阈值（占位，未标定，需 H1 用真实数据校准）。

    ``weights`` 与 ``high/medium_threshold`` 来自 CONFIDENCE_DESIGN §3.2 初始占位。
    其余硬 flag / 归一化阈值均为**结构占位**（CONFIDENCE_DESIGN §3.1 只给了定性描述，
    无标定数值）。禁止把 ``score`` 当模型概率，也禁止在本阶段调这些值。

    例外：``conf_v2_*`` 一组不是占位——它是竞品四项加权公式的**字节确证常量**
    （护栏「Confidence 公式冻结」已按 DECISIONS.md 2026-09-28 窄范围豁免；
    保留项「不用 GT 字段/score 非概率/禁止裸余弦」仍生效）。
    """

    # CONFIDENCE_DESIGN §3.2 初始权重（占位，需 H1 标定）
    weights: list[float] = field(default_factory=lambda: [0.30, 0.25, 0.15, 0.15, 0.08, 0.07])
    high_threshold: float = 0.75
    medium_threshold: float = 0.55
    # --- 硬 flag / 归一化阈值（占位，待标定）---
    margin_low: float = 0.08          # best-sec 差距 < best*s 倍 -> 竞争（low_candidate_margin）
    similar_band: float = 0.10        # 落在 best score X 倍内的候选视为"相似"
    window_width_min_s: float = 1.0   # 窗口过窄 -> source_window_anomaly
    window_width_max_s: float = 60.0  # 与 clustering.MAX_WINDOW_S 对齐（超限 -> anomaly）
    qcov_dispersed: float = 0.4       # qcov < X -> query 覆盖分散
    sim_high: float = 0.6             # mean_sim 高于此值但结构异常 -> 暗场景混淆
    cov_low: float = 0.3              # best_cover 低于此值 -> 结构异常
    sim_std_high: float = 0.35        # 候选内代表 sim 标准差高于此值 -> 命中不均匀/分散
    finloc_stable_s: float = 4.0      # span_stability 归一化锚点（秒）
    min_run_s: float = 2.0            # 最长 run 短于此 -> finloc_unstable
    dark_penalty: float = 0.8         # 暗场景混淆时的 score 倍率
    # ---- 竞品四项加权置信公式（并行通道，只降不升；2026-09-28 护栏豁免，用户拍板）----
    # 常量全部来自竞品 ``cutmatch.matching.fast_timeline.options``（profile_v1, blob 0x174bb2ea,
    # key_off/val_off 名次配对, level=确证）。默认 **关**（现行 6 软信号 + 硬 flag 行为零变化）。
    # 信号映射与口径缺口（coarse/consistency 为推断级代理）见 DECISIONS.md 2026-09-28。
    conf_v2_enabled: bool = False
    conf_v2_local_weight: float = 0.4        # confidence_local_weight
    conf_v2_coarse_weight: float = 0.3       # confidence_coarse_weight
    conf_v2_consistency_weight: float = 0.2  # confidence_consistency_weight
    conf_v2_margin_weight: float = 0.1       # confidence_margin_weight
    conf_v2_min_score: float = 0.6           # min_confidence_score（低于此值才降档）
    conf_v2_min_valid_samples: int = 3       # min_valid_samples -> insufficient_samples
    conf_v2_min_support_ratio: float = 0.35  # min_support_ratio -> weak_offset_support
    conf_v2_min_local_score: float = 0.55    # min_local_score -> weak_local_consistency
    # min_candidate_margin=0.03（options 字典；BREAKTHROUGH §9b 原记 0.1 系 confidence 自身
    # blob 的「相邻配对假象」，实为 local_refiner 同名键，已按 2026-09-26 复核口径更正）。
    conf_v2_min_candidate_margin: float = 0.03


@dataclass
class SeqAlignConfig:
    """帧级 moment 定位（时序单调 DP）参数（seq_align，用户 2026-08-28 授权产品化）。

    ``enabled`` 默认 True（授权后开）；置 False 则 EvidenceLocalizer 不注入 seq_align，
    moment 精修关闭、回退 scene 级。约束：``min_hits <= montage_min_frames``、
    ``mean_sim_min <= montage_min_sim``（moment 门控不严于 evidence 门控，避免"有 scene 无 moment"）。
    """

    enabled: bool = True
    sim_thresh: float = 0.40          # DP 阈值（ta._dp_path 默认 0.5 过严致 total_pred=0 -> 放宽 0.40）
    mean_sim_min: float = 0.40        # in-scope moment 均值门控（<= montage_min_sim=0.40）
    min_hits: int = 2                 # 每 moment 最少命中帧（<= montage_min_frames=2）
    min_moment_s: float = 1.0         # 最短 moment 时长
    pad_s: float = 15.0               # 全局候选窗在 evidence span 外的扩展（原死配置 5.0 -> 启用 15.0，含 scene 偏差外正确 moment）
    diag_penalty: float = 0.5         # 与 ta.py 对齐
    step_penalty: float = 1.0
    max_edited_gap: int = 3           # 段合并（temporal_align 默认）
    max_orig_gap: int = 8
    max_cells: int = 20000            # 超限跳过（性能护栏）
    edit_fps: float = 8.0             # 全局对齐用密帧重采样率（>edited_segment_fps，app 层重采样）
    global_mean_sim_min: float = 0.20  # out-of-scope moment 门控（低于 in-scope 0.40；放行 scene 偏差外正确 moment，如 seg1 1319）
    window_max_s: float = 45.0        # 全局候选窗宽度上限（防 DP 游走）
    max_query_frames: int = 64        # 每 cluster 密查询帧上限（cell 护栏）
    moment_half_s: float = 1.0        # moment ±1s 收窄半宽（用户"正负1秒"）


@dataclass
class PipelineConfig:
    """冻结流水线参数（MVP 基线，见 MVP_ARCHITECTURE §8）。"""

    index_sampling_fps: float = 1.0   # 索引密度（0.5→1.0，1-2s 短镜头定位更细；feature_version @1_l2 自动重建）
    edited_segment_fps: float = 2.0
    # 原始 span 宽度上限（峰值覆盖核心 + 按编辑支持比例，短镜头不定位成 30s 场景）
    max_orig_span_s: float = 15.0
    span_width_factor: float = 4.0
    min_span_s: float = 2.0
    # 检索 Top-K（正确区不被噪声帧挤出；retrieval.py FROZEN_TOP_K 是硬上限，config 侧可调）
    retrieval_top_k: int = 28
    clustering_max_window_s: float = 60.0
    ranking_alpha: float = 0.5
    # --- 查询单元切分参数（向召回侧微调：快切蒙太奇适度拆分，不碎片化）---
    seg_cut_abs: float = 0.26
    seg_z_thresh: float = 1.7
    seg_min_shot_s: float = 0.8
    seg_smooth: int = 1
    # --- 蒙太奇多段定位参数（向召回侧微调：短子镜头成簇、粗段适度拆分、弱子镜头保留）---
    montage_min_frames: int = 2
    montage_min_sim: float = 0.40
    montage_cluster_gap_s: float = 15.0
    montage_weak_cover: float = 0.30
    montage_weak_sim: float = 0.45
    # --- 子 span 严格门 + IoU 去重（GT v3 实证：暗色外观巧合假阳性子 span）---
    subspan_min_cover: float = 0.45
    subspan_min_sim: float = 0.45
    subspan_iou_merge: float = 0.60
    subspan_max_keep: int = 4
    # --- 黑底文字卡/logo 守卫（GT v3 n04：TikTok 片尾 logo ↔ 版权卡 HIGH 0.95 误配）---
    card_black_ratio: float = 0.85   # 近黑像素占比门限（max RGB<32）;0.60→0.85:test1 r10 夜间误杀修复三
    # （实测真卡 black≥0.93:n04 TikTok logo 0.934-0.969、test1 片尾卡 0.96-0.99;
    #   夜间剧情画面 black≤0.78 但被解说字幕白字行+窗光骗过 spread/连通域判据）
    card_bright_lo: float = 0.01     # 亮像素占比下限（max RGB>=200；纯黑场不算文字卡）
    card_bright_hi: float = 0.30     # 亮像素占比上限（超过=普通画面）
    card_bright_max_spread: float = 48.0  # 亮像素通道扩散上限（白字≈0;橙色爆炸/暖光灯≫48,夜间误杀修复）
    card_bright_min_area_frac: float = 0.004  # 最大亮色连通域面积占比（logo/文字块大实体;夜间高光零星小点,误杀修复二）
    card_shot_ratio: float = 0.60    # 段内卡帧占比>=此值 → not_in_source 跳检索
    card_run_ratio: float = 0.50     # 最长连续卡帧 run 占比>=此值同样判卡（test4 r17：淡入稀释占比的逃逸路径）
    # --- 长块二级细分（GT v3 实证：13-24s 多镜头长块均值 embedding 淹没子镜头）---
    seg_max_shot_s: float = 8.0
    seg_fine_cut_factor: float = 0.75
    seg_fine_z_factor: float = 0.85
    seg_fine_min_shot_s: float = 0.6
    # --- 两级分层切分 + 白闪守卫（C 项验证 2026-09-05 用户拍板进 runtime）---
    # 粗采样(5-8 帧步长)找候选切点 + 局部 ±20 帧密帧精修真实边界 + 最短镜头保护 0.5s;
    # 白闪/亮度尖峰邻域切点删除(转场非真实镜头)。验证: 四片严格 112/139 (+8)、
    # 场景级 136/139 (+18)、负例 4/9 持平。seg_twopass_enabled=False 回退旧路径。
    seg_twopass_enabled: bool = True
    seg_twopass_coarse_step_frames: int = 6      # 粗采样步长(帧): 5-8 区间取 6
    seg_twopass_fine_window_frames: int = 20     # 精修窗: 切点 ±20 帧
    seg_twopass_fine_step_frames: int = 2        # 精修采样步长(帧): 1-2 区间取 2
    seg_twopass_min_shot_s: float = 0.5          # 最短镜头保护(秒, 精修后)
    # --- 白闪守卫参数（C 项校准值, 见 FINDINGS_C_ITEM_8FPS 七章）---
    flash_mean_th: float = 200.0        # 白闪灰度均值门槛
    flash_frac_th: float = 0.5          # 白闪亮像素(>=200)占比门槛
    flash_margin_s: float = 0.25        # 白闪/尖峰邻域切点删除边距(秒)
    flash_dyn_min_shot_s: float = 1.0   # 白闪邻域动态最短镜头阈值(秒)
    flash_merge_frac: float = 0.5       # 段内白闪占比>=此值合并相邻镜头
    bright_spike_delta: float = 80.0    # 相邻帧亮度差>=此值=突变区
    bright_spike_peak_th: float = 180.0 # 突变峰值>=此值=过曝级白闪型
    # --- OCR 文字锚点重排（Phase 21 首选第二信号：同场景字牌/字卡 CLS 不可分,文字可判）---
    text_anchor_enabled: bool = True
    text_anchor_min_sim: float = 0.35    # 候选窗文字相似度低于此值不晋级
    text_anchor_min_gain: float = 0.15   # 子span须比主 span 文字相似度高此值才晋级
    # --- 全局时序一致性 DP 重排（Phase 21 场景身份:test4 实证 7 次时间倒退=相似镜头挑错实例）---
    seq_dp_enabled: bool = True
    seq_dp_order_lambda: float = 0.001   # 时间倒退罚/秒
    seq_dp_skip_penalty: float = 0.30    # 跳过罚(闪回/乱序剪辑逃生门)
    seq_dp_min_score: float = 0.50       # 晋级候选的归一分下限
    # --- patch 最大匹配二阶段重排（Phase 21 E21:同场景兄弟机位 CLS 排 32→patch 排 2）---
    patch_rerank_enabled: bool = True
    patch_rerank_keep_near: float = 8.0  # patch 最优窗与 CLS 主定位距离≤此值 → 不改写
    patch_weights_path: str | None = None  # CPU torch 权重(缺省走 resolve_weights)
    patch_onnx_model: str = ""  # DML 双输出 ONNX(518→CLS+patches);空=走 resolve_patch_onnx(env/产品目录), 均缺省回退 CPU torch
    # --- patch v2 近场重排（2026-09-06 立项, 门控数据 probe_patch_gate.py）---
    # 在主定位 ±radius 的近场均匀池上 patch 匹配; {offset≤radius 且 margin>threshold} 才改写
    # 主定位(旧主定位保留为子 span)。门控数据: 仅放行 p26 型(margin 强+近场), 挡住 t3r26/p10 型。
    patch_v2_enabled: bool = True
    patch_v2_margin: float = 0.075  # 0.08→0.075: p26 实测 margin 0.080 骑线被拒(GPU 浮点差), 门控探针口径 +0.085
    patch_v2_radius_s: float = 30.0
    patch_v2_stride_s: float = 4.0
    # --- 场景指纹召回扩展层（Phase 21:帧级 top-K 为主,场景级只扩池）---
    scene_recall_enabled: bool = True
    scene_top_k: int = 5                 # 场景指纹 top-K 场景扩池
    scene_max_expand_frames: int = 120   # 扩池帧总数上限(防止长场景淹没证据池)
    # --- 事件单元扩池（方向 A 完整阶段 2026-09-05:场景实例身份建模, 探针 POSITIVE）---
    # 事件 = 时序近邻+指纹联合归并的场景组(同场对话戏/兄弟机位);查询均值 vs 事件指纹
    # top-K 命中 → 事件时间窗内帧(预算内)作扩池单元, 独立精化+门控, 与场景扩池同语义
    # (不参与帧级聚类/montage 计数/primary 竞争/置信信号; 帧级+场景均零证据才救回)。
    event_recall_enabled: bool = True
    event_top_k: int = 3                 # 事件指纹 top-K 事件扩池
    event_max_expand_frames: int = 240   # 事件扩池帧总数上限(事件比场景更粗, 预算更大)
    # --- 时序离群修复（test1 r18 实证：暗夜相似场景跨场景误配；前后段定位彼此接近、
    # 本段远离两者 → 在前后段定位窗口内重新检索拉回。test1 29 段人工裁决 28/29 后实现）---
    temporal_repair_enabled: bool = True
    tr_neighbor_gap_s: float = 180.0     # 前后两段定位彼此接近的判定上限
    tr_outlier_min_dist_s: float = 600.0  # 本段定位与前后段的最小偏离(≥10 分钟才算离群)
    # --- 时间轴→Ambiguity（NEXT_STEPS ⑥：时间轴是外部独立 Ambiguity 信号）---
    # Ambiguity 原型证内部置信信号(margin/multiple)无法分离正确/错配 HIGH; 时间轴是外部信号:
    # 定位与前后段严重冲突(离群) = "可疑", 即使内部 margin 很高 → 离群段降档转人工
    # (不改定位——那是 temporal_repair 的职责; 只改置信档位)。复用同一离群判定。
    temporal_ambiguity_enabled: bool = True
    ta_max_downgrade: str = "MEDIUM"     # 离群段最高降到 MEDIUM(转人工提示); 支持 "LOW"
    # --- 单调弱先验进候选生成（NEXT_STEPS ②③, 2026-09-02 拍板：编辑序≈原片序作为候选弱倾向）---
    # 只作用于 Ambiguous 型段(n_strong_clusters>=2/多候选难分): 用前序段定位中点做锚点,
    # 离锚点近的候选簇优先(弱倾向, 非强制); 唯一强候选段不碰(可靠命中零扰动);
    # 带逃生门: 首段/前段未定位不触发; cover 落差超过 ta_max_cover_drop 不切换(防误伤真实回溯 8/29)。
    timeline_prior_enabled: bool = True
    ta_band_s: float = 45.0        # 前序锚点±此秒数内=时序合理带; 带内候选不惩罚
    ta_max_cover_drop: float = 0.10  # 切换候选允许的 cover 落差上限(难分才切, 强候选不切)
    dense_retry_min_sim: float = 0.62
    # --- P0 密集起点复核（2026-09-26 续10i/k, 竞品 dense_alignment 语义重建; DECISIONS 2026-09-26 豁免裁决）---
    # 已定位主 span 起点 ±margin @10fps 密集窗多帧首段证据复核; 采纳门 = 增益(>=min_gain)
    # + max_shift(<=2s, 防"一致但错"远漂移) + 距离平局裁决。沙盒四片 89/139 净+6 零退化;
    # 生产口径(518/2fps/两级切分)与沙盒不同须独立回归, 故默认关。
    dense_recheck_enabled: bool = False
    dense_recheck_margin_s: float = 4.0
    dense_recheck_min_gain: float = 0.04
    dense_recheck_max_shift_s: float = 2.0
    dense_recheck_fps: int = 10
    # --- 偏移投票起点先验（2026-09-27 续10m/续11 立项, 竞品 coarse_retrieval 语义重建; 用户拍板）---
    # 段内采样帧逐帧独立检索全片源索引 -> 0.05s 分桶加权偏移投票 -> 共识簇质心 = 起点种子。
    # 跨查询全局共识信号（与 P0 密集复核的局部窗本质不同）。沙盒四片截等长严格 89 -> 100/139
    # （test1 +10 零退化）; 生产四片双臂回归 117 -> 119/139（+2 零回退, 续11）。
    # 2026-09-28(续20) 打包验收通过（发行三防线/随机端口/元数据/四格式导出/预览直链）
    # ⇒ 按拍板翻默认开。dense_recheck/conf_v2 因实测零增益/1-231 维持默认关。
    vote_prior_enabled: bool = True
    vote_prior_bucket_s: float = 0.05
    vote_prior_cluster_half_buckets: int = 1
    vote_prior_min_support: float = 0.2
    vote_prior_max_shift_s: float = 4.0
    # --- 连续重复起点修正（E1, 2026-09-28; 竞品 resolve_consecutive_scene_offsets 语义重建）---
    # 相邻已定位对起点重复(<=tol) => 后段起点平移到前段终点(宽度保持)。容差 1.0s = 竞品字节确证常量。
    # 影响面预统计仅 7 对/四片且多对疑似合法复用 => 默认关, 待双臂实测+逐图裁决(续21 E1)。
    resolve_consecutive_enabled: bool = False
    resolve_consecutive_dup_tol_s: float = 1.0
    # --- 快速全局锚定（PROJECT_FAST_GLOBAL_ANCHOR, 2026-09-28 立项）---
    # vote_prior 同内核升级: 8fps dense 降采样至 3fps 输入 + 无位移帽 + 分散度门 + 平移保宽度。
    # 启用时替换 vote_prior 应用点(同一机制超集, 不叠加)。
    # 2026-09-29 用户拍板翻默认开: M1 双臂过门(严格 119→127 零回退、口径 82→105)且 M2 四腿
    # 消融实测收口(a top-k/腿 b 宽窗 std/腿 c 质量权均证伪不采纳, 腿 d min3 零翻转)——
    # 生产形态 = M1 形态(下列旋钮默认值), 1 项已知回退 t2r01b(row4 邻镜滑移)逐项登记在案。
    fast_global_enabled: bool = True
    fast_global_fps: float = 3.0
    # 窄簇 support 降到 0.1(防单票退化簇即可): 1fps 库网格 + 3fps 查询的 proj 天然错开 0.33s,
    # 0.2 的窄门是 2fps+4s帽时代遗留, 无帽形态下安全门=wide_support(±1.5s>=0.5)。机理依据, 非 GT 拟合。
    fast_global_min_support: float = 0.1
    # 双臂实测证伪(2026-09-28 M1 裁决, work/fastglobal_on_min2_metrics.json): 取 2 时
    # 真匹配在 1s 库网格量化下 proj 天然单票窄桶, 锚定几乎全灭(口径 105->82, 严格 127->118),
    # "窄簇票数"不是假共识(t2r01b row4)与真共识的判别维度。保留参数=消融腿接口, 生产=1。
    fast_global_min_cluster_votes: int = 1
    fast_global_wide_win_s: float = 1.5
    fast_global_min_wide_support: float = 0.5
    # --- M2 消融腿旋钮（PROJECT_FAST_GLOBAL_ANCHOR §6, 2026-09-28; 默认值=M1 生产形态, 行为零变化）---
    # a) 逐样本 top-k 投票(竞品 coarse 原始形态, k 未确证; 1=M1 top-1)。对症 row4 邻镜滑移:
    #    正确区样本的 rank2/3 候选可参与竞争, 分裂"连贯但错位"的单峰共识。
    fast_global_vote_top_k: int = 1
    # b) 宽窗内票集 std 门(竞品 dispersion≤0.35s 门的宽窗重建; 0=关)。
    fast_global_wide_std_max_s: float = 0.0
    # d) 参与投票样本数下限(竞品 min_valid_samples 2/3; 2=M1 现状)。
    fast_global_min_valid_samples: int = 2
    # c) 质量权重腿（2026-09-29 用户拍板立项）: 每样本票权乘质量分。形态=沙盒复现链 F1
    #    (FINDINGS_FAST_GLOBAL_REPRO §1, 推断级——竞品权重形状未确证): 亮度 mean/255、
    #    对比 std/128、清晰度 min(Laplacian var/2000, 1.5), 全 ED 密帧 min-max 归一后
    #    0.2/0.3/0.5 加权, clip [0.2,1]; 投票权 = sim × 质量(沙盒 F2 同款)。
    #    像素统计走独立 dense_quality 缓存通道(仅启用时解码); 启用会改变缓存指纹(密帧重提一次)。
    fast_global_quality_weights_enabled: bool = False
    fast_global_qw_bright: float = 0.2
    fast_global_qw_contrast: float = 0.3
    fast_global_qw_sharp: float = 0.5
    # --- 定向子镜头回退（蒙太奇段整段失败时, 帧级距离突变阈值; 2026-09-05）---
    subshot_cut_thresh: float = 0.5
    # 2026-09-05 结案默认关闭: 子镜头回退(定向/漂移两版)四片零收益, 且 weak-hit 整体替换
    # evidence 会丢 montage 已命中簇(test2 t2r02b 实证 HIT->MISS)——FINDINGS_SUBSHOT_QUERY。
    subshot_enabled: bool = False
    subshot_min_sub: int = 3
    subshot_retry_min_sim: float = 0.62
    # --- 编辑侧分析持久缓存（A4 性能优化 2026-09-05）---
    # 缓存两级切分产物 + 每段 8fps 密帧特征到 app data（键=文件身份+feature_version+管线配置+
    # 设备数值口径）。同一编辑片重复定位免重切分/重 embed; 任一口径变化自动失效。纯缓存零语义。
    edited_cache_enabled: bool = True
    # 密帧重试命中相似度下限(test4 r10/r12 实证:
    # 全片同质化场景里重试弱命中 0.53-0.60 是假定位;test1 合法重试簇 0.66+)
    # --- 相邻重叠冲突修复（Phase 24:几何触发+内容证据接受;test3 r10 实证——
    # 真值区 441-443 有被压制证据峰 0.73 vs 错位区 0.87;非相邻复用重叠不触发,
    # r6(对)/r8(对) 几何同构由"只看编辑序相邻"天然排除）---
    conflict_rerank_enabled: bool = True
    conflict_max_mover_width_s: float = 8.0  # 复合蒙太奇宽 span 不作 mover
    conflict_overlap_min_s: float = 0.5      # 与相邻段定位重叠≥此值才触发
    conflict_alt_min_sim: float = 0.60       # 空隙候选相似度底线
    conflict_max_drop: float = 0.25          # 允许的 cur−alt 相似度落差上限
    # --- 退化拒绝门 + 场景覆盖门槛（2026-09-28 续19, 竞品 results.validation 三条硬停的其中两条;
    #     用户拍板 T1-1 接入）。竞品确证值 max_duplicate_scene_ratio=0.8 / min_scene_coverage=0.2。
    #     我方口径见 engine/localization/degradation_gate.py 模块头：重复率 = 本段主 span 被其它段
    #     主 span 覆盖的比例；覆盖不足 = 子 span cover 低于门槛即丢弃。
    #     ⚠️ 已知误伤面：解说片故意复用同一源镜头（回闪/前后呼应）会被误拒 ⇒ 默认关，须四片 A/B
    #     + 逐图复核翻转段后再定默认值（离线重放脚本 mvp/scripts/replay_degradation_gate.py）。
    degradation_gate_enabled: bool = False
    max_duplicate_scene_ratio: float = 0.8
    min_scene_coverage: float = 0.2
    # 段级拆分（2026-09-30 续32 形态4 runtime 化，engine/localization/shot_split.py）：
    # 多镜头结果段按编辑窗内切镜重排为逐镜子结果（宽 span 保全 ⇒ 严格结构性零回退）。
    # 2026-10-01 续35 翻默认开（用户拍板）：生产路径双臂验收 = 严格 130→132 · 导出实得 107→119 ·
    # FP 4→4，与离线组合验证逐位一致；续34 抓帧提速后 ON/OFF 开销比实测 2.72×。
    shot_split_enabled: bool = True
    # patch 局部精排（2026-09-30 续32 形态6 runtime 化, engine/localization/patch_refine.py）：
    # 歧义段 top-K 候选各自 ±5s 局部窗 patch+global 融合精排再择优（老主降子 ⇒ 严格零回退）。
    # 2026-10-01 续35 翻默认开（用户拍板）：离线 9/9 读图确证 + 生产双臂 13 增 1 损；
    # 续34 整条 locate 全字段逐位一致 + 高精度全片实测 ≈18 min（test1）。
    patch_refine_enabled: bool = True
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)
    seq_align: SeqAlignConfig = field(default_factory=SeqAlignConfig)


@dataclass
class ExportConfig:
    """Phase 22 导出策略（EDL / FCP7 XML / 剪映草稿）。

    - ``min_confidence``：置信门槛（默认 MEDIUM=HIGH/MEDIUM 直进工程）。
      LOW 的去向由 ``low_policy`` 定（待镜头级 GT + Confidence 多案例标定后定稿）。
    - ``low_policy``：``exclude``（默认，LOW 不导）/ ``backup``（LOW 进独立备用轨；
      EDL 无轨概念，LOW 主 clip 照常出事件）。
    - ``snap_scenes`` / ``snap_tolerance_s``：源片侧 clip 边界吸附到最近原片镜头
      切点（``scenes.npy`` 边界，±tol 秒内才吸附）。
    """

    min_confidence: str = "MEDIUM"
    low_policy: str = "exclude"
    snap_scenes: bool = True
    snap_tolerance_s: float = 1.0
    material_expand: bool = True   # 剪映卷轴取材扩展：核心窗口沿帧相似度扩到内容边界（反馈三轮）
    min_clip_s: float = 0.15       # 导出前碎片告警阈值（竞品 segments.builder「单帧片段=闪烁视频」）
    # 重复认领告警（2026-09-29 续31）: 多个导出 clip 指向原片同一区间时提示可合并。
    # 竞品 max_duplicate_scene_ratio 的同构安全形态——只提示, 不删答案（删答案形态实测砍
    # 正确段, 见 DECISIONS 续19/续31）。判据 = 重叠/较窄一方宽度 ≥ 该比例。
    duplicate_claim_warn: bool = True
    duplicate_claim_min_ratio: float = 0.8
    # 宽度比下限: 窄/宽 < 该值的两条不算重复认领。我方输出是「帧级窄 span + 场景池宽 span」
    # 分层并存, 宽包窄是常态（读图实测 test3 第 30/31 段: 8s 宽 span 含 2s 窄 span, 两条
    # 各自对应不同角色不同镜头且都定位正确）, 只比宽度相近的认领才是用户能感知的重复素材。
    duplicate_claim_min_width_ratio: float = 0.5
    # --- 展示层两件套（2026-09-29 用户拍板; 竞品 boundary_guard._record_boundary_split +
    #     exporting/segments/builder 单帧守卫语义重建）---
    # ① 时间线切点展开: 定位 span 内部的真实原片转场切点(scenes.npy)在 EDL/FCP7/剪映
    #    时间线上展开成多段——用户在 NLE 里看到真实剪辑切点而非跨镜长条。记录侧按源宽
    #    等比分配(匀速假设, 与剪映 speed 计算一致)。
    # ② 单帧守卫(硬): 切分**新产生**的碎片 < min_piece_s 时并入邻段, 绝不出 1 帧闪烁片;
    #    对既有 clip 维持"只告警不裁剪"(LOC-2001, 反馈既有拍板)不变。
    boundary_split_enabled: bool = True
    boundary_min_piece_s: float = 0.5


@dataclass
class RenderConfig:
    """成片渲染（2026-09-29 续30 立项；竞品 ``exporting.rendering.video_renderer`` 移植）。

    显式入口才触发（``/api/tasks/render`` / service ``render_movie``），既有定位与
    文本工程导出链路零改动 ⇒ 对生产基线零影响。竞品确证与工程先验的边界见
    ``media/ffmpeg/timeline_render.py`` 模块头与
    ``user_case/competitor_cutmatch/FINDINGS_VIDEO_RENDER_PORT.md``。
    """

    enabled: bool = True            # 渲染入口总闸（关闭时请求直接报错）
    crf: int = 18                   # 软件档质量（工程先验，与合并/素材链路同档）
    preset: str = "medium"
    prefer_hw: bool = True          # 先试硬件 H.264（本机 amf/qsv/nvenc），失败拉黑回退 libx264
    workers: int = 2                # 片段并发数（竞品在位常量 2/6；编码是 CPU/GPU 重活，取保守端）
    stall_timeout_s: float = 120.0  # 竞品确证停滞阈值语义（blob 数值 120.0 在位）
    timeout_s: float = 1800.0       # 单条 ffmpeg 命令总超时（blob 数值 1800.0 在位）
    sample_rate: int = 48000        # 统一音频采样率（blob 数值 48000 在位）——concat 流复制前提
    out_dir: str | Path | None = None   # None -> app data 下 ``rendered/``


@dataclass
class SourceMergeConfig:
    """多原片合并（2026-09-29 立项; 竞品 processing.video.concat + web.file_api.concat 移植）。

    用户给「分集/多段原片」时入库前物理拼接为单文件，下游索引/匹配仍单原片
    （竞品同款形态，非多索引并行）。单原片输入永不触发本链路 ⇒ 对现役基线零影响。
    口径差异见 ``media/ffmpeg/source_merge.py`` 模块头（mkvmerge 路由缺失等）。
    """

    enabled: bool = True           # 多路径入口总闸（关闭时 >1 原片直接报错而非合并）
    timeout_s: float = 3600.0      # 竞品确证 >1h 超时监护语义
    prefer_hw: bool = True         # 转码链先试硬件 HEVC 编码器，libx265(medium/CRF18) 兜底
    crf: int = 18                  # 竞品 libx265 兜底档（字节确证）


@dataclass
class AppConfig:
    """产品配置聚合入口。``data_dir`` None -> 用 ``paths`` 的平台默认。"""

    media: MediaConfig = field(default_factory=MediaConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    source_merge: SourceMergeConfig = field(default_factory=SourceMergeConfig)
    render: RenderConfig = field(default_factory=RenderConfig)
    data_dir: str | Path | None = None


_CFG_LOG = None


def _get_config_logger():
    global _CFG_LOG
    if _CFG_LOG is None:
        import logging
        _CFG_LOG = logging.getLogger("infrastructure.config")
    return _CFG_LOG


def _cast(value, default):
    """按默认值类型收敛 JSON 值。bool 必须先于 int 判（bool 是 int 子类）。"""
    if default is None or isinstance(default, (list, dict, tuple)):
        return value
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if isinstance(default, int) and not isinstance(default, bool):
        return int(value)
    if isinstance(default, float):
        return float(value)
    if isinstance(default, str):
        return str(value)
    return value


def _build_dataclass(cls, values: dict, **nested):
    """用字段名从 ``values`` 构造 dataclass；``nested`` 覆盖子 dataclass 字段。"""
    kwargs = {}
    for f in fields(cls):
        if f.name in nested:
            kwargs[f.name] = nested[f.name]
        elif f.name in values:
            kwargs[f.name] = _cast(values[f.name], getattr(cls(), f.name, None))
    return cls(**kwargs)


def _merge(dst_meta: dict, raw: dict, prefix: str = "") -> dict:
    """将 raw 的键递归合并到 dst，只保留已知字段（忽略未知，防 typo 吞掉）。"""
    out = dict(dst_meta)
    for k, v in raw.items():
        key = k if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            sub = dst_meta.get(k)
            if isinstance(sub, dict):
                out[k] = _merge(sub, v, key)
            else:
                out[k] = v
        else:
            out[k] = v
    return out


def load_config(path: str | Path | None = None) -> AppConfig:
    """构造 AppConfig：默认值 + 可选 JSON 覆盖。

    ``path`` 为 None 时返回纯默认。JSON 存在但非法 -> ``ConfigError``。
    """
    cfg = AppConfig()
    if path is None:
        return cfg
    p = Path(path)
    if not p.exists():
        raise ConfigError(f"config file not found: {p}")
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid config JSON in {p}: {exc}") from exc

    media = _merge(asdict(cfg.media), raw.get("media", {}))
    conf = _merge(asdict(cfg.pipeline.confidence), raw.get("confidence", {}))
    seq = _merge(asdict(cfg.pipeline.seq_align), raw.get("seq_align", {}))
    exp = _merge(asdict(cfg.export), raw.get("export", {}))
    dev = _merge(asdict(cfg.device), raw.get("device", {}))
    src_merge = _merge(asdict(cfg.source_merge), raw.get("source_merge", {}))
    render = _merge(asdict(cfg.render), raw.get("render", {}))
    # 泛化覆盖：以 dataclass 字段为唯一权威清单，杜绝「JSON 里写了但白名单没列 → 静默忽略」。
    # 未知键不再丢弃而是告警留痕（不静默出错）。
    pipe_known = {k: v for k, v in asdict(cfg.pipeline).items()
                  if k not in ("confidence", "seq_align")}
    pipe_raw = raw.get("pipeline", {}) or {}
    unknown = sorted(k for k in pipe_raw if k not in pipe_known)
    if unknown:
        _get_config_logger().warning("config JSON has unknown pipeline key(s) ignored: %s",
                                     ", ".join(unknown))
    pipe = _merge(pipe_known, {k: v for k, v in pipe_raw.items() if k in pipe_known})

    return AppConfig(
        media=_build_dataclass(MediaConfig, media),
        device=_build_dataclass(DeviceConfig, dev),
        pipeline=_build_dataclass(PipelineConfig, pipe,
                                  confidence=ConfidenceConfig(**conf),
                                  seq_align=SeqAlignConfig(**seq)),
        export=_build_dataclass(ExportConfig, exp),
        source_merge=_build_dataclass(SourceMergeConfig, src_merge),
        render=_build_dataclass(RenderConfig, render),
        data_dir=raw.get("data_dir", cfg.data_dir),
    )
