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
from dataclasses import asdict, dataclass, field
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
    """

    # CONFIDENCE_DESIGN §3.2 初始权重（占位，需 H1 标定）
    weights: list[float] = field(default_factory=lambda: [0.30, 0.25, 0.15, 0.15, 0.08, 0.07])
    high_threshold: float = 0.75
    medium_threshold: float = 0.55
    # --- 硬 flag / 归一化阈值（占位，待标定）---
    margin_low: float = 0.08          # best-sec 差距 < best*s 倍 -> 竞争（low_candidate_margin）
    similar_band: float = 0.10        # 落在 best score X 倍内的候选视为"相似"
    max_similar: int = 2              # 相似候选数 > N -> multiple_similar_candidates
    window_width_min_s: float = 1.0   # 窗口过窄 -> source_window_anomaly
    window_width_max_s: float = 60.0  # 与 clustering.MAX_WINDOW_S 对齐（超限 -> anomaly）
    nreps_dispersed: int = 5          # n_reps < N -> query 覆盖分散
    qcov_dispersed: float = 0.4       # qcov < X -> query 覆盖分散
    scene_div_montage: int = 2        # scene_div >= N -> montage 指示
    sim_high: float = 0.6             # mean_sim 高于此值但结构异常 -> 暗场景混淆
    cov_low: float = 0.3              # best_cover 低于此值 -> 结构异常
    sim_std_high: float = 0.35        # 候选内代表 sim 标准差高于此值 -> 命中不均匀/分散
    finloc_stable_s: float = 4.0      # span_stability 归一化锚点（秒）
    min_run_s: float = 2.0            # 最长 run 短于此 -> finloc_unstable
    dark_penalty: float = 0.8         # 暗场景混淆时的 score 倍率


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
    vectorized: bool = False          # 反对角线 numpy DP（未来整段对齐用）
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


@dataclass
class AppConfig:
    """产品配置聚合入口。``data_dir`` None -> 用 ``paths`` 的平台默认。"""

    media: MediaConfig = field(default_factory=MediaConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    export: ExportConfig = field(default_factory=ExportConfig)
    data_dir: str | Path | None = None


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

    media = _merge(
        {"ffmpeg_path": cfg.media.ffmpeg_path, "ffprobe_path": cfg.media.ffprobe_path,
         "timeout_s": cfg.media.timeout_s},
        raw.get("media", {}),
    )
    conf = _merge(asdict(cfg.pipeline.confidence), raw.get("confidence", {}))
    seq = _merge(asdict(cfg.pipeline.seq_align), raw.get("seq_align", {}))
    exp = _merge(asdict(cfg.export), raw.get("export", {}))
    dev = _merge(
        {"preferred": cfg.device.preferred, "onnx_model": cfg.device.onnx_model,
         "dml_device_id": cfg.device.dml_device_id, "dml_batch_size": cfg.device.dml_batch_size},
        raw.get("device", {}),
    )
    pipe = _merge(
        {"index_sampling_fps": cfg.pipeline.index_sampling_fps,
         "edited_segment_fps": cfg.pipeline.edited_segment_fps,
         "max_orig_span_s": cfg.pipeline.max_orig_span_s,
         "span_width_factor": cfg.pipeline.span_width_factor,
         "min_span_s": cfg.pipeline.min_span_s,
         "retrieval_top_k": cfg.pipeline.retrieval_top_k,
         "clustering_max_window_s": cfg.pipeline.clustering_max_window_s,
         "ranking_alpha": cfg.pipeline.ranking_alpha,
         "seg_cut_abs": cfg.pipeline.seg_cut_abs,
         "seg_z_thresh": cfg.pipeline.seg_z_thresh,
         "seg_min_shot_s": cfg.pipeline.seg_min_shot_s,
         "seg_smooth": cfg.pipeline.seg_smooth,
         "montage_min_frames": cfg.pipeline.montage_min_frames,
         "montage_min_sim": cfg.pipeline.montage_min_sim,
         "montage_cluster_gap_s": cfg.pipeline.montage_cluster_gap_s,
         "montage_weak_cover": cfg.pipeline.montage_weak_cover,
         "montage_weak_sim": cfg.pipeline.montage_weak_sim,
         "subspan_min_cover": cfg.pipeline.subspan_min_cover,
         "subspan_min_sim": cfg.pipeline.subspan_min_sim,
         "subspan_iou_merge": cfg.pipeline.subspan_iou_merge,
         "subspan_max_keep": cfg.pipeline.subspan_max_keep,
         "card_black_ratio": cfg.pipeline.card_black_ratio,
         "card_bright_lo": cfg.pipeline.card_bright_lo,
         "card_bright_hi": cfg.pipeline.card_bright_hi,
         "card_bright_max_spread": cfg.pipeline.card_bright_max_spread,
         "card_bright_min_area_frac": cfg.pipeline.card_bright_min_area_frac,
         "card_shot_ratio": cfg.pipeline.card_shot_ratio,
         "card_run_ratio": cfg.pipeline.card_run_ratio,
         "seg_max_shot_s": cfg.pipeline.seg_max_shot_s,
         "seg_fine_cut_factor": cfg.pipeline.seg_fine_cut_factor,
         "seg_fine_z_factor": cfg.pipeline.seg_fine_z_factor,
         "seg_fine_min_shot_s": cfg.pipeline.seg_fine_min_shot_s,
         "seg_twopass_enabled": cfg.pipeline.seg_twopass_enabled,
         "seg_twopass_coarse_step_frames": cfg.pipeline.seg_twopass_coarse_step_frames,
         "seg_twopass_fine_window_frames": cfg.pipeline.seg_twopass_fine_window_frames,
         "seg_twopass_fine_step_frames": cfg.pipeline.seg_twopass_fine_step_frames,
         "seg_twopass_min_shot_s": cfg.pipeline.seg_twopass_min_shot_s,
         "flash_mean_th": cfg.pipeline.flash_mean_th,
         "flash_frac_th": cfg.pipeline.flash_frac_th,
         "flash_margin_s": cfg.pipeline.flash_margin_s,
         "flash_dyn_min_shot_s": cfg.pipeline.flash_dyn_min_shot_s,
         "flash_merge_frac": cfg.pipeline.flash_merge_frac,
         "bright_spike_delta": cfg.pipeline.bright_spike_delta,
         "bright_spike_peak_th": cfg.pipeline.bright_spike_peak_th,
         "text_anchor_enabled": cfg.pipeline.text_anchor_enabled,
         "text_anchor_min_sim": cfg.pipeline.text_anchor_min_sim,
         "text_anchor_min_gain": cfg.pipeline.text_anchor_min_gain,
         "seq_dp_enabled": cfg.pipeline.seq_dp_enabled,
         "seq_dp_order_lambda": cfg.pipeline.seq_dp_order_lambda,
         "seq_dp_skip_penalty": cfg.pipeline.seq_dp_skip_penalty,
         "seq_dp_min_score": cfg.pipeline.seq_dp_min_score,
         "patch_rerank_enabled": cfg.pipeline.patch_rerank_enabled,
         "patch_rerank_keep_near": cfg.pipeline.patch_rerank_keep_near,
         "patch_weights_path": cfg.pipeline.patch_weights_path,
         "scene_recall_enabled": cfg.pipeline.scene_recall_enabled,
         "scene_top_k": cfg.pipeline.scene_top_k,
         "scene_max_expand_frames": cfg.pipeline.scene_max_expand_frames,
         "event_recall_enabled": cfg.pipeline.event_recall_enabled,
         "event_top_k": cfg.pipeline.event_top_k,
         "event_max_expand_frames": cfg.pipeline.event_max_expand_frames,
         "temporal_repair_enabled": cfg.pipeline.temporal_repair_enabled,
         "tr_neighbor_gap_s": cfg.pipeline.tr_neighbor_gap_s,
         "tr_outlier_min_dist_s": cfg.pipeline.tr_outlier_min_dist_s,
         "temporal_ambiguity_enabled": cfg.pipeline.temporal_ambiguity_enabled,
         "ta_max_downgrade": cfg.pipeline.ta_max_downgrade,
         "timeline_prior_enabled": cfg.pipeline.timeline_prior_enabled,
         "ta_band_s": cfg.pipeline.ta_band_s,
         "ta_max_cover_drop": cfg.pipeline.ta_max_cover_drop,
         "dense_retry_min_sim": cfg.pipeline.dense_retry_min_sim,
         "conflict_rerank_enabled": cfg.pipeline.conflict_rerank_enabled,
         "conflict_max_mover_width_s": cfg.pipeline.conflict_max_mover_width_s,
         "conflict_overlap_min_s": cfg.pipeline.conflict_overlap_min_s,
         "conflict_alt_min_sim": cfg.pipeline.conflict_alt_min_sim,
         "conflict_max_drop": cfg.pipeline.conflict_max_drop,
        },
        raw.get("pipeline", {}),
    )

    return AppConfig(
        media=MediaConfig(
            ffmpeg_path=media["ffmpeg_path"],
            ffprobe_path=media["ffprobe_path"],
            timeout_s=float(media["timeout_s"]),
        ),
        device=DeviceConfig(
            preferred=str(dev["preferred"]),
            onnx_model=dev["onnx_model"],
            dml_device_id=int(dev["dml_device_id"]),
            dml_batch_size=int(dev["dml_batch_size"]),
        ),
        pipeline=PipelineConfig(
            index_sampling_fps=float(pipe["index_sampling_fps"]),
            edited_segment_fps=float(pipe["edited_segment_fps"]),
            max_orig_span_s=float(pipe["max_orig_span_s"]),
            span_width_factor=float(pipe["span_width_factor"]),
            min_span_s=float(pipe["min_span_s"]),
            retrieval_top_k=int(pipe["retrieval_top_k"]),
            clustering_max_window_s=float(pipe["clustering_max_window_s"]),
            ranking_alpha=float(pipe["ranking_alpha"]),
            seg_cut_abs=float(pipe["seg_cut_abs"]),
            seg_z_thresh=float(pipe["seg_z_thresh"]),
            seg_min_shot_s=float(pipe["seg_min_shot_s"]),
            seg_smooth=int(pipe["seg_smooth"]),
            montage_min_frames=int(pipe["montage_min_frames"]),
            montage_min_sim=float(pipe["montage_min_sim"]),
            montage_cluster_gap_s=float(pipe["montage_cluster_gap_s"]),
            montage_weak_cover=float(pipe["montage_weak_cover"]),
            montage_weak_sim=float(pipe["montage_weak_sim"]),
            subspan_min_cover=float(pipe["subspan_min_cover"]),
            subspan_min_sim=float(pipe["subspan_min_sim"]),
            subspan_iou_merge=float(pipe["subspan_iou_merge"]),
            subspan_max_keep=int(pipe["subspan_max_keep"]),
            card_black_ratio=float(pipe["card_black_ratio"]),
            card_bright_lo=float(pipe["card_bright_lo"]),
            card_bright_hi=float(pipe["card_bright_hi"]),
            card_bright_max_spread=float(pipe["card_bright_max_spread"]),
            card_bright_min_area_frac=float(pipe["card_bright_min_area_frac"]),
            card_shot_ratio=float(pipe["card_shot_ratio"]),
            card_run_ratio=float(pipe["card_run_ratio"]),
            seg_max_shot_s=float(pipe["seg_max_shot_s"]),
            seg_fine_cut_factor=float(pipe["seg_fine_cut_factor"]),
            seg_fine_z_factor=float(pipe["seg_fine_z_factor"]),
            seg_fine_min_shot_s=float(pipe["seg_fine_min_shot_s"]),
            seg_twopass_enabled=bool(pipe["seg_twopass_enabled"]),
            seg_twopass_coarse_step_frames=int(pipe["seg_twopass_coarse_step_frames"]),
            seg_twopass_fine_window_frames=int(pipe["seg_twopass_fine_window_frames"]),
            seg_twopass_fine_step_frames=int(pipe["seg_twopass_fine_step_frames"]),
            seg_twopass_min_shot_s=float(pipe["seg_twopass_min_shot_s"]),
            flash_mean_th=float(pipe["flash_mean_th"]),
            flash_frac_th=float(pipe["flash_frac_th"]),
            flash_margin_s=float(pipe["flash_margin_s"]),
            flash_dyn_min_shot_s=float(pipe["flash_dyn_min_shot_s"]),
            flash_merge_frac=float(pipe["flash_merge_frac"]),
            bright_spike_delta=float(pipe["bright_spike_delta"]),
            bright_spike_peak_th=float(pipe["bright_spike_peak_th"]),
            text_anchor_enabled=bool(pipe["text_anchor_enabled"]),
            text_anchor_min_sim=float(pipe["text_anchor_min_sim"]),
            text_anchor_min_gain=float(pipe["text_anchor_min_gain"]),
            seq_dp_enabled=bool(pipe["seq_dp_enabled"]),
            seq_dp_order_lambda=float(pipe["seq_dp_order_lambda"]),
            seq_dp_skip_penalty=float(pipe["seq_dp_skip_penalty"]),
            seq_dp_min_score=float(pipe["seq_dp_min_score"]),
            patch_rerank_enabled=bool(pipe["patch_rerank_enabled"]),
            patch_rerank_keep_near=float(pipe["patch_rerank_keep_near"]),
            patch_weights_path=pipe.get("patch_weights_path"),
            scene_recall_enabled=bool(pipe["scene_recall_enabled"]),
            scene_top_k=int(pipe["scene_top_k"]),
            scene_max_expand_frames=int(pipe["scene_max_expand_frames"]),
            event_recall_enabled=bool(pipe["event_recall_enabled"]),
            event_top_k=int(pipe["event_top_k"]),
            event_max_expand_frames=int(pipe["event_max_expand_frames"]),
            temporal_repair_enabled=bool(pipe["temporal_repair_enabled"]),
            tr_neighbor_gap_s=float(pipe["tr_neighbor_gap_s"]),
            tr_outlier_min_dist_s=float(pipe["tr_outlier_min_dist_s"]),
            temporal_ambiguity_enabled=bool(pipe["temporal_ambiguity_enabled"]),
            ta_max_downgrade=str(pipe["ta_max_downgrade"]),
            timeline_prior_enabled=bool(pipe["timeline_prior_enabled"]),
            ta_band_s=float(pipe["ta_band_s"]),
            ta_max_cover_drop=float(pipe["ta_max_cover_drop"]),
            dense_retry_min_sim=float(pipe["dense_retry_min_sim"]),
            conflict_rerank_enabled=bool(pipe["conflict_rerank_enabled"]),
            conflict_max_mover_width_s=float(pipe["conflict_max_mover_width_s"]),
            conflict_overlap_min_s=float(pipe["conflict_overlap_min_s"]),
            conflict_alt_min_sim=float(pipe["conflict_alt_min_sim"]),
            conflict_max_drop=float(pipe["conflict_max_drop"]),
            confidence=ConfidenceConfig(**conf),
            seq_align=SeqAlignConfig(**seq),
        ),
        export=ExportConfig(
            min_confidence=str(exp["min_confidence"]),
            low_policy=str(exp["low_policy"]),
            snap_scenes=bool(exp["snap_scenes"]),
            snap_tolerance_s=float(exp["snap_tolerance_s"]),
            material_expand=bool(exp["material_expand"]),
        ),
        data_dir=raw.get("data_dir", cfg.data_dir),
    )
