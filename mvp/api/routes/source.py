"""routes.source — ``POST /api/source/merge``：多原片合并（竞品 web.file_api.concat 对应）。

入库前的独立显式步骤：把 N 段原片文件合并为单个稳定命名缓存文件，返回路径供
后续 /api/index、/api/tasks/analyze 当普通单原片使用。合并语义/监护/回退链全部
复用 ``media.ffmpeg.source_merge``（业务不在桥层重复实现）。

错误口径：路径非法 400；``MediaError``（缺轨道/时长未知/合并失败）经全局
``LocatorError`` handler → 500 + ``public_error``（LOC 码 + 对外话术，不吐完整本机路径，
与日志脱敏同立场）。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..dependencies import AppContext, get_context
from ..schemas import SourceMergeRequest, SourceMergeResponse

router = APIRouter()

_MIN_SOURCES = 2  # 0/1 个文件无需合并（竞品：文件夹只有 1 个视频时直接使用）


@router.post("/api/source/merge", response_model=SourceMergeResponse)
def merge_sources(req: SourceMergeRequest, ctx: AppContext = Depends(get_context)):
    sources = [p for p in (req.paths or []) if str(p).strip()]
    if len(sources) < _MIN_SOURCES:
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request",
                     "detail": f"at least {_MIN_SOURCES} original files are required"},
        )
    info = ctx.service.merge_originals(sources)
    return SourceMergeResponse(
        merged_path=str(info["merged_path"]),
        mode=str(info["mode"]),
        reused=bool(info["reused"]),
        duration_s=info.get("duration_s"),
    )
