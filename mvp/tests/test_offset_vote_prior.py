# -*- coding: utf-8 -*-
"""偏移投票起点先验 单测（2026-09-27 续10m/续11 立项移植）。

合成特征验证: ①共识种子正确性 ②support 门 ③max_shift 门 ④越界拒绝 ⑤失败隔离输入。
沙盒依据: FINDINGS_FAST_GLOBAL_REPRO.md（四片 89 -> 100/139, test1 +10 零退化）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent))

from engine.localization.offset_vote_prior import offset_vote_seed  # noqa: E402


def _unit(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.maximum(n, 1e-8)


def _make_lib(seed: int, n: int = 200, dim: int = 64, fps: float = 1.0):
    rng = np.random.default_rng(seed)
    feats = _unit(rng.normal(size=(n, dim)).astype(np.float32))
    times = np.arange(n, dtype=np.float64) / fps
    return feats, times


class TestOffsetVoteSeed(unittest.TestCase):
    def test_consensus_seed_recovers_true_start(self):
        """过半样本命中真值区 -> 共识种子落在真值起点附近。"""
        lib_f, lib_t = _make_lib(7)
        true_start = 100.0
        # 查询段 2s @2fps = 5 帧; 段内容 = 源 [100,102) 逐帧对应 + 1 个离群样本
        q_times = np.arange(5) * 0.5
        q_feats = np.stack([lib_f[int((true_start + d) * 1.0)] for d in q_times[:4]]
                           + [lib_f[10]]).astype(np.float32)
        seed, info = offset_vote_seed(q_feats, q_times, lib_f, lib_t,
                                      span_start=98.0)
        self.assertTrue(info["applied"])
        self.assertIsNotNone(seed)
        self.assertLess(abs(seed - true_start), 0.6)
        self.assertGreaterEqual(info["support"], 0.2)

    def test_support_gate_blocks_scattered_votes(self):
        """样本各自命中不相邻位置 -> support 低于门槛, 不采纳。"""
        lib_f, lib_t = _make_lib(11)
        rng = np.random.default_rng(3)
        q_times = np.arange(8) * 0.5
        picks = rng.choice(len(lib_t), size=8, replace=False)
        q_feats = np.stack([lib_f[j] for j in picks]).astype(np.float32)
        seed, info = offset_vote_seed(q_feats, q_times, lib_f, lib_t,
                                      span_start=50.0)
        self.assertIsNone(seed)
        self.assertFalse(info["applied"])
        self.assertEqual(info["reason"], "support_below_threshold")

    def test_max_shift_gate_blocks_far_seed(self):
        """种子与当前起点距离超限 -> 拒绝（防多实例场景种子偏置）。"""
        lib_f, lib_t = _make_lib(13)
        true_start = 150.0
        q_times = np.arange(5) * 0.5
        q_feats = np.stack([lib_f[int(true_start + d)] for d in q_times]).astype(np.float32)
        seed, info = offset_vote_seed(q_feats, q_times, lib_f, lib_t,
                                      span_start=140.0, max_shift_s=4.0)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "move_exceeds_max_shift")
        # 同输入放宽上限后采纳
        seed2, info2 = offset_vote_seed(q_feats, q_times, lib_f, lib_t,
                                        span_start=140.0, max_shift_s=12.0)
        self.assertIsNotNone(seed2)
        self.assertTrue(info2["applied"])

    def test_seed_out_of_source_range_rejected(self):
        lib_f, lib_t = _make_lib(17, n=50)
        q_times = np.arange(4) * 0.5
        q_feats = np.stack([lib_f[2 + k] for k in range(4)]).astype(np.float32)
        # 投影 seed ≈ 1.0s; source_duration 传 0.5 -> 越界拒绝
        seed, info = offset_vote_seed(q_feats, q_times, lib_f, lib_t,
                                      span_start=None, source_duration_s=0.5)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "seed_out_of_range")

    def test_insufficient_frames(self):
        lib_f, lib_t = _make_lib(19)
        seed, info = offset_vote_seed(np.zeros((1, 64), np.float32),
                                      np.array([0.0]), lib_f, lib_t)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "insufficient_frames")

    def test_single_dominant_cluster_weighted_centroid(self):
        """簇内质心 = 加权均值（高 sim 票主导）。"""
        lib_f, lib_t = _make_lib(23)
        base = 80.0
        q_times = np.arange(6) * 0.5
        # 5 票一致 + 1 票相邻簇外(>±1 桶): 投影 80.0 x3, 80.05 x2(同簇), 85 x1(离群)
        proj = [80.0, 80.0, 80.0, 80.05, 80.05, 85.0]
        # 样本 i 须命中帧 (proj_i + q_times[i]) 才能产生投影 proj_i
        q_feats = np.stack([lib_f[int(round(p + q_times[i]))]
                            for i, p in enumerate(proj)]).astype(np.float32)
        seed, info = offset_vote_seed(q_feats, q_times, lib_f, lib_t,
                                      span_start=80.0)
        self.assertTrue(info["applied"])
        self.assertLess(abs(seed - 80.0), 0.6)
        self.assertLess(info["dispersion_s"], 0.5)

    def test_no_side_effects_on_inputs(self):
        lib_f, lib_t = _make_lib(29)
        q_times = np.arange(4) * 0.5
        q_feats = np.stack([lib_f[50 + k] for k in range(4)]).astype(np.float32)
        q0 = q_feats.copy()
        offset_vote_seed(q_feats, q_times, lib_f, lib_t, span_start=50.0)
        np.testing.assert_array_equal(q_feats, q0)


if __name__ == "__main__":
    unittest.main()
