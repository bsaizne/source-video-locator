"""Unit tests for mvp.api.routes.media (GET /api/media/info).

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_media_info -v

FakeService.ffmpeg.metadata 注入可控，不触发真实 ffprobe / 视频文件。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_MVP = Path(__file__).resolve().parents[2]   # .../mvp
if str(_MVP.parent) not in sys.path:
    sys.path.insert(0, str(_MVP.parent))     # .../ (benchmark)，使 `import mvp.api.*` 生效

from fastapi.testclient import TestClient

from media.ffmpeg import VideoMetadata
from media.ffmpeg._runner import MediaError

from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context


def _meta(path: Path) -> VideoMetadata:
    return VideoMetadata(
        path=path, duration=7667.9, size_bytes=123456789,
        format_name="matroska,webm", width=1920, height=804,
        fps=23.976, video_codec="hevc", has_video=True, has_audio=True,
    )


class FakeFFmpeg:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[Path] = []

    def metadata(self, path):
        self.calls.append(Path(path))
        if self.fail:
            raise MediaError("ffprobe exploded")
        return _meta(Path(path))


class FakeService:
    def __init__(self, ffmpeg: FakeFFmpeg):
        self.ffmpeg = ffmpeg


class MediaInfoApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ffmpeg = FakeFFmpeg()
        self.context = AppContext(service=FakeService(self.ffmpeg))  # type: ignore[arg-type]
        self.app = create_app()
        self.app.dependency_overrides[get_context] = lambda: self.context
        self.client = TestClient(self.app)

    def tearDown(self):
        self.app.dependency_overrides.clear()

    # ------------------------------------------------------------------ happy
    def test_success_returns_all_fields(self):
        f = Path(self.tmp.name) / "real movie.mkv"
        f.write_bytes(b"x")
        r = self.client.get("/api/media/info", params={"path": str(f)})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(
            set(body.keys()),
            {"path", "duration", "fps", "width", "height", "size_bytes",
             "format_name", "video_codec", "has_audio"},
        )
        self.assertEqual(body["duration"], 7667.9)
        self.assertAlmostEqual(body["fps"], 23.976)
        self.assertEqual((body["width"], body["height"]), (1920, 804))
        self.assertEqual(body["size_bytes"], 123456789)
        self.assertEqual(body["video_codec"], "hevc")
        self.assertTrue(body["has_audio"])
        self.assertEqual(self.ffmpeg.calls, [f])

    # ------------------------------------------------------------------ 400
    def test_bare_filename_rejected(self):
        r = self.client.get("/api/media/info", params={"path": "movie.mkv"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "invalid_path")
        self.assertEqual(self.ffmpeg.calls, [])

    def test_empty_path_rejected(self):
        r = self.client.get("/api/media/info", params={"path": ""})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "invalid_path")

    def test_relative_with_separators_rejected(self):
        r = self.client.get("/api/media/info", params={"path": "sub\\movie.mkv"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "invalid_path")

    # ------------------------------------------------------------------ 404
    def test_missing_file_404_with_redacted_detail(self):
        r = self.client.get("/api/media/info", params={"path": "D:/no/such/secret.mkv"})
        self.assertEqual(r.status_code, 404)
        body = r.json()
        self.assertEqual(body["error"], "file_not_found")
        self.assertEqual(body["detail"], "secret.mkv")   # 只回文件名，不吐完整路径
        self.assertEqual(self.ffmpeg.calls, [])

    # ------------------------------------------------------------------ 500
    def test_ffprobe_failure_maps_to_public_error(self):
        self.context.service = FakeService(FakeFFmpeg(fail=True))  # type: ignore[assignment]
        f = Path(self.tmp.name) / "broken.mkv"
        f.write_bytes(b"x")
        r = self.client.get("/api/media/info", params={"path": str(f)})
        self.assertEqual(r.status_code, 500)
        body = r.json()
        self.assertEqual(body["error"], "MediaError")
        self.assertTrue(str(body["code"]).startswith("LOC-"))
        self.assertIn("message", body)


if __name__ == "__main__":
    unittest.main(verbosity=2)
