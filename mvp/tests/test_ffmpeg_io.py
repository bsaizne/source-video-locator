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

    def test_grab_frames_batch_matches_single(self):
        # 续46 窗批量解码：零语义 = 与 grab_frame 逐字节一致（同选取规则：首个 pts≥t）
        times = [0.5, 1.0, 2.0, 2.5, 3.5, 4.5]
        singles = [self.io.grab_frame(SYNTH, t) for t in times]
        batch = self.io.grab_frames(SYNTH, times)
        self.assertEqual(set(batch.keys()), {round(t, 6) for t in times})
        for t, single in zip(times, singles):
            self.assertTrue(np.array_equal(single, batch[round(t, 6)]),
                            f"窗批量帧与单帧 grab 不一致 t={t}")

    def test_grab_frames_unsorted_with_dup(self):
        # API 返回 {round(t,6): frame}，重复时间按 key 合并（调用方按索引展开）
        times = [3.0, 0.5, 3.0]
        batch = self.io.grab_frames(SYNTH, times)
        self.assertEqual(sorted(batch.keys()), [0.5, 3.0])
        self.assertTrue(np.array_equal(self.io.grab_frame(SYNTH, 0.5), batch[0.5]))
        self.assertTrue(np.array_equal(self.io.grab_frame(SYNTH, 3.0), batch[3.0]))

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


    def _assert_frame_close(self, frame, t, msg):
        """网格帧必须命中 t 或 t±1 源帧中的一个（select 抽取的相位误差 ≤1 源帧）。"""
        step = 1.0 / max(1.0, self.io.metadata(SYNTH).fps)
        best = 10 ** 9
        for dt in (-step, 0.0, step):
            ref = self.io.grab_frame(SYNTH, max(0.0, t + dt))
            best = min(best, int(np.abs(frame.astype(np.int16) - ref.astype(np.int16)).max()))
        self.assertLess(best, 40, f"{msg}: 与 t +/- 1 帧内任何单帧都不符 (best={best})")

    def test_grab_grid_matches_single_first_ge(self):
        # 续50 L1：网格抽取（select + first_ge）在网格点上应与冻结契约帧一致（≤1 源帧）
        grid = self.io.grab_grid(SYNTH, 0.0, 1.0, 5)
        self.assertEqual(sorted(grid.keys()), [0.0, 1.0, 2.0, 3.0, 4.0])
        for t in sorted(grid.keys()):
            single = self.io.grab_frame(SYNTH, t)
            self.assertEqual(grid[t].shape, single.shape)
            self.assertEqual(grid[t].dtype, np.uint8)
            self._assert_frame_close(grid[t], t, f"网格 t={t}")

    def test_grab_grid_arbitrary_phase(self):
        # 任意相位（0.5s 起点）也必须给出全部网格点，且每帧命中 t±1 源帧
        grid = self.io.grab_grid(SYNTH, 0.5, 1.0, 4)
        self.assertEqual(sorted(grid.keys()), [0.5, 1.5, 2.5, 3.5])
        for t in sorted(grid.keys()):
            self._assert_frame_close(grid[t], t, f"相位 t={t}")

    def test_grab_frames_filters_and_size(self):
        # 消费者侧预缩放：size 必须与 filters 输出一致（形状 = 缩放后尺寸）
        got = self.io.grab_frames(SYNTH, [1.0, 2.0], filters="scale=320:180", size=(320, 180))
        self.assertEqual(sorted(got.keys()), [1.0, 2.0])
        for f in got.values():
            self.assertEqual(f.shape, (180, 320, 3))
            self.assertEqual(f.dtype, np.uint8)

    def test_grab_grid_fps_plus_scale(self):
        # 组合：网格抽取 + 预缩放（L1 的完整形态），逐点形状/时间轴必须齐
        got = self.io.grab_grid(SYNTH, 0.0, 1.0, 3, filters="fps=1,scale=256:144", size=(256, 144))
        self.assertEqual(sorted(got.keys()), [0.0, 1.0, 2.0])
        for f in got.values():
            self.assertEqual(f.shape, (144, 256, 3))

    def test_grab_grid_size_appends_scale(self):
        # size 必须由滤镜链产生（2026-10-03 实测踩坑：只传 size 不拼 scale ⇒ 读到垃圾帧）
        got = self.io.grab_grid(SYNTH, 0.0, 1.0, 3, size=(480, 270))
        self.assertEqual(sorted(got.keys()), [0.0, 1.0, 2.0])
        for f in got.values():
            self.assertEqual(f.shape, (270, 480, 3))
            self.assertGreater(f.mean(), 1.0)      # 不是错位读出来的噪声

    def test_grab_grid_subsecond_falls_back(self):
        # 续50 实测边界：select 在亚秒步长上逐步累积漂移（3s/0.208s 只有 3/15 同帧）
        # ⇒ step < MIN_GRID_STEP_S 一律回退旧路径，结果与 grab_frames 逐字节一致
        times = [0.0, 0.208, 0.416, 0.624]
        ref = self.io.grab_frames(SYNTH, times)
        got = self.io.grab_grid_times(SYNTH, times, step=0.208)
        self.assertEqual(sorted(got.keys()), sorted(ref.keys()))
        for t in ref:
            self.assertTrue(np.array_equal(got[t], ref[t]), f"t={t} 亚秒步长未回退旧路径")

    def test_decode_window_rejects_unknown_match(self):
        with self.assertRaises(ValueError):
            self.io.grab_frames(SYNTH, [1.0], match="bogus")


if __name__ == "__main__":
    unittest.main(verbosity=2)
