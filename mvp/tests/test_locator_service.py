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

            def grab_frame(self, path, t):
                # shot_split 默认开后 locate 会抓编辑窗帧做切镜探测（2026-10-01 续35）
                return np.zeros((8, 8, 3), dtype=np.uint8)

        srv = SourceLocatorService(ffmpeg=_Ffmpeg(), backend=_Back())
        batch = srv.locate("edited.mp4", "dummy.mkv", index_bundle=bundle)
        self.assertGreaterEqual(len(batch.results), 1)   # 更细切分可能拆成多段
        self.assertEqual(batch.original_video, bundle.meta.source_file)
        self.assertEqual(batch.edited_video, str(Path("edited.mp4").resolve()))
        centers = [(r.original.start + r.original.end) / 2 for r in batch.results]
        self.assertTrue(any(40.0 <= c <= 58.0 for c in centers),
                        "some result centers copy region")     # 至少某结果 moment 中心在正确区
        self.assertIsInstance(batch.results[0].confidence.level, ConfidenceLevel)


class RefineModeTest(unittest.TestCase):
    """快/精双模式（2026-10-02）：``locate(refine=...)`` 逐任务覆盖后处理旋钮。

    快速档（refine=False）必须**不发**「拆分多镜头段」消息（切镜拆分被跳过）；
    默认/显式 True 走 config 默认（开）应看到该消息。patch 精排在假体下因缺
    重排资产自动跳过，不进入断言。
    """

    def _messages(self, **kw):
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

            def grab_frame(self, path, t):
                return np.zeros((8, 8, 3), dtype=np.uint8)

        msgs: list[str] = []
        srv = SourceLocatorService(ffmpeg=_Ffmpeg(), backend=_Back())
        srv.locate("edited.mp4", "dummy.mkv", index_bundle=bundle,
                   on_progress=lambda ev: msgs.append(ev.message), **kw)
        return msgs

    def test_default_runs_shot_split(self):
        self.assertTrue(any("拆分多镜头段" in m for m in self._messages()))

    def test_fast_mode_skips_shot_split(self):
        self.assertFalse(any("拆分多镜头段" in m for m in self._messages(refine=False)))

    def test_explicit_precise_equals_default(self):
        self.assertTrue(any("拆分多镜头段" in m for m in self._messages(refine=True)))


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


class FixChainTickTest(unittest.TestCase):
    """修复链两条重腿必须**逐段**发进度（2026-10-07 续63 补五）。

    旧形态：整腿只有边界一条事件 ⇒ 打包日志实测进度条能静止几分钟
    （10-06 那次：shot_split 18:11:36 → patch_refine 18:20:41 → isc_refine 18:29:55），
    用户观感就是"卡住了"。两条重腿（fast_global / dense_recheck 每段抓密帧+嵌入）
    的循环都在 service 里 ⇒ 加 on_tick 逐段回报。
    """

    @staticmethod
    def _results(n=5):
        out = []
        for i in range(n):
            r = Result(edited=TimeSpan(i * 4.0, i * 4.0 + 2.0),
                       original=TimeSpan(40.0 + i * 5.0, 45.0 + i * 5.0),
                       confidence=Confidence(ConfidenceLevel.HIGH, 0.9))
            out.append(r)
        return out

    @staticmethod
    def _shots(n=5):
        rng = np.random.RandomState(7)
        feats = _l2(rng.randn(n, 6, 384).astype(np.float32))
        times = (np.arange(6) * 0.5).astype(np.float32)
        return [ShotSegment(TimeSpan(i * 4.0, i * 4.0 + 2.5), feats[i], times)
                for i in range(n)]

    def _service(self):
        class _Back:
            def embed_frames(self, frames, batch_size=8):
                return np.zeros((len(frames), 384), dtype=np.float32)

            def device_name(self):
                return "cpu"

        return SourceLocatorService(ffmpeg=_EmptyFFmpeg(), backend=_Back())

    def test_dense_start_recheck_ticks_once_per_result(self):
        srv = self._service()
        seen: list[tuple[int, int]] = []
        srv._apply_dense_start_recheck(self._results(5), self._shots(5), Path("x.mkv"),
                                       cfg=srv.config.pipeline, cancel_token=None,
                                       on_tick=lambda done, total: seen.append((done, total)))
        self.assertEqual([d for d, _ in seen], [0, 1, 2, 3, 4])
        self.assertTrue(all(total == 5 for _, total in seen), seen)

    def test_fast_global_anchor_ticks_once_per_result(self):
        bundle, _orig, _times = _continuous_bundle()
        srv = self._service()
        seen: list[tuple[int, int]] = []
        srv._apply_fast_global_anchor(self._results(4), self._shots(4), bundle, "ed.mp4",
                                      cfg=srv.config.pipeline, cancel_token=None,
                                      on_tick=lambda done, total: seen.append((done, total)))
        self.assertEqual([d for d, _ in seen], [0, 1, 2, 3])
        self.assertTrue(all(total == 4 for _, total in seen), seen)

    def test_text_anchor_ticks_once_per_result(self):
        """第三条重腿（OCR 字牌复核）也要逐段报——实测它能让进度停 4.2 分钟。"""
        class _FakeOcr:
            def ensure(self):
                return True

            def lines(self, frames):
                return []

        srv = self._service()
        srv._ocr_engine = _FakeOcr()
        seen: list[tuple[int, int]] = []
        srv._apply_text_anchor(self._results(4), Path("ed.mp4"), "om.mkv",
                               cfg=srv.config.pipeline, cancel_token=None,
                               on_tick=lambda done, total: seen.append((done, total)))
        self.assertEqual([d for d, _ in seen], [0, 1, 2, 3])
        self.assertTrue(all(total == 4 for _, total in seen), seen)

    def test_legs_still_work_without_a_tick_callback(self):
        """on_tick 是可选参数：不传时两条腿照常跑（生产默认路径不能依赖回调存在）。"""
        bundle, _orig, _times = _continuous_bundle()
        srv = self._service()
        srv._apply_dense_start_recheck(self._results(2), self._shots(2), Path("x.mkv"),
                                       cfg=srv.config.pipeline, cancel_token=None)
        srv._apply_fast_global_anchor(self._results(2), self._shots(2), bundle, "ed.mp4",
                                      cfg=srv.config.pipeline, cancel_token=None)
        class _NoOcr:
            def ensure(self):
                return False

        srv._ocr_engine = _NoOcr()
        srv._apply_text_anchor(self._results(2), Path("ed.mp4"), "om.mkv",
                               cfg=srv.config.pipeline, cancel_token=None)


class LocateLegLoggingTest(unittest.TestCase):
    """腿边界埋点（2026-10-08 续63 补九 ①）：一次 locate 必须留下**每腿一行**的
    ``locate leg=… elapsed=…s units=a->b/48 chain=…s`` 记录，外加链首一行开关汇总。

    为什么要有这条：进度事件此前**完全不落日志**（UI 只在内存里读 progress）⇒ 售后
    只拿到支持档时看不出「进度停在哪条腿」，`mvp/scripts/review_packaged_support_log.py`
    的 C 面把这个观测面缺口登记过（只能靠 patch_refine/isc_refine 这类腿内自带行间接推断）。
    埋点是**观测面**改动，所以这里同时锁「不改行为」：REFINE 的 fix ramp 仍单调推进并到 48。
    还锁「行数不爆炸」：腿内 tick 不落日志（tick 一次真实 locate 可达上百条，会把刚做完的
    支持档降噪直接抵消）。
    """

    LEGS = ("global_anchor", "dense_recheck", "text_anchor", "seq_rerank",
            "temporal_repair", "conflict_rerank", "temporal_ambiguity",
            "consecutive_resolve", "degradation_gate",
            "shot_split", "patch_refine", "isc_refine")

    def _run(self):
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

            def grab_frame(self, path, t):
                return np.zeros((8, 8, 3), dtype=np.uint8)

        srv = SourceLocatorService(ffmpeg=_Ffmpeg(), backend=_Back())
        events: list = []
        with self.assertLogs("app.locator_service", level="INFO") as cm:
            srv.locate("edited.mp4", "dummy.mkv", index_bundle=bundle,
                       on_progress=events.append)
        return cm, events

    def test_one_line_per_leg_with_elapsed_and_units(self):
        import re
        cm, _events = self._run()
        msgs = [r.getMessage() for r in cm.records]
        pat = re.compile(r"^locate leg=(\w+) elapsed=([\d.]+)s units=(\d+)->(\d+)/(\d+) "
                         r"chain=([\d.]+)s$")
        got = [pat.match(m) for m in msgs if m.startswith("locate leg=")]
        self.assertTrue(got, "腿边界埋点一行都没落")
        self.assertEqual([m.group(1) for m in got], list(self.LEGS),
                         "腿顺序/数量必须与 locate 的执行顺序一致")
        # 刻度只增不减、累计耗时只增不减（= 埋点自身口径自洽，售后可直接按行读）
        self.assertEqual([int(m.group(4)) for m in got],
                         sorted(int(m.group(4)) for m in got))
        chains = [float(m.group(6)) for m in got]
        self.assertEqual(chains, sorted(chains))
        # elapsed 必须非负，且各腿相加 ~= 累计（容 0.2s 取整缝）
        self.assertTrue(all(float(m.group(2)) >= 0 for m in got))
        self.assertAlmostEqual(sum(float(m.group(2)) for m in got), chains[-1], delta=0.3)
        self.assertEqual(got[-1].group(5), "48")

    def test_leg_toggles_logged_once_at_chain_start(self):
        cm, _events = self._run()
        starts = [r.getMessage() for r in cm.records
                  if r.getMessage().startswith("locate refine start")]
        self.assertEqual(len(starts), 1, "开关汇总行只能有一条")
        self.assertIn("units=0/48", starts[0])
        legs = starts[0].split("legs=", 1)[1].split(",")
        self.assertEqual(len(legs), 12, "12 条腿的开关状态都要交代（含默认关的）")
        self.assertTrue(all(("on" in kv or "off" in kv) for kv in legs), legs)

    def test_ticks_do_not_pollute_the_log(self):
        """腿内 tick 不落日志：一次 locate 的 `locate leg=` 行数恰等于腿数（12）。"""
        cm, _events = self._run()
        n = sum(1 for r in cm.records if r.getMessage().startswith("locate leg="))
        self.assertEqual(n, len(self.LEGS))

    def test_ramp_behaviour_unchanged_by_the_new_logging(self):
        """埋点**只加日志**：fix ramp 仍按刻度单调推进，终点仍到 48。"""
        _cm, events = self._run()
        fix = [(e.current, e.message) for e in events
               if getattr(e, "phase", "") == "fix"]
        self.assertTrue(fix, "修复链一条进度事件都没有")
        currents = [c for c, _ in fix]
        self.assertEqual(currents, sorted(currents), "ramp 回退了")
        self.assertEqual(currents[-1], 48)

    def test_leg_lines_land_in_the_support_log(self):
        """文件侧：腿行必须真的落进**支持档文件**（售后拿到的就是那份文件）。

        `assertLogs` 只在 logger 上挂 handler，证明不了 formatter/文件 handler 这一层；
        这里走 `configure_logging(log_dir=临时目录)`（= 打包态同一套 handler 栈，续63 补二
        已实测隔离子进程的 INFO 进得到那份文件），跑完读回文件逐条核。
        """
        import logging
        import tempfile
        from infrastructure.logging import configure_logging
        with tempfile.TemporaryDirectory() as td:
            snap = (logging.getLogger().level, list(logging.getLogger().handlers))
            try:
                configure_logging(log_dir=td)
                bundle, orig, _ = _continuous_bundle()
                q = _l2(orig[20:30] + 1e-3 * np.random.RandomState(1).randn(10, 384)
                        .astype(np.float32))

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

                    def grab_frame(self, path, t):
                        return np.zeros((8, 8, 3), dtype=np.uint8)

                srv = SourceLocatorService(ffmpeg=_Ffmpeg(), backend=_Back())
                srv.locate("edited.mp4", "dummy.mkv", index_bundle=bundle)
                for h in logging.getLogger().handlers:
                    h.flush()
                text = (Path(td) / "video_locator.log").read_text(encoding="utf-8")
            finally:
                lvl, handlers = snap
                logging.getLogger().setLevel(lvl)
                for h in list(logging.getLogger().handlers):
                    logging.getLogger().removeHandler(h)
                    h.close()
                for h in handlers:
                    logging.getLogger().addHandler(h)
            leg_lines = [l for l in text.splitlines() if "locate leg=" in l]
            self.assertEqual(len(leg_lines), 12,
                             "支持档里腿行应恰 12 条（一次 locate）：%s" % leg_lines)
            self.assertTrue(all("module=app.locator_service" in l for l in leg_lines),
                            leg_lines[:2])
            self.assertTrue(any("locate refine start" in l for l in text.splitlines()))
            # 字牌腿那条必须把刻度从密集复核的 9 推到 42（= 售后可按刻度还原显示宽度占比）
            self.assertTrue(any("locate leg=text_anchor" in l and "units=9->42/48" in l
                                for l in leg_lines), leg_lines)


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

class GrabGridBatchTest(unittest.TestCase):
    """`_grab_grid_batch`（续50 L1 接线）：旋钮开关 / 接口缺省 / 超片尾回退三条路径。"""

    class _FF:
        def __init__(self, with_grid=True):
            self.calls = []
            if with_grid:
                self.grab_grid_times = self._grid
            self.grab_frames = self._win

        def _grid(self, path, times):
            self.calls.append(("grid", list(times)))
            return {round(float(t), 6): ("grid", float(t)) for t in times}

        def _win(self, path, times):
            self.calls.append(("win", list(times)))
            return {round(float(t), 6): ("win", float(t)) for t in times}

    def _stub(self, grid_on=True, with_grid=True, miss=()):
        from types import SimpleNamespace
        svc = SimpleNamespace()
        svc.config = SimpleNamespace(pipeline=SimpleNamespace(grab_grid_decode=grid_on))
        ff = self._FF(with_grid=with_grid)
        if miss:
            orig = ff.grab_grid_times

            def _g(path, times):
                got = orig(path, times)
                for t in list(got):
                    if float(t) in miss:
                        got.pop(t)
                return got

            ff.grab_grid_times = _g
        svc.ffmpeg = ff
        svc._grab_cache = {}
        svc._grab_frame_cached = lambda p, t: ("single", float(t))
        return svc

    def test_off_uses_window_path(self):
        svc = self._stub(grid_on=False)
        got = SourceLocatorService._grab_grid_batch(svc, "p", [0.0, 2.0, 4.0])
        self.assertEqual(sorted(got), [0.0, 2.0, 4.0])
        self.assertEqual(svc.ffmpeg.calls[0][0], "win")

    def test_on_uses_grid_path_and_caches(self):
        svc = self._stub(grid_on=True)
        got = SourceLocatorService._grab_grid_batch(svc, "p", [10.0, 12.0])
        self.assertEqual(got[10.0], ("grid", 10.0))
        self.assertEqual(svc.ffmpeg.calls[0][0], "grid")
        self.assertEqual(len(svc._grab_cache), 2)
        svc.ffmpeg.calls.clear()
        again = SourceLocatorService._grab_grid_batch(svc, "p", [10.0, 12.0])
        self.assertEqual(svc.ffmpeg.calls, [])          # 二次全命中缓存
        self.assertEqual(again[12.0], ("grid", 12.0))

    def test_missing_interface_falls_back(self):
        svc = self._stub(grid_on=True, with_grid=False)
        SourceLocatorService._grab_grid_batch(svc, "p", [1.0])
        self.assertEqual(svc.ffmpeg.calls[0][0], "win")

    def test_grid_miss_falls_back_to_single(self):
        svc = self._stub(grid_on=True, miss=(2.0,))
        got = SourceLocatorService._grab_grid_batch(svc, "p", [0.0, 2.0])
        self.assertEqual(got[2.0], ("single", 2.0))
        self.assertEqual(got[0.0], ("grid", 0.0))


if __name__ == "__main__":
    unittest.main()

# --- 续50 追加区（放在 main 之后以保证文件尾部追加安全） ---


