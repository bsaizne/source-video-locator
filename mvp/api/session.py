"""api.session — 本机 HTTP 门禁（会话令牌 + 构建期发行闸门）。

为什么要有（2026-09-28 续19, T1-3）：我方 FastAPI 之前监听固定 ``127.0.0.1:8765`` 且
**无任何鉴权**，同机任意进程（含浏览器里的网页）都能调我们的分析接口、读用户视频路径。
参照桌面软件通行做法（本机随机端口 + 会话令牌 + 常量时间比较 + 配置缺失拒启）落一层最小门禁。

规则：
- ``SVL_BUILD_CHANNEL=release``（打包发行）⇒ **强制**：必须有 ``SVL_SESSION_TOKEN``，
  否则 ``create_app`` 直接 ``ConfigError`` 拒启（不静默降级）。这正是我方 2026-09-22
  「CI 缺 .env.production → 整包静默跑在 Mock 上」事故的同型解法。
- 开发通道（默认）⇒ 未给令牌时门禁关闭并 warning 留痕（不打断本地手工 uvicorn 调试）。
- 校验：``X-Locator-Session`` 头 或 ``?svl_session=`` 查询参数，``hmac.compare_digest``
  常量时间比较；``/api/health`` 与 ``/docs``/``/openapi.json`` 放行（就绪探针与文档）。
"""
from __future__ import annotations

import hmac
import os
import secrets

from fastapi import Request
from fastapi.responses import JSONResponse

from infrastructure.errors import ConfigError
from infrastructure.logging import get_logger

SESSION_HEADER = "X-Locator-Session"
SESSION_QUERY = "svl_session"
OPEN_PATHS = ("/api/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico")
TOKEN_BYTES = 32

_log = get_logger("api.session")


def build_channel() -> str:
    return (os.environ.get("SVL_BUILD_CHANNEL") or "dev").strip().lower()


def is_release_channel() -> bool:
    return build_channel() == "release"


def new_session_token() -> str:
    return secrets.token_urlsafe(TOKEN_BYTES)


def resolve_session_token() -> str | None:
    """发行通道缺令牌 = 拒启；开发通道缺令牌 = 门禁关闭（留痕）。"""
    token = (os.environ.get("SVL_SESSION_TOKEN") or "").strip()
    if token:
        return token
    if is_release_channel():
        raise ConfigError(
            "release build requires SVL_SESSION_TOKEN (local API gate); "
            "refusing to start with an unauthenticated local server")
    return None


def announce_lines(token: str | None) -> list[str]:
    """供 Electron 侧解析的启动公告（不含令牌本身——令牌由父进程注入，无需回读）。"""
    lines = ["SVL_BUILD_CHANNEL %s" % build_channel()]
    lines.append("SVL_SESSION_ENABLED %s" % ("1" if token else "0"))
    return lines


def session_middleware(token: str | None):
    """返回一个可直接 ``app.middleware("http")`` 注册的函数。"""
    if not token:
        def _passthrough(request: Request, call_next):   # pragma: no cover - 关闭态
            return call_next(request)
        return _passthrough

    expected = token.encode("utf-8")

    async def _gate(request: Request, call_next):
        path = request.url.path
        if request.method == "OPTIONS" or path in OPEN_PATHS or not path.startswith("/api/"):
            return await call_next(request)
        got = request.headers.get(SESSION_HEADER) or request.query_params.get(SESSION_QUERY) or ""
        if hmac.compare_digest(got.encode("utf-8"), expected):
            return await call_next(request)
        _log.warning("rejected unauthenticated local request %s %s", request.method, path)
        return JSONResponse(status_code=401, content={
            "error": "session_required", "code": "LOC-1201",
            "message": "本机服务校验未通过，请重启软件。", "detail": "missing or bad session token"})

    return _gate
