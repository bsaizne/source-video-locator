"""Phase 21 场景指纹召回扩展层单测:场景表生命周期 + 证据扩池语义。

覆盖(交接执行单 ④):
- FeatureStore 索引 build 落盘 scenes.npy/scene_feats.npy,validate 纳入场景表存在性;
- 扩池把真值场景并入证据集(帧级 argmax 全落在错误场景时,真值场景经场景指纹救回);
- 开关关闭 → 与无场景表基线零变化;
- 场景表缺失 → 优雅降级(不崩,行为等同关闭);
- 扩池帧数上限 scene_max_expand_frames 生效。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_scene_recall -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from dataclasses import fields as dc_fields
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


def _scene_bundle(*, with_scenes: bool):
    """200 帧 @1fps 索引;frames 150-159=w(错误高相似),40-59=t(真值场景,查询均值中等相似)。

    查询 = L2(0.7w+0.5t) 重复 6 帧 → 帧级 argmax 全落 w 场景(sim .81 > .58),
    场景指纹 top-5 含 t 场景 → 扩池应把 [40,60) 并入证据集。
    """
    rng = np.random.RandomState(7)
    orig = _l2(rng.randn(200, 384).astype(np.float32))
    w = _l2(rng.randn(1, 384).astype(np.float32))[0]
    t = _l2(rng.randn(1, 384).astype(np.float32))[0]
    orig[150:160] = w
    orig[40:60] = t
    qv = _l2((0.7 * w + 0.5 * t).astype(np.float32)[None, :])[0]
    query = np.vstack([qv for _ in range(6)])
    q_times = (np.arange(6) * 0.5).astype(np.float32)
    times = np.arange(200, dtype=np.float32)
    meta = IndexMeta("src", 0, 200.0, "hash")
    scenes = scene_feats = None
    if with_scenes:
        bounds = [0, 40, 60, 150, 160, 200]
        scenes = np.array([[float(times[a]), float(times[b - 1]) + 1.0]
                           for a, b in zip(bounds[:-1], bounds[1:])], dtype=np.float32)
        scene_feats = _l2(np.vstack([orig[a:b].mean(axis=0)
                                     for a, b in zip(bounds[:-1], bounds[1:])]))
    return (IndexBundle(meta, orig.astype(np.float32), times, scenes=scenes,
                        scene_feats=scene_feats),
            query.astype(np.float32), q_times)


def _spans(ev):
    """全部定位 span(帧级 spans + 场景扩池 scene_spans)。"""
    out = [s.original_span for s in ev.spans if s.original_span is not None]
    out += [s.original_span for s in ev.scene_spans if s.original_span is not None]
    return out


def _overlaps(spans, a, b, frac=0.5):
    for s0, s1 in spans:
        inter = max(0.0, min(s1, b) - max(s0, a))
        if inter / (b - a) >= frac:
            return True
    return False


class SceneExpansionTest(unittest.TestCase):
    """证据扩池语义(纯合成,无 IO)。"""

    def test_expansion_recovers_true_scene(self):
        """扩展集含真值:帧级 argmax 全错时,真值场景经场景指纹扩池进入证据集(场景 span)。

        帧级为主断言:帧级主定位(错误场景)不变、mode 不因扩池从 clean 翻成 montage、
        置信诊断字段(purity 来源 spans)不含场景 span。
        """
        bundle, q, qt = _scene_bundle(with_scenes=True)
        ev = EvidenceLocalizer().localize(q, qt, bundle)
        self.assertTrue(_overlaps(_spans(ev), 40.0, 60.0),
                        f"true scene [40,60) not in evidence spans: {_spans(ev)}")
        # 帧级主定位仍是 argmax 错误场景,不被场景噪声翻车
        self.assertEqual(ev.mode, "clean")
        self.assertTrue(_overlaps([ev.primary.original_span], 150.0, 160.0))
        self.assertFalse(_overlaps([s.original_span for s in ev.spans], 40.0, 60.0))
        self.assertTrue(_overlaps([s.original_span for s in ev.scene_spans], 40.0, 60.0))

    def test_disabled_matches_no_scene_table_baseline(self):
        """开关关闭 → 与无场景表基线逐字段零变化。"""
        bundle, q, qt = _scene_bundle(with_scenes=True)
        bare, _, _ = _scene_bundle(with_scenes=False)
        ev_off = EvidenceLocalizer(scene_recall_enabled=False).localize(q, qt, bundle)
        ev_base = EvidenceLocalizer().localize(q, qt, bare)
        self.assertEqual(ev_off.mode, ev_base.mode)
        self.assertEqual(ev_off.n_clusters, ev_base.n_clusters)
        self.assertEqual(len(ev_off.spans), len(ev_base.spans))
        self.assertEqual(ev_off.scene_spans, ev_base.scene_spans)
        for a, b in zip(ev_off.spans, ev_base.spans):
            self.assertEqual(a.original_span, b.original_span)
            self.assertEqual(a.cover, b.cover)
            self.assertEqual(a.best_sim, b.best_sim)
            self.assertEqual(a.cluster_frames, b.cluster_frames)
        self.assertEqual(ev_off.evidence_qcov, ev_base.evidence_qcov)

    def test_missing_scene_table_degrades(self):
        """场景表缺失 → 优雅降级(不崩,等同关闭,无扩池 span)。"""
        bundle, q, qt = _scene_bundle(with_scenes=False)
        ev = EvidenceLocalizer().localize(q, qt, bundle)
        self.assertFalse(_overlaps(_spans(ev), 40.0, 60.0))
        off = EvidenceLocalizer(scene_recall_enabled=False).localize(q, qt, bundle)
        self.assertEqual(ev.mode, off.mode)
        self.assertEqual(_spans(ev), _spans(off))

    def test_scene_shape_mismatch_degrades(self):
        """scenes 与 scene_feats 行数不一致 → 视为无场景表,降级不崩。"""
        bundle, q, qt = _scene_bundle(with_scenes=True)
        bad = IndexBundle(bundle.meta, bundle.features, bundle.times,
                          scenes=bundle.scenes, scene_feats=bundle.scene_feats[:-1])
        ev = EvidenceLocalizer().localize(q, qt, bad)
        self.assertFalse(_overlaps(_spans(ev), 40.0, 60.0))

    def test_expand_budget_cap(self):
        """scene_max_expand_frames 上限生效:超大场景扩池条目数不超过上限。"""
        bundle, q, qt = _scene_bundle(with_scenes=True)
        ev = EvidenceLocalizer(scene_max_expand_frames=8).localize(q, qt, bundle)
        true_spans = [s for s in ev.spans
                      if s.original_span and s.original_span[0] < 60.0 < s.original_span[1]]
        if true_spans:  # 真值簇被扩出时,其池条目数不得超过上限
            for s in true_spans:
                self.assertLessEqual(s.cluster_frames, 8)

    def test_scene_rescue_when_frame_level_empty(self):
        """帧级零证据(逐帧 argmax sim 全部低于门控)时,场景指纹救回为主定位。

        聚合效应:单查询帧与场景帧相似度 0.37<0.40(帧级无簇),但查询均值与
        场景指纹 ≈1.0(场景单元过门)→ clean 模式 + 场景主定位(诚实救回路径)。
        """
        rng = np.random.RandomState(11)
        t = _l2(rng.randn(1, 384).astype(np.float32))[0]
        orig = _l2(rng.randn(120, 384).astype(np.float32))
        orig[80:100] = t
        times = np.arange(120, dtype=np.float32)
        # 单位噪声向量:逐帧 sim(q_i,t)≈0.37<0.40,均值噪声部分抵消 → qf·t≈0.7
        noise = _l2(rng.randn(6, 384).astype(np.float32))
        q = _l2((0.4 * t[None, :] + 1.0 * noise).astype(np.float32))
        # 校验前提:逐帧 argmax sim < min_sim(0.40)
        sim = q @ orig.T
        self.assertLess(float(sim.max(axis=1).mean()), 0.40)
        q_times = (np.arange(6) * 0.5).astype(np.float32)
        bounds = [0, 80, 100, 120]
        scenes = np.array([[float(times[a]), float(times[b - 1]) + 1.0]
                           for a, b in zip(bounds[:-1], bounds[1:])], dtype=np.float32)
        scene_feats = _l2(np.vstack([orig[a:b].mean(axis=0)
                                     for a, b in zip(bounds[:-1], bounds[1:])]))
        meta = IndexMeta("src", 0, 120.0, "hash")
        bundle = IndexBundle(meta, orig.astype(np.float32), times,
                             scenes=scenes, scene_feats=scene_feats)
        ev = EvidenceLocalizer().localize(q, q_times, bundle)
        self.assertEqual(ev.mode, "clean")
        self.assertIsNotNone(ev.primary)
        self.assertTrue(_overlaps([ev.primary.original_span], 80.0, 100.0))
        self.assertEqual(ev.primary.query_frames, 0)   # 纯场景救回,无查询帧 argmax 证据
        self.assertTrue(_overlaps(_spans(ev), 80.0, 100.0))

    def test_qcov_uses_query_frames_only(self):
        """qcov 口径保持查询帧(扩池帧不稀释时序覆盖信号)。"""
        bundle, q, qt = _scene_bundle(with_scenes=True)
        ev = EvidenceLocalizer().localize(q, qt, bundle)
        self.assertLessEqual(ev.evidence_qcov, 1.0 + 1e-9)
        for s in list(ev.spans) + list(ev.scene_spans):
            self.assertLessEqual(s.query_frames, s.cluster_frames)
            self.assertEqual(s.query_frames, len(s.edited_frames))


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists() and SYNTH.exists(),
                     "FFmpegIO assets not present")
class SceneTableLifecycleTest(unittest.TestCase):
    """索引侧场景表生命周期(真实 ffmpeg + FakeBackend,同 feature_store 测试约定)。"""

    def setUp(self):
        from media.ffmpeg import FFmpegIO
        self.ffmpeg = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)

    def test_build_writes_scene_table_and_validates(self):
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td)
            self.assertIn("+scn1", store.feature_version)
            meta = store.create_index(SYNTH, FakeBackend())
            d = store.index_dir(SYNTH)
            self.assertTrue((d / "scenes.npy").exists())
            self.assertTrue((d / "scene_feats.npy").exists())
            scenes = np.load(d / "scenes.npy")
            scene_feats = np.load(d / "scene_feats.npy")
            times = np.load(d / "times.npy")
            self.assertEqual(scenes.ndim, 2)
            self.assertEqual(scenes.shape[1], 2)
            self.assertEqual(scene_feats.shape, (scenes.shape[0], 384))
            self.assertGreaterEqual(scenes.shape[0], 1)
            self.assertAlmostEqual(float(scenes[0, 0]), float(times[0]), places=3)
            self.assertGreaterEqual(float(scenes[-1, 1]), float(times[-1]))
            norms = np.linalg.norm(scene_feats, axis=1)
            self.assertTrue(np.allclose(norms, 1.0, atol=1e-4))
            self.assertEqual(store.validate_index(SYNTH).status, IndexValidationStatus.VALID)
            bundle = store.load_index(SYNTH)
            self.assertIsNotNone(bundle.scenes)
            self.assertIsNotNone(bundle.scene_feats)
            self.assertEqual(bundle.scenes.shape[0], bundle.scene_feats.shape[0])

    def test_scene_table_missing_invalidates(self):
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td)
            store.create_index(SYNTH, FakeBackend())
            d = store.index_dir(SYNTH)
            (d / "scenes.npy").unlink()
            v = store.validate_index(SYNTH)
            self.assertEqual(v.status, IndexValidationStatus.INVALID)
            self.assertEqual(v.reason, "scene table missing")


if __name__ == "__main__":
    unittest.main()
