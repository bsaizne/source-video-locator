"""routes.logs — 日志快照（Phase 22 用户反馈 ⑮：一键复制 / 下载压缩包）。

- ``GET /api/logs/recent``：最新日志尾部文本（默认 48KB），供 UI 一键复制。
- ``GET /api/logs/archive``：日志目录全部日志打成 zip 下载。
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from infrastructure.logging import LOG_FILENAME, log_dir

router = APIRouter()


@router.get("/api/logs/recent")
def recent(bytes_limit: int = 49152) -> dict:
    """返回最新日志尾部文本（截断头部并标注）。"""
    p = Path(log_dir()) / LOG_FILENAME
    if not p.exists():
        return {"path": str(p), "truncated": False, "text": ""}
    data = p.read_bytes()
    truncated = len(data) > bytes_limit
    tail = data[-bytes_limit:] if truncated else data
    text = tail.decode("utf-8", errors="replace")
    if truncated:
        text = "…（仅最近 48KB，完整内容请下载压缩包）\n" + text
    return {"path": str(p), "truncated": truncated, "text": text}


@router.get("/api/logs/archive")
def archive() -> Response:
    """把日志目录下全部日志文件打成 zip 返回（下载）。"""
    d = Path(log_dir())
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(d.glob("*.log*")):
            if f.is_file():
                zf.write(f, arcname=f.name)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="video_locator_logs.zip"'},
    )
