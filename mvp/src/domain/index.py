"""domain.index — 原片特征索引的元数据模型（纯数据，无 numpy）。

``IndexMeta`` 严格对应 INDEX_SPEC §3 的 ``index.json`` schema；惰性只包含可
JSON 序列化的 metadata。特征数组（``features.npy``/``times.npy``）属于
engine/feature_store 的 ``IndexBundle``，不放进纯数据 domain。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .enums import IndexValidationStatus


@dataclass(frozen=True)
class ExtractorConfig:
    """特征提取器的精确配置。``preprocess_sha`` 捕捉预处理配置的哈希，
    任一变化都应触发索引失效（INDEX_SPEC §4 的 extractor.preprocess_sha 判据）。"""

    normalize: str = "l2"
    resize: str = "518x518"
    mean_std: str = "imagenet"
    preprocess_sha: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ExtractorConfig":
        return cls(
            normalize=str(d.get("normalize", "l2")),
            resize=str(d.get("resize", "518x518")),
            mean_std=str(d.get("mean_std", "imagenet")),
            preprocess_sha=str(d.get("preprocess_sha", "")),
        )


@dataclass
class IndexMeta:
    """一个 Original Video 索引的 metadata（index.json 内容）。"""

    source_file: str
    file_size: int
    duration: float
    file_hash: str
    index_version: int = 1
    feature_model: str = "dinov2_vits14"
    feature_version: str = "handwritten_vits14_cls_384d@0.5fps_l2"
    sampling_fps: float = 0.5
    feature_dim: int = 384
    num_frames: int = 0
    backend: str = "cpu"
    created_at: str = ""
    device_machine_id: str = ""
    extractor: ExtractorConfig = field(default_factory=ExtractorConfig)

    def to_dict(self) -> dict:
        return {
            "index_version": self.index_version,
            "source_file": self.source_file,
            "file_size": self.file_size,
            "duration": self.duration,
            "file_hash": self.file_hash,
            "feature_model": self.feature_model,
            "feature_version": self.feature_version,
            "sampling_fps": self.sampling_fps,
            "feature_dim": self.feature_dim,
            "num_frames": self.num_frames,
            "backend": self.backend,
            "created_at": self.created_at,
            "device_machine_id": self.device_machine_id,
            "extractor": self.extractor.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "IndexMeta":
        return cls(
            source_file=str(d["source_file"]),
            file_size=int(d["file_size"]),
            duration=float(d["duration"]),
            file_hash=str(d["file_hash"]),
            index_version=int(d.get("index_version", 1)),
            feature_model=str(d.get("feature_model", "dinov2_vits14")),
            feature_version=str(d.get("feature_version", "")),
            sampling_fps=float(d.get("sampling_fps", 0.5)),
            feature_dim=int(d.get("feature_dim", 384)),
            num_frames=int(d.get("num_frames", 0)),
            backend=str(d.get("backend", "cpu")),
            created_at=str(d.get("created_at", "")),
            device_machine_id=str(d.get("device_machine_id", "")),
            extractor=ExtractorConfig.from_dict(d.get("extractor") or {}),
        )


@dataclass(frozen=True)
class IndexValidation:
    """FeatureStore.validate_index 的结果。INVALID 时带 reason。"""

    status: IndexValidationStatus
    reason: str | None = None

    def to_dict(self) -> dict:
        return {"status": self.status.value, "reason": self.reason}
