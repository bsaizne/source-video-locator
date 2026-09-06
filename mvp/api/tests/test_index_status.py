"""Unit tests for mvp.api routes.index /api/index/status (真实索引状态查询).

验证状态端点返回真实磁盘索引状态（VALID/INVALID/MISSING + reason），并从源头区分
「源片不存在」的 INVALID。用 FakeService 覆盖 service.index_status，不依赖真实索引。

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_index_status -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_MVP = Path(__file__).resolve().parents[2]
for _p in (str(_MVP.parent), str(_MVP / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi.testclient import TestClient

from domain import IndexValidation, IndexValidationStatus
from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context


class FakeService:
    def __init__(self, status: IndexValidationStatus, reason: str | None = None):
        self._v = IndexValidation(status, reason)
        self.calls: list[str] = []

    def index_status(self, original):
        self.calls.append(original)
        return self._v


class IndexStatusTest(unittest.TestCase):
    def _client(self, fake: FakeService) -> TestClient:
        app = create_app()
        app.dependency_overrides[get_context] = lambda: AppContext(service=fake)
        return TestClient(app)

    def test_status_valid(self):
        fake = FakeService(IndexValidationStatus.VALID)
        r = self._client(fake).get("/api/index/status", params={"video_path": "D:/a.mkv"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "VALID", "reason": None})
        self.assertEqual(fake.calls, ["D:/a.mkv"])

    def test_status_missing(self):
        fake = FakeService(IndexValidationStatus.MISSING)
        r = self._client(fake).get("/api/index/status", params={"video_path": "D:/b.mkv"})
        self.assertEqual(r.json()["status"], "MISSING")

    def test_status_source_missing_reason(self):
        fake = FakeService(IndexValidationStatus.INVALID, "source video missing")
        r = self._client(fake).get("/api/index/status", params={"video_path": "D:/c.mkv"})
        body = r.json()
        self.assertEqual(body["status"], "INVALID")
        self.assertEqual(body["reason"], "source video missing")

    def test_missing_query_param_is_422(self):
        fake = FakeService(IndexValidationStatus.MISSING)
        r = self._client(fake).get("/api/index/status")
        self.assertEqual(r.status_code, 422)


if __name__ == "__main__":
    unittest.main()
