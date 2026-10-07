"""② 子进程设备回报标记（2026-10-07 立项）单测。

`SourceLocatorService._announce_device`：stdout 一次性机器可 grep 标记行
``BACKEND_DEVICE <actual_name> <actual_type>``，与 BACKEND_LISTEN 同风格；
懒构建点 = 真实解析点 ⇒ 打印的必然是实际值而非配置意图。
"""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infrastructure.config import AppConfig


class _FakeBackend:
    def device_name(self):
        return "directml"

    def device_type(self):
        return "amd"


class DeviceAnnounceTest(unittest.TestCase):
    def _service(self):
        from app import SourceLocatorService
        cfg = AppConfig()
        return SourceLocatorService(config=cfg, index_root=self.tmp, export_root=self.tmp)

    def setUp(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def test_announce_prints_actual_device_once(self):
        svc = self._service()
        svc._backend = _FakeBackend()          # 不触真探测（单测无 GPU 依赖）
        buf = io.StringIO()
        with redirect_stdout(buf):
            svc._announce_device()
            svc._announce_device()             # 二次调用必须静默（一次性）
        out = buf.getvalue()
        self.assertEqual(out.count("BACKEND_DEVICE directml amd"), 1)
        self.assertIn("BACKEND_DEVICE directml amd\n", out)

    def test_announce_swallows_backend_errors(self):
        svc = self._service()
        svc._backend = mock.Mock()
        svc._backend.device_name.side_effect = RuntimeError("boom")
        buf = io.StringIO()
        with redirect_stdout(buf):
            svc._announce_device()             # 观测行绝不阻断主流程
        self.assertNotIn("BACKEND_DEVICE", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
