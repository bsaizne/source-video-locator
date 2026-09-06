"""Unit tests for mvp.api routes.settings (device backend switch).

验证 GET/POST /api/settings/device：偏好查询、切换生效、非法值 400。
用 FakeService 覆盖 service 方法（``app.dependency_overrides[get_context]`` 一处注入），
不依赖真实 GPU / 模型，确定性强。

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_settings -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_MVP = Path(__file__).resolve().parents[2]   # .../mvp
for _p in (str(_MVP.parent), str(_MVP / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient

from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context


class FakeService:
    """镜像 SourceLocatorService 的设备设置相关方法（确定性，无 GPU）。"""

    def __init__(self):
        self.preferred = "auto"
        self.set_calls: list[str] = []
        # preferred -> (device_name, device_type, is_accelerator, fallback)
        self._devices = {
            "auto": ("directml", "amd", True, False),
            "directml": ("directml", "amd", True, False),
            "cpu": ("cpu", "cpu", False, False),
        }

    def set_device_preference(self, preferred: str) -> None:
        self.set_calls.append(preferred)
        self.preferred = preferred

    def device_settings(self) -> dict:
        name, typ, accel, fb = self._devices.get(self.preferred, ("cpu", "cpu", False, True))
        return {
            "preferred": self.preferred,
            "actual_device_name": name,
            "actual_device_type": typ,
            "is_accelerator": accel,
            "fallback": fb,
            "available_devices": ["cpu", "directml"],
        }


class SettingsTest(unittest.TestCase):
    def setUp(self):
        self.fake = FakeService()
        app = create_app()
        app.dependency_overrides[get_context] = lambda: AppContext(service=self.fake)
        self.client = TestClient(app)

    def test_get_returns_current_preference(self):
        r = self.client.get("/api/settings/device")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["preferred"], "auto")
        self.assertEqual(body["actual_device_type"], "amd")
        self.assertIn("directml", body["available_devices"])

    def test_post_directml_switches_and_calls_service(self):
        r = self.client.post("/api/settings/device", json={"preferred": "directml"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.fake.preferred, "directml")
        self.assertEqual(r.json()["actual_device_type"], "amd")
        self.assertEqual(r.json()["is_accelerator"], True)
        self.assertEqual(self.fake.set_calls, ["directml"])

    def test_post_cpu_switches_to_cpu(self):
        r = self.client.post("/api/settings/device", json={"preferred": "cpu"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["actual_device_type"], "cpu")
        self.assertEqual(r.json()["is_accelerator"], False)

    def test_post_invalid_preference_returns_400(self):
        r = self.client.post("/api/settings/device", json={"preferred": "gpu"})
        self.assertEqual(r.status_code, 400)
        # 非法值不应触发 set_device_preference
        self.assertEqual(self.fake.set_calls, [])


if __name__ == "__main__":
    unittest.main()
