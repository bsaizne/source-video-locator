"""Unit tests for mvp.app (SourceLocatorService).

Deterministic: constructed L2-normalized feature arrays + IndexBundle, no DINOv2 /
real video. Verifies orchestration of the frozen pipeline: single / multi segment,
failure isolation (one segment fails -> unresolved + later continue), no-candidate,
progress events, cancellation, empty edited -> ApplicationError, invalid original
index -> IndexError, and Result/ResultBatch persistence round-trips.
Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_locator_service -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np
from unittest.mock import patch

from app import CancellationToken, ProgressStage, SourceLocatorService
from domain import (Confidence, ConfidenceLevel, IndexMeta, Result, ResultBatch,
                    ResultSource, TimeSpan)
from engine.candidates import produce_candidates as _real_produce_candidates
from engine.feature_store import FeatureStoreError, IndexBundle
from engine.segment import ShotSegment
from infrastructure.results_repo import load_results, save_results


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


def _continuous_bundle():
    """orig: 100 frames @0.5fps. query = orig[20:30] -> true region [40,58]."""
    rng = np.random.RandomState(0)
    orig = _l2(rng.randn(100, 384).astype(np.float32))
    orig_times = (np.arange(100) * 2.0).astype(np.float32)
    bundle = IndexBundle(IndexMeta("src", 0, 198.0, "hash"), orig, orig_times)
    return bundle, orig, orig_times


def _match_shot(bundle_orig, slot: int) -> ShotSegment:
    """Shot whose query is a noisy copy of orig[20:30] (true region [40,58])."""
    rng = np.random.RandomState(slot)
    src = bundle_orig[20:30]
    q = _l2(src + 1e-3 * rng.randn(10, 384).astype(np.float32))
    qt = (np.arange(10) * 0.5).astype(np.float32)
    return ShotSegment(TimeSpan(0.0, 4.5), q, qt)


def _noise_shot(slot: int, base: float = 100.0) -> ShotSegment:
    """Shot with random features (no true match -> low conf; wide candidate)."""
    rng = np.random.RandomState(slot + 100)
    q = _l2(rng.randn(6, 384).astype(np.float32))
    qt = (np.arange(6) * 0.5 + base).astype(np.float32)
    return ShotSegment(TimeSpan(base, base + 2.5), q, qt)


class _EmptyFFmpeg:
    "@@no deps: an ffmpeg whose iter_frames yields nothing (for the empty-edited test)."
    def iter_frames(self, path, fps, *, start=None, end=None, scale=None, meta=None):
        yield from ()


class _RaisingStore:
    def validate_index(self, original):
        raise FeatureStoreError("index boom")


class SourceLocatorServiceTest(unittest.TestCase):
    def setUp(self):
        self.srv = SourceLocatorService()

    # -- 正常单 segment ---------------------------------------------------- #
    def test_single_segment(self):
        bundle, orig, _ = _continuous_bundle()
        shot = _match_shot(bundle.features, 0)
        res = self.srv._locate_features([shot], bundle, cfg=self.srv.config.pipeline)
        self.assertEqual(len(res), 1)
        r = res[0]
        self.assertEqual(r.edited, TimeSpan(0.0, 4.5))     # edited = shot.span
        self.assertIsNone(r.failure_reason)
        self.assertEqual(r.source, ResultSource.AUTO)
        self.assertFalse(r.montage_flag)
        self.assertIsInstance(r.alternatives, list)
        self.assertIn(r.confidence.level, (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM,
                                           ConfidenceLevel.LOW))
        # span 应落在真拷贝区 [40,58]
        ov = max(0.0, min(r.original.end, 58.0) - max(r.original.start, 40.0))
        self.assertGreaterEqual(ov / 18.0, 0.5)

    # -- 多 segment：每段一个 Result，按 edited 时间升序 --------------------- #
    def test_multi_segment_ordering(self):
        bundle, orig, _ = _continuous_bundle()
        shots = [_match_shot(bundle.features, 1), _noise_shot(2)]
        res = self.srv._locate_features(shots, bundle, cfg=self.srv.config.pipeline)
        self.assertEqual(len(res), 2)
        self.assertLess(res[0].edited.start, res[1].edited.start)
        # 每段 edited == shot.span
        self.assertEqual(res[0].edited, shots[0].span)
        self.assertEqual(res[1].edited, shots[1].span)

    # -- 一个 segment 失败 -> unresolved，后续继续 --------------------------- #
    def test_segment_failure_isolated(self):
        bundle, orig, _ = _continuous_bundle()
        shots = [_match_shot(bundle.features, 3), _noise_shot(4)]
        calls = {"n": 0}

        def raiser(ed_feats, ed_times, index_bundle, *, cfg=None):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")   # 第一段失败
            return _real_produce_candidates(ed_feats, ed_times, index_bundle, cfg=cfg)

        with patch("app.locator_service.produce_candidates", side_effect=raiser):
            res = self.srv._locate_features(shots, bundle, cfg=self.srv.config.pipeline)
        self.assertEqual(len(res), 2)
        r0, r1 = res[0], res[1]
        self.assertEqual(r0.confidence.level, ConfidenceLevel.LOW)   # 失败段 -> LOW
        self.assertTrue(r0.confidence.reasons[0].startswith("segment_error"))
        self.assertTrue(r0.failure_reason.startswith("segment_error"))
        self.assertEqual(r0.original, TimeSpan(0.0, 0.0))            # 无有效原片区间
        self.assertIsNone(r1.failure_reason)                        # 后续段继续且正常
        self.assertEqual(r1.edited, shots[1].span)                  # 保留段 span，非失败残留
        self.assertEqual(r1.source, ResultSource.AUTO)

    # -- no_candidates -> LOW + reason ------------------------------------- #
    def test_no_candidates(self):
        bundle, orig, _ = _continuous_bundle()
        shots = [_noise_shot(5)]
        with patch("app.locator_service.produce_candidates", return_value=[]):
            res = self.srv._locate_features(shots, bundle, cfg=self.srv.config.pipeline)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].confidence.level, ConfidenceLevel.LOW)
        self.assertIn("no_candidates", res[0].confidence.reasons)
        self.assertEqual(res[0].failure_reason, "no_candidates")

    # -- progress callback 逐阶段 ------------------------------------------- #
    def test_progress_events(self):
        bundle, orig, _ = _continuous_bundle()
        shots = [_match_shot(bundle.features, 6)]
        events = []
        self.srv._locate_features(shots, bundle, cfg=self.srv.config.pipeline,
                                  on_progress=events.append)
        stages = [e.stage for e in events]
        self.assertIn(ProgressStage.CANDIDATE_RETRIEVAL, stages)
        self.assertIn(ProgressStage.LOCALIZATION, stages)
        self.assertIn(ProgressStage.CONFIDENCE, stages)
        # current/total 单调且用 len(shots)
        for e in events:
            if e.total:
                self.assertEqual(e.total, len(shots))

    # -- cancellation 穿透（不落入失败隔离） -------------------------------- #
    def test_cancellation_raises(self):
        bundle, orig, _ = _continuous_bundle()
        shots = [_match_shot(bundle.features, 7)]
        tok = CancellationToken()
        tok.cancel()
        with self.assertRaises(Exception) as ctx:
            self.srv._locate_features(shots, bundle, cfg=self.srv.config.pipeline,
                                      cancel_token=tok)
        self.assertEqual(type(ctx.exception).__name__, "ApplicationError")

    # -- empty edited -> ApplicationError ----------------------------------- #
    def test_empty_edited(self):
        srv = SourceLocatorService(ffmpeg=_EmptyFFmpeg())
        with self.assertRaises(Exception) as ctx:
            srv.analyze_edited_video("nothing.mp4")
        self.assertEqual(type(ctx.exception).__name__, "ApplicationError")

    # -- invalid original index -> IndexError ------------------------------- #
    def test_invalid_index_raises_index_error(self):
        srv = SourceLocatorService()
        srv._store = _RaisingStore()
        with self.assertRaises(Exception) as ctx:
            srv.build_original_index("missing.mkv")
        self.assertEqual(type(ctx.exception).__name__, "IndexError")

    # -- locate(index_bundle=...) 复用路径（UI 入口） ------------------------- #
    def test_locate_index_bundle_reuse(self):
        bundle, orig, _ = _continuous_bundle()
        q = _l2(orig[20:30] + 1e-3 * np.random.RandomState(1).randn(10, 384).astype(np.float32))

        class _Back:
            def embed_frames(self, frames, batch_size=8):
                return q
            def device_name(self):
                return "cpu"

        class _Ffmpeg:
            def iter_frames(self, path, fps, *, start=None, end=None,
                            scale=None, meta=None):
                for i in range(q.shape[0]):
                    yield (i / fps, np.zeros((8, 8, 3), dtype=np.uint8))

        srv = SourceLocatorService(ffmpeg=_Ffmpeg(), backend=_Back())
        batch = srv.locate("edited.mp4", "dummy.mkv", index_bundle=bundle)
        self.assertEqual(len(batch.results), 1)
        self.assertEqual(batch.original_video, bundle.meta.source_file)
        self.assertEqual(batch.edited_video, str(Path("edited.mp4").resolve()))
        r = batch.results[0]
        ov = max(0.0, min(r.original.end, 58.0) - max(r.original.start, 40.0))
        self.assertGreaterEqual(ov / 18.0, 0.5)
        self.assertIsInstance(r.confidence.level, ConfidenceLevel)


class PersistenceTest(unittest.TestCase):
    def test_result_from_dict_roundtrip(self):
        r = Result(edited=TimeSpan(1.0, 2.0), original=TimeSpan(3.0, 4.0),
                   confidence=Confidence(ConfidenceLevel.HIGH, 0.9, ("rank1",)),
                   candidate_rank=1, source=ResultSource.AUTO,
                   montage_flag=True, failure_reason=None)
        self.assertEqual(Result.from_dict(r.to_dict()).to_dict(), r.to_dict())

    def test_manual_override_roundtrip(self):
        auto = Result(edited=TimeSpan(0, 1), original=TimeSpan(2, 3),
                      confidence=Confidence(ConfidenceLevel.HIGH, 0.91, ("rank1",)))
        manual = Result(edited=TimeSpan(0, 1), original=TimeSpan(5, 7),
                        confidence=Confidence(ConfidenceLevel.LOW, 0.4, ()),
                        source=ResultSource.MANUAL, manual_override=True,
                        manual_timestamp="2026-08-25T00:00:00", auto_result=auto)
        self.assertEqual(Result.from_dict(manual.to_dict()).to_dict(), manual.to_dict())

    def test_batch_repo_roundtrip(self):
        batch = ResultBatch(schema_version=1, original_video="o.mkv",
                            edited_video="e.mp4",
                            results=[Result(edited=TimeSpan(0, 2),
                                            original=TimeSpan(40, 58),
                                            confidence=Confidence(ConfidenceLevel.HIGH, 0.9, ("rank1",)))])
        with tempfile.TemporaryDirectory() as td:
            p = save_results(batch, out_dir=td)
            self.assertTrue(p.exists())
            self.assertEqual(p.suffix, ".json")
            loaded = load_results(p)
        self.assertEqual(loaded.to_dict(), batch.to_dict())


if __name__ == "__main__":
    unittest.main(verbosity=2)
