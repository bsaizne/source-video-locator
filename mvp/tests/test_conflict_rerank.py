"""conflict_rerank 单测(Phase 24):相邻重叠冲突修复——几何触发 + 内容证据接受。"""
import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SRC.parent))  # mvp 包

from domain import Confidence, ConfidenceLevel, IndexMeta, Result, TimeSpan
from engine.localization.conflict_rerank import (accept_repair, best_free_span,
                                                 find_span_conflicts,
                                                 span_mean_sim)
from engine.feature_store import IndexBundle
from app.locator_service import SourceLocatorService


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


class FindSpanConflictsTest(unittest.TestCase):
    def test_r10_shape_flagged_with_gap_window(self):
        # test3 r10 形态:与编辑序相邻的 next 重叠 1.5s,空隙 (442,447.5) 容纳 2s;
        # mover 须为低分一方(r10 0.858 < r11 0.9404),高分 keeper 不触发
        positions = [(440.0, 442.0), (447.0, 449.0), (447.5, 452.4), (476.0, 478.0)]
        scores = [0.9, 0.858, 0.9404, 0.8]
        got = find_span_conflicts(positions, scores=scores)
        self.assertEqual(len(got), 1)
        idx, window = got[0]
        self.assertEqual(idx, 1)
        self.assertEqual(window, (442.0, 447.5))
        # 不给 scores 时 keeper 也会被几何触发(证据门槛兜底),但 idx=1 总在列
        self.assertIn(1, [i for i, _ in find_span_conflicts(positions)])

    def test_non_adjacent_reuse_not_flagged(self):
        # r6(对)/r8(对) 形态:重叠发生在**非编辑序相邻**段之间 → 不触发(几何可分点)
        positions = [(425.0, 427.0), (434.0, 436.0), (445.0, 447.0),
                     (447.0, 449.0), (434.48, 437.63)]
        self.assertEqual(find_span_conflicts(positions), [])

    def test_wide_mover_excluded(self):
        # 复合蒙太奇宽 span(15s)覆盖相邻 claim 位置是合法现象,不作 mover
        positions = [(419.0, 421.0), (420.0, 435.0), (500.0, 502.0)]
        self.assertEqual(find_span_conflicts(positions, max_mover_width_s=8.0), [])
        # 放宽宽度限制后会触发(证明排除来自宽度门而非无重叠)
        self.assertEqual(find_span_conflicts(positions, max_mover_width_s=20.0)[0][0], 1)

    def test_crossing_claims_skipped(self):
        positions = [(440.0, 460.0), (447.0, 449.0), (445.0, 452.0)]
        self.assertEqual(find_span_conflicts(positions), [])

    def test_gap_too_narrow_skipped(self):
        positions = [(440.0, 446.0), (447.0, 449.0), (447.5, 452.4)]
        self.assertEqual(find_span_conflicts(positions), [])

    def test_unpositioned_neighbors_skipped(self):
        positions = [None, (447.0, 449.0), (447.5, 452.4)]
        self.assertEqual(find_span_conflicts(positions), [])


class BestFreeSpanTest(unittest.TestCase):
    """空隙窗扣除全部 claim 后的无主张子区间重定位(test3-r10 实证形态)。"""

    def _feats(self):
        rng = np.random.RandomState(3)
        feats = _l2(rng.randn(60, 64).astype(np.float32))
        times = np.arange(60, dtype=np.float64)
        return feats, times

    def test_prefers_claim_free_subinterval(self):
        feats, times = self._feats()
        # 真内容在 43-45(r10 真值形态);整窗最优块会被 r5 claim (445,447) 撞掉
        q = _l2(feats[40:43].mean(axis=0, keepdims=True))[0]
        feats[43:46] = q[None, :]
        feats = _l2(feats)
        # 窗 (42,47.5) 内 r5 claim 占 (445,447) → 无主张区 (42,445)/(447,47.5)
        span, sim = best_free_span(q, feats, times, (42.0, 47.5),
                                   [(445.0, 447.0)], 2.0)
        self.assertIsNotNone(span)
        self.assertEqual(span, (43.0, 45.0))
        self.assertGreater(sim, 0.9)

    def test_no_room_returns_none(self):
        feats, times = self._feats()
        q = feats[10].copy()
        span, sim = best_free_span(q, feats, times, (40.0, 50.0),
                                   [(41.0, 49.5)], 2.0)
        self.assertIsNone(span)
        self.assertIsNone(sim)

    def test_tie_breaks_toward_higher_sim(self):
        feats, times = self._feats()
        q = _l2(feats[50:53].mean(axis=0, keepdims=True))[0]
        feats[50:53] = q[None, :]
        feats = _l2(feats)
        span, sim = best_free_span(q, feats, times, (48.0, 55.0), [], 2.0)
        self.assertEqual(span, (50.0, 52.0))


class AcceptRepairTest(unittest.TestCase):
    def test_none_sim_rejected(self):
        self.assertFalse(accept_repair(None, 0.9))
        self.assertFalse(accept_repair(0.9, None))

    def test_alt_below_floor_rejected(self):
        self.assertFalse(accept_repair(0.85, 0.55, alt_min_sim=0.60))

    def test_drop_too_large_rejected(self):
        self.assertFalse(accept_repair(0.90, 0.62, alt_min_sim=0.60, max_drop=0.25))

    def test_accepts_r10_like_case(self):
        # cur 0.81 vs alt 0.69:落差 0.12 ≤ 0.25 → 接受(预研实测形态)
        self.assertTrue(accept_repair(0.81, 0.69, alt_min_sim=0.60, max_drop=0.25))

    def test_alt_better_always_accepts(self):
        self.assertTrue(accept_repair(0.60, 0.95, alt_min_sim=0.60, max_drop=0.0))


class SpanMeanSimTest(unittest.TestCase):
    def test_mean_over_span(self):
        feats = _l2(np.random.RandomState(0).randn(10, 8).astype(np.float32))
        times = np.arange(10, dtype=np.float64)
        q = feats[3].copy()
        s = span_mean_sim(q, feats, times, (2.0, 5.0))
        self.assertIsNotNone(s)
        # span 内含 q 本帧(3s)→ 均值应明显高于全局随机
        self.assertGreater(s, 0.0)

    def test_empty_window_returns_none(self):
        feats = _l2(np.random.RandomState(0).randn(10, 8).astype(np.float32))
        times = np.arange(10, dtype=np.float64)
        self.assertIsNone(span_mean_sim(feats[0], feats, times, (50.0, 60.0)))


class ServiceWiringTest(unittest.TestCase):
    """端到端:_apply_conflict_rerank 在真实 Result 列表上重定位冲突段。"""

    def _make_bundle(self):
        rng = np.random.RandomState(7)
        orig = _l2(rng.randn(120, 384).astype(np.float32))
        times = np.arange(120, dtype=np.float64)  # 1fps
        return IndexBundle(IndexMeta("src", 0, 120.0, "h"), orig, times), orig

    def _result(self, edited, orig_span, score=0.8):
        return Result(edited=TimeSpan(*edited), original=TimeSpan(*orig_span),
                      confidence=Confidence(ConfidenceLevel.HIGH, score))

    def test_conflicting_segment_relocated(self):
        bundle, orig = self._make_bundle()
        # 真位置 = 44-46(空隙内,3 帧同内容,无噪声保证确定性平局取首块);
        # 冲突区 47-49 为低相似噪声(非内容)
        q = _l2(orig[40:43].mean(axis=0, keepdims=True))[0]
        orig[44:47] = q[None, :]
        orig[47:50] = _l2(0.8 * q[None, :] + 0.6 * np.random.RandomState(1)
                          .randn(3, 384).astype(np.float32))
        orig = _l2(orig)
        bundle = IndexBundle(bundle.meta, orig, bundle.times)

        results = [
            self._result((0.0, 2.0), (40.0, 42.0), score=0.9),
            self._result((3.0, 4.5), (47.0, 49.0), score=0.7),  # mover:低分+与 next 重叠
            self._result((5.0, 7.0), (47.5, 52.0), score=0.9),
        ]

        class _Back:
            def embed_frames(self, frames, batch_size=8):
                return q[None, :]

            def device_name(self):
                return "cpu"

        class _Ffmpeg:
            def iter_frames(self, path, fps, *, start=None, end=None,
                            scale=None, meta=None):
                yield (0.0, np.zeros((8, 8, 3), dtype=np.uint8))

        srv = SourceLocatorService(ffmpeg=_Ffmpeg(), backend=_Back())
        srv._apply_conflict_rerank(results, bundle, "edited.mp4",
                                   cfg=srv.config.pipeline)
        r = results[1]
        self.assertEqual((r.original.start, r.original.end), (44.0, 46.0))
        olds = [(s.start, s.end) for s in r.original_segments]
        self.assertIn((47.0, 49.0), olds)                       # 原定位留痕
        self.assertIn("conflict_rerank", r.confidence.reasons)  # 诚实留痕

    def test_low_evidence_alternative_kept(self):
        bundle, orig = self._make_bundle()
        # 空隙(42,47.5)内无实质证据(随机噪声)→ 即便几何冲突也不动
        q = orig[48].copy()
        results = [
            self._result((0.0, 2.0), (40.0, 42.0)),
            self._result((3.0, 4.5), (47.0, 49.0)),
            self._result((5.0, 7.0), (47.5, 52.0)),
        ]

        class _Back:
            def embed_frames(self, frames, batch_size=8):
                return q[None, :]

            def device_name(self):
                return "cpu"

        class _Ffmpeg:
            def iter_frames(self, path, fps, *, start=None, end=None,
                            scale=None, meta=None):
                yield (0.0, np.zeros((8, 8, 3), dtype=np.uint8))

        srv = SourceLocatorService(ffmpeg=_Ffmpeg(), backend=_Back())
        srv._apply_conflict_rerank(results, bundle, "edited.mp4",
                                   cfg=srv.config.pipeline)
        self.assertEqual((results[1].original.start, results[1].original.end),
                         (47.0, 49.0))

    def test_not_in_source_and_failures_are_not_movers(self):
        bundle, orig = self._make_bundle()
        r0 = self._result((0.0, 2.0), (40.0, 42.0))
        r1 = self._result((3.0, 4.5), (47.0, 49.0))
        r1.not_in_source = True
        r2 = self._result((5.0, 7.0), (47.5, 52.0))
        srv = SourceLocatorService()
        srv._apply_conflict_rerank([r0, r1, r2], bundle, "edited.mp4",
                                   cfg=srv.config.pipeline)
        self.assertEqual((r1.original.start, r1.original.end), (47.0, 49.0))


if __name__ == "__main__":
    unittest.main()
