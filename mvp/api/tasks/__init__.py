"""mvp.api.tasks — 后端异步任务基础设施（adapter/infrastructure 层）。

不实现算法，只做：任务模型 + 后台 worker（调 SourceLocatorService）+ TaskManager。
"""
from __future__ import annotations

from .manager import TaskManager
from .models import Task, TaskStage, TaskStatus
from .worker import map_progress_stage, run_worker

__all__ = ["TaskManager", "Task", "TaskStage", "TaskStatus", "map_progress_stage", "run_worker"]
