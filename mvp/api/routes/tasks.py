"""routes.tasks — 后端异步分析任务。

- ``POST /api/tasks/analyze``：创建任务并后台调度 → ``{task_id}``。
- ``GET  /api/tasks/{task_id}``：查询任务状态（status/stage/progress/result/error）。
- ``POST /api/tasks/{task_id}/cancel``：请求取消 → ``{status: "cancel_requested"}``。
- ``WS   /ws/progress/{task_id}``：本阶段未实现（仅占位回复 not implemented）。

本阶段不实现真实进度与 WebSocket 推送（下一阶段接入 service hook 后补）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..dependencies import AppContext, get_context
from ..schemas import AnalyzeTaskRequest

router = APIRouter()


def _task_manager(ctx: AppContext):
    """取 TaskManager；未配置则返回 None。"""
    return ctx.task_manager


@router.post("/api/tasks/analyze")
def create_task(req: AnalyzeTaskRequest, ctx: AppContext = Depends(get_context)) -> dict:
    if not req.edited_path or not req.original_path:
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request", "detail": "edited_path and original_path are required"},
        )
    tm = _task_manager(ctx)
    if tm is None:
        return JSONResponse(
            status_code=500,
            content={"error": "no_task_manager", "detail": "task manager not configured"},
        )
    task = tm.submit_analyze(req.edited_path, req.original_path)
    return {"task_id": task.task_id}


@router.get("/api/tasks/{task_id}")
def query_task(task_id: str, ctx: AppContext = Depends(get_context)) -> dict:
    tm = _task_manager(ctx)
    if tm is None:
        return JSONResponse(
            status_code=500,
            content={"error": "no_task_manager", "detail": "task manager not configured"},
        )
    task = tm.get(task_id)
    if task is None:
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "detail": f"unknown task {task_id}"},
        )
    return task.to_dict()


@router.post("/api/tasks/{task_id}/cancel")
def cancel_task(task_id: str, ctx: AppContext = Depends(get_context)) -> dict:
    tm = _task_manager(ctx)
    if tm is None:
        return JSONResponse(
            status_code=500,
            content={"error": "no_task_manager", "detail": "task manager not configured"},
        )
    if not tm.cancel(task_id):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "detail": f"unknown task {task_id}"},
        )
    return {"status": "cancel_requested"}
