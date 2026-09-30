"""Unit tests for mvp.device.CPUBackend + mvp.engine.feature_store.

Fast by design: FeatureStore is tested against a ``FakeBackend`` (no real DINOv2
inference), so the suite needs torch only for CPUBackend's *cheap* methods.
Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_device_feature_store -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np
import torch

from device import CPUBackend, DeviceBackend
from domain import IndexValidationStatus
from engine.feature_store import FeatureStore

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"


class FakeBackend:
    """Deterministic DeviceBackend stand-in (no model; returns fixed vectors)."""
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


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists() and SYNTH.exists(),
                     "FFmpegIO assets not present")
class FeatureStoreTest(unittest.TestCase):
    def setUp(self):
        from media.ffmpeg import FFmpegIO
        self.ffmpeg = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)

    def test_lifecycle(self):
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td)
            backend = FakeBackend()
            self.assertEqual(store.validate_index(SYNTH).status, IndexValidationStatus.MISSING)
            meta = store.create_index(SYNTH, backend)
            self.assertGreaterEqual(meta.num_frames, 2)
            self.assertEqual(meta.feature_dim, 384)
            self.assertEqual(meta.backend, "cpu")
            self.assertEqual(store.validate_index(SYNTH).status, IndexValidationStatus.VALID)
            bundle = store.load_index(SYNTH)
            self.assertEqual(bundle.features.shape, (meta.num_frames, 384))
            self.assertEqual(bundle.times.shape, (meta.num_frames,))
            self.assertEqual(store.get_metadata(SYNTH).file_hash, meta.file_hash)
            store.invalidate_index(SYNTH)
            self.assertEqual(store.validate_index(SYNTH).status, IndexValidationStatus.MISSING)
            store.delete_index(SYNTH)
            self.assertFalse(store.index_dir(SYNTH).exists())

    def test_feature_version_change_invalidates(self):
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td)
            store.create_index(SYNTH, FakeBackend())
            self.assertEqual(store.validate_index(SYNTH).status, IndexValidationStatus.VALID)
            # 换一个 feature_version -> 判 INVALID（版本变化须触发失效）
            store2 = FeatureStore(self.ffmpeg, td, feature_version="other@0.5_l2")
            self.assertEqual(store2.validate_index(SYNTH).status, IndexValidationStatus.INVALID)

    def test_preprocess_sha_recorded_and_stable(self):
        """A2：新建索引必须写入真实预处理摘要（历史上这字段恒为空串）。"""
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td)
            meta = store.create_index(SYNTH, FakeBackend())
            self.assertTrue(meta.extractor.preprocess_sha, "preprocess_sha must be recorded")
            self.assertEqual(store.validate_index(SYNTH).status, IndexValidationStatus.VALID)
            # 摘要稳定（同口径重复计算必须一致，否则会误判失效）
            self.assertEqual(meta.extractor.preprocess_sha, store.preprocess_sha(384))

    def test_preprocess_change_invalidates(self):
        """预处理口径变了（如 resize 518->384）而 feature_version 没 bump -> 必须 INVALID。"""
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td)
            store.create_index(SYNTH, FakeBackend())
            self._tamper_sha(td, store, "deadbeefdeadbeef")
            v = store.validate_index(SYNTH)
            self.assertEqual(v.status, IndexValidationStatus.INVALID)
            self.assertIn("preprocess", v.reason or "")

    def test_legacy_index_without_sha_backfilled_not_rebuilt(self):
        """字段实装前建的历史索引：放行一次并回填摘要，不触发全量重建。"""
        with tempfile.TemporaryDirectory() as td:
            store = FeatureStore(self.ffmpeg, td)
            store.create_index(SYNTH, FakeBackend())
            self._tamper_sha(td, store, "")
            self.assertEqual(store.validate_index(SYNTH).status, IndexValidationStatus.VALID)
            import json
            d = json.loads((store.index_dir(SYNTH) / "index.json").read_text(encoding="utf-8"))
            self.assertTrue(d["extractor"]["preprocess_sha"],
                            "legacy index should be upgraded in place")
            # 回填后第二次校验仍 VALID（幂等，不反复写盘）
            self.assertEqual(store.validate_index(SYNTH).status, IndexValidationStatus.VALID)

    def _tamper_sha(self, td, store, value):
        import json
        p = store.index_dir(SYNTH) / "index.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["extractor"]["preprocess_sha"] = value
        p.write_text(json.dumps(d), encoding="utf-8")

    def test_probe_fingerprint_tracks_actual_preprocess(self):
        """指纹测的是真实函数行为：换 resize 必须改变摘要（声明式字段做不到这点）。"""
        from unittest.mock import patch

        from device import dinov2_model as dm
        from engine.feature_store.feature_store import preprocess_probe_bytes
        base = preprocess_probe_bytes()
        self.assertEqual(preprocess_probe_bytes(), base)
        real = dm._imagenet_preprocess

        def smaller(frame):           # 模拟 resize 杠杆（518 -> 224）
            import torch
            t = real(frame)
            return torch.nn.functional.interpolate(t, size=(224, 224), mode="bilinear")

        with patch.object(dm, "_imagenet_preprocess", smaller):
            self.assertNotEqual(preprocess_probe_bytes(), base)
        self.assertEqual(preprocess_probe_bytes(), base)   # patch 退出后恢复


class CPUBackendTest(unittest.TestCase):
    def test_cheap_interface_no_model_load(self):
        b = CPUBackend()
        self.assertTrue(b.is_available())
        self.assertEqual(b.device_name(), "cpu")
        self.assertEqual(b.device_type(), "cpu")
        self.assertGreater(b.memory_info()["total_gb"], 0)

    def test_is_device_backend(self):
        # Protocol 一致性：CPUBackend 满足 DeviceBackend
        self.assertIsInstance(CPUBackend(), DeviceBackend)
        self.assertIsInstance(FakeBackend(), DeviceBackend)


if __name__ == "__main__":
    unittest.main(verbosity=2)
