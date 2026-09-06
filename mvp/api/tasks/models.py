"""tasks.models — 后端异步任务的纯数据模型。

只建模一次分析任务的状态（status/stage/progress/result/error）与实时进度广播；
**不实现算法**；真正的编排由 :class:`SourceLocatorService` 承担（worker 只调用它）。

线程安全：worker 线程写状态 + 广播，查询线程读，WebSocket 订阅方经 ``queue.Queue``
接收进度帧。``token``（CancellationToken）、订阅队列与锁不参与序列化。
"""
from __future__ import annotations

import queue
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.models import CancellationToken


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStage(str, Enum):
    IDLE = "idle"
    INDEXING = "indexing"
    SEGMENTING = "segmenting"
    EMBEDDING = "embedding"
    RETRIEVAL = "retrieval"
    EXPORTING = "exporting"
    FINISHED = "finished"


@dataclass
class Task:
    """一次后台分析任务。``result`` 存 ``ResultBatch.to_dict()``（或 None）；``error`` 存
    失败原因。所有状态变更经 ``*_set*`` 方法（锁内），并自动向订阅者广播对应帧。"""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    edited_path: str = ""
    original_path: str = ""
    status: TaskStatus = TaskStatus.PENDING
    stage: TaskStage = TaskStage.IDLE
    progress: int = 0
    created_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    result: dict | None = None
    error: str | None = None
    cancel_requested: bool = False
    token: CancellationToken = field(default_factory=CancellationToken, repr=False, compare=False)
    _message: str = field(default="", repr=False, compare=False)
    _subscribers: list[queue.Queue] = field(default_factory=list, repr=False, compare=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    # -- 订阅 / 广播（线程安全） ------------------------------------------- #
    def subscribe(self) -> queue.Queue:
        """新增一个订阅者队列。放入一个当前状态快照帧（避免错过连接前的状态），返回队列。
        订阅方用 ``queue.get()`` 阻塞读取，完成后调 :meth:`unsubscribe`。"""
        q: queue.Queue = queue.Queue(maxsize=256)
        with self._lock:
            self._subscribers.append(q)
            snapshot = self._frame()
        self._put(q, snapshot)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    def broadcast_current(self) -> None:
        """向所有订阅者重放当前帧（TaskManager.publish 用）。"""
        with self._lock:
            frame = self._frame()
            subs = list(self._subscribers)
        self._send(frame, subs)

    def _send(self, frame: dict, subs: list[queue.Queue]) -> None:
        for q in subs:
            self._put(q, frame)

    @staticmethod
    def _put(q: queue.Queue, frame: dict) -> None:
        try:
            q.put_nowait(frame)
        except queue.Full:
            # 慢消费者：丢弃旧帧，腾一个位置保证最新状态能送达（进度帧可覆盖）。
            try:
                q.get_nowait()
            except queue.Empty:
                pass
            try:
                q.put_nowait(frame)
            except queue.Full:
                pass

    # -- 帧构造 ------------------------------------------------------------ #
    def _frame(self) -> dict:
        if self.status is TaskStatus.COMPLETED:
            return {"type": "completed", "task_id": self.task_id}
        if self.status is TaskStatus.FAILED:
            return {"type": "failed", "task_id": self.task_id, "error": self.error or ""}
        if self.status is TaskStatus.CANCELLED:
            return {"type": "cancelled", "task_id": self.task_id}
        # running / pending:进度帧
        return {
            "type": "progress",
            "task_id": self.task_id,
            "status": self.status.value,
            "stage": self.stage.value,
            "progress": self.progress,
            "message": self._message,
        }

    # -- 状态变更（worker 线程）→ 更新 + 广播 -------------------------------- #
    def mark_running(self) -> None:
        with self._lock:
            self.status = TaskStatus.RUNNING
            subs = list(self._subscribers)
            frame = self._frame()
        self._send(frame, subs)

    def update_progress(self, stage: TaskStage, percent: int, message: str = "") -> None:
        with self._lock:
            if self.status is TaskStatus.PENDING:
                self.status = TaskStatus.RUNNING
            self.stage = stage
            self.progress = max(0, min(100, percent))
            if message:
                self._message = message
            subs = list(self._subscribers)
            frame = self._frame()
        self._send(frame, subs)

    def mark_completed(self, result: dict) -> None:
        with self._lock:
            self.status = TaskStatus.COMPLETED
            self.stage = TaskStage.FINISHED
            self.progress = 100
            self.finished_at = _now_iso()
            self.result = result
            subs = list(self._subscribers)
            frame = self._frame()
        self._send(frame, subs)

    def mark_failed(self, error: str) -> None:
        with self._lock:
            self.status = TaskStatus.FAILED
            self.finished_at = _now_iso()
            self.error = error
            subs = list(self._subscribers)
            frame = self._frame()
        self._send(frame, subs)

    def mark_cancelled(self) -> None:
        with self._lock:
            self.status = TaskStatus.CANCELLED
            self.finished_at = _now_iso()
            subs = list(self._subscribers)
            frame = self._frame()
        self._send(frame, subs)

    # -- 取消（main 线程） -------------------------------------------------- #
    def cancel(self) -> None:
        """请求取消：置位 CancellationToken 并标记 cancel_requested。实际状态由 worker
        检测到取消后转为 CANCELLED。"""
        self.token.cancel()
        with self._lock:
            self.cancel_requested = True

    # -- 读取 --------------------------------------------------------------- #
    def to_dict(self) -> dict:
        with self._lock:
            return {
                "task_id": self.task_id,
                "status": self.status.value,
                "stage": self.stage.value,
                "progress": self.progress,
                "created_at": self.created_at,
                "finished_at": self.finished_at,
                "result": self.result,
                "error": self.error,
                "cancel_requested": self.cancel_requested,
                "message": self._message,
            }
