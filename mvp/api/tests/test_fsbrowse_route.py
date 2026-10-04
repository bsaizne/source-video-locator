"""API route tests for routes.fsbrowse（GET /api/fs/browse）。"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.app import create_app  # noqa: E402


class FsBrowseRouteTest(unittest.TestCase):
    def setUp(self):
        # dev 通道无令牌 = 门禁关闭（session.py 语义），只测路由本体
        self.client = TestClient(create_app())

    def test_root_returns_drives(self):
        r = self.client.get("/api/fs/browse")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["kind"], "root")
        self.assertTrue(body["drives"])

    def test_dir_listing(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "b10.mp4").write_bytes(b"x")
            (Path(td) / "b2.mp4").write_bytes(b"x")
            (Path(td) / "readme.txt").write_bytes(b"x")
            r = self.client.get("/api/fs/browse", params={"path": td})
            self.assertEqual(r.status_code, 200)
            names = [e["name"] for e in r.json()["entries"]]
            self.assertEqual(names, ["b2.mp4", "b10.mp4"])

    def test_missing_path_404_name_only(self):
        r = self.client.get("/api/fs/browse", params={"path": r"Z:\no_such_dir_xyz"})
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "not_found")
        # detail 只回名字，不吐完整路径（脱敏同立场）
        self.assertNotIn("Z:", r.json()["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
