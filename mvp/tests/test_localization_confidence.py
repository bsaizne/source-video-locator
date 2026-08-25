"""Unit tests for mvp.engine.localization + mvp.engine.confidence.

Deterministic: constructed L2-normalized feature arrays, no DINOv2 / real video.
Verifies finloc (longest_run + per-orig max-over-query coverage), montage detection,
and ConfidenceEngine (HIGH / montage-LOW / no-span-LOW). Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_localization_confidence -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from domain import Candidate, ConfidenceLevel, IndexMeta
from engine.candidates import produce_candidates
from engine.confidence import ConfidenceEngine
from engine.feature_store import IndexBundle
from engine.localization import (LocalizationResult, finloc_window, longest_run)
from engine.localization.pipeline import localize_segment

from infrastructure.config import ConfidenceConfig


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


def _continuous_bundle():
    """orig: 100 frames @0.5fps (times 0..198). query = orig[20:30]+noise -> true region [40,58]."""
    rng = np.random.RandomState(0)
    orig = _l2(rng.randn(100, 384).astype(np.float32))
    orig_times = (np.arange(100) * 2.0).astype(np.float32)
    src = orig[20:30]
    query = _l2(src + 1e-3 * rng.randn(10, 384).astype(np.float32))
    q_times = (np.arange(10) * 0.5).astype(np.float32)
    meta = IndexMeta("src", 0, 198.0, "hash")
    bundle = IndexBundle(meta, orig, orig_times)
    return query, q_times, bundle


def _montage_bundle():
    """orig: 100 frames @0.5fps. query = orig[20:24]+noise + orig[45:49]+noise -> two islands, big gap."""
    rng = np.random.RandomState(3)
    orig = _l2(rng.randn(100, 384).astype(np.float32))
    orig_times = (np.arange(100) * 2.0).astype(np.float32)
    query = np.concatenate([orig[20:24], orig[45:49]], axis=0) + 1e-3 * rng.randn(8, 384)
    query = _l2(query.astype(np.float32))
    q_times = (np.arange(8) * 0.5).astype(np.float32)   # second island has same times as first (misaligned) but that's fine for coverage
    meta = IndexMeta("src", 0, 198.0, "hash")
    bundle = IndexBundle(meta, orig, orig_times)
    return query, q_times, bundle


class FinlocTest(unittest.TestCase):
    def test_longest_run(self):
        mask = np.array([False, True, True, True, False, True, False])
        ln, s, e = longest_run(mask)
        self.assertEqual((ln, s, e), (3, 1, 4))
        self.assertEqual(longest_run(np.array([False, False]))[0], 0)

    def test_continuous_span(self):
        q, _, bundle = _continuous_bundle()
        cand = Candidate(40, 58, 18, 0.99, 0.9, 0.9, 40, 10, 1.0, 0.05, 1.5)
        loc = finloc_window(cand, q, bundle.features, bundle.times)
        self.assertIsNotNone(loc.span)
        self.assertFalse(loc.multi_island)
        self.assertGreater(loc.best_cover, 0.8)
        self.assertGreaterEqual(loc.run_len_frames, 8)
        # span 应落在真实拷贝区 [40,58] 附近
        tr0, tr1 = loc.span
        self.assertGreaterEqual(tr0, 38.0)
        self.assertLessEqual(tr1, 60.0)
        self.assertGreaterEqual(loc.span_stability, 0.8)

    def test_montage_multi_island(self):
        q, _, bundle = _montage_bundle()
        cand = Candidate(40, 98, 58, 0.99, 0.9, 0.8, 40, 8, 1.0, 0.1, 1.0)
        loc = finloc_window(cand, q, bundle.features, bundle.times)
        self.assertTrue(loc.multi_island, "two islands with a large gap should flag multi_island")
        self.assertGreaterEqual(loc.significant_runs, 2)
        self.assertGreaterEqual(loc.largest_gap_s, 5.0)
        self.assertLess(loc.coverage_quality, 0.9)   # 分岛 => 单峰集中度下降

    def test_no_span_when_window_out_of_range(self):
        q, _, bundle = _continuous_bundle()
        cand = Candidate(800, 820, 20, 0.5, 0.5, 0.9, 5, 5, 0.5, 0.1, 0.0)
        loc = finloc_window(cand, q, bundle.features, bundle.times)
        self.assertIsNone(loc.span)
        self.assertEqual(loc.best_cover, 0.0)


class ConfidenceTest(unittest.TestCase):
    def test_continuous_high(self):
        q, _, bundle = _continuous_bundle()
        best = Candidate(40, 58, 18, 0.99, 0.9, 0.9, 40, 10, 1.0, 0.05, 1.5)
        competitor = Candidate(100, 110, 10, 0.8, 0.7, 0.8, 20, 5, 0.9, 0.1, 0.5)
        cands = [best, competitor]
        loc = finloc_window(best, q, bundle.features, bundle.times)
        assess = ConfidenceEngine(ConfidenceConfig()).assess(cands, loc, best=best)
        self.assertEqual(assess.confidence.level, ConfidenceLevel.HIGH)
        self.assertFalse(assess.montage_flag)
        self.assertFalse(assess.hard_flags)
        self.assertGreater(assess.confidence.score, 0.7)
        self.assertIn("rank1", assess.confidence.reasons)
        self.assertIn("large_candidate_margin", assess.confidence.reasons)
        self.assertTrue(any("candidate_margin" in r for r in map(str, assess.confidence.reasons)))

    def test_montage_low(self):
        q, _, bundle = _montage_bundle()
        best = Candidate(40, 98, 58, 0.99, 0.9, 0.8, 40, 8, 1.0, 0.1, 1.0)
        cands = [best, Candidate(120, 130, 10, 0.7, 0.6, 0.9, 10, 4, 0.9, 0.05, 1.5)]
        loc = finloc_window(best, q, bundle.features, bundle.times)
        assess = ConfidenceEngine(ConfidenceConfig()).assess(cands, loc, best=best)
        self.assertTrue(assess.montage_flag)
        self.assertEqual(assess.confidence.level, ConfidenceLevel.LOW)
        self.assertIn("montage", assess.hard_flags)
        self.assertIn("possible_montage", assess.confidence.reasons)

    def test_no_span_low(self):
        q, _, bundle = _continuous_bundle()
        best = Candidate(800, 820, 20, 0.5, 0.5, 0.9, 5, 5, 0.5, 0.1, 0.0)
        loc = finloc_window(best, q, bundle.features, bundle.times)
        cands = [best]
        assess = ConfidenceEngine(ConfidenceConfig()).assess(cands, loc, best=best)
        self.assertEqual(assess.confidence.level, ConfidenceLevel.LOW)
        self.assertIn("finloc_unstable", assess.hard_flags)
        self.assertIn("finloc_unstable", assess.confidence.reasons)

    def test_dark_confusion_penalty_no_high(self):
        # mean_sim 高但 best_cover 低 (暗场景结构性异常) => 不冒 HIGH, 带 reason
        best = Candidate(40, 58, 18, 0.95, 0.8, 0.9, 40, 10, 1.0, 0.05, 1.5)
        loc = _fake_loc(best_cover=0.1, span=(40.0, 58.0), run_len_s=18,
                        run_len_frames=10, span_stability=1.0, multi_island=False)
        cands = [best]
        assess = ConfidenceEngine(ConfidenceConfig()).assess(cands, loc, best=best)
        self.assertNotEqual(assess.confidence.level, ConfidenceLevel.HIGH)
        self.assertIn("dark_scene_semantic_confusion", assess.confidence.reasons)


class LocalizeSegmentTest(unittest.TestCase):
    def test_end_to_end_continuous(self):
        q, q_times, bundle = _continuous_bundle()
        cands = produce_candidates(q, q_times, bundle)
        refined = localize_segment(cands, q, bundle)
        self.assertIsNotNone(refined)
        # best_cover 已回填（候选窗可能比精确匹配段宽，故 >0 即可）
        self.assertGreater(refined.candidate.best_cover, 0.2)
        self.assertFalse(refined.montage_flag)
        # 精确 span 应落在真实拷贝区附近
        ov = max(0.0, min(refined.original.end, 58.0) - max(refined.original.start, 40.0))
        self.assertGreaterEqual(ov / 18.0, 0.6,
                                f"span {refined.original.start}..{refined.original.end} not in copy region")
        self.assertLessEqual(refined.original.start, refined.original.end)
        self.assertIsInstance(refined.confidence.level, ConfidenceLevel)
        self.assertIsInstance(refined.alternatives, list)
        self.assertIsInstance(refined.montage_flag, bool)

    def test_no_candidate_returns_none(self):
        q, _, bundle = _continuous_bundle()
        self.assertIsNone(localize_segment([], q, bundle))


def _fake_loc(best_cover, span, run_len_s, run_len_frames, span_stability, multi_island):
    """构造一个 LocalizationResult 用于隔离 ConfidenceEngine 的确定性用例。"""
    return LocalizationResult(
        span=span, best_cover=best_cover, run_len_s=run_len_s, run_len_frames=run_len_frames,
        num_runs=1, significant_runs=1, largest_gap_s=0.0, span_coverage=1.0,
        coverage_quality=1.0, span_stability=span_stability, multi_island=multi_island,
        window_width=18.0, mean_sim=0.8, peak_sim=0.95, n_query=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
