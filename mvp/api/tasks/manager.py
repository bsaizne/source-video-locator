"""tasks.manager — TaskManager：分析任务的提交 / 查询 / 取消。

只做任务生命周期管理（创建 + 后台 worker 调度 + 状态字典）。真正的分析由
:class:`SourceLocatorService` 在 worker 线程里完成。``run_in_background`` 可注入，
生产用 ``threading.Thread``，测试传入同步执行函数即可获得确定性时序（不起真线程）。
"""
from __future__ import annotations

import queue
import threading
from typing import Callable

from .models import Task, TaskKind
from .worker import run_worker

# 默认后台执行：起一个 daemon 线程跑 `fn`。
def _background_thread(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, name="svl-task-worker", daemon=True).start()


class TaskManager:
    """持有所有在跑 / 已完成的任务，提供提交、查询、取消。线程安全。"""

    def __init__(self, service, *, run_in_background: Callable[[Callable[[], None]], None] | None = None,
                 log: Callable[..., None] | None = None, isolated: bool = False):
        self._service = service
        self._run = run_in_background or _background_thread
        self._log = log or (lambda *a, **k: None)
        # ④ 任务级进程隔离（2026-10-07）：True = analyze/render 在独立子进程执行
        # （硬崩只损失本任务）。生产（dependencies）开启；测试用假 service 默认关。
        self._isolated = isolated
        self._tasks: dict[str, Task] = {}
        self._lock = threading.Lock()

    def submit_analyze(self, edited_path: str, original_path: str,
                       original_paths: list[str] | None = None,
                       refine: bool | None = None) -> Task:
        """创建一个 PENDING 任务并在后台调度 worker。返回 Task（可在任何线程查）。"""
        task = Task(edited_path=edited_path, original_path=original_path,
                    original_paths=list(original_paths or []), refine=refine)
        with self._lock:
            self._tasks[task.task_id] = task
        self._log("task submitted task_id=%s edited=%s original=%s originals=%s",
                  task.task_id, edited_path, original_path, len(task.original_paths))
        self._run(lambda: run_worker(task, self._service, log=self._log,
                                    isolated=self._isolated))
        return task

    def submit_render(self, batch, *, out_dir: str | None = None,
                      min_confidence: str | None = None, low_policy: str | None = None,
                      snap_scenes: bool | None = None) -> Task:
        """创建成片渲染任务（2026-09-29 续30）。结果批**在提交时锁定**放进 task，
        worker 只读它，不读"会话最新批"（避免排队期间新定位把渲染目标换掉）。"""
        task = Task(kind=TaskKind.RENDER,
                    edited_path=str(getattr(batch, "edited_video", "") or ""),
                    original_path=str(getattr(batch, "original_video", "") or ""),
                    render_batch=batch,
                    render_params={"out_dir": out_dir or "",
                                   "min_confidence": min_confidence,
                                   "low_policy": low_policy,
                                   "snap_scenes": snap_scenes})
        with self._lock:
            self._tasks[task.task_id] = task
        self._log("task submitted (render) task_id=%s original=%s edited=%s",
                  task.task_id, task.original_path, task.edited_path)
        # ④ 隔离标志必须与 submit_analyze 同源传递：漏了就走默认 False ⇒ 渲染永远在线程内跑，
        # 而 DML/ffmpeg 崩溃照样拖垮整个后端（2026-10-07 r15 包内成片实测抓到：
        # 日志里没有 `isolated child started`，也没有 spawn 回落留痕 ⇒ 分支根本没进）。
        self._run(lambda: run_worker(task, self._service, log=self._log,
                                     isolated=self._isolated))
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
