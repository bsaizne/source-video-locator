"""app.models — Application Service 层的 DTO（进度 / 取消）。纯数据，无 IO。

- ``ProgressStage``：显式阶段枚举（GUI 用于状态机 / 进度条标签）。
- ``ProgressEvent``：一次进度回调的载荷，``stage/current/total/message``。
- ``CancellationToken``：``threading.Event`` 封装，供 GUI 后台线程取消长任务。
  取消在 Index build / edited feature extraction / segment loop / export 处检查。
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from enum import Enum


class ProgressStage(str, Enum):
    """应用服务的显式进度阶段。"""

    INDEX_BUILD = "INDEX_BUILD"
    EDITED_FEATURE_EXTRACTION = "EDITED_FEATURE_EXTRACTION"
    SEGMENT_DETECTION = "SEGMENT_DETECTION"
    CANDIDATE_RETRIEVAL = "CANDIDATE_RETRIEVAL"
    LOCALIZATION = "LOCALIZATION"
    CONFIDENCE = "CONFIDENCE"
    EXPORT = "EXPORT"


@dataclass(frozen=True)
class ProgressEvent:
    """一次进度回调。``total`` 为 0 表示未知。"""

    stage: ProgressStage
    current: int = 0
    total: int = 0
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "stage": self.stage.value,
            "current": self.current,
            "total": self.total,
            "message": self.message,
        }


class CancellationToken:
    """可取消标志。GUI 在后台线程调用：``cancel()`` 置位；service 轮询
    ``is_cancelled()`` / 必要时 ``raise_if_cancelled()`` 抛 ``ApplicationError``。
    """

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    def is_cancelled(self) -> bool:
        return self._event.is_set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            from infrastructure.errors import ApplicationError

            raise ApplicationError("operation cancelled")
