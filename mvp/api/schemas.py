"""schemas — 桥的请求/响应模型（纯 API 层，不复制 domain）。

只负责 API 输入输出。结果的线格式直接复用冻结的 ``ResultBatch.to_dict()``
（拍平 confidence），不在此镜像一套 Pydantic，避免与冻结 domain 双写。
"""
from __future__ import annotations

from pydantic import BaseModel


class IndexRequest(BaseModel):
    video_path: str


class IndexResponse(BaseModel):
    status: str = "completed"
    frames: int
    backend: dict[str, str]   # {device_name, device_type}（device_type 仅供展示）


class IndexStatusResponse(BaseModel):
    """真实索引状态（透传 FeatureStore.validate_index）：VALID / INVALID / MISSING + 原因。"""

    status: str
    reason: str | None = None


class AnalyzeRequest(BaseModel):
    edited_path: str


class ResultsRequest(BaseModel):
    edited_path: str
    original_path: str | None = None


class ExportRequest(BaseModel):
    """导出请求。``format``：``json``（默认，*.results.json）/ ``edl`` /
    ``fcp7_xml`` / ``jianying``（Phase 22 NLE 工程导出）。其余可选覆盖导出策略。"""

    output_dir: str
    format: str = "json"
    min_confidence: str | None = None
    low_policy: str | None = None
    snap_scenes: bool | None = None
    material_width: str | None = None   # scene=所在完整镜头(默认) / core=仅核心定位窗口


class AnalyzeTaskRequest(BaseModel):
    edited_path: str = ""
    original_path: str = ""


class PreviewRequest(BaseModel):
    """从原片抽取一段区间：``original_path`` + ``[start, end]``（秒）。"""

    original_path: str
    start: float
    end: float


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1"


class DeviceSettingsRequest(BaseModel):
    preferred: str


class DeviceSettingsResponse(BaseModel):
    preferred: str
    actual_device_name: str
    actual_device_type: str
    is_accelerator: bool
    fallback: bool
    available_devices: list[str]
