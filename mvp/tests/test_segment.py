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
from engine.segment import adjacent_distances, detect_shots
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
