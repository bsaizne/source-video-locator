"""main — uvicorn 入口。

暴露 ``app`` 供 ``uvicorn mvp.api.main:app``；也支持 ``python -m mvp.api.main`` 本地启动。
"""
from __future__ import annotations

from .app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
