"""routes.media — ``GET /api/media/info``：ffprobe 读视频文件元数据（时长/fps/分辨率/大小）。

纯只读探测，复用冻结的 ``media.ffmpeg``（``FFmpegIO.metadata`` → ffprobe，
MKV duration 取 format.duration 的坑已在该层修复），桥内不写第二套探测逻辑。
前端用它消灭项目卡写死的片名与恒 0 的「时长」（2026-09-28 续19 遗留 P0）。

错误口径（与 preview 一致的 ``error``+``detail`` JSON）：
- 400 ``invalid_path``：空 / 相对路径 / 裸文件名（前端 ``isAbsPath`` 同口径）。
- 404 ``file_not_found``：文件不存在；detail 只回**文件名**（日志脱敏同立场，不吐完整路径）。
- 500：ffprobe 失败（非视频/损坏）→ ``MediaError`` 走既有 ``public_error``（LOC 码 + 话术）。
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..dependencies import AppContext, get_context
from ..schemas import MediaInfoResponse

router = APIRouter()


@router.get("/api/media/info", response_model=MediaInfoResponse)
def media_info(path: str, ctx: AppContext = Depends(get_context)):
    """探测 ``path`` 指向的视频文件，返回展示用元数据。"""
    p = Path(path)
    if not str(path).strip() or not p.is_absolute():
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_path", "detail": "path must be absolute"},
        )
    if not p.is_file():
        return JSONResponse(
            status_code=404,
            content={"error": "file_not_found", "detail": p.name},
        )
    meta = ctx.service.ffmpeg.metadata(p)
    return MediaInfoResponse(
        path=str(meta.path),
        duration=meta.duration,
        fps=meta.fps,
        width=meta.width,
        height=meta.height,
        size_bytes=meta.size_bytes,
        format_name=meta.format_name,
        video_codec=meta.video_codec,
        has_audio=meta.has_audio,
    )
