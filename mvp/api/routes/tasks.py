"""routes.tasks — 后端异步任务（定位分析 / 成片渲染）。

- ``POST /api/tasks/analyze``：创建任务并后台调度 → ``{task_id}``。
- ``POST /api/tasks/render``：渲染**提交时锁定的会话结果批**为单个成片 → ``{task_id}``
  （2026-09-29 续30，竞品 ``exporting.rendering.video_renderer`` 移植）。
- ``GET  /api/tasks/{task_id}``：查询任务状态（status/stage/progress/result/error）。
- ``POST /api/tasks/{task_id}/cancel``：请求取消 → ``{status: "cancel_requested"}``。
- ``WS   /ws/progress/{task_id}``：本阶段未实现（仅占位回复 not implemented）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..dependencies import AppContext, get_context
from ..schemas import AnalyzeTaskRequest, RenderTaskRequest

router = APIRouter()


def _task_manager(ctx: AppContext):
    """取 TaskManager；未配置则返回 None。"""
    return ctx.task_manager


@router.post("/api/tasks/analyze")
def create_task(req: AnalyzeTaskRequest, ctx: AppContext = Depends(get_context)) -> dict:
    sources = [p for p in (req.original_paths or []) if p.strip()]
    if req.original_path and req.original_path.strip() and req.original_path not in sources:
        sources.insert(0, req.original_path)
    if not req.edited_path or not sources:
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request",
                     "detail": "edited_path and at least one original file are required"},
        )
    tm = _task_manager(ctx)
    if tm is None:
        return JSONResponse(
            status_code=500,
            content={"error": "no_task_manager", "detail": "task manager not configured"},
        )
    # ≥2 段原片：original_path 置空，由 worker 合并后回写（2026-09-29 video.concat 移植）。
    single = "" if len(sources) > 1 else sources[0]
    task = tm.submit_analyze(req.edited_path, single, original_paths=sources,
                             refine=req.refine)
    return {"task_id": task.task_id}


@router.post("/api/tasks/render")
def create_render_task(req: RenderTaskRequest, ctx: AppContext = Depends(get_context)) -> dict:
    """渲染会话当前结果批为成片（异步任务；进度/取消与 /api/tasks/analyze 同通道）。

    结果批口径与 ``/api/export`` 一致：优先本会话 ``ctx.current_batch``，否则回退
    service 最近一次 locate 的批。**提交时把批锁进任务**，排队期间新定位不会改变渲染目标。
    """
    batch = ctx.current_batch or ctx.service.last_result_batch()
    if batch is None:
        return JSONResponse(
            status_code=400,
            content={"error": "no_results",
                     "detail": "no results batch; call /api/results first"},
        )
    tm = _task_manager(ctx)
    if tm is None:
        return JSONResponse(
            status_code=500,
            content={"error": "no_task_manager", "detail": "task manager not configured"},
        )
    task = tm.submit_render(batch, out_dir=req.output_dir or None,
                            min_confidence=req.min_confidence,
                            low_policy=req.low_policy, snap_scenes=req.snap_scenes)
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
