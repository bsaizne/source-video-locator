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

    def test_grab_frame_beyond_end_rescues_not_raises(self):
        """LOC-1107 片尾越界（2026-10-06）：t 取不到帧 ⇒ 返回片内最后一帧，不再抛。

        旧行为 = 抛 MediaError ⇒ 任何一个候选窗越过片尾（isc_refine 宽扫/精扫、
        patch 精扫、近场池）就把整条 locate 打死。
        **严格惰性**：兜底只在「原始 t 真的吐不出帧」的分支里发生，绝不做预先钳制
        （r11/r12 双臂实测：cap 早于末帧真实 pts，先钳会换帧换结果段数）。
        """
        m = self.io.metadata(SYNTH)
        cap = self.io._decodable_cap(m)
        self.assertIsNotNone(cap)
        self.assertGreater(cap, 0.0)
        f = self.io.grab_frame(SYNTH, m.duration + 5.0)
        self.assertEqual(f.shape, (720, 1280, 3))
        self.assertGreater(f.mean(), 1.0)                      # 真帧，不是造出来的黑帧
        last = self.io._grab_last_frame(SYNTH, m, None, 1280, 720, 1280 * 720 * 3)
        self.assertTrue(np.array_equal(f, last))               # = 片内最后一帧

    def test_grab_frame_in_bounds_untouched_by_rescue(self):
        """界内请求必须走原来的单次 spawn（严格惰性的可观测面：不多一次解码、帧同）。"""
        m = self.io.metadata(SYNTH)
        for t in (0.0, 1.5, round(m.duration - 0.3, 6)):
            with self.subTest(t=t):
                f = self.io.grab_frame(SYNTH, t)
                self.assertTrue(np.array_equal(f, self.io.grab_frames(SYNTH, [t])[round(t, 6)]))

    def test_grab_frames_beyond_end_keeps_original_keys(self):
        """批量口同样收口，且**返回键仍是原始请求值**（调用方按原 t 取帧）。"""
        m = self.io.metadata(SYNTH)
        beyond = round(m.duration + 5.0, 6)
        got = self.io.grab_frames(SYNTH, [1.0, beyond])
        self.assertIn(1.0, got)
        self.assertIn(beyond, got)
        # 片内请求逐位不变（构造性零语义）
        got2 = self.io.grab_frames(SYNTH, [0.5, 1.5])
        self.assertEqual(sorted(got2), [0.5, 1.5])
        self.assertTrue(np.array_equal(got2[1.5], self.io.grab_frame(SYNTH, 1.5)))

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

    # ---- 续55：簇间并发解码（media.cluster_workers，默认 1 = 现役串行）----

    def test_cluster_parallel_equals_serial_and_single(self):
        """零语义：多簇并发与串行逐簇结果逐字节一致，且都等于单帧 grab_frame。"""
        serial = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE, cluster_workers=1)
        par = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE, cluster_workers=4)
        times = [0.5, 1.5, 4.8]          # 0.5/1.5 同簇（间隔≤4s），4.8 自成第二簇
        a = serial.grab_frames(SYNTH, times)
        b = par.grab_frames(SYNTH, times)
        self.assertEqual(sorted(a.keys()), sorted(b.keys()))
        for t in times:
            self.assertTrue(np.array_equal(a[round(t, 6)], b[round(t, 6)]),
                            f"并发簇与串行簇帧不一致 t={t}")
            self.assertTrue(np.array_equal(self.io.grab_frame(SYNTH, t), b[round(t, 6)]),
                            f"并发簇帧与单帧 grab 不一致 t={t}")

    def test_cluster_parallel_keeps_failure_fallback(self):
        """某簇解码失败时，并发路径同样逐帧回退（与串行版语义一致），其他簇不受影响。"""
        par = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE, cluster_workers=4)
        real = par._decode_window

        def boom(path, ts_sorted, **kw):
            if ts_sorted and ts_sorted[0] >= 4.0:
                raise MediaError("synthetic cluster failure")
            return real(path, ts_sorted, **kw)

        par._decode_window = boom
        times = [0.5, 1.5, 4.8]
        got = par.grab_frames(SYNTH, times)
        self.assertEqual(sorted(got.keys()), [0.5, 1.5, 4.8])
        for t in times:
            self.assertTrue(np.array_equal(self.io.grab_frame(SYNTH, t), got[round(t, 6)]),
                            f"失败簇回退后帧不一致 t={t}")

    def test_cluster_workers_default_one(self):
        """默认构造 = 串行（现役行为逐位不变）。"""
        self.assertEqual(FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE).cluster_workers, 1)
        self.assertEqual(FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE, cluster_workers=0)
                         .cluster_workers, 1)

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
