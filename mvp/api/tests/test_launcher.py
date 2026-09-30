"""Unit tests for mvp.api.launcher (BACKEND_LISTEN 公告 + 随机端口).

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_launcher -v

含一个真实 uvicorn 起停例（port=0 → 解析公告里的端口能连通 /health），
证明公告端口 = 实际绑定端口，且绑定失败时不产公告（宁缺毋假）。
"""
from __future__ import annotations

import io
import socket
import sys
import threading
import unittest
import urllib.request
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

_MVP = Path(__file__).resolve().parents[2]   # .../mvp
if str(_MVP.parent) not in sys.path:
    sys.path.insert(0, str(_MVP.parent))

from mvp.api.launcher import (
    format_listen_line,
    listen_host_port,
    make_server,
    startup_announce_lines,
)


def _server_stub(*, started: bool, addr, sockets_error: bool = False):
    class _Sock:
        def getsockname(self):
            if sockets_error:
                raise OSError("socket closed")
            return addr

    return SimpleNamespace(
        started=started,
        servers=[SimpleNamespace(sockets=[_Sock()])] if (addr or sockets_error) else [],
    )


class PureHelperTest(unittest.TestCase):
    def test_format_line(self):
        self.assertEqual(format_listen_line("127.0.0.1", 5111), "BACKEND_LISTEN 127.0.0.1 5111")

    def test_listen_host_port_reads_real_socket(self):
        stub = _server_stub(started=True, addr=("127.0.0.1", 5111))
        self.assertEqual(listen_host_port(stub), ("127.0.0.1", 5111))

    def test_wildcard_host_normalized_to_loopback(self):
        for host in ("0.0.0.0", "::"):
            stub = _server_stub(started=True, addr=(host, 5111))
            self.assertEqual(listen_host_port(stub), ("127.0.0.1", 5111))

    def test_no_announce_when_not_started(self):
        stub = _server_stub(started=False, addr=("127.0.0.1", 5111))
        self.assertEqual(
            startup_announce_lines(stub, host="127.0.0.1", port=0, extra=["SVL_BUILD_CHANNEL dev"]),
            [],
        )

    def test_no_announce_when_socket_unreadable(self):
        stub = _server_stub(started=True, addr=None, sockets_error=True)
        self.assertEqual(startup_announce_lines(stub, host="127.0.0.1", port=0), [])

    def test_extra_lines_come_before_listen(self):
        stub = _server_stub(started=True, addr=("127.0.0.1", 5111))
        lines = startup_announce_lines(stub, host="127.0.0.1", port=0,
                                       extra=["SVL_BUILD_CHANNEL release", "SVL_SESSION_ENABLED 1"])
        self.assertEqual(lines, [
            "SVL_BUILD_CHANNEL release", "SVL_SESSION_ENABLED 1",
            "BACKEND_LISTEN 127.0.0.1 5111",
        ])


async def _asgi_app(scope, receive, send):
    """最小 ASGI：lifespan 握手 + /health 返回 ok（不触碰真 app 的重依赖）。"""
    if scope["type"] == "lifespan":
        while True:
            msg = await receive()
            if msg["type"] == "lifespan.startup":
                await send({"type": "lifespan.startup.complete"})
            elif msg["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return
        return
    body = b'{"status":"ok"}'
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(body)).encode())]})
    await send({"type": "http.response.body", "body": body})


class RealServerRandomPortTest(unittest.TestCase):
    """port=0 → 公告里的真实端口必须就是可连通的监听端口。"""

    def test_random_port_announced_and_serves(self):
        buf = io.StringIO()
        server = make_server(_asgi_app, host="127.0.0.1", port=0,
                             announce=["SVL_BUILD_CHANNEL dev"])
        err: list[BaseException] = []

        def _run():
            try:
                with redirect_stdout(buf):
                    server.run()
            except BaseException as exc:  # noqa: BLE001
                err.append(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        try:
            _wait_until(lambda: "BACKEND_LISTEN" in buf.getvalue(), timeout=15.0)
            self.assertFalse(err, f"server thread died: {err!r}")
            line = next(l for l in buf.getvalue().splitlines() if l.startswith("BACKEND_LISTEN"))
            host, port_s = line.split()[1], line.split()[2]
            port = int(port_s)
            self.assertGreater(port, 0, "公告端口应为 OS 分配值而非 0")
            with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=5) as r:
                self.assertEqual(r.read(), b'{"status":"ok"}')
        finally:
            server.should_exit = True
            t.join(timeout=15)

    def test_port_in_use_no_announce(self):
        """端口被占用 → uvicorn 启动失败退出，不得有 BACKEND_LISTEN（宁缺毋假）。"""
        blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        blocker.bind(("127.0.0.1", 0))
        blocker.listen(1)
        taken = blocker.getsockname()[1]
        try:
            buf = io.StringIO()
            server = make_server(_asgi_app, host="127.0.0.1", port=taken)
            t = threading.Thread(target=lambda: _run_quiet(server, buf), daemon=True)
            t.start()
            t.join(timeout=15)
            self.assertNotIn("BACKEND_LISTEN", buf.getvalue())
        finally:
            blocker.close()


def _run_quiet(server, buf):
    import logging
    logging.getLogger("uvicorn.error").setLevel(logging.CRITICAL)
    try:
        with redirect_stdout(buf):
            server.run()
    except SystemExit:
        pass  # 绑定失败 → uvicorn sys.exit(1)，正是我们断言"无公告"的路径


def _wait_until(pred, *, timeout: float, interval: float = 0.05):
    import time
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return
        time.sleep(interval)
    raise AssertionError("condition not met within timeout")


if __name__ == "__main__":
    unittest.main(verbosity=2)
