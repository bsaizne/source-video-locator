"""Unit tests for mvp.media.ffmpeg.FFmpegIO.

Fast path: uses the tiny synthetic ``a1.mp4``. The heavy (1GB hash, 2h MKV
random-access, frame-precision clip) acceptance is covered by
``mvp/scripts/smoke_ffmpeg_io.py``. Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_ffmpeg_io -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from media.ffmpeg import FFmpegIO, MediaError

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists() and SYNTH.exists(),
                     "real FFmpegIO assets not present")
class FFmpegIOTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.io = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)

    def test_metadata(self):
        m = self.io.metadata(SYNTH)
        self.assertEqual((m.width, m.height), (1280, 720))
        self.assertEqual(m.video_codec, "h264")
        self.assertTrue(abs(m.duration - 5.0) < 0.5)
        self.assertTrue(m.has_video)
        self.assertGreaterEqual(m.fps, 1.0)

    def test_iter_frames_time_grid(self):
        frames = list(self.io.iter_frames(SYNTH, 0.5))
        self.assertGreaterEqual(len(frames), 2)
        self.assertEqual(frames[0][0], 0.0)
        self.assertEqual(frames[0][1].shape, (720, 1280, 3))
        self.assertEqual(frames[0][1].dtype, np.uint8)
        # strictly increasing absolute timestamps on a 1/fps grid
        ts = [t for t, _ in frames]
        self.assertTrue(all(b > a for a, b in zip(ts, ts[1:])))

    def test_grab_frame(self):
        f = self.io.grab_frame(SYNTH, 1.5)
        self.assertEqual(f.shape, (720, 1280, 3))
        self.assertEqual(f.dtype, np.uint8)
        self.assertGreater(f.mean(), 1.0)  # not black

    def test_clip_precision(self):
        out = Path(tempfile.mkdtemp()) / "c.mp4"
        r = self.io.extract_clip(SYNTH, 1.0, 3.0, out)
        self.assertEqual(r, out)
        self.assertTrue(out.exists())
        m = self.io.metadata(out)
        self.assertTrue(abs(m.duration - 2.0) < 0.3)

    def test_invalid_clip_range_raises(self):
        with self.assertRaises(MediaError):
            self.io.extract_clip(SYNTH, 3.0, 1.0, Path(tempfile.mkdtemp()) / "x.mp4")

    def test_hash_file(self):
        h = self.io.hash_file(SYNTH)
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


if __name__ == "__main__":
    unittest.main(verbosity=2)
