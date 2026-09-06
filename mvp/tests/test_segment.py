"""Unit tests for mvp.engine.segment (无 GT 编辑侧 shot 切分).

Deterministic: synthesizes L2-normalized feature arrays with *known* shot structure
(no DINOv2 / real video), so boundary assertions are strong and seed-fixed.
Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_segment -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from domain import TimeSpan
from engine.common import cosine_similarity
from engine.segment import ShotSegment, adjacent_distances, detect_shots
from engine.segment.segment import SEG_MIN_SHOT_S, _merge_short


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


def _times(n, fps=2.0):
    return (np.arange(n) / fps).astype(np.float32)


def _blocks(shape_blocks, base_noise=1e-2, seed=0):
    """每块一个随机基准向量 + 小噪声：块内 d≈0，块间 d≈1（清晰可切分边界）。

    返回拼接后的 [N,384] L2 归一化特征，块与块之间为独立随机场景。
    """
    rng = np.random.RandomState(seed)
    out = []
    for nb in shape_blocks:
        base = rng.randn(1, 384).astype(np.float32)
        blk = _l2(base + base_noise * rng.randn(nb, 384).astype(np.float32))
        out.append(blk)
    return np.concatenate(out, axis=0).astype(np.float32)


def _orthonormal(n, seed=0):
    """n 个相互正交的单位向量（QR）：任意两帧 cos=0 -> 相邻 d=1 均匀，无内部尖峰。"""
    rng = np.random.RandomState(seed)
    q, _ = np.linalg.qr(rng.randn(384, n))
    return _l2(q[:, :n].T.astype(np.float32))


class DetectShotsTest(unittest.TestCase):
    def test_empty(self):
        feats = np.zeros((0, 384), np.float32)
        self.assertEqual(detect_shots(feats, np.zeros(0, np.float32)), [])

    def test_single_frame(self):
        feats = _orthonormal(1)
        times = np.array([0.0], np.float32)
        shots = detect_shots(feats, times)
        self.assertEqual(len(shots), 1)
        self.assertEqual(shots[0].span, TimeSpan(0.0, 0.0))
        self.assertEqual(shots[0].nq, 1)

    def test_three_blocks_three_shots(self):
        feats = _blocks([5, 5, 5])            # 15 帧，3 个清晰可切分场景
        times = _times(15)                    # 0..7.0 @2fps
        shots = detect_shots(feats, times)
        self.assertEqual(len(shots), 3)
        # 帧数与时间窗
        for s, want in zip(shots, [5, 5, 5]):
            self.assertEqual(s.nq, want)
        self.assertAlmostEqual(shots[0].span.start, 0.0, places=1)
        self.assertAlmostEqual(shots[0].span.end, 2.0, places=1)
        self.assertAlmostEqual(shots[1].span.start, 2.5, places=1)
        self.assertAlmostEqual(shots[1].span.end, 4.5, places=1)
        self.assertAlmostEqual(shots[2].span.start, 5.0, places=1)
        self.assertAlmostEqual(shots[2].span.end, 7.0, places=1)
        # 特征/时间切片自洽且为读视图；段与段连续（无重叠、无缝隙）
        self.assertEqual(shots[0].feats.shape, (5, 384))
        self.assertTrue(np.array_equal(shots[0].feats, feats[0:5]))
        self.assertTrue(np.array_equal(shots[1].feats, feats[5:10]))
        self.assertTrue(np.array_equal(shots[2].feats, feats[10:15]))
        for s in shots:
            self.assertTrue(np.all(np.diff(s.times) > 0), "times strictly ascending")
        self.assertLess(shots[0].span.end, shots[1].span.start)
        self.assertLess(shots[1].span.end, shots[2].span.start)

    def test_uniform_high_d_single_shot(self):
        """研究警示场景：相邻距离几乎处处高（正交向量 -> d=1），但无内部尖峰。
        绝不能因为绝对距离高而被大量误切（产品约束 #3）。"""
        feats = _orthonormal(10)
        shots = detect_shots(feats, _times(10))
        self.assertEqual(len(shots), 1, "uniform high-d must NOT be over-segmented")
        self.assertEqual(shots[0].nq, 10)

    def test_continuous_scene_single_shot(self):
        feats = _blocks([10])                 # 单一连续场景，块内 d≈0
        shots = detect_shots(feats, _times(10))
        self.assertEqual(len(shots), 1)
        self.assertEqual(shots[0].nq, 10)

    def test_min_shot_larger_than_duration(self):
        feats = _blocks([5, 5])               # 本可切 2 段，但 min_shot_s 过大
        shots = detect_shots(feats, _times(10), min_shot_s=10.0)
        self.assertEqual(len(shots), 1)

    def test_alternating_no_fragmentation(self):
        """高度交替内容 -> 不产生单帧碎片；每段帧数 >= min_gap（产品约束 #2 下切分）。"""
        feats = _orthonormal(6)
        shots = detect_shots(feats, _times(6))
        min_gap = max(1, int(round(SEG_MIN_SHOT_S * 2.0)))
        self.assertGreaterEqual(len(shots), 1)
        for s in shots:
            self.assertGreaterEqual(s.nq, min_gap, f"degenerate {s.nq}-frame shot")


class MergeShortTest(unittest.TestCase):
    """白盒：`_merge_short` 消除过短/退化段，并入更弱边界一侧（约束 #2 防碎片化）。"""

    def test_interior_degenerate_merged(self):
        n = 12
        feats = np.zeros((n, 384), np.float32)
        times = _times(n)
        s = np.ones(n - 1, np.float64)        # cut 强度均等
        shots = _merge_short([2, 5], s, min_gap=4, ed_times=times, ed_feats=feats)
        # 初始段 [0,3,6,12] -> 前三段帧数 [3,3,6]，两个 <4 段逐叠吸收 -> [0,6,12] = 2 段 6/6
        self.assertEqual(len(shots), 2)
        self.assertGreaterEqual(shots[0].nq, 4)
        self.assertGreaterEqual(shots[1].nq, 4)

    def test_edge_degenerate_merged(self):
        n = 12
        feats = np.zeros((n, 384), np.float32)
        times = _times(n)
        s = np.ones(n - 1, np.float64)
        shots = _merge_short([2], s, min_gap=4, ed_times=times, ed_feats=feats)
        self.assertEqual(len(shots), 1)       # [0,3,12] 首段 3<4 -> 并入末段

    def test_no_degenerate_no_merge(self):
        n = 15
        feats = np.zeros((n, 384), np.float32)
        times = _times(n)
        s = np.ones(n - 1, np.float64)
        shots = _merge_short([4], s, min_gap=2, ed_times=times, ed_feats=feats)
        self.assertEqual(len(shots), 2)       # [0,5,15] 两段均 >=2，不动


class AdjacentDistanceTest(unittest.TestCase):
    def test_frozen_equivalence(self):
        f = _blocks([4, 4, 4])
        d = adjacent_distances(f)
        sim = cosine_similarity(f[:-1], f[1:])
        self.assertTrue(np.allclose(d, 1.0 - np.diag(sim), atol=1e-5))
        self.assertGreaterEqual(float(d.min()), 0.0)
        self.assertLessEqual(float(d.max()), 2.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


# --------------------------------------------------------------------------- #
# 二级细分(GT v3 迭代):长块内部弱边界由放宽参数补切
# --------------------------------------------------------------------------- #
class DetectShotsTwoLevelTest(unittest.TestCase):
    def _features_weak_second_boundary(self):
        """3 块:|b1|b2| 强边界(粗参数可见),|b2|b3| 弱边界(cos d≈0.4,粗参数不可见)。"""
        rng = np.random.default_rng(3)
        base = rng.normal(size=(3, 384))
        base = base / np.linalg.norm(base, axis=1, keepdims=True)
        mixed = 0.6 * base[1] + 0.8 * base[2]
        mixed = mixed / np.linalg.norm(mixed)

        def block(direction, n, noise=0.01):
            # noise=0.01:384 维下块内 cos d≈0.04,边界 cos d≈0.4 —— 信噪比足够 z 判别
            return direction[None, :] + rng.normal(0, noise, (n, 384))

        feats = np.vstack([block(base[0], 20), block(base[1], 20), block(mixed, 12)])
        feats = feats / np.linalg.norm(feats, axis=1, keepdims=True)
        times = np.arange(len(feats), dtype=np.float32) / 2.0
        return feats, times

    def test_two_level_recovers_weak_internal_boundary(self):
        from engine.segment import detect_shots_two_level
        feats, times = self._features_weak_second_boundary()
        coarse = detect_shots(feats, times, cut_abs=0.5, z_thresh=2.0,
                              min_shot_s=0.5, fps=2.0)
        self.assertLess(len(coarse), 3)  # 前置:弱边界对粗参数不可见
        fine = detect_shots_two_level(feats, times, cut_abs=0.5, z_thresh=2.0,
                                      min_shot_s=0.5, fps=2.0, max_shot_s=8.0,
                                      fine_cut_factor=0.75, fine_z_factor=0.85,
                                      fine_min_shot_s=0.5)
        self.assertGreater(len(fine), len(coarse))       # 长块内部补切
        self.assertAlmostEqual(fine[0].span.start, times[0], places=5)
        self.assertAlmostEqual(fine[-1].span.end, times[-1], places=5)  # 覆盖完整

    def test_short_blocks_untouched(self):
        from engine.segment import detect_shots_two_level
        rng = np.random.default_rng(5)
        base = rng.normal(size=(3, 384))
        base = base / np.linalg.norm(base, axis=1, keepdims=True)
        feats = np.vstack([base[i] + rng.normal(0, 0.05, (6, 384)) for i in range(3)])
        feats = feats / np.linalg.norm(feats, axis=1, keepdims=True)
        times = np.arange(len(feats), dtype=np.float32) / 2.0
        coarse = detect_shots(feats, times, cut_abs=0.3, z_thresh=1.5,
                              min_shot_s=0.5, fps=2.0)
        fine = detect_shots_two_level(feats, times, cut_abs=0.3, z_thresh=1.5,
                                      min_shot_s=0.5, fps=2.0, max_shot_s=8.0)
        self.assertEqual(len(coarse), len(fine))  # 短块(3s<8s)不触发二级

    def test_card_ratio_default_zero(self):
        rng = np.random.default_rng(6)
        feats = rng.normal(size=(5, 384)).astype(np.float32)
        shot = ShotSegment(span=TimeSpan(0.0, 2.0), feats=feats,
                           times=np.arange(5, dtype=np.float32))
        self.assertEqual(shot.card_ratio, 0.0)
