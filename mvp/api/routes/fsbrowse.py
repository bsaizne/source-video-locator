"""routes.fsbrowse — ``GET /api/fs/browse``：素材入库浏览（盘符/目录/白名单视频）。

薄壳：语义全在 ``infrastructure.fsbrowse``（竞品 web.file_api.browser 移植）。
错误口径与 media 路由同族：detail 只回**名字**不回完整路径（日志脱敏同立场）。

- 200：``{kind, path, parent, drives, entries, free_bytes?, total_bytes?}``
- 400 ``invalid_path``：非法路径（ValueError）
- 404 ``not_found`` / ``not_a_directory``：不存在 / 是文件
- 403 ``permission_denied``：目录无读取权限
"""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from infrastructure import fsbrowse

router = APIRouter()


@router.get("/api/fs/browse")
def browse(path: str = ""):
    try:
        return fsbrowse.browse(path or None)
    except ValueError:
        return JSONResponse(status_code=400,
                            content={"error": "invalid_path", "detail": "path must not be empty"})
    except NotADirectoryError as exc:
        return JSONResponse(status_code=404,
                            content={"error": "not_a_directory", "detail": str(exc)})
    except FileNotFoundError as exc:
        return JSONResponse(status_code=404,
                            content={"error": "not_found", "detail": str(exc)})
    except PermissionError as exc:
        return JSONResponse(status_code=403,
                            content={"error": "permission_denied", "detail": str(exc)})
