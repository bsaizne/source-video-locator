"""Unit tests for mvp.api.services.preview_service (段抽取 + 异常 + 日志).

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_preview_service -v

用 FakeFFmpeg 注入，不依赖真实视频/ffprobe。
"""
from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import SimpleNamespace

_MVP = Path(__file__).resolve().parents[2]   # .../mvp
if str(_MVP.parent) not in sys.path:
    sys.path.insert(0, str(_MVP.parent))     # .../ (benchmark)，使 `import mvp.api.*` 生效

from infrastructure.logging import configure_logging, set_session_id
from media.ffmpeg import MediaError

from mvp.api.services.preview_service import PreviewError, PreviewService
from mvp.api.services.preview_service import _slug


# ----------------------------------------------------------------- FakeFFmpeg
class FakeFFmpeg:
    """镜像 FFmpegIO 的 metadata/extract_clip 签名，行为可控。"""

    def __init__(self, *, duration: float = 100.0, fail_extract: bool = False):
        self._duration = duration
        self.fail_extract = fail_extract
        self.metadata_calls: list[Path] = []
        self.extract_calls: list[tuple[Path, float, float, Path]] = []

    def metadata(self, path):
        self.metadata_calls.append(Path(path))
        return SimpleNamespace(duration=self._duration, width=1280, height=720, name=Path(path).name)

    def extract_clip(self, path, start, end, out_path, **kw):
        self.extract_calls.append((Path(path), start, end, Path(out_path)))
        if self.fail_extract:
            raise MediaError("boom in extract_clip")
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        Path(out_path).write_bytes(b"fake-mp4-bytes")


# ------------------------------------------------------------ Root isolate
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


class DummyRoot(unittest.TestCase, _RootIsolateMixin):
    pass


# -------------------------------------------------------------------- Tests
class ExtractHappyPathTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.video = Path(self.tmp.name) / "movie.mkv"
        self.video.write_bytes(b"\x00" * 16)
        self.ff = FakeFFmpeg(duration=100.0)
        self.svc = PreviewService(ffmpeg=self.ff, preview_dir=Path(self.tmp.name) / "previews")

    def test_extract_segment_produces_file_and_duration(self):
        pr = self.svc.extract_segment(self.video, 10.0, 30.0)
        self.assertEqual(pr.duration, 20.0)
        self.assertTrue(pr.path.is_file())
        self.assertEqual(pr.path.parent, self.svc.preview_dir)
        # extract_clip 收到正确的区间与输出路径
        (path, start, end, out) = self.ff.extract_calls[0]
        self.assertEqual(path, self.video)
        self.assertEqual((start, end), (10.0, 30.0))
        self.assertEqual(out, pr.path)

    def test_output_path_is_deterministic_and_slugged(self):
        pr = self.svc.extract_segment(self.video, 10.0, 30.0)
        self.assertEqual(pr.path.name, "movie__10-30.mp4")
        # 同区间重复调用覆盖同一文件
        pr2 = self.svc.extract_segment(self.video, 10.0, 30.0)
        self.assertEqual(pr.path, pr2.path)

    def test_slug_replaces_noisy_chars(self):
        self.assertEqual(_slug("a b/c:d.mp4"), "a_b_c_d.mp4")


class ExtractFailuresTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.video = Path(self.tmp.name) / "movie.mkv"
        self.video.write_bytes(b"\x00" * 16)
        self.ff = FakeFFmpeg(duration=100.0)
        self.svc = PreviewService(ffmpeg=self.ff, preview_dir=Path(self.tmp.name) / "previews")

    def test_missing_file_raises_preview_error(self):
        with self.assertRaises(PreviewError) as cm:
            self.svc.extract_segment(Path(self.tmp.name) / "nope.mkv", 0.0, 10.0)
        self.assertIn("not found", str(cm.exception))

    def test_invalid_time_range_raises_preview_error(self):
        with self.assertRaises(PreviewError):
            self.svc.extract_segment(self.video, 30.0, 10.0)   # end <= start

    def test_start_beyond_duration_raises_preview_error(self):
        with self.assertRaises(PreviewError) as cm:
            self.svc.extract_segment(self.video, 120.0, 130.0)  # start >= duration 100
        self.assertIn("beyond duration", str(cm.exception))

    def test_end_exceeds_duration_raises_preview_error(self):
        with self.assertRaises(PreviewError):
            self.svc.extract_segment(self.video, 10.0, 500.0)   # end > duration + 0.5

    def test_ffmpeg_failure_raises_preview_error(self):
        self.ff.fail_extract = True
        with self.assertRaises(PreviewError) as cm:
            self.svc.extract_segment(self.video, 10.0, 30.0)
        self.assertIn("ffmpeg extract failed", str(cm.exception))


class ExtractLoggingTest(unittest.TestCase, _RootIsolateMixin):
    def test_ffmpeg_failure_logs_exception(self):
        snap = self._snapshot()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        video = Path(tmp.name) / "movie.mkv"
        video.write_bytes(b"\x00" * 16)
        ff = FakeFFmpeg(duration=100.0, fail_extract=True)
        svc = PreviewService(ffmpeg=ff, preview_dir=Path(tmp.name) / "previews")
        try:
            configure_logging(log_dir=tmp.name)
            with self.assertRaises(PreviewError):
                svc.extract_segment(video, 10.0, 30.0)
            self._flush_files()
            text = (Path(tmp.name) / "video_locator.log").read_text(encoding="utf-8")
            self.assertIn("preview extract failed", text)
            self.assertIn("module=mvp.api.services.preview_service", text)
        finally:
            set_session_id("")
            self._restore(snap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
