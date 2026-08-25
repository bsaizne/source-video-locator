"""domain — 纯数据模型与枚举（无 IO / numpy / torch / media 依赖）。

分层：UI → ApplicationService → LocalizationEngine → FeatureStore → DeviceBackend
/ FFmpeg。domain 是各层共享的纯数据类型；infrastructure 是跨切面的配置/日志/
错误模型/路径。
"""
from .enums import ConfidenceLevel, IndexValidationStatus, ResultSource
from .index import ExtractorConfig, IndexMeta, IndexValidation
from .models import (Alternative, Candidate, Confidence, IndexProgress, Result,
                     ResultBatch, TimeSpan)

__all__ = [
    "ConfidenceLevel",
    "ResultSource",
    "IndexValidationStatus",
    "ExtractorConfig",
    "IndexMeta",
    "IndexValidation",
    "Alternative",
    "Candidate",
    "Confidence",
    "Result",
    "ResultBatch",
    "TimeSpan",
    "IndexProgress",
]
