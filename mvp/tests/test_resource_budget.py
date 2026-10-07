"""① 低内存收缩 batch+预取（2026-10-07 立项）单测。

- ``media.resource_budget.compute_media_budget``：阈值分档 + 探针不可用全默认（宁缺毋假）。
- ``isc_l2_index.build_tp_index(max_cluster_frames=)``：簇切小只改批次不改帧
  （times/feats 与不设上限逐字节一致），且确实产生更多批（收缩真实生效）。
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from media.resource_budget import (DEFAULT_GRAB_WORKERS,           # noqa: E402
                                   DEFAULT_MAX_CLUSTER_FRAMES, compute_media_budget)

GB = 1024 ** 3


class ComputeMediaBudgetTest(unittest.TestCase):
    def test_unknown_probe_returns_defaults(self):
        b = compute_media_budget(None)
        self.assertFalse(b.low_memory_mode)
        self.assertEqual(b.tier, "unknown")
        self.assertEqual(b.grab_workers, DEFAULT_GRAB_WORKERS)
        self.assertEqual(b.max_cluster_frames, DEFAULT_MAX_CLUSTER_FRAMES)

    def test_generous_memory_is_ok_tier(self):
        b = compute_media_budget(64 * GB)
        self.assertEqual((b.tier, b.grab_workers, b.max_cluster_frames),
                         ("ok", 4, 120))
        self.assertFalse(b.low_memory_mode)

    def test_tight_tier_shrinks(self):
        # usable = 4GB − 2GB = 2GB → 落紧档
        b = compute_media_budget(4 * GB)
        self.assertEqual((b.tier, b.grab_workers, b.max_cluster_frames),
                         ("tight", 2, 64))
        self.assertTrue(b.low_memory_mode)

    def test_critical_tier_floor(self):
        # usable = 1GB − 2GB → 0，但绝不给 0 线程/0 帧（下限 1/16）
        b = compute_media_budget(1 * GB)
        self.assertEqual((b.tier, b.grab_workers, b.max_cluster_frames),
                         ("critical", 1, 16))
        self.assertTrue(b.low_memory_mode)

    def test_boundary_exact_thresholds(self):
        # usable 恰好 = 6GB → ok；恰好 4GB（= 6−2）→ tight
        self.assertEqual(compute_media_budget(8 * GB).tier, "ok")
        self.assertEqual(compute_media_budget(6 * GB).tier, "tight")


class _FakeMeta:
    duration = 10.0


class _FakeFfmpeg:
    """grab_grid 每次 spawn 返回 {t: frame}；记录调用次数与每次窗口。"""

    ffprobe = "ffprobe"

    def __init__(self, n_targets, fps):
        self.fps = fps
        self.n = n_targets
        self.calls = []

    def metadata(self, src):
        return _FakeMeta()

    def grab_grid(self, src, c0, step, n_targets, max_span_s=0.0):
        self.calls.append((round(c0, 6), int(n_targets)))
        out = {}
        for k in range(int(n_targets)):
            t = c0 + k * step
            out[round(t, 6)] = np.full((2, 2, 3), int(t * self.fps) % 255, np.uint8)
        return out


class _FakeScorer:
    def embed(self, frame):
        return np.asarray(frame[:, :, 0], dtype=np.float32) / 255.0


class BuildTpIndexCapTest(unittest.TestCase):
    def _build(self, **kw):
        import tempfile
        from engine.localization import isc_l2_index
        fps = 1.0
        src = Path(tempfile.mkdtemp()) / "fake.mp4"
        src.write_bytes(b"0" * 16)             # meta 里 sha256_of 要读真文件
        ff = _FakeFfmpeg(10, fps)
        with mock.patch.object(isc_l2_index, "_capped_target_n", return_value=10):
            return isc_l2_index.build_tp_index(src, ffmpeg=ff, scorer=_FakeScorer(),
                                               fps=fps, **kw), ff

    def test_cap_splits_clusters_but_keeps_frames_identical(self):
        (T1, F1, _), ff1 = self._build()
        (T2, F2, _), ff2 = self._build(max_cluster_frames=3)
        np.testing.assert_array_equal(T1, T2)
        np.testing.assert_array_equal(F1, F2)          # 帧逐字节一致
        self.assertEqual(len(ff2.calls) > len(ff1.calls), True)   # 收缩真实生效（更多批）
        self.assertTrue(all(n <= 3 for _, n in ff2.calls))        # 每批 ≤ 上限

    def test_default_no_extra_cap(self):
        (T1, F1, _), ff1 = self._build()
        self.assertEqual(ff1.calls, [(0.0, 10)])       # 现役：一簇全取


if __name__ == "__main__":
    unittest.main()
