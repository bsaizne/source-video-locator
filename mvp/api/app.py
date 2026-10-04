"""app — FastAPI 桥装配。

只做：创建 FastAPI 实例、挂路由、CORS、异常处理、请求级 session 中间件、lifespan。
**不创建业务对象、不初始化 LocatorService**（由 ``dependencies.get_context`` 惰性承担）。
复用已有 ``infrastructure.logging``（startup 调幂等 ``configure_logging()``），不建第二套日志。
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from infrastructure.errors import LocatorError, public_error
from infrastructure.logging import configure_logging, get_logger, set_session_id

from .dependencies import get_context
from .session import build_channel, resolve_session_token, session_middleware
from .routes import analysis, fsbrowse, health, index, logs, media, preview, progress, results, settings, source, tasks

_log = get_logger("api")


def _cleanup_backend() -> None:
    """关闭时安全清理推理后端（service 从未被构造则跳过，不强制加载）。"""
    info = get_context.cache_info()
    if info.currsize == 0:
        return  # service 未构造 → 无 backend 可清理
    backend = getattr(get_context().service, "_backend", None)
    if backend is not None:
        cleanup = getattr(backend, "cleanup", None)
        if callable(cleanup):
            try:
                cleanup()
            except Exception:  # noqa: BLE001 - shutdown 清理失败不阻塞退出
                _log.warning("backend cleanup failed on shutdown", exc_info=True)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        configure_logging()  # 幂等 startup 钩子
        _log.info("api server started")
        yield
        _cleanup_backend()
        _log.info("api server stopped")

    app = FastAPI(title="Source Video Locator Bridge", version="0.1", lifespan=lifespan)

    # 请求级 session + 访问日志（每请求生成新 session；输出 module=api session=<sid> POST /api/index）
    @app.middleware("http")
    async def _session_middleware(request: Request, call_next):
        set_session_id(None)
        response = await call_next(request)
        _log.info("%s %s", request.method, request.url.path)
        return response

    # 本机门禁（T1-3）：注册在 CORS 之前 ⇒ CORS 仍是最外层，401 也带跨域头可被前端读到。
    session_token = resolve_session_token()
    if session_token is None:
        _log.warning("local API session gate DISABLED (no SVL_SESSION_TOKEN; channel=%s)",
                     build_channel())
    else:
        _log.info("local API session gate enabled (channel=%s)", build_channel())
    app.middleware("http")(session_middleware(session_token))

    # 路由
    for r in (health.router, index.router, analysis.router, results.router, tasks.router,
              progress.router, preview.router, settings.router, logs.router, media.router,
              source.router, fsbrowse.router):
        app.include_router(r)

    # 异常处理
    @app.exception_handler(LocatorError)
    async def _locator_handler(request: Request, exc: LocatorError) -> JSONResponse:
        _log.exception("locator error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(status_code=500, content=public_error(exc))

    @app.exception_handler(HTTPException)
    async def _http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        _log.debug("http error %s %s: %s", request.method, request.url.path, exc.status_code)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(Exception)
    async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        _log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=public_error(exc))

    # CORS 放最外层，保证预检 (OPTIONS) 在访问日志之前被处理
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:5174"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    return app
