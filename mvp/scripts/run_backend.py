"""run_backend — 生产后端 PyInstaller 入口。

打包后以单进程启动 FastAPI 桥（127.0.0.1:8765）。宿主/端口可用环境变量
``SVL_BACKEND_HOST`` / ``SVL_BACKEND_PORT`` 覆盖（Electron 主进程默认
127.0.0.1:8765，与 ``electron/backend/config.ts`` 的 BACKEND_HOST/PORT 一致）。

该入口**不复制任何算法**，只 ``import mvp.api.main`` 得到 FastAPI app 并 ``uvicorn.run``。
"""
import os

import uvicorn

# 显式 import，确保 PyInstaller 静态分析把 mvp.api.main（及 mvp/src 的
# app/domain/engine/device/infrastructure/media）一起打进 bundle。
import mvp.api.main  # noqa: F401


def main() -> None:
    host = os.environ.get("SVL_BACKEND_HOST", "127.0.0.1")
    port = int(os.environ.get("SVL_BACKEND_PORT", "8765"))
    uvicorn.run("mvp.api.main:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
