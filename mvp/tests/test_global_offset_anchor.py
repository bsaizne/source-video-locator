# -*- coding: utf-8 -*-
"""Unit tests for engine.localization.offset_vote_prior.global_offset_anchor (fast-global M1).

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_global_offset_anchor -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engine.localization.offset_vote_prior import (frame_quality_stats,
                                                   global_offset_anchor,
                                                   offset_vote_seed)

DIM = 64


def _lib(n: int = 60):
    """源库: n 帧 @1fps, 第 i 帧 = 单位向量 e_i(检索 top-1 完全可指定)。"""
    feats = np.eye(n, dtype=np.float32)
    times = np.arange(n, dtype=np.float64)
    return feats, times


def _q(times, targets, n_lib: int = 60):
    """查询帧: 第 k 帧 = e_{targets[k]}(top-1 指定命中源帧 targets[k])。"""
    idx = np.asarray(targets, dtype=int)
    feats = np.zeros((len(idx), max(n_lib, idx.max() + 1)), np.float32)
    feats[np.arange(len(idx)), idx] = 1.0
    return feats, np.asarray(times, dtype=np.float64)


class GlobalAnchorTest(unittest.TestCase):
    def test_large_shift_allowed_without_cap(self):
        # 4 采样帧(两帧同时刻→众数桶 2 票), 位移 5s。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 10.0, 10.33, 10.67], [5, 5, 6, 7])
        # proj = lib_t[j] - (q_t - q_t0) = 5,5,5.67,6.33。众数簇 {5,5}=2 票,
        # support=0.5, 宽窗(±1.5s)=4/4=1.0。种子=5.0, 位移 5s。
        s_vp, i_vp = offset_vote_seed(qf, q_t, Lf, Lt, span_start=10.0)
        s_g, i_g = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNotNone(s_g, msg=str(i_g))
        self.assertTrue(i_g["applied"])
        self.assertGreater(i_g["move_s"], 4.0)   # 同款数据 vote_prior 必拒
        self.assertIsNone(s_vp)
        self.assertEqual(i_vp["reason"], "move_exceeds_max_shift")

    def test_scattered_votes_rejected_by_wide_gate(self):
        # 5 票: 众数桶 2 票(过 support/cluster 门), 其余散在 24/34/44s(多实例形态)
        # → 宽窗 ±1.5s 只有 2/5=0.4 < 0.5, 必须被宽门拒。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 10.0, 10.67, 11.0, 11.33], [5, 5, 25, 35, 45])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "wide_support_below_threshold")

    def test_support_gate_still_applies(self):
        # 6 票全落互异桶且众数桶 2 票(support=2/6≈0.333>=0.1): 过窄门,
        # 但宽窗 2/6<0.5 => 宽门拒 —— 门序 support→cluster→wide 不受新门影响。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 10.0, 10.2, 10.4, 10.6, 10.8],
                     [5, 5, 15, 25, 35, 45])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "wide_support_below_threshold")

    def test_degenerate_single_vote_cluster_rejected(self):
        # 11 票互异(support=1/11≈0.09<0.1): 窄门兜底仍有效。
        Lf, Lt = _lib(60)
        qf, q_t = _q([10.0 + 0.1 * i for i in range(11)],
                     [1, 7, 13, 19, 25, 31, 37, 43, 49, 55, 3])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "support_below_threshold")

    def test_seed_out_of_range(self):
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 10.0], [1, 1])   # proj 全=1.0, 众数簇 2 票
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0,
                                          source_duration_s=0.5)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "seed_out_of_range")

    def test_insufficient_frames(self):
        Lf, Lt = _lib()
        seed, info = global_offset_anchor(np.zeros((1, DIM), np.float32),
                                          np.array([10.0]), Lf, Lt)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "insufficient_frames")

    def test_single_vote_mode_cluster_rejected(self):
        # 消融腿回归(门机理本身): 显式 min_cluster_votes=2 时, 众数桶 1 票(support=1/3 过 0.1 门)
        # → cluster_votes_below_min。注意: 生产默认=1(M1 双臂证伪了票数判别, 见 config 注释),
        # 此测只保证门语义与诊断 reason 不回坏。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 10.33, 10.67], [5, 6, 7])   # proj 5/5.67/6.33 互异桶
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0,
                                          min_cluster_votes=2)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "cluster_votes_below_min")

    def test_production_default_allows_single_vote_cluster(self):
        # M1 证伪回归: 同款数据(单票众数簇)在生产默认(min_cluster_votes=1)下必须采纳——
        # 真匹配在 1s 库网格上天然单票窄桶, 门=2 会饿死整个锚定机制(105->82 实测)。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 10.33, 10.67], [5, 6, 7])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNotNone(seed, msg=str(info))
        self.assertTrue(info["applied"])
        self.assertEqual(info["cluster_votes"], 1)

    def test_tight_small_shift_matches_vote_prior_seed(self):
        # proj 完全重合的小位移: 两函数种子一致(升级不动已兑现 +2 的行为面)。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 11.0, 12.0], [9, 10, 11])   # proj 全 = 9.0
        s1, i1 = offset_vote_seed(qf, q_t, Lf, Lt, span_start=8.0)
        s2, i2 = global_offset_anchor(qf, q_t, Lf, Lt, span_start=8.0)
        self.assertIsNotNone(s1, msg=str(i1))
        self.assertIsNotNone(s2, msg=str(i2))
        self.assertEqual(s1, s2)

    # ---------------- M2 消融腿（默认值=M1 生产形态, 行为零变化） ----------------

    def _graded_q(self, times, targets):
        """查询帧 = 0.6e_a+0.3e_b+0.1e_c（top-3 序确定: a>b>c）。"""
        rows, dim = [], 60
        for t in targets:
            v = np.zeros(dim, np.float32)
            v[t] = 0.6
            v[t + 1] = 0.3
            v[t + 2] = 0.1
            rows.append(v / np.linalg.norm(v))
        return np.stack(rows), np.asarray(times, np.float64)

    def test_topk_default_is_top1(self):
        # 默认 vote_top_k=1: votes=样本数, 与 M1 行为逐位一致。
        Lf, Lt = _lib()
        qf, q_t = self._graded_q([10.0, 10.33], [5, 5])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNotNone(seed, msg=str(info))
        self.assertEqual(info["votes"], 2)

    def test_topk3_expands_votes(self):
        # 腿 a: k=3 每样本 3 票(votes=6); 两样本同目标同时刻 → top-1 票同桶聚成众数簇(2 票),
        # rank2/3 票(6.0/7.0)散开但部分仍在宽窗, wide>=0.5 过门 → 采纳, 种子仍=5.0。
        Lf, Lt = _lib()
        qf, q_t = self._graded_q([10.0, 10.0], [5, 5])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0,
                                          vote_top_k=3)
        self.assertIsNotNone(seed, msg=str(info))
        self.assertEqual(seed, 5.0)
        self.assertEqual(info["votes"], 6)
        self.assertEqual(info["cluster_votes"], 2)

    def test_wide_std_default_off(self):
        # 腿 b 默认 0=关: 宽窗内票集 std≈0.55 的数据照常采纳(M1 行为不变)。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 10.0, 10.33, 10.67], [5, 5, 6, 7])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNotNone(seed, msg=str(info))
        self.assertNotIn("wide_std_s", info)

    def test_wide_std_gate_rejects_dispersed_window(self):
        # 腿 b: 同款数据开 0.35 门 → 宽窗票集 std≈0.55 > 0.35 拒(竞品 dispersion 门的宽窗重建)。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 10.0, 10.33, 10.67], [5, 5, 6, 7])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0,
                                          wide_std_max_s=0.35)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "wide_std_above_threshold")
        self.assertGreater(info["wide_std_s"], 0.35)

    def test_wide_std_gate_allows_tight_window(self):
        # 腿 b 正例: proj 全等(std=0)时 0.35 门放行——门拒散不拒紧。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 11.0, 12.0], [9, 10, 11])   # proj 全 = 9.0
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0,
                                          wide_std_max_s=0.35)
        self.assertIsNotNone(seed, msg=str(info))

    def test_min_valid_samples_default2(self):
        # 腿 d 默认 2: 2 样本照常采纳(M1 现状)。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 11.0], [9, 9])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNotNone(seed, msg=str(info))

    def test_min_valid_samples3_rejects_short(self):
        # 腿 d: min_valid_samples=3 时 2 样本不足(竞品 insufficient_samples 形态)。
        Lf, Lt = _lib()
        qf, q_t = _q([10.0, 11.0], [9, 9])
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0,
                                          min_valid_samples=3)
        self.assertIsNone(seed)
        self.assertEqual(info["reason"], "insufficient_frames")

    # ---------------- M2 消融腿 c（质量权重, 默认关=None=均匀权） ----------------

    def _two_way_q(self):
        """两样本竞争: s0 弱匹配 e5(sim≈0.707) / s1 强匹配 e6(sim≈0.994), 同刻。"""
        Lf, Lt = _lib()
        v0 = np.zeros(60, np.float32); v0[5] = 0.5; v0[9] = 0.5
        v1 = np.zeros(60, np.float32); v1[6] = 0.9; v1[9] = 0.1
        qf = np.stack([v0 / np.linalg.norm(v0), v1 / np.linalg.norm(v1)])
        return qf, np.array([10.0, 10.0]), Lf, Lt

    def test_quality_weight_none_is_uniform(self):
        # 腿 c 默认 None=均匀权: 强匹配票赢 → 种子 6.0(M1 行为不变)。
        qf, q_t, Lf, Lt = self._two_way_q()
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0)
        self.assertIsNotNone(seed, msg=str(info))
        self.assertEqual(seed, 6.0)

    def test_quality_weight_flips_mode_to_high_quality_sample(self):
        # 腿 c: s1 匹配强但质量低(0.2)、s0 匹配弱但质量高(1.0) → 加权后 s0 票赢, 种子 5.0。
        # 机理 = 沙盒 F2 同款投票权 = 相似度 × 质量; support/wide 仍按票数计(2/2=1.0 过门)。
        qf, q_t, Lf, Lt = self._two_way_q()
        seed, info = global_offset_anchor(qf, q_t, Lf, Lt, span_start=10.0,
                                          quality_w=np.array([1.0, 0.2]))
        self.assertIsNotNone(seed, msg=str(info))
        self.assertEqual(seed, 5.0)
        self.assertEqual(info["votes"], 2)
        self.assertEqual(info["cluster_votes"], 1)

    def test_frame_quality_stats_bright_vs_dark(self):
        bright = np.full((90, 160, 3), 255, np.uint8)
        dark = np.zeros((90, 160, 3), np.uint8)
        b_b, _, _ = frame_quality_stats(bright)
        b_d, _, _ = frame_quality_stats(dark)
        self.assertAlmostEqual(b_b, 1.0, places=5)
        self.assertAlmostEqual(b_d, 0.0, places=5)

    def test_frame_quality_stats_sharp_vs_flat(self):
        flat = np.full((90, 160, 3), 128, np.uint8)
        checker = np.kron(np.ones((45, 80)), [[0, 255], [255, 0]]).astype(np.uint8)
        checker = np.stack([checker] * 3, axis=-1)
        _, _, s_flat = frame_quality_stats(flat)
        _, _, s_sharp = frame_quality_stats(checker)
        self.assertGreater(s_sharp, s_flat)
        self.assertLessEqual(s_sharp, 1.5)   # 清晰度帽


if __name__ == "__main__":
    unittest.main(verbosity=2)
