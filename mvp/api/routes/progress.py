"""routes.progress — 实时任务进度 WebSocket。

- ``GET /ws/progress/{task_id}``：订阅任务实时进度帧（来自 TaskManager.subscribe）。
  服务端推送进度帧 ``{type:"progress", task_id, status, stage, progress, message}``；终态帧
  ``{type:"completed"|"failed"|"cancelled", task_id, [error]}``。
- 客户端可发 ``{"type":"cancel"}``：请求取消（TaskManager.cancel → CancellationToken，
  **不强制杀线程**；worker 自检测取消耗）。

实现：一个后台 reader task 持续读客户端消息（取消指令）；主协程从任务订阅队列读帧并推送，
每帧后检查 cancel。两种 await 互不阻塞。本阶段进度为**阶段级**；不实现算法。
任务不存在 → ``{type:"error", error:"unknown_task"}`` 并关闭。
"""
from __future__ import annotations

import asyncio
import json
import queue

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from ..dependencies import AppContext, get_context

router = APIRouter()

_POLL_TIMEOUT = 0.5
_TERMINAL = ("completed", "failed", "cancelled", "error")


def _get_frame(q: queue.Queue, timeout: float = _POLL_TIMEOUT):
    """在 worker/主进程线程阻塞取一帧；超时返回 None（供 asyncio.to_thread）。"""
    try:
        return q.get(timeout=timeout)
    except queue.Empty:
        return None


@router.websocket("/ws/progress/{task_id}")
async def ws_progress(websocket: WebSocket, task_id: str,
                      ctx: AppContext = Depends(get_context)) -> None:
    tm = ctx.task_manager
    if tm is None or tm.get(task_id) is None:
        await websocket.accept()
        await websocket.send_json(
            {"type": "error", "error": "unknown_task", "detail": f"unknown task {task_id}"}
        )
        await websocket.close()
        return

    q = tm.subscribe(task_id)
    await websocket.accept()
    cancel_q: asyncio.Queue[bool] = asyncio.Queue()

    async def _reader() -> None:
        """持续读客户端消息；遇到 {type:cancel} 置入取消队列。"""
        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    msg = json.loads(raw)
                except (ValueError, TypeError):
                    msg = {}
                if msg.get("type") == "cancel":
                    await cancel_q.put(True)
        except (WebSocketDisconnect, RuntimeError):
            pass

    reader_task = asyncio.create_task(_reader())
    try:
        while True:
            frame = await asyncio.to_thread(_get_frame, q)
            if frame is not None:
                await websocket.send_json(frame)
                if frame.get("type") in _TERMINAL:
                    break
            if not cancel_q.empty():
                try:
                    cancel_q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                tm.cancel(task_id)
    finally:
        reader_task.cancel()
        tm.unsubscribe(task_id, q)
