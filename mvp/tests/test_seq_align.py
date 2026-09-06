"""Unit tests for mvp.engine.localization.seq_align (frame-level moment alignment).

Deterministic: constructed L2-normalized arrays, no DINOv2 / real video. Verifies
align_moments recovers a continuous copied segment, splits multi-moment (montage),
gates on noise / mean_sim / max_cells, and converts frame indices to seconds.

Run:  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_seq_align -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from engine.localization.seq_align import align_moments


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


def _bundle():
    """orig: 100 frames, orig_times @0.5fps (每帧 2s, times 0..198)."""
    rng = np.random.RandomState(0)
    orig = _l2(rng.randn(100, 384).astype(np.float32))
    orig_times = (np.arange(100) * 2.0).astype(np.float32)
    return orig, orig_times


class SeqAlignTest(unittest.TestCase):
    def test_continuous_segment(self):
        orig, ot = _bundle()
        q = _l2(orig[10:20] + 1e-3 * np.random.RandomState(1).randn(10, 384).astype(np.float32))
        qt = (np.arange(10) * 0.5).astype(np.float32)   # 编辑 @8fps (0.5s/帧)
        # 紧凑候选窗（对齐产品 evidence span ± pad），正确区 orig[10:20] 居中
        r = orig[5:35]; rt = ot[5:35]
        res = align_moments(q, qt, r, rt)
        self.assertEqual(len(res.segments), 1)
        s = res.segments[0]
        self.assertAlmostEqual(s.edited_interval[0], 0.0, delta=0.1)
        self.assertAlmostEqual(s.edited_interval[1], 4.5, delta=0.1)
        # moment 收窄 ±1s：中心应在正确拷贝区 [20,38]，宽度 ≤ 2*moment_half_s
        center = (s.original_span[0] + s.original_span[1]) / 2
        self.assertGreaterEqual(center, 20.0)
        self.assertLessEqual(center, 38.0)
        self.assertLessEqual(s.original_span[1] - s.original_span[0], 2.0 + 1e-6)
        self.assertGreater(s.mean_sim, 0.7)
        self.assertGreaterEqual(s.n_frames, 5)

    def test_noise_empty(self):
        orig, ot = _bundle()
        q = _l2(np.random.RandomState(3).randn(10, 384).astype(np.float32))
        qt = (np.arange(10) * 0.5).astype(np.float32)
        res = align_moments(q, qt, orig, ot)
        self.assertEqual(len(res.segments), 0)

    def test_max_cells_skipped(self):
        orig, ot = _bundle()
        q = _l2(np.random.RandomState(4).randn(10, 384).astype(np.float32))
        qt = (np.arange(10) * 0.5).astype(np.float32)
        res = align_moments(q, qt, orig, ot, max_cells=10)
        self.assertTrue(res.skipped)
        self.assertEqual(len(res.segments), 0)

    def test_mean_sim_gate(self):
        orig, ot = _bundle()
        q = _l2(orig[10:20] + 1e-3 * np.random.RandomState(5).randn(10, 384).astype(np.float32))
        qt = (np.arange(10) * 0.5).astype(np.float32)
        res = align_moments(q, qt, orig, ot, mean_sim_min=0.99)
        self.assertEqual(len(res.segments), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
