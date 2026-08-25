"""app — Application Service 层（用例编排 + Result 汇总 + 持久化 + 进度/取消）。

UI 的唯一入口。只做 orchestrate / progress / cancellation / error 汇总，
把冻结链路（engine.retrieval/clustering/ranking/finloc/confidence）串起来，
不写视觉算法、不触碰冻结语义。
"""
from .locator_service import SourceLocatorService
from .models import CancellationToken, ProgressEvent, ProgressStage

__all__ = ["SourceLocatorService", "CancellationToken", "ProgressEvent",
           "ProgressStage"]
