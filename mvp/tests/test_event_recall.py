# -*- coding: utf-8 -*-
"""方向 A 事件单元扩池单测（2026-09-05 用户拍板立项完整阶段, 探针 POSITIVE）。

覆盖:
- FeatureStore 索引 build 落盘 events.npy/event_feats.npy, validate 纳入事件表存在性;
- 事件扩池把真值事件并入证据集(帧级 argmax 全落兄弟机位时, 真值机位经事件指纹救回);
- 开关关闭 → 与无事件表基线零变化;
- 事件表缺失 → 优雅降级(不崩, 行为等同关闭);
- 扩池帧数上限 event_max_expand_frames 生效。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_event_recall -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from domain import IndexMeta, IndexValidationStatus
from engine.feature_store import FeatureStore, IndexBundle
from engine.localization import EvidenceLocalizer

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


class FakeBackend:
    """确定性 DeviceBackend 替身(同 test_device_feature_store 约定)。"""
    def is_available(self): return True
    def device_name(self): return "cpu"
    def device_type(self): return "cpu"
    def memory_info(self): return {"device": "cpu"}
    def load_feature_model(self): return None
    def embed_frames(self, bgr_frames, batch_size=8):
        n = len(bgr_frames)
        v = np.random.RandomState(0).randn(n, 384).astype(np.float32)
        return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-8)
    def cleanup(self): pass


def _event_bundle(*, with_events: bool, with_scenes: bool = True):
    """200 帧 @1fps 索引;场景: [0,40) [40,60)=兄弟A(真值) [60,150) [150,160)=兄弟B(帧级错) [160,200)。

    查询 = L2(0.7*brotherB + 0.5*brotherA) 重复 6 帧 → 帧级 argmax 全落兄弟B场景,
    但兄弟A/B 归并同一事件 → 事件扩池应把兄弟A场景帧并入证据集。
    """
    rng = np.random.RandomState(7)
    orig = _l2(rng.randn(200, 384).astype(np.float32))
    bA = _l2(rng.randn(1, 384).astype(np.float32))[0]
    bB = _l2(rng.randn(1, 384).astype(np.float32))[0]
    orig[40:60] = bA
    orig[150:160] = bB
    qv = _l2((0.7 * bB + 0.5 * bA).astype(np.float32)[None, :])[0]
    query = np.vstack([qv for _ in range(6)])
    q_times = (np.arange(6) * 0.5).astype(np.float32)
    times = np.arange(200, dtype=np.float32)
    meta = IndexMeta("src", 0, 200.0, "hash")
    scenes = scene_feats = None
    events = event_feats = None
    if with_scenes:
        bounds = [0, 40, 60, 150, 160, 200]
        scenes = np.array([[float(times[a]), float(times[b - 1]) + 1.0]
                           for a, b in zip(bounds[:-1], bounds[1:])], dtype=np.float32)
        scene_feats = _l2(np.vstack([orig[a:b].mean(axis=0)
                                     for a, b in zip(bounds[:-1], bounds[1:])]))
        if with_events:
            # 兄弟A(场景1, 40-60)与兄弟B(场景3, 150-160)手工归并为同一事件(事件0),
            # 其余场景(0,2,4)为事件1。事件0指纹=两机位指纹混合(兄弟同事件)。
            events = np.array([[40.0, 161.0], [0.0, 40.0]], dtype=np.float32)
            event_feats = _l2(np.vstack([scene_feats[1] * 0.6 + scene_feats[3] * 0.6,
                                          scene_feats[[0, 2, 4]].mean(axis=0)]))
    return (IndexBundle(meta, orig.astype(np.float32), times, scenes=scenes,
                        scene_feats=scene_feats, events=events, event_feats=event_feats),
            query.astype(np.float32), q_times)


def _spans(ev):
    out = [s.original_span for s in ev.spans if s.original_span is not None]
    out += [s.original_span for s in ev.scene_spans if s.original_span is not None]
    out += [s.original_span for s in ev.event_spans if s.original_span is not None]
    return out


def _overlaps(spans, a, b, frac=0.5):
    for s0, s1 in spans:
        inter = max(0.0, min(s1, b) - max(s0, a))
        if inter / (b - a) >= frac:
            return True
    return False


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists() and SYNTH.exists(),
                     "FFmpegIO assets not present")
class EventTableLifecycleTest(unittest.TestCase):
    """事件表生命周期: build 落盘 + validate 纳入 + 缺失降级(真实 FFmpeg + 合成视频)。"""

    def setUp(self):
        from media.ffmpeg import FFmpegIO
        self.ffmpeg = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)

    def test_build_index_persists_event_table(self):
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td, sampling_fps=1.0)
            meta = store.create_index(SYNTH, FakeBackend())
            d = store.index_dir(SYNTH)
            self.assertTrue((d / "events.npy").exists())
            self.assertTrue((d / "event_feats.npy").exists())
            self.assertIn("evt1", meta.feature_version)
            bundle = store.load_index(SYNTH)
            self.assertIsNotNone(bundle.events)
            self.assertIsNotNone(bundle.event_feats)
            self.assertEqual(store.validate_index(SYNTH).status,
                             IndexValidationStatus.VALID)

    def test_event_table_missing_invalidates(self):
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td, sampling_fps=1.0)
            store.create_index(SYNTH, FakeBackend())
            d = store.index_dir(SYNTH)
            (d / "events.npy").unlink()
            self.assertEqual(store.validate_index(SYNTH).status,
                             IndexValidationStatus.INVALID)

    def test_missing_event_table_graceful_degrade(self):
        bundle, q, qt = _event_bundle(with_events=False)
        ev = EvidenceLocalizer().localize(q, qt, bundle)
        self.assertIn(ev.mode, ("clean", "montage", "empty"))


class EventExpansionTest(unittest.TestCase):
    """事件扩池语义(纯合成, 无 IO)。"""

    def test_event_expansion_recovers_true_brother(self):
        """帧级 argmax 全落兄弟B时, 真值兄弟A场景经场景扩池进入证据集(场景 span)。

        事件扩池 = 事件身份路由(查询均值 vs 事件指纹 top-K → 事件窗内帧作精修窗);
        精修后事件 span 是 finloc 精确 run(span_mode="run", 不 ∪ 事件窗全范围),
        与帧级主定位/场景 span IoU 去重——若 run 与帧级同区则被去重(不重复展示),
        真值救回由场景扩池承担(兄弟A场景指纹命中)。任何保留的事件 span 必须窄
        (不超过事件窗宽度), 不产生粗跨度假命中。
        """
        bundle, q, qt = _event_bundle(with_events=True)
        ev = EvidenceLocalizer(event_top_k=2).localize(q, qt, bundle)
        # 帧级主定位仍是 argmax 兄弟B, 不被扩池噪声翻车
        self.assertEqual(ev.mode, "clean")
        self.assertTrue(_overlaps([ev.primary.original_span], 150.0, 160.0))
        # 真值兄弟A经场景扩池救回(事件身份路由 → 事件窗 → 场景指纹精修)
        self.assertTrue(_overlaps(_spans(ev), 40.0, 60.0),
                        f"true brother A [40,60) not in evidence spans: {_spans(ev)}")
        # 事件 span(若有)必须是精确 run, 宽度受限于事件窗内的 finloc run(≤15s 上限)
        for s in ev.event_spans:
            if s.original_span is not None:
                self.assertLessEqual(s.original_span[1] - s.original_span[0],
                                     15.0 + 1e-3,
                                     f"event span not refined: {s.original_span}")
        # 事件 span 不产生粗跨度(无 100s+ 事件窗跨度)
        for s in ev.event_spans:
            if s.original_span is not None:
                self.assertLess(s.original_span[1] - s.original_span[0], 100.0)

    def test_disabled_matches_no_event_table_baseline(self):
        bundle, q, qt = _event_bundle(with_events=True)
        bare, _, _ = _event_bundle(with_events=False)
        ev_on = EvidenceLocalizer(event_recall_enabled=True).localize(q, qt, bundle)
        ev_off = EvidenceLocalizer(event_recall_enabled=False).localize(q, qt, bundle)
        ev_bare = EvidenceLocalizer(event_recall_enabled=True).localize(q, qt, bare)
        for ev in (ev_off, ev_bare):
            self.assertEqual(ev.mode, ev_on.mode)
            self.assertEqual(len(ev.spans), len(ev_on.spans))
            self.assertEqual(len(ev.event_spans), 0)

    def test_event_expansion_budget(self):
        bundle, q, qt = _event_bundle(with_events=True)
        loc = EvidenceLocalizer(event_top_k=1, event_max_expand_frames=5)
        ev = loc.localize(q, qt, bundle)
        for s in ev.event_spans:
            self.assertLessEqual(s.cluster_frames, 5)


if __name__ == "__main__":
    unittest.main()