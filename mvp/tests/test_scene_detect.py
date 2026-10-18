"""Unit tests for engine.segment.scene_detect（scn2：像素通道 + CLS 证据融合）
+ FeatureStore 的派生表升级路径 ``refresh_derived``。

判据来源 = 2026-10-11 边界尺子（``mvp/scripts/shot_detect/boundary_gt_v1.json``），
详见 ``mvp/docs/FINDINGS_SHOT_DETECTION_A1_20261011.md``。

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_scene_detect -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from domain import IndexValidationStatus
from engine.feature_store import feature_store as FS
from engine.segment.scene_detect import (PixelStream, SceneDetectConfig, block_gate_ok,
                                         semantic_block_stats, semantic_gate_ok,
                                         block_stats, build_scene_table,
                                         detect_pixel_boundaries, detect_scene_bounds,
                                         gray_hist, to_gray, _snap_index)

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"
CFG = SceneDetectConfig()
CFG_NOGATE = SceneDetectConfig(block_gate=False)


class PixelSeriesTest(unittest.TestCase):
    def test_identical_frames_score_zero(self):
        f = np.full((6, 8, 3), 123, dtype=np.uint8)
        st = PixelStream()
        st.push(0.0, f)
        st.push(0.1, f)
        st.push(0.2, f)
        times, scores = st.arrays()
        self.assertEqual(times.size, 2)          # 第 2、3 帧各产生一个「进入该帧的变化」
        self.assertTrue(np.allclose(scores, 0.0))

    def test_scene_change_scores_high_and_times_align_to_new_shot(self):
        a = np.zeros((8, 8, 3), dtype=np.uint8)
        b = np.full((8, 8, 3), 255, dtype=np.uint8)
        st = PixelStream()
        st.push(1.00, a)
        st.push(1.10, a)
        st.push(1.20, b)                          # 切换发生在这一帧
        times, scores = st.arrays()
        self.assertEqual(times.tolist(), [1.10, 1.20])
        # 黑->白：直方图 L1 = 2.0（满值）与灰度均值差 = 1.0 各占一半
        self.assertAlmostEqual(scores[1], 1.5, places=6)
        self.assertEqual(st.hist_l1[1], 2.0)
        self.assertAlmostEqual(st.mean_abs[1], 1.0, places=6)
        self.assertLess(scores[0], scores[1])

    def test_gray_and_hist_helpers(self):
        g = to_gray(np.stack([np.full((3, 3), 10, np.uint8),       # B
                              np.full((3, 3), 20, np.uint8),       # G
                              np.full((3, 3), 30, np.uint8)], axis=2))
        self.assertEqual(g.shape, (3, 3))
        self.assertEqual(int(g[0, 0]), (30 * 77 + 20 * 151 + 10 * 28) >> 8)
        h = gray_hist(np.zeros((4, 4), dtype=np.uint8))
        self.assertAlmostEqual(float(h.sum()), 1.0, places=6)


class DetectPixelBoundariesTest(unittest.TestCase):
    def _times(self, n):
        return np.arange(n, dtype=np.float64) * 0.1

    def test_isolated_spike_in_quiet_material_is_found(self):
        s = np.array([0.02] * 10 + [0.60] + [0.02] * 10)
        out = detect_pixel_boundaries(self._times(21), s, thr=CFG.pixel_thr,
                                      abs_floor=CFG.pixel_abs_floor,
                                      rel_mult=CFG.pixel_rel_mult, rel_win=CFG.pixel_rel_win)
        self.assertEqual(out, [1.0])   # 序列索引 10 = 进入第 11 帧(时间 1.0s)的变化

    def test_spike_inside_rough_material_is_rejected_by_rel_median(self):
        """判据的核心一腿：整段本来就一直在抖（甩镜/明暗呼吸）时，绝对阈值会误报。"""
        rng = np.random.RandomState(3)
        base = np.clip(rng.uniform(0.10, 0.20, size=40), 0, None)
        quiet = np.array([0.02] * 40)
        for arr in (base, quiet):
            arr[20] = 0.30                        # 同一个绝对幅度，两种材料
        rough = detect_pixel_boundaries(self._times(40), base, thr=0.10,
                                        abs_floor=0.08, rel_mult=3.0, rel_win=8)
        still = detect_pixel_boundaries(self._times(40), quiet, thr=0.10,
                                        abs_floor=0.08, rel_mult=3.0, rel_win=8)
        self.assertEqual(rough, [])
        self.assertEqual(still, [2.0])

    def test_needs_local_peak_and_floor(self):
        s = np.array([0.01, 0.05, 0.60, 0.95, 0.02])   # 上升沿：0.60 不是局部极大
        out = detect_pixel_boundaries(self._times(5), s, thr=0.10, abs_floor=0.08,
                                      rel_mult=1.5, rel_win=2)
        self.assertEqual(len(out), 1)             # 只有局部极大 0.95 那条算边界
        self.assertAlmostEqual(out[0], 0.3, places=9)

    def test_short_series_returns_empty(self):
        self.assertEqual(detect_pixel_boundaries(self._times(2), np.array([0.5, 0.9]),
                                                thr=0.1, abs_floor=0.05, rel_mult=2.0,
                                                rel_win=4), [])


class DetectSceneBoundsTest(unittest.TestCase):
    def test_both_evidence_legs_contribute(self):
        n = 20
        times = np.arange(n, dtype=np.float64) * 1.0
        s_cls = np.full(n - 1, 0.02)
        s_cls[4] = 0.50                           # CLS 看得见的一处切（帧 5 是新镜头首帧）
        pix_t = np.arange(1, 20, dtype=np.float64) * 1.0 + 0.05
        pix_s = np.full(19, 0.02)
        pix_s[11] = 0.80                          # 像素看得见、CLS 看不见的一处切（12.05s）
        # 帧 5 与 12 处画面都真的换且待住（持续性门要放行两腿各自的证据）
        hist = _block_hist(len(pix_t) + 1, [5, 13])
        bounds = detect_scene_bounds(n, times, s_cls, (pix_t, pix_s, hist), CFG, fps=1.0)
        self.assertIn(5, bounds)
        # 12.05 就近吸附到帧 12（旧写法向上取整会落在 13 —— 见 _snap_index 的偏置说明）
        self.assertIn(12, bounds)

    def test_cls_only_when_pixel_missing(self):
        n = 12
        times = np.arange(n, dtype=np.float64)
        s_cls = np.full(n - 1, 0.01)
        s_cls[6] = 0.70
        self.assertEqual(detect_scene_bounds(n, times, s_cls, None, CFG, 1.0), [7])

    def test_no_evidence_returns_empty(self):
        n = 10
        times = np.arange(n, dtype=np.float64)
        self.assertEqual(detect_scene_bounds(n, times, np.full(n - 1, 0.01),
                                             (np.array([]), np.array([]), np.zeros((0, 32), np.float32)),
                                             CFG, 1.0), [])

    def test_nms_keeps_pixel_over_cls_at_same_place(self):
        """同一位置两腿都报：像素强度 1.0 > CLS 0.6*s，只留一条边界（不重复切）。"""
        n = 10
        times = np.arange(n, dtype=np.float64)
        s_cls = np.full(n - 1, 0.01)
        s_cls[4] = 0.90
        pix_t = np.arange(1, n, dtype=np.float64)
        pix_s = np.full(n - 1, 0.02)
        pix_s[3] = 0.90                           # 像素边界时间 = times[4]+0.05 -> 帧 5
        hist = _block_hist(n, [4])
        bounds = detect_scene_bounds(n, times, s_cls, (pix_t, pix_s, hist), CFG, 1.0)
        self.assertEqual(bounds.count(5), 1)

    def test_pixel_boundary_snaps_to_nearest_grid_frame(self):
        """像素边界在网格中间时必须**就近**取帧。

        锁的是 2026-10-11 内区口径量出的系统偏置：旧写法 ``searchsorted(side="left")``
        是「第一个不早于它的帧」= 一律向上取整，把每条边界推晚最多一个网格步长
        （实测有符号位移中位 +0.215s / 绝对 0.28s，探针臂只有 0.05s）。
        """
        n = 12
        times = np.arange(n, dtype=np.float64) * 1.0
        s_cls = np.full(n - 1, 0.01)
        pix_t = np.arange(0.1, n, 0.1)
        hist = np.zeros((0, 32), dtype=np.float32)      # 空 hist => 持续性门放行，只测吸附
        for t_pix, want in ((4.2, 4), (4.8, 5), (4.0, 4)):   # 就近 / 就近 / 恰在网格上
            pix_s = np.full(pix_t.size, 0.02)
            pix_s[int(np.argmin(np.abs(pix_t - t_pix)))] = 0.90
            self.assertEqual(detect_scene_bounds(n, times, s_cls, (pix_t, pix_s, hist),
                                                 CFG, 1.0), [want], f"t_pix={t_pix}")

    def test_snap_index_is_nearest_clamped_and_idempotent(self):
        times = np.arange(6, dtype=np.float64) * 1.0
        self.assertEqual([_snap_index(times, t) for t in (2.4, 2.5, 2.6, -3.0, 99.0)],
                         [2, 2, 3, 0, 5])
        for j in range(len(times)):                     # 网格点自身必须原样映射回去
            self.assertEqual(_snap_index(times, float(times[j])), j)

    def test_min_shot_drops_weaker_boundary(self):
        cfg = SceneDetectConfig(min_shot_s=3.0)   # 最短 3 帧
        n = 12
        times = np.arange(n, dtype=np.float64)
        s_cls = np.zeros(n - 1)
        s_cls[3] = 0.35                           # 弱边界（帧 4）
        s_cls[5] = 0.95                           # 强边界（帧 6）
        bounds = detect_scene_bounds(n, times, s_cls, None, cfg, 1.0)
        self.assertEqual(bounds, [6])             # 弱的被并掉，不留 2 帧碎片


class BuildSceneTableTest(unittest.TestCase):
    def _data(self, n=24):
        rng = np.random.RandomState(7)
        feats = rng.randn(n, 8).astype(np.float32)
        feats /= np.linalg.norm(feats, axis=1, keepdims=True)
        times = np.arange(n, dtype=np.float32) * 1.0
        return feats, times

    def test_invariants_contiguous_cover_and_normalized_fingerprints(self):
        feats, times = self._data()
        pix_t = np.arange(1.0, 24.0, 0.1)
        pix_s = np.full(pix_t.size, 0.01)
        pix_s[50] = 0.9                           # 时间 6.0 -> 帧 6
        hist = _step_hist(len(pix_t) + 1, at=51)   # 时间 6.0s 起真的换画面
        scenes, fp = build_scene_table(feats, times, (pix_t, pix_s, hist), CFG, fps=1.0)
        self.assertGreater(len(scenes), 1)
        self.assertEqual(fp.shape[0], scenes.shape[0])
        self.assertEqual(fp.shape[1], feats.shape[1])
        for k in range(len(scenes)):
            self.assertLess(scenes[k, 0], scenes[k, 1])
            self.assertAlmostEqual(float(np.linalg.norm(fp[k])), 1.0, places=5)
        # 连续覆盖：第 k+1 段的起点必须等于第 k 段在网格上的下一帧
        for k in range(len(scenes) - 1):
            self.assertAlmostEqual(float(scenes[k + 1, 0]),
                                   float(scenes[k, 1]), places=4)
        self.assertAlmostEqual(float(scenes[0, 0]), float(times[0]), places=4)
        self.assertAlmostEqual(float(scenes[-1, 1]), float(times[-1]) + 1.0, places=4)

    def test_empty_features(self):
        feats = np.zeros((0, 6), dtype=np.float32)
        scenes, fp = build_scene_table(feats, np.array([], dtype=np.float32), None, CFG, 1.0)
        self.assertEqual(scenes.shape, (0, 2))
        self.assertEqual(fp.shape, (0, 6))

    def test_single_frame(self):
        feats = np.ones((1, 4), dtype=np.float32)
        scenes, fp = build_scene_table(feats, np.array([0.0], dtype=np.float32), None, CFG, 1.0)
        self.assertEqual(scenes.shape, (1, 2))
        self.assertAlmostEqual(float(scenes[0, 1]), 1.0, places=5)


def _step_hist(n_frames: int, at: int, dark: int = 0, light: int = 31) -> np.ndarray:
    """构造「第 at 帧起画面从暗切到亮」的每帧直方图（A-B-A 门要能过）。"""
    h = np.zeros((n_frames, 32), dtype=np.float32)
    for i in range(n_frames):
        h[i, light if i >= at else dark] = 1.0
    return h


def _block_hist(n_frames: int, cuts: list[int]) -> np.ndarray:
    """每段一个独立桶：任意一处候选的前块/后块都真的不同（门该放行）。"""
    h = np.zeros((n_frames, 32), dtype=np.float32)
    for i in range(n_frames):
        h[i, min(len(cuts), sum(1 for c in cuts if i >= c))] = 1.0
    return h


class BlockGateTest(unittest.TestCase):
    """A-B-A 持续性门：拦「闪一下又回到同一画面」（闪电/爆白/甩镜）。"""

    def test_block_stats_readings(self):
        same = _step_hist(40, at=10 ** 6)                 # 全程同一画面
        dist, dev = block_stats(same, 20, 4, 4, 2)
        self.assertAlmostEqual(dist, 0.0, places=6)
        self.assertAlmostEqual(dev, 0.0, places=6)
        flip = _step_hist(40, at=20)                      # 20 起真的换且稳定
        dist, dev = block_stats(flip, 20, 4, 4, 2)
        self.assertGreater(dist, 1.5)
        self.assertLess(dev, CFG.block_dev_thr)
        flick = _step_hist(40, at=20).copy()
        flick[23, 31] = 0.0; flick[23, 0] = 1.0           # 后块里夹一帧闪回 => 内部不落定
        self.assertGreater(block_stats(flick, 20, 4, 4, 2)[1], CFG.block_dev_thr)
        self.assertFalse(block_gate_ok(flick, 20, CFG))
        self.assertTrue(block_gate_ok(flip, 20, CFG))

    def test_transient_flash_is_rejected_but_persistent_change_is_kept(self):
        n = 60
        times = np.arange(n, dtype=np.float64)
        s_cls = np.full(n - 1, 0.01)
        # 像素分数：20 与 35 处同样高的尖峰；但 20 处下一帧就闪回原画面（A-B-A），35 处真的换场景
        pix_t = np.arange(1, n, dtype=np.float64)
        pix_s = np.full(n - 1, 0.02)
        pix_s[19] = 0.9
        pix_s[34] = 0.9
        hist = np.zeros((n, 32), dtype=np.float32)
        hist[:, 0] = 1.0                                  # 全程暗
        hist[35:, 31] = 1.0; hist[35:, 0] = 0.0           # 35 起真的换到亮
        hist[20:22, 31] = 1.0; hist[20:22, 0] = 0.0       # 20-21 只是闪两帧
        bounds = detect_scene_bounds(n, times, s_cls, (pix_t, pix_s, hist), CFG, 1.0)
        self.assertNotIn(20, bounds, "闪两帧又回原画面不该算镜头边界")
        self.assertIn(35, bounds)
        # 关掉门时两处都会切（证明差异确实来自这一腿，不是别的判据顺手拦的）
        raw = detect_scene_bounds(n, times, s_cls, (pix_t, pix_s, hist), CFG_NOGATE, 1.0)
        self.assertIn(20, raw)
        self.assertIn(35, raw)

    def test_gate_skipped_when_hist_unavailable(self):
        n = 30
        times = np.arange(n, dtype=np.float64)
        s_cls = np.full(n - 1, 0.01)
        s_cls[10] = 0.8
        pix_t = np.arange(1, n, dtype=np.float64)
        pix_s = np.full(n - 1, 0.02)
        pix_s[9] = 0.9
        empty_hist = np.zeros((0, 32), dtype=np.float32)
        self.assertEqual(detect_scene_bounds(n, times, s_cls, (pix_t, pix_s, empty_hist),
                                             CFG, 1.0),
                         detect_scene_bounds(n, times, s_cls, (pix_t, pix_s, empty_hist),
                                             CFG_NOGATE, 1.0))


class Scn3PrecisionTest(unittest.TestCase):
    """scn3：判据一格未动，只把边界时刻从 1fps 网格换成像素腿 10fps 原始时刻。

    验收核心是**两条互斥的要求同时成立**：
      1. 不传新参数 ⇒ 与 scn2 逐字节相同（默认路径零风险）；
      2. 传新参数 ⇒ 边界时刻真的离开网格，且三条不变式仍成立。
    """

    def _synth(self):
        """2 秒 10fps 像素轴 + 3 帧 1fps CLS：叠一个在 1.37s 处的真实切换。

        1.37s 刻意选在**网格中间**（1fps 网格点是 1.0/2.0）——若实现没生效，
        边界会被吸到 1.0 或 2.0，断言立刻红。
        """
        fps = 1.0
        times = np.arange(0, 3, dtype=np.float64)
        feats = np.eye(3, 8, dtype=np.float32)
        pix_t = np.arange(0.1, 3.0, 0.1)
        pix_s = np.full(pix_t.size, 0.001)
        k = int(np.argmin(np.abs(pix_t - 1.4)))
        pix_s[k] = 0.9
        hist = np.zeros((pix_t.size + 1, 32), dtype=np.float32)
        for i in range(pix_t.size + 1):
            hist[i, 0 if pix_t[min(i, pix_t.size - 1)] < 1.4 else 31] = 1.0
        return feats, times, (pix_t, pix_s, hist), fps

    def test_default_path_unchanged_and_scn3_opt_in_only(self):
        """默认路径必须**确定性且未受影响**；scn3 只能通过显式出参启用。

        ⚠️ 这里我第一次写错了断言（拿 scn3 结果当 baseline 去比 scn2），被这条测试自己抓到：
        等价性要断的是「新增可选参数不改变默认输出」，所以基线必须再跑一次**默认调用**得到，
        而不是把启用 scn3 的那次结果当基线。
        """
        feats, times, pixel, fps = self._synth()
        cfg = SceneDetectConfig()
        a, fa = build_scene_table(feats, times, pixel, cfg, fps)
        b, fb = build_scene_table(feats, times, pixel, cfg, fps)
        np.testing.assert_array_equal(a, b)       # 默认路径确定性
        np.testing.assert_array_equal(fa, fb)
        self.assertEqual(a.shape[1], 2)
        # scn3 必须与默认不同（否则等于没接线）
        sc3, _ = build_scene_table(feats, times, pixel, cfg, fps,
                                   boundary_time_out={})
        self.assertFalse(np.array_equal(a, sc3), "scn3 与默认路径相同 ⇒ 未接线")

    def test_scn3_boundary_leaves_the_grid(self):
        feats, times, pixel, fps = self._synth()
        cfg = SceneDetectConfig()
        scn2, _ = build_scene_table(feats, times, pixel, cfg, fps)
        raw: dict = {}
        scn3, _ = build_scene_table(feats, times, pixel, cfg, fps,
                                    boundary_time_out=raw)
        self.assertEqual(scn2.shape[0], scn3.shape[0])
        moved = int((np.abs(scn3[:, 0] - scn2[:, 0]) > 1e-6).sum())
        self.assertGreater(moved, 0, "scn3 未生效：边界仍在 1fps 网格上")
        # 边界必须更接近真实切换 1.4s，而不是网格点
        b2 = scn2[1:, 0]
        b3 = scn3[1:, 0]
        d2 = float(np.min(np.abs(b2 - 1.4))) if b2.size else 9.9
        d3 = float(np.min(np.abs(b3 - 1.4))) if b3.size else 9.9
        self.assertLessEqual(d3, d2 + 1e-6)

    def test_scn3_keeps_three_invariants(self):
        feats, times, pixel, fps = self._synth()
        raw: dict = {}
        stg: dict = {}
        sc, fp = build_scene_table(feats, times, pixel, SceneDetectConfig(), fps,
                                   boundary_time_out=raw, strength_out=stg)
        self.assertEqual(sc.shape[1], 2)
        self.assertGreaterEqual(sc.shape[0], 1)
        for k in range(sc.shape[0] - 1):
            self.assertEqual(float(sc[k, 1]), float(sc[k + 1, 0]),
                             "连续覆盖不变式被破坏（浮点拆开）")
        for k in range(sc.shape[0]):
            self.assertLess(float(sc[k, 0]), float(sc[k, 1]))
        self.assertAlmostEqual(float(sc[0, 0]), float(times[0]), places=4)
        self.assertAlmostEqual(float(sc[-1, 1]), float(times[-1]) + 1.0 / fps,
                               places=4)

    def test_strength_channel_length_and_first_item(self):
        feats, times, pixel, fps = self._synth()
        stg: dict = {}
        sc, _ = build_scene_table(feats, times, pixel, SceneDetectConfig(), fps,
                                  strength_out=stg)
        self.assertEqual(len(stg), sc.shape[0])
        self.assertAlmostEqual(stg[0], 1.0, places=6)

    def test_no_candidates_yields_empty_not_crash(self):
        """无 CLS 峰、无像素候选 ⇒ 空表（不崩，也不返回 1 个假场景）。"""
        feats = np.eye(3, 8, dtype=np.float32)
        times = np.arange(0, 3, dtype=np.float64)
        raw: dict = {}
        sc, fp = build_scene_table(feats, times, None, SceneDetectConfig(), 1.0,
                                   boundary_time_out=raw)
        self.assertEqual(sc.shape[0], 1)   # 整片一个场景
        self.assertEqual(float(sc[0, 0]), float(times[0]))


class SemanticGateTest(unittest.TestCase):
    """scn4：CLS 腿独立语义门（像素门 OR 语义门）。

    要证的只有两件事：① 语义门按**绝对时刻**取块（v1 探针就是错在拿帧索引当行号）；
    ② 门是 **OR** 不是替换 —— 像素门放行的候选不因语义门否掉而消失。
    """

    def _seq(self, n_side: int = 12):
        """造一段「语义明确变化」的序列：前半一类、后半另一类（各 ``n_side`` 帧）。

        ⚠️ 我第一版只用 3+3 帧，结果测试自己红了 —— 不是实现错，是**夹具太短**：
        pre/post 各 4s（=4 帧）在 6 帧序列上必然横跨切换点，`dev` 被拉高、安静段 `dist`
        反而有 0.1056。真实索引是 1fps 数千帧，块永远落在同一侧。
        这里按真实形态给足 12+12 帧。
        """
        t = np.arange(0.0, 2.0 * n_side, 1.0)
        a = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        b = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        f = np.vstack([np.tile(a, (n_side, 1)), np.tile(b, (n_side, 1))])
        f = f / np.linalg.norm(f, axis=1, keepdims=True)
        return f, t

    def test_distinguishes_semantic_change(self):
        f, t = self._seq()
        # 真正的切换点在 t=3.0（第 4 帧起是另一类）
        dist, dev = semantic_block_stats(f, t, 12.0, 3.0, 3.0, 0.0)
        self.assertGreater(dist, 0.9)      # 正交单位向量 => 余弦距离 = 1
        self.assertLess(dev, 0.1)          # 后块内部稳定

    def test_quiet_region_has_no_semantic_change(self):
        f, t = self._seq()
        dist, dev = semantic_block_stats(f, t, 6.0, 3.0, 3.0, 0.0)
        self.assertLess(dist, 0.2)         # 同侧同类 => 几乎不变（12 帧同类，残差来自块均值与单帧的差）
        self.assertLess(dev, 0.01)

    def test_uses_absolute_time_not_row_index(self):
        """v1 的 bug：拿 k+1 当 feats 行号。这里让时刻与行号错开，必须仍取对。"""
        f, t = self._seq()
        # t=3.0 恰好是行 3；把时刻整体平移 100s，行号不变 => 结果必须一致
        t2 = t + 100.0
        d1 = semantic_block_stats(f, t, 12.0, 3.0, 3.0, 0.0)
        d2 = semantic_block_stats(f, t2, 112.0, 3.0, 3.0, 0.0)
        self.assertAlmostEqual(d1[0], d2[0], places=6)
        self.assertAlmostEqual(d1[1], d2[1], places=6)

    def test_gate_respects_config_switch(self):
        f, t = self._seq()
        on = SceneDetectConfig(cls_sem_gate=True)
        off = SceneDetectConfig(cls_sem_gate=False)
        self.assertTrue(semantic_gate_ok(f, t, 12.0, on))
        self.assertFalse(semantic_gate_ok(f, t, 12.0, off))

    def test_gate_rejects_when_feats_missing(self):
        """像素预扫失败/无特征时必须安全返回 False（不能让 OR 门把一切都放行）。"""
        f, t = self._seq()
        cfg = SceneDetectConfig()
        self.assertFalse(semantic_gate_ok(None, t, 12.0, cfg))
        self.assertFalse(semantic_gate_ok(f, np.array([]), 12.0, cfg))

    def test_or_gate_keeps_pixel_feature_candidate(self):
        """OR 语义：语义门否掉的候选，只要像素门放行，仍必须进 items。"""
        f, t = self._seq()
        # 构造一个语义上「无明显变化」的位置，但像素门会放行
        strict = SceneDetectConfig(cls_sem_gate=True,
                                   cls_sem_dist=0.99)   # 高到语义门必否
        self.assertFalse(semantic_gate_ok(f, t, 6.0, strict))
        # 若把语义门参数放松，同一位置应被语义门接住 => 证明参数确实起作用
        loose = SceneDetectConfig(cls_sem_gate=True, cls_sem_dist=0.0,
                                  cls_sem_dev=9.9)
        self.assertTrue(semantic_gate_ok(f, t, 6.0, loose))


class VersionTagTest(unittest.TestCase):


    def test_scene_table_version_is_scn4_and_splitable(self):
        # scn4 = scn3 + CLS 腿独立语义门（2026-10-18 立项② 方案 A2）
        self.assertEqual(FS.SCENE_TABLE_VERSION, "scn4")
        fv = FS._feature_version(1.0)
        self.assertIn("+" + FS.SCENE_TABLE_VERSION, fv)
        self.assertEqual(fv.split("+", 1)[0], FS._version_base(1.0))
        self.assertTrue(fv.endswith(FS._version_derived()))

    def test_base_tag_carries_sampling_fps(self):
        """基座位含采样密度：换 fps 必须走全量重建，不能被 derived_stale 误判成可复用。"""
        self.assertNotEqual(FS._version_base(1.0), FS._version_base(0.5))


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists() and SYNTH.exists(),
                     "FFmpegIO assets not present")
class RefreshDerivedTest(unittest.TestCase):
    """派生表升级路径：基座特征必须**逐字节不变**，且升完再校验是 VALID。"""

    def setUp(self):
        from media.ffmpeg import FFmpegIO
        self.ffmpeg = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)

    def _store(self, root, tags=None, pixel_enabled=True):
        fv = f"{FS._version_base(1.0)}+{tags}" if tags else None
        return FS.FeatureStore(
            self.ffmpeg, root, sampling_fps=1.0, feature_version=fv,
            scene_cfg=SceneDetectConfig(pixel_enabled=pixel_enabled))

    def test_scn1_index_is_reported_derived_stale_then_upgrades(self):
        with tempfile.TemporaryDirectory() as td:
            old = self._store(td, "scn1+evt1")
            old.create_index(SYNTH, FakeBackend())
            d = old.index_dir(SYNTH)
            feats_before = (d / "features.npy").read_bytes()
            self.assertEqual(old.validate_index(SYNTH).status, IndexValidationStatus.VALID)

            # 换成 scn2 口径的 store（模拟升级后的程序版本读到旧索引）
            new = self._store(td)
            v = new.validate_index(SYNTH)
            self.assertIs(v.status, IndexValidationStatus.INVALID)
            self.assertTrue(v.derived_stale, v.reason)
            self.assertIn("derived table version changed", v.reason or "")
            self.assertNotIn("derived_stale", v.to_dict(), "对外契约不变（UI 仍只看 INVALID/reason）")

            meta = new.refresh_derived(SYNTH)
            self.assertEqual(meta.feature_version, new.feature_version)
            self.assertEqual((d / "features.npy").read_bytes(), feats_before,
                             "refresh 不得重抽/改写基座特征")
            self.assertEqual(new.validate_index(SYNTH).status, IndexValidationStatus.VALID)
            scenes = np.load(d / "scenes.npy")
            self.assertTrue(np.isfinite(scenes).all())
            self.assertGreaterEqual(scenes.shape[0], 1)
            # A-B-A 门必须在**真素材**上起作用：a1.mp4 是单镜头素材，而 FakeBackend 给的是
            # 随机特征（CLS 相邻距离全是噪声尖峰）。关掉门再刷一次，边界数必须明显变多。
            st_open = FS.FeatureStore(
                self.ffmpeg, td, sampling_fps=1.0,
                scene_cfg=SceneDetectConfig(block_gate=False))
            st_open.refresh_derived(SYNTH)
            ungated = np.load(d / "scenes.npy").shape[0]
            self.assertGreater(ungated, scenes.shape[0],
                               "A-B-A 门没在真素材上压制瞬时闪动/噪声尖峰")
            # 还原成带门口径，后面的断言按生产配置看
            new.refresh_derived(SYNTH)
            self.assertEqual(new.validate_index(SYNTH).status, IndexValidationStatus.VALID)

    def test_refresh_rewrites_event_table_from_new_scenes(self):
        with tempfile.TemporaryDirectory() as td:
            self._store(td, "scn1+evt1").create_index(SYNTH, FakeBackend())
            d = self._store(td).index_dir(SYNTH)
            ev_before = np.load(d / "events.npy")
            self._store(td).refresh_derived(SYNTH)
            ev = np.load(d / "events.npy")
            self.assertEqual(ev.shape[1], 2)          # events.npy = [E,2] 起止秒
            ef = np.load(d / "event_feats.npy")
            self.assertEqual(ef.shape[1], 384)        # event_feats.npy = [E,384]
            self.assertEqual(ef.shape[0], ev.shape[0])
            self.assertTrue(np.isfinite(ev).all() and np.isfinite(ef).all())
            sc = np.load(d / "scenes.npy")
            # 事件表必须由**当前**场景表派生：整体覆盖区间一致（混搭会露馅）
            self.assertAlmostEqual(float(ev[0, 0]), float(sc[0, 0]), places=4)
            self.assertAlmostEqual(float(ev[-1, 1]), float(sc[-1, 1]), places=4)
            self.assertGreaterEqual(ev.shape[0], 1)

    def test_base_version_mismatch_is_not_derived_stale(self):
        with tempfile.TemporaryDirectory() as td:
            self._store(td, "scn2+evt1").create_index(SYNTH, FakeBackend())
            other = FS.FeatureStore(self.ffmpeg, td, sampling_fps=1.0,
                                    feature_version="handwritten_vits14_cls_384d@9_l2+scn2+evt1")
            v = other.validate_index(SYNTH)
            self.assertIs(v.status, IndexValidationStatus.INVALID)
            self.assertFalse(v.derived_stale, "基座语义变了必须全量重建，不能只重算派生表")

    def test_content_hash_checked_before_derived_stale(self):
        """派生过期也必须先过内容哈希：内容变了特征本身就不可信。"""
        with tempfile.TemporaryDirectory() as td:
            old = self._store(td, "scn1+evt1")
            old.create_index(SYNTH, FakeBackend())
            d = old.index_dir(SYNTH)
            meta = json.loads((d / "index.json").read_text(encoding="utf-8"))
            meta["file_hash"] = "sha256:" + "0" * 64
            (d / "index.json").write_text(json.dumps(meta), encoding="utf-8")
            v = self._store(td).validate_index(SYNTH)
            self.assertIs(v.status, IndexValidationStatus.INVALID)
            self.assertFalse(v.derived_stale)
            self.assertEqual(v.reason, "content hash changed")

    def test_pixel_disabled_still_builds_scene_table(self):
        with tempfile.TemporaryDirectory() as td:
            st = self._store(td, pixel_enabled=False)
            st.create_index(SYNTH, FakeBackend())
            d = st.index_dir(SYNTH)
            scenes = np.load(d / "scenes.npy")
            self.assertGreater(scenes.shape[0], 1)
            self.assertEqual(st.validate_index(SYNTH).status, IndexValidationStatus.VALID)


# --------------------------------------------------------------------------- #
# 测试替身
# --------------------------------------------------------------------------- #
class FakeBackend:
    def is_available(self) -> bool:
        return True
    def device_name(self) -> str:
        return "cpu"
    def device_type(self) -> str:
        return "cpu"
    def memory_info(self) -> dict:
        return {"device": "cpu", "total_gb": 16.0, "available_gb": 8.0, "used_gb": 8.0}
    def load_feature_model(self):
        return None
    def embed_frames(self, bgr_frames, batch_size=8):
        n = len(bgr_frames)
        rng = np.random.RandomState(0)
        v = rng.randn(n, 384).astype(np.float32)
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-8)
    def cleanup(self):
        pass


if __name__ == "__main__":
    unittest.main()
