"""routes.results — 定位结果 + 导出。

- ``POST /api/results``：原片为 ``original_path`` 或最近一次 /api/index 记录的原片；
  两者皆无 → 400。返回 ``ResultBatch.to_dict()`` 原样（拍平 confidence，冻结线格式）。
- ``POST /api/results/load``：读回已导出的 ``*.results.json`` → 恢复为当前会话结果批。
- ``POST /api/export``：导出最近一次 /api/results 得到的结果批。
"""
from __future__ import annotations

import copy
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from domain.enums import ResultSource
from infrastructure.errors import ApplicationError, public_error

from ..dependencies import AppContext, get_context
from ..schemas import ExportRequest, ResultsRequest

router = APIRouter()


class ExcludeRequest(BaseModel):
    """手动排除/恢复某段的导出（反馈四轮 r16：内容不匹配的段不进剪辑软件）。"""

    result_id: str
    excluded: bool


class OverrideRequest(BaseModel):
    """手动替换某条结果的原片区（Phase 22 反馈 ⑧/⑨：选择片段替换在本软件内完成，
    替换后的批才是导出源——保证导出的工程是最终完成态）。"""

    result_id: str
    start: float
    end: float


class LoadResultsRequest(BaseModel):
    """读回一个已导出的结果批（``*.results.json``），恢复会话上下文。

    补这条链是因为：后端 ``service.load_results`` 早就存在，但没有 HTTP 端点，
    前端重启后只能重新跑一遍定位——用户的手工修正随之作废。
    """

    path: str


@router.post("/api/results")
def locate(req: ResultsRequest, ctx: AppContext = Depends(get_context)) -> dict:
    original = req.original_path or ctx.current_original
    if original is None:
        return JSONResponse(
            status_code=400,
            content={
                "error": "no_original",
                "detail": "call /api/index first or provide original_path",
            },
        )
    batch = ctx.service.locate(req.edited_path, original)
    ctx.current_batch = batch
    ctx.current_original = Path(original)
    return batch.to_dict()


@router.post("/api/results/load")
def load_results(req: LoadResultsRequest, ctx: AppContext = Depends(get_context)) -> dict:
    """从磁盘读回结果批并设为当前会话批（之后可直接 /api/export）。"""
    try:
        batch = ctx.service.load_results(req.path)
    except Exception as exc:                       # 缺文件/坏 JSON/schema 不符
        return JSONResponse(
            status_code=400,
            content={"error": "load_failed", "code": "LOC-1103",
                     "message": "结果文件无法读取，请重新运行分析或改选其它结果文件。",
                     "detail": f"{type(exc).__name__}: {exc}"},
        )
    ctx.current_batch = batch
    ctx.current_original = Path(batch.original_video) if batch.original_video else None
    return batch.to_dict()


@router.post("/api/results/exclude")
def exclude(req: ExcludeRequest, ctx: AppContext = Depends(get_context)) -> dict:
    batch = ctx.current_batch or ctx.service.last_result_batch()
    if batch is None:
        return JSONResponse(status_code=400, content={"error": "no_results",
                                                      "detail": "no results batch"})
    target = next((r for r in batch.results if r.result_id == req.result_id), None)
    if target is None:
        return JSONResponse(status_code=404, content={"error": "no_such_result",
                                                      "detail": req.result_id})
    target.excluded = bool(req.excluded)
    return target.to_dict()


@router.post("/api/results/override")
def override(req: OverrideRequest, ctx: AppContext = Depends(get_context)) -> dict:
    batch = ctx.current_batch or ctx.service.last_result_batch()
    if batch is None:
        return JSONResponse(status_code=400, content={"error": "no_results",
                                                      "detail": "no results batch"})
    if req.end <= req.start:
        return JSONResponse(status_code=400, content={"error": "bad_range",
                                                      "detail": "end must be > start"})
    target = next((r for r in batch.results if r.result_id == req.result_id), None)
    if target is None:
        return JSONResponse(status_code=404, content={"error": "no_such_result",
                                                      "detail": req.result_id})
    # auto/manual 双轨：保留原自动结果副本（与 domain 设计一致）
    if not target.manual_override:
        auto = copy.deepcopy(target)
        auto.manual_override = False
        auto.auto_result = None
        target.auto_result = auto
    target.original = type(target.original)(start=round(req.start, 3),
                                            end=round(req.end, 3))
    target.source = ResultSource.MANUAL
    target.manual_override = True
    target.manual_timestamp = datetime.now(timezone.utc).isoformat()
    return target.to_dict()


@router.post("/api/export")
def export(req: ExportRequest, ctx: AppContext = Depends(get_context)) -> dict:
    # 优先用本请求上下文的中转结果批，否则回退 service 最近一次 locate 的结果批
    # （异步 /api/tasks/analyze 不写 ctx.current_batch，只写 service._current_batch）。
    batch = ctx.current_batch or ctx.service.last_result_batch()
    if batch is None:
        return JSONResponse(
            status_code=400,
            content={
                "error": "no_results",
                "detail": "no results batch; call /api/results first",
            },
        )
    # Phase 22：format=json 走原 *.results.json 通道；edl / fcp7_xml / jianying
    # 走 NLE 工程导出（策略默认取 config.export，请求可逐次覆盖）。
    fmt = (req.format or "json").lower()
    try:
        if fmt == "json":
            path = ctx.service.export_results(batch, out_dir=req.output_dir)
        else:
            path = ctx.service.export_project(
                batch, fmt=fmt, out_dir=req.output_dir or None,
                min_confidence=req.min_confidence, low_policy=req.low_policy,
                snap_scenes=req.snap_scenes,
                material_width=req.material_width)
    except ApplicationError as exc:
        body = public_error(exc)
        body["error"] = "export_failed"
        return JSONResponse(status_code=400, content=body)
    # 导出即弃会话预览：清空预览缓存目录，避免自动生成的预览片段长期占用磁盘。
    if ctx.preview_service is not None:
        try:
            ctx.preview_service.cleanup()
        except Exception:  # noqa: BLE001 - 清理失败不阻塞导出
            pass
    return {"path": str(path),
            "warnings": list(getattr(ctx.service, "last_export_warnings", []) or [])}
