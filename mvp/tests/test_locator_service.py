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
from engine.feature_store import FeatureStoreError, IndexBundle
from engine.localization.evidence_localize import EvidenceLocalizer, EvidenceResult
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


def _montage_shot(bundle_orig, slot: int) -> ShotSegment:
    """Query = noisy copies of orig[20:30] and orig[70:80] (两个远区 -> 蒙太奇多段)。"""
    rng = np.random.RandomState(slot + 200)
    a = _l2(bundle_orig[20:30])
    b = _l2(bundle_orig[70:80])
    q = _l2(np.vstack([a, b]) + 1e-3 * rng.randn(20, 384).astype(np.float32))
    qt = (np.arange(20) * 0.5).astype(np.float32)
    return ShotSegment(TimeSpan(0.0, 9.5), q, qt)


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
        # 单答案 = ±1s moment：中心应在正确拷贝区 [40,58]，宽度 ≤2s（覆盖语义变窄）
        center = (r.original.start + r.original.end) / 2
        self.assertGreaterEqual(center, 40.0)
        self.assertLessEqual(center, 58.0)
        self.assertLessEqual(r.original.end - r.original.start, 2.0 + 1e-6)

    # -- 蒙太奇段：多段定位（original_segments + 诚实 LOW + montage_flag） --------- #
    def test_montage_multi_span(self):
        bundle, orig, _ = _continuous_bundle()
        shot = _montage_shot(bundle.features, 0)
        res = self.srv._locate_features([shot], bundle, cfg=self.srv.config.pipeline)
        self.assertEqual(len(res), 1)
        r = res[0]
        self.assertTrue(r.montage_flag)
        self.assertEqual(r.confidence.level, ConfidenceLevel.LOW)   # 蒙太奇=部分命中，诚实降 LOW
        self.assertGreaterEqual(len(r.original_segments), 2)
        spans = sorted((s.start, s.end) for s in r.original_segments)
        self.assertLess(spans[0][1], spans[-1][0])                   # 两子 span 分属两个远区

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
        shots = [_match_shot(bundle.features, 3), _match_shot(bundle.features, 9)]
        calls = {"n": 0}
        real_bound = EvidenceLocalizer().localize   # patch 前捕获真绑定，避免 patch 覆盖自身递归

        def raiser(ed_feats, ed_times, index_bundle, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")   # 第一段失败
            return real_bound(ed_feats, ed_times, index_bundle)

        with patch("app.locator_service.EvidenceLocalizer.localize", side_effect=raiser):
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

    # -- no_evidence -> LOW + reason ------------------------------------- #
    def test_no_candidates(self):
        bundle, orig, _ = _continuous_bundle()
        shots = [_noise_shot(5)]
        with patch("app.locator_service.EvidenceLocalizer.localize",
                   return_value=EvidenceResult(mode="empty")):
            res = self.srv._locate_features(shots, bundle, cfg=self.srv.config.pipeline)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].confidence.level, ConfidenceLevel.LOW)
        self.assertIn("no_evidence", res[0].confidence.reasons)
        self.assertEqual(res[0].failure_reason, "no_evidence")

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
        self.assertGreaterEqual(len(batch.results), 1)   # 更细切分可能拆成多段
        self.assertEqual(batch.original_video, bundle.meta.source_file)
        self.assertEqual(batch.edited_video, str(Path("edited.mp4").resolve()))
        centers = [(r.original.start + r.original.end) / 2 for r in batch.results]
        self.assertTrue(any(40.0 <= c <= 58.0 for c in centers),
                        "some result centers copy region")     # 至少某结果 moment 中心在正确区
        self.assertIsInstance(batch.results[0].confidence.level, ConfidenceLevel)


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


# --------------------------------------------------------------------------- #
# 黑底文字卡守卫(GT v3 n04 迭代):卡片段跳检索 → not_in_source
# --------------------------------------------------------------------------- #
class CardShotNotInSourceTest(unittest.TestCase):
    def _bundle(self):
        rng = np.random.RandomState(0)
        orig = _l2(rng.randn(100, 384).astype(np.float32))
        return IndexBundle(IndexMeta("src", 0, 198.0, "hash"), orig,
                           (np.arange(100) * 2.0).astype(np.float32))

    def _shot(self, card_ratio: float) -> ShotSegment:
        rng = np.random.default_rng(1)
        feats = _l2(rng.standard_normal((4, 384)).astype(np.float32))
        return ShotSegment(span=TimeSpan(122.8, 124.8), feats=feats,
                           times=np.array([122.8, 123.3, 123.8, 124.3], dtype=np.float32),
                           card_ratio=card_ratio)

    def test_card_shot_short_circuits_retrieval(self):
        """卡片段(card_ratio>=阈值)不进检索,直接 not_in_source(LOW)。"""
        svc = SourceLocatorService()
        with patch.object(EvidenceLocalizer, "localize") as mock_loc:
            results = svc._locate_features([self._shot(1.0)], self._bundle(),
                                           cfg=svc.config.pipeline)
        mock_loc.assert_not_called()
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].not_in_source)
        self.assertEqual(results[0].failure_reason, "text_card_not_in_source")
        self.assertEqual(results[0].confidence.level, ConfidenceLevel.LOW)
        self.assertEqual(results[0].original.start, 0.0)  # 不产出误导性定位

    def test_non_card_shot_still_retrieves(self):
        svc = SourceLocatorService()
        with patch.object(EvidenceLocalizer, "localize",
                          return_value=EvidenceResult(mode="empty")) as mock_loc:
            results = svc._locate_features([self._shot(0.0)], self._bundle(),
                                           cfg=svc.config.pipeline)
        mock_loc.assert_called_once()
        self.assertFalse(results[0].not_in_source)

    def test_not_in_source_round_trip_and_legacy_compat(self):
        r = Result(edited=TimeSpan(0.0, 1.0), not_in_source=True)
        d = r.to_dict()
        self.assertTrue(d["not_in_source"])
        self.assertTrue(Result.from_dict(d).not_in_source)
        legacy = {k: v for k, v in d.items() if k != "not_in_source"}
        self.assertFalse(Result.from_dict(legacy).not_in_source)  # 旧 JSON 向后兼容


class ShortShotDenseQueryTest(unittest.TestCase):
    """④ ≤0.5s 超短切(2fps 采样只有 1 帧查询):用 8fps 密帧做查询特征。

    test4 实证:单帧查询 → no_evidence;密帧(≈4 帧)给检索/聚类足够证据。
    """

    def _svc_with_spy(self, dense):
        srv = SourceLocatorService()
        real_localizer = srv._evidence_localizer
        captured = {}

        class _Spy:
            seq_align = real_localizer.seq_align

            def localize(self, feats, times, bundle, *, dense_query=None):
                captured["feats"] = feats
                captured["times"] = times
                captured["dense"] = dense_query
                return real_localizer.localize(feats, times, bundle,
                                               dense_query=dense_query)

        srv._evidence_localizer = _Spy()
        srv._embed_dense_query = lambda shot, edited: dense
        return srv, captured

    def test_single_frame_shot_uses_dense_query(self):
        bundle, orig, _ = _continuous_bundle()
        rng = np.random.RandomState(7)
        q = _l2(orig[20:21] + 1e-3 * rng.randn(1, 384).astype(np.float32))
        qt = np.array([10.0], dtype=np.float32)
        shot = ShotSegment(TimeSpan(10.0, 10.5), q, qt)          # 单帧查询
        dense_feats = _l2(orig[20:24] + 1e-3 * rng.randn(4, 384).astype(np.float32))
        dense = (dense_feats, (np.arange(4) * 0.125 + 10.0).astype(np.float32))
        srv, captured = self._svc_with_spy(dense)
        res = srv._locate_features([shot], bundle, cfg=srv.config.pipeline,
                                   edited="fake.mp4")
        self.assertEqual(captured["feats"].shape[0], 4)          # 密帧替换单帧查询
        self.assertEqual(captured["feats"].shape[1], 384)
        self.assertIs(captured["dense"], dense)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0].edited, TimeSpan(10.0, 10.5))    # 查询替换不改动段本身

    def test_multi_frame_shot_keeps_own_feats(self):
        bundle, orig, _ = _continuous_bundle()
        shot = _match_shot(bundle.features, 0)                   # 10 帧
        dense = (bundle.features[20:24].copy(),
                 (np.arange(4) * 0.125).astype(np.float32))
        srv, captured = self._svc_with_spy(dense)
        srv._locate_features([shot], bundle, cfg=srv.config.pipeline,
                             edited="fake.mp4")
        self.assertEqual(captured["feats"].shape[0], 10)         # 常规段保持自身特征
        self.assertIs(captured["feats"], shot.feats)

    def test_no_evidence_retries_with_dense(self):
        """首次 no_evidence → 用 8fps 密帧重试一次(只影响未定位段)。"""
        bundle, orig, _ = _continuous_bundle()
        shot = _noise_shot(0)
        rng = np.random.RandomState(3)
        dense_feats = _l2(orig[20:32] + 1e-3 * rng.randn(12, 384).astype(np.float32))
        dense = (dense_feats, (np.arange(12) * 0.125).astype(np.float32))
        srv = SourceLocatorService()
        real_localizer = srv._evidence_localizer
        calls = []

        class _Spy:
            seq_align = real_localizer.seq_align

            def localize(self, feats, times, bundle, *, dense_query=None):
                calls.append(feats.shape[0])
                if len(calls) == 1:
                    return EvidenceResult(mode="empty")   # 首次无证据(实证形态)
                return real_localizer.localize(feats, times, bundle, dense_query=dense_query)

        srv._evidence_localizer = _Spy()
        srv._embed_dense_query = lambda s, e: dense
        res = srv._locate_features([shot], bundle, cfg=srv.config.pipeline,
                                   edited="fake.mp4")
        self.assertEqual(calls, [6, 12])         # 首次 2fps 特征 + 密帧重试
        r = res[0]
        self.assertIsNone(r.failure_reason)      # 重试后真定位
        center = (r.original.start + r.original.end) / 2
        self.assertGreaterEqual(center, 40.0)    # 密帧指向拷贝区 [40,58]
        self.assertLessEqual(center, 58.0)


class OutOfScopeMomentTest(unittest.TestCase):
    """锚定原语义（DECISIONS『时序离群定位修复』条目的 Rejected 记录）：
    out-of-scope moment 回退保留原样——三案实证它有时对（test3 r6）有时错
    （test3 r16），cover/sim 强弱不可分（特征上限边界）。错配走结果页手动替换。"""

    def _svc_with_evidence(self, evidence):
        srv = SourceLocatorService()
        real = srv._evidence_localizer

        class _Stub:
            seq_align = None

            def localize(self, feats, times, bundle, *, dense_query=None):
                return evidence

        srv._evidence_localizer = _Stub()
        return srv

    def test_out_of_scope_moment_is_used_as_fallback(self):
        """原语义：无 in-scope moment 时回退用 out-of-scope moment（含已知误配风险）。"""
        from engine.localization.evidence_localize import EvidenceResult, EvidenceSpan
        bundle, orig, _ = _continuous_bundle()
        span = EvidenceSpan(edited_interval=(80.0, 83.0), original_span=(464.0, 481.0),
                            cover=0.638, best_sim=0.611, edited_frames=None, cluster_frames=None)
        ev = EvidenceResult(mode="clean", primary=span, spans=[span], n_clusters=1)
        ev.primary.moments = [type("M", (), {"original_span": (484.5, 486.5),
                                             "mean_sim": 0.9,
                                             "edited_interval": (80.0, 83.0)})()]
        shot = ShotSegment(TimeSpan(80.0, 83.0), orig[464:471].copy(),
                           np.arange(464, 471, dtype=np.float32))
        srv = self._svc_with_evidence(ev)
        res = srv._locate_features([shot], bundle, cfg=srv.config.pipeline)
        center = (res[0].original.start + res[0].original.end) / 2
        self.assertAlmostEqual(center, 485.5, delta=25)   # moment 被采用（原语义）

    def test_in_scope_moment_still_wins(self):
        """in-scope moment 优先于 scene 级回退（不受本轮变更影响）。"""
        from engine.localization.evidence_localize import EvidenceResult, EvidenceSpan
        bundle, orig, _ = _continuous_bundle()
        span = EvidenceSpan(edited_interval=(0.0, 2.0), original_span=(40.0, 58.0),
                            cover=0.9, best_sim=0.9, edited_frames=None, cluster_frames=None)
        ev = EvidenceResult(mode="clean", primary=span, spans=[span], n_clusters=1)
        ev.primary.moments = [type("M", (), {"original_span": (46.0, 48.0),
                                             "mean_sim": 0.9,
                                             "edited_interval": (0.0, 2.0)})()]
        shot = ShotSegment(TimeSpan(0.0, 2.0), orig[20:21].copy(),
                           np.array([0.0], dtype=np.float32))
        srv = self._svc_with_evidence(ev)
        res = srv._locate_features([shot], bundle, cfg=srv.config.pipeline)
        self.assertTrue(res[0].frame_precision)
        center = (res[0].original.start + res[0].original.end) / 2
        self.assertGreaterEqual(center, 40.0)
        self.assertLessEqual(center, 58.0)


