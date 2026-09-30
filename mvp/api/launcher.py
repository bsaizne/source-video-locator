"""launcher — 后端启动共用入口（打包 exe ``run_backend.py`` 与 ``python -m mvp.api.main``）。

端口（2026-09-28 续19-T1-3 接线补全）：``port=0`` = 让操作系统分配随机端口。
真实监听地址在 uvicorn **绑定成功之后**才打印 ``BACKEND_LISTEN <host> <port>``
到 stdout（uvicorn 0.52 在 ``startup()`` 末尾置 ``server.started=True``；绑定失败
直接 ``sys.exit(STARTUP_FAILURE)``，公告**不会**输出 ⇒ 宿主侧只会得到健康检查
超时，不存在假公告）。Electron 主进程解析该行，把 port/healthUrl/页面 query
的 ``svl_port`` 切到真实端口。
"""
from __future__ import annotations

from typing import Any, Iterable, Sequence

import uvicorn

LISTEN_PREFIX = "BACKEND_LISTEN"


def listen_host_port(server: Any) -> tuple[str, int] | None:
    """从已启动的 uvicorn Server 读实际绑定地址（多 listener 取第一个）；未监听=None。"""
    for srv in getattr(server, "servers", None) or []:
        for sock in getattr(srv, "sockets", None) or []:
            try:
                addr = sock.getsockname()
            except OSError:
                continue
            if addr and len(addr) >= 2:
                host = str(addr[0])
                # 通配地址改写成回环，宿主直连即可（本项目只允许监听本机）。
                if host in ("0.0.0.0", "::"):
                    host = "127.0.0.1"
                return host, int(addr[1])
    return None


def format_listen_line(host: str, port: int) -> str:
    return f"{LISTEN_PREFIX} {host} {port}"


def startup_announce_lines(
    server: Any, *, host: str, port: int, extra: Sequence[str] = ()
) -> list[str]:
    """startup 成功后的 stdout 公告：extra 行（通道/门禁）+ BACKEND_LISTEN 真实地址。

    ``server.started`` 为假时返回空列表（宁缺毋假——宿主端以超时失败收口）。
    请求的 port=0 时若读不到 socket（理论不该发生），同样不猜测端口。
    """
    if not getattr(server, "started", False):
        return []
    lines = list(extra)
    real = listen_host_port(server)
    if real is None:
        return []
    lines.append(format_listen_line(*real))
    return lines


def make_server(app: Any, *, host: str, port: int,
                announce: Iterable[str] = ()) -> "uvicorn.Server":
    """构造已挂好「绑定成功后公告 BACKEND_LISTEN」钩子的 uvicorn Server。"""
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="info"))
    extra = list(announce)
    original_startup = server.startup

    async def _startup(sockets: list[Any] | None = None) -> None:
        await original_startup(sockets=sockets)  # type: ignore[misc]
        for line in startup_announce_lines(server, host=host, port=port, extra=extra):
            print(line, flush=True)

    server.startup = _startup  # type: ignore[method-assign]
    return server


def run_app(app: Any, *, host: str, port: int, announce: Iterable[str] = ()) -> None:
    """起 uvicorn；绑定成功后向 stdout 公告真实监听地址（port=0 → OS 随机端口）。"""
    make_server(app, host=host, port=port, announce=announce).run()
