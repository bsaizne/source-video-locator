"""routes.preview — 视频预览（片段抽取 + 播放文件服务）。

- ``POST /api/preview``：从 ``original_path`` 抽取 ``[start, end]`` 区间为 mp4，返回
  ``{path, duration}``。独立能力，不改 locate / 置信度 / Result schema。
- ``GET /api/preview/media/{filename}``：以 ``FileResponse`` 供抽取出的预览片段播放
  （Starlette 支持 HTTP Range，HTML5 video 可拖动）。
- ``GET /api/preview/edited``：供当前会话的编辑视频播放（仅服务会话记录的那份，
  不以客户端传入路径为准，避免任意文件读取）。

安全：media 路由只取 ``path.name``（basename），并限制在 ``preview_dir`` 内，杜绝目录穿越。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from ..dependencies import AppContext, get_context
from ..schemas import PreviewRequest
from ..services.preview_service import PreviewService

router = APIRouter()


def _preview_service(ctx: AppContext) -> PreviewService:
    """惰性构建预览服务；测试通过 ``ctx.preview_service`` 注入 fake。"""
    if ctx.preview_service is None:
        ctx.preview_service = PreviewService(ffmpeg=ctx.service.ffmpeg)
    return ctx.preview_service


@router.post("/api/preview")
def preview(req: PreviewRequest, ctx: AppContext = Depends(get_context)) -> dict:
    """抽取原片段并返回产物路径与时长。失败抛 PreviewError -> 500。"""
    svc = _preview_service(ctx)
    pr = svc.extract_segment(req.original_path, req.start, req.end)
    return {"path": str(pr.path), "duration": pr.duration}


@router.get("/api/preview/media/{filename}")
def preview_media(filename: str, ctx: AppContext = Depends(get_context)) -> FileResponse:
    """服务一个抽取出的预览片段（只按 basename 取，限 preview_dir 内）。"""
    svc = _preview_service(ctx)
    name = Path(filename).name
    if name != filename:
        # 拒绝任何带路径分隔的标识（防目录穿越）；basename 正常进不来。
        raise HTTPException(status_code=400, detail="invalid preview filename")
    file = svc.preview_dir / name
    if not file.is_file():
        raise HTTPException(status_code=404, detail="preview not found")
    return FileResponse(file)


@router.get("/api/preview/edited")
def preview_edited(ctx: AppContext = Depends(get_context)):
    """服务当前会话的编辑视频（仅记录过的那份）。无批/文件缺失 -> 4xx。"""
    batch = ctx.current_batch
    if batch is None or not batch.edited_video:
        return JSONResponse(
            status_code=400,
            content={
                "error": "no_edited_video",
                "detail": "no edited video in session; run /api/results first",
            },
        )
    file = Path(batch.edited_video)
    if not file.is_file():
        raise HTTPException(status_code=404, detail="edited video not found")
    return FileResponse(file)
