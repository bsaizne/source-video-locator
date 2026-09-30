"""main — uvicorn 入口。

暴露 ``app`` 供 ``uvicorn mvp.api.main:app``；也支持 ``python -m mvp.api.main`` 本地启动。

端口（2026-09-28 续20 接线补全）：``SVL_API_PORT`` 可覆盖默认 8765；填 ``0`` = 让操作系统
分配随机端口。实际端口由 :mod:`mvp.api.launcher` 在 uvicorn **绑定成功后**打印的
``BACKEND_LISTEN <host> <port>`` 行回报给 Electron 侧解析（会话/通道公告同批输出；
令牌本身由父进程 env 注入，不经 stdout 回读）。
"""
from __future__ import annotations

import os

from .app import create_app
from .session import resolve_session_token

app = create_app()

DEFAULT_PORT = 8765


def resolve_listen() -> tuple[str, int]:
    host = os.environ.get("SVL_API_HOST") or "127.0.0.1"
    raw = (os.environ.get("SVL_API_PORT") or "").strip() or str(DEFAULT_PORT)
    try:
        port = int(raw)
    except ValueError:
        port = DEFAULT_PORT
    return host, max(0, port)


if __name__ == "__main__":
    from .launcher import run_app
    from .session import announce_lines

    _host, _port = resolve_listen()
    run_app(app, host=_host, port=_port, announce=announce_lines(resolve_session_token()))
