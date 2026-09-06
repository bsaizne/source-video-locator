"""Unit tests for mvp.engine.segment.flash_guard (白闪守卫, C 项验证提取入库).

Deterministic: synthetic BGR frames + synthetic cut/spike times. No DINOv2.
Run: venv python -m unittest mvp.tests.test_flash_guard -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from engine.segment.flash_guard import (brightness_spike_regions,
                                        drop_brightness_spike_cuts,
                                        drop_flash_cuts, dynamic_min_shot,
                                        frame_mean_brightness, is_flash_frame,
                                        merge_flash_segments)


def _frame(v: float, size: int = 64) -> np.ndarray:
    """单色 BGR 帧, 亮度 v。"""
    return np.full((size, size, 3), v, dtype=np.uint8)


class IsFlashFrameTest(unittest.TestCase):
    def test_bright_frame_is_flash(self):
        ok, mean, frac = is_flash_frame(_frame(230), 200.0, 0.5)
        self.assertTrue(ok)
        self.assertGreaterEqual(mean, 200)
        self.assertGreaterEqual(frac, 0.5)

    def test_normal_frame_not_flash(self):
        ok, _, _ = is_flash_frame(_frame(90), 200.0, 0.5)
        self.assertFalse(ok)

    def test_bright_but_not_dominant_not_flash(self):
        # 高均值但亮像素占比不够（如大面积灰 + 局部过曝）→ 不判白闪
        f = np.full((64, 64, 3), 120, dtype=np.uint8)
        f[0:8, 0:8] = 250
        ok, _, _ = is_flash_frame(f, 200.0, 0.5)
        self.assertFalse(ok)


class BrightnessSpikeTest(unittest.TestCase):
    def test_overexposed_spike_detected(self):
        means = [26.6, 188.2, 40.0]
        times = [0.0, 0.34, 0.69]
        spikes = brightness_spike_regions(means, times, delta=80.0, peak_th=180.0)
        # 白闪型: 暗→过曝(0.34) 与 过曝→回落(0.69) 两侧都满足 delta+peak → 两个边界
        self.assertEqual(spikes, [0.34, 0.69])

    def test_normal_cut_not_spike(self):
        means = [139.4, 21.1, 90.0]
        times = [0.0, 0.34, 0.69]
        spikes = brightness_spike_regions(means, times, delta=80.0, peak_th=180.0)
        self.assertEqual(spikes, [])        # 单向变暗, 峰值<180 → 不判白闪


class DropCutsTest(unittest.TestCase):
    def test_drop_flash_cuts(self):
        cuts = [1.0, 5.0, 9.0]
        flash = [5.1]
        kept = drop_flash_cuts(cuts, flash, flash_margin_s=0.2)
        self.assertEqual(kept, [1.0, 9.0])

    def test_drop_brightness_spike_cuts(self):
        cuts = [1.0, 5.0, 9.0]
        spikes = [9.1]
        kept = drop_brightness_spike_cuts(cuts, spikes, margin_s=0.25)
        self.assertEqual(kept, [1.0, 5.0])

    def test_no_overlap_keeps_all(self):
        cuts = [1.0, 5.0, 9.0]
        self.assertEqual(drop_flash_cuts(cuts, [20.0]), cuts)
        self.assertEqual(drop_brightness_spike_cuts(cuts, [20.0]), cuts)


class DynamicMinShotTest(unittest.TestCase):
    def test_flash_area_gets_dynamic_threshold(self):
        segs = [(0.0, 2.0), (2.0, 4.0)]
        ths = dynamic_min_shot(segs, [2.5], min_shot_s=0.5, dyn_s=1.0,
                               flash_margin_s=0.2)
        self.assertEqual(ths, [0.5, 1.0])   # 白闪 2.5 在段 (2,4) 内 → 该段抬到 1.0

    def test_no_flash_flat_threshold(self):
        segs = [(0.0, 2.0), (2.0, 4.0)]
        ths = dynamic_min_shot(segs, [], min_shot_s=0.5, dyn_s=1.0)
        self.assertEqual(ths, [0.5, 0.5])


class MergeFlashSegmentsTest(unittest.TestCase):
    def test_high_flash_share_merges(self):
        segs = [(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)]
        out = merge_flash_segments(segs, [2.1, 3.9], merge_frac=0.5)
        # 段 (2,4) 白闪跨度 1.8/2.0=0.9>=0.5 → 删右边界 → 合并
        self.assertEqual(len(out), 2)

    def test_no_flash_no_change(self):
        segs = [(0.0, 2.0), (2.0, 4.0)]
        self.assertEqual(merge_flash_segments(segs, []), segs)


class FrameBrightnessTest(unittest.TestCase):
    def test_mean(self):
        self.assertAlmostEqual(frame_mean_brightness(_frame(100)), 100.0)


if __name__ == "__main__":
    unittest.main()
