"""Unit tests for mvp.api.routes.preview (POST /api/preview + media/edited 服务).

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_preview -v

用 FakeService/FakePreviewService 覆盖 ``get_context``，不触发真实模型/视频。
"""
from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path

_MVP = Path(__file__).resolve().parents[2]   # .../mvp
if str(_MVP.parent) not in sys.path:
    sys.path.insert(0, str(_MVP.parent))     # .../ (benchmark)，使 `import mvp.api.*` 生效

from fastapi.testclient import TestClient

from domain import Result, ResultBatch, TimeSpan
from infrastructure.logging import configure_logging, set_session_id

from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context
from mvp.api.services.preview_service import PreviewError, PreviewResult


# --------------------------------------------------------------------- Fakes
class FakeService:
    """预览路径只需要 app 能构造；预览服务由 ctx.preview_service 注入。"""

    def __init__(self):
        # 若某测试意外走到 _preview_service 的懒构建（未注入 preview_service），
        # 该 .ffmpeg 会缺属性 —— 测试一律显式注入 preview_service，避免依赖它。
        pass


class FakePreviewService:
    """镜像 PreviewService 的 extract_segment + preview_dir，行为可控。"""

    def __init__(self, *, preview_dir: Path, fail: bool = False):
        self.preview_dir = preview_dir
        self.fail = fail
        self.extract_calls: list[tuple[str, float, float]] = []

    def extract_segment(self, video_path, start, end):
        self.extract_calls.append((video_path, start, end))
        if self.fail:
            raise PreviewError("boom in preview")
        out = self.preview_dir / "result_xxx.mp4"
        out.write_bytes(b"fake-video-bytes")
        return PreviewResult(path=out, duration=end - start)


# ------------------------------------------------------------------ Root isolate
class _RootIsolateMixin:
    def _snapshot(self):
        root = logging.getLogger()
        return (root.level, list(root.handlers))

    def _restore(self, snap):
        root = logging.getLogger()
        root.setLevel(snap[0])
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()
        for h in snap[1]:
            root.addHandler(h)

    def _flush_files(self):
        for h in logging.getLogger().handlers:
            if isinstance(h, RotatingFileHandler):
                h.flush()


class PreviewApiBase(unittest.TestCase, _RootIsolateMixin):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.preview_dir = Path(self.tmp.name) / "previews"
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        self.preview = FakePreviewService(preview_dir=self.preview_dir)
        self.context = AppContext(service=FakeService(), preview_service=self.preview)
        self.app = create_app()
        self.app.dependency_overrides[get_context] = lambda: self.context
        self._client = TestClient(self.app)
        self._client.__enter__()

    def tearDown(self):
        self._client.__exit__(None, None, None)
        self.app.dependency_overrides.clear()


# --------------------------------------------------------------------- Tests
class PreviewPostTest(PreviewApiBase):
    def test_preview_returns_path_and_duration(self):
        r = self._client.post(
            "/api/preview", json={"original_path": "D:/movie/source.mkv", "start": 6349, "end": 6602})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(set(body.keys()), {"path", "duration"})
        self.assertTrue(str(body["path"]).endswith("result_xxx.mp4"))
        self.assertEqual(body["duration"], 253)
        self.assertEqual(self.preview.extract_calls, [("D:/movie/source.mkv", 6349, 6602)])

    def test_preview_error_maps_to_500(self):
        self.context.preview_service = FakePreviewService(preview_dir=self.preview_dir, fail=True)
        r = self._client.post(
            "/api/preview", json={"original_path": "D:/movie/source.mkv", "start": 6349, "end": 6602})
        self.assertEqual(r.status_code, 500)
        body = r.json()
        self.assertEqual(body["error"], "PreviewError")
        self.assertIn("detail", body)


class PreviewMediaTest(PreviewApiBase):
    def test_media_serves_extracted_file(self):
        f = self.preview_dir / "result_xxx.mp4"
        f.write_bytes(b"fake-video-bytes")
        r = self._client.get("/api/preview/media/result_xxx.mp4")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"fake-video-bytes")

    def test_media_missing_file_returns_404(self):
        r = self._client.get("/api/preview/media/does-not-exist.mp4")
        self.assertEqual(r.status_code, 404)


class PreviewEditedTest(PreviewApiBase):
    def test_edited_without_batch_returns_400(self):
        r = self._client.get("/api/preview/edited")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "no_edited_video")

    def test_edited_missing_file_returns_404(self):
        self.context.current_batch = ResultBatch(edited_video="D:/missing/edited.mp4")
        r = self._client.get("/api/preview/edited")
        self.assertEqual(r.status_code, 404)

    def test_edited_serves_session_video(self):
        f = Path(self.tmp.name) / "edited.mp4"
        f.write_bytes(b"fake-edit-bytes")
        self.context.current_batch = ResultBatch(edited_video=str(f))
        r = self._client.get("/api/preview/edited")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.content, b"fake-edit-bytes")
        self.assertEqual(r.headers.get("content-type"), "video/mp4")


class PreviewLoggingTest(PreviewApiBase):
    def test_preview_error_logged(self):
        self.context.preview_service = FakePreviewService(preview_dir=self.preview_dir, fail=True)
        snap = self._snapshot()
        with tempfile.TemporaryDirectory() as td:
            try:
                configure_logging(log_dir=td)
                r = self._client.post(
                    "/api/preview", json={"original_path": "x.mkv", "start": 0, "end": 10})
                self.assertEqual(r.status_code, 500)
                self._flush_files()
                text = (Path(td) / "video_locator.log").read_text(encoding="utf-8")
                self.assertIn("module=api", text)
                self.assertIn("POST /api/preview", text)
            finally:
                set_session_id("")
                self._restore(snap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
