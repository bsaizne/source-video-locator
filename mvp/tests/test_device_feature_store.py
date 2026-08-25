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
