"""run_backend — 生产后端 PyInstaller 入口。

打包后以单进程启动 FastAPI 桥。宿主/端口用环境变量 ``SVL_BACKEND_HOST`` /
``SVL_BACKEND_PORT`` 覆盖；``SVL_BACKEND_PORT=0`` = OS 分配随机端口，Electron 主进程
解析 stdout 的 ``BACKEND_LISTEN <host> <port>`` 公告拿到真实端口（见
``mvp/api/launcher.py``；公告在绑定成功后才打印，失败则只有健康检查超时）。

**包形态（2026-09-28 打包验收修复）**：bundle 内桥是**顶层包** ``api``（pathex=mvp），
``api`` 内部又以顶层 ``app/domain/...``（pathex=mvp/src）绝对导入——所以必须走
``import api.main``，不能用 ``mvp.api``（那是源码树/测试的形态，frozen 里不存在）。
try/except 双形态 = 打包与源码直跑都可用。该入口**不复制任何算法**。
"""
import os

try:
    # 打包形态（PyInstaller）：顶层 api；显式 import 确保静态分析收全
    # mvp.api→api、mvp/src→app/domain/engine/device/infrastructure/media。
    import api.main as api_main
    from api.launcher import run_app
    from api.session import announce_lines, resolve_session_token
except ModuleNotFoundError:  # pragma: no cover - 源码树直跑形态
    import mvp.api.main as api_main
    from mvp.api.launcher import run_app
    from mvp.api.session import announce_lines, resolve_session_token


def main() -> None:
    host = os.environ.get("SVL_BACKEND_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("SVL_BACKEND_PORT", "8765"))
    except ValueError:
        port = 8765
    run_app(api_main.app, host=host, port=max(0, port),
            announce=announce_lines(resolve_session_token()))


if __name__ == "__main__":
    main()
