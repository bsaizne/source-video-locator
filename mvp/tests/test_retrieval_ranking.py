"""Unit tests for mvp.engine.retrieval / clustering / ranking / candidates.

Deterministic: uses constructed L2-normalized feature arrays with an unambiguous
copied region, so the correct candidate MUST win — no DINOv2 / real video needed.
Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_retrieval_ranking -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from domain import Candidate, TimeSpan
from engine.candidates import produce_candidates
from engine.clustering import build_candidates, cluster_continuous
from engine.common import cosine_similarity
from engine.feature_store import IndexBundle
from engine.ranking import rank_candidates, v2_score
from engine.retrieval import Hits, retrieve_hits

from domain import IndexMeta


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


def _scenario():
    """orig: 100 frames @0.5fps (2s/frame). query: 10 frames @2fps copied from
    orig frames [20:30] with a little noise -> the true region is orig times
    [40,58]. Returns (ed_feats, ed_times, bundle)."""
    rng = np.random.RandomState(0)
    orig = _l2(rng.randn(100, 384).astype(np.float32))
    orig_times = (np.arange(100) * 2.0).astype(np.float32)          # 0..198
    src = orig[20:30]                                               # true copy source
    query = _l2(src + 1e-3 * rng.randn(10, 384).astype(np.float32))
    q_times = (np.arange(10) * 0.5).astype(np.float32)              # 0..4.5
    meta = IndexMeta("src", 0, 198.0, "hash")
    bundle = IndexBundle(meta, orig, orig_times)
    return query, q_times, bundle


class RetrievalTest(unittest.TestCase):
    def test_hits_shape_and_alignment(self):
        query, q_times, bundle = _scenario()
        hits = retrieve_hits(query, q_times, bundle.features, bundle.times, top_k=5)
        self.assertEqual(hits.nq, 10)
        self.assertEqual(len(hits.ed_t), 10 * 5)
        self.assertEqual(len(hits.orig_t), 10 * 5)
        self.assertEqual(len(hits.sims), 10 * 5)
        # 全局最佳命中必须落在真实拷贝区 [40,58]（orig 帧 20:30 @2s/帧）
        best_i = int(hits.sims.argmax())
        self.assertTrue(40.0 <= hits.orig_t[best_i] <= 58.0,
                        f"best hit at {hits.orig_t[best_i]:.1f}s not in copy region")
        self.assertGreater(hits.sims.max(), 0.95)

    def test_cosine_normalized(self):
        query, _, bundle = _scenario()
        s = cosine_similarity(query, bundle.features)
        self.assertEqual(s.shape, (10, 100))
        self.assertLessEqual(s.max(), 1.0 + 1e-6)


class ClusteringTest(unittest.TestCase):
    def test_returns_true_region(self):
        query, q_times, bundle = _scenario()
        hits = retrieve_hits(query, q_times, bundle.features, bundle.times, top_k=5)
        cands = build_candidates(hits)
        self.assertGreaterEqual(len(cands), 1)
        top = cands[0]
        # 候选窗应覆盖真实拷贝区 [40,58]（orig 帧 20:30 @2s/帧）的大部分
        ov = max(0.0, min(58.0, top.end) - max(40.0, top.start))
        self.assertGreaterEqual(ov / 18.0, 0.6, f"top candidate covers only {ov/18.0:.2f}")
        self.assertGreaterEqual(top.n_reps, 8)   # 覆盖了大部分 edited 查询帧


class RankingTest(unittest.TestCase):
    def test_v2_score_formula(self):
        c = Candidate(0, 10, 10, 0.9, 0.9, 0.8, 20, 5, 1.0, 0.1, 0.0)
        s = v2_score(c, alpha=0.5)
        base = 0.9 * np.sqrt(20) * (0.5 + 0.5 * 0.8)
        self.assertAlmostEqual(s, base * (5 ** 0.5), places=4)

    def test_rank_sorts_desc(self):
        cands = [Candidate(0, 5, 5, 0.9, 0.9, 0.8, 10, 3, 1.0, 0.1, 0.0, 0, 1),
                 Candidate(0, 5, 5, 0.8, 0.8, 0.7, 8, 2, 0.9, 0.1, 0.0, 0, 1)]
        ranked = rank_candidates(cands, 0.5)
        self.assertGreaterEqual(ranked[0].rank_score, ranked[1].rank_score)
        self.assertTrue(all(c.rank_score > 0 for c in ranked))


class PipelineTest(unittest.TestCase):
    def test_top_candidate_is_true_region(self):
        query, q_times, bundle = _scenario()
        cands = produce_candidates(query, q_times, bundle)
        self.assertGreaterEqual(len(cands), 1)
        top = cands[0]
        # 语义明确的场景下，top 候选应覆盖真实拷贝区且 rank_score 最高
        ov = max(0.0, min(58.0, top.end) - max(40.0, top.start))
        self.assertGreaterEqual(ov / 18.0, 0.6, f"top candidate covers only {ov/18.0:.2f}")
        self.assertEqual(top.rank_score, max(c.rank_score for c in cands))

    def test_returns_domain_candidate(self):
        query, q_times, bundle = _scenario()
        for c in produce_candidates(query, q_times, bundle):
            self.assertIsInstance(c, Candidate)
            self.assertIsInstance(c.rank_score, float)


if __name__ == "__main__":
    unittest.main(verbosity=2)
