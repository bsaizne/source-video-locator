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
    dml_batch_size: int = 8


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
class PipelineConfig:
    """冻结流水线参数（MVP 基线，见 MVP_ARCHITECTURE §8）。"""

    index_sampling_fps: float = 0.5
    edited_segment_fps: float = 2.0
    # 检索 Top-K 冻结值 = 20（Phase 14A/16B 采用，禁调）
    retrieval_top_k: int = 20
    clustering_max_window_s: float = 60.0
    ranking_alpha: float = 0.5
    # --- 查询单元切分参数（占位，待真实 edited 视频标定；禁 sweep）---
    # 产品约束：偏向下切分（过长可接受、碎片化更危险）。
    seg_cut_abs: float = 0.30
    seg_z_thresh: float = 2.0
    seg_min_shot_s: float = 1.0
    seg_smooth: int = 1
    confidence: ConfidenceConfig = field(default_factory=ConfidenceConfig)


@dataclass
class AppConfig:
    """产品配置聚合入口。``data_dir`` None -> 用 ``paths`` 的平台默认。"""

    media: MediaConfig = field(default_factory=MediaConfig)
    device: DeviceConfig = field(default_factory=DeviceConfig)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
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
    dev = _merge(
        {"preferred": cfg.device.preferred, "onnx_model": cfg.device.onnx_model,
         "dml_device_id": cfg.device.dml_device_id, "dml_batch_size": cfg.device.dml_batch_size},
        raw.get("device", {}),
    )
    pipe = _merge(
        {"index_sampling_fps": cfg.pipeline.index_sampling_fps,
         "edited_segment_fps": cfg.pipeline.edited_segment_fps,
         "retrieval_top_k": cfg.pipeline.retrieval_top_k,
         "clustering_max_window_s": cfg.pipeline.clustering_max_window_s,
         "ranking_alpha": cfg.pipeline.ranking_alpha,
         "seg_cut_abs": cfg.pipeline.seg_cut_abs,
         "seg_z_thresh": cfg.pipeline.seg_z_thresh,
         "seg_min_shot_s": cfg.pipeline.seg_min_shot_s,
         "seg_smooth": cfg.pipeline.seg_smooth},
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
            retrieval_top_k=int(pipe["retrieval_top_k"]),
            clustering_max_window_s=float(pipe["clustering_max_window_s"]),
            ranking_alpha=float(pipe["ranking_alpha"]),
            seg_cut_abs=float(pipe["seg_cut_abs"]),
            seg_z_thresh=float(pipe["seg_z_thresh"]),
            seg_min_shot_s=float(pipe["seg_min_shot_s"]),
            seg_smooth=int(pipe["seg_smooth"]),
            confidence=ConfidenceConfig(**conf),
        ),
        data_dir=raw.get("data_dir", cfg.data_dir),
    )
