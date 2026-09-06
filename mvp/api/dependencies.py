"""dependencies — DI：service 实例 + 轻量请求状态。

桥只持有 :class:`SourceLocatorService` 实例与请求状态（当前原片 / 当前结果批）。
**初始化不加载模型、不建索引**——核验过 :class:`SourceLocatorService` 构造是惰性的
（``ffmpeg``/``backend``/``store`` 都是 lazy property，``__init__`` 只算路径并置状态）。

路由用 ``Depends(get_context)`` 取上下文；测试可 ``app.dependency_overrides[get_context]``
一处注入 fake。不散落 global（实例集中在 DI 层）。
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from app.locator_service import SourceLocatorService
from domain import ResultBatch

from .services.preview_service import PreviewService
from .tasks import TaskManager


@dataclass
class AppContext:
    """桥进程内的请求状态。``current_original`` 由 /api/index 或 /api/results 记录，
    ``current_batch`` 由 /api/results 产生，供 /api/export 复用。
    ``task_manager`` 承担异步分析任务的生命周期（/api/tasks/*）。
    ``preview_service`` 惰性持有（/api/preview），首次用到才用 service 的 ffmpeg 构建。"""

    service: SourceLocatorService
    task_manager: TaskManager | None = None
    preview_service: PreviewService | None = None
    current_original: Path | None = None
    current_batch: ResultBatch | None = None


@lru_cache
def get_context() -> AppContext:
    """首次调用才构造 service（惰性、廉价；不加载模型/不建索引）。TaskManager 复用
    同一 service 实例，避免双份后端。"""
    service = SourceLocatorService()
    return AppContext(service=service, task_manager=TaskManager(service))


def get_locator_service(ctx: AppContext = Depends(get_context)) -> SourceLocatorService:
    """便利依赖：只取 service。子依赖 override ``get_context`` 即同时覆盖本处。"""
    return ctx.service
