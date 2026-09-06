"""tasks.manager — TaskManager：分析任务的提交 / 查询 / 取消。

只做任务生命周期管理（创建 + 后台 worker 调度 + 状态字典）。真正的分析由
:class:`SourceLocatorService` 在 worker 线程里完成。``run_in_background`` 可注入，
生产用 ``threading.Thread``，测试传入同步执行函数即可获得确定性时序（不起真线程）。
"""
from __future__ import annotations

import queue
import threading
from typing import Callable

from .models import Task
from .worker import run_worker

# 默认后台执行：起一个 daemon 线程跑 `fn`。
def _background_thread(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, name="svl-task-worker", daemon=True).start()


class TaskManager:
    """持有所有在跑 / 已完成的任务，提供提交、查询、取消。线程安全。"""

    def __init__(self, service, *, run_in_background: Callable[[Callable[[], None]], None] | None = None,
                 log: Callable[..., None] | None = None):
        self._service = service
        self._run = run_in_background or _background_thread
        self._log = log or (lambda *a, **k: None)
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def submit_analyze(self, edited_path: str, original_path: str) -> Task:
        """创建一个 PENDING 任务并在后台调度 worker。返回 Task（可在任何线程查）。"""
        task = Task(edited_path=edited_path, original_path=original_path)
        with self._lock:
            self._tasks[task.task_id] = task
        self._log("task submitted task_id=%s edited=%s original=%s",
                  task.task_id, edited_path, original_path)
        self._run(lambda: run_worker(task, self._service, log=self._log))
        return task

    def get(self, task_id: str) -> Task | None:
        with self._lock:
            return self._tasks.get(task_id)

    def cancel(self, task_id: str) -> bool:
        """请求取消。返回是否存在该任务；存在则置位 CancellationToken + cancel_requested。"""
        task = self.get(task_id)
        if task is None:
            return False
        task.cancel()
        self._log("cancel requested task_id=%s", task_id)
        return True

    # -- 实时进度订阅（WebSocket 层用） ------------------------------------- #
    def subscribe(self, task_id: str) -> queue.Queue | None:
        """为任务新增一个进度订阅队列（含一个当前状态快照帧）。任务不存在返回 None。"""
        task = self.get(task_id)
        if task is None:
            return None
        return task.subscribe()

    def unsubscribe(self, task_id: str, q: queue.Queue) -> None:
        task = self.get(task_id)
        if task is not None:
            task.unsubscribe(q)

    def publish(self, task_id: str) -> None:
        """向该任务所有订阅者重放当前帧（WebSocket 层 / 测试用）。"""
        task = self.get(task_id)
        if task is not None:
            task.broadcast_current()

    def clear(self) -> None:
        """清空所有任务（测试/进程内使用）。"""
        with self._lock:
            self._tasks.clear()
