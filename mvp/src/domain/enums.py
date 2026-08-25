"""domain.enums — 产品级枚举（纯数据，无 IO / numpy / media 依赖）。

``str`` 枚举保证序列化结果为产品契约定义的字符串（如 "HIGH" / "auto"）。
"""
from __future__ import annotations

from enum import Enum


class ConfidenceLevel(str, Enum):
    """三档置信度。``score`` 是工程 confidence score，不是模型概率。"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ResultSource(str, Enum):
    """一条结果的来源：自动 vs 人工修正。"""

    AUTO = "auto"
    MANUAL = "manual"


class IndexValidationStatus(str, Enum):
    """FeatureStore.validate_index 的三态结果。"""

    VALID = "VALID"
    INVALID = "INVALID"
    MISSING = "MISSING"
