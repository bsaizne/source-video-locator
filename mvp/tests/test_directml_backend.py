"""Unit tests for mvp.device.DirectMLBackend + backend resolver.

分两类（§11）：
  A. 普通环境测试——没有 DirectML 也能跑：resolver 的 CPU 路径、能力探测返回结构、
     探测失败时自动 fallback CPU、DirectML 不破坏 CPU MVP。
  B. AMD 实机测试——仅当本机有 ``DmlExecutionProvider`` + ONNX 资产时执行：推理成功、
     shape/dtype/L2 norm/correctness vs CPUBackend、FeatureStore 完整兼容。

无 AMD GPU 的机器对 B 类自动 skip，不会失败。运行：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_directml_backend -v
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

import device as dev
from device import CPUBackend, DirectMLBackend, DeviceBackend, directml_available, resolve_backend
from engine.feature_store import FeatureStore

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"

DML_OK, DML_REASON = directml_available()


def _bgrs(n: int, seed: int = 0) -> list[np.ndarray]:
    rng = np.random.RandomState(seed)
    return [rng.randint(0, 256, (480, 640, 3), dtype=np.uint8) for _ in range(n)]


# --------------------------------------------------------------------------- #
# A. 环境无关：resolver / fallback / probe
# --------------------------------------------------------------------------- #
class ResolverFallbackTest(unittest.TestCase):
    def test_cpu_requested_always_returns_cpu(self):
        be = resolve_backend("cpu")
        self.assertEqual(be.device_type(), "cpu")
        self.assertIsInstance(be, CPUBackend)

    def test_probe_returns_bool_reason_tuple(self):
        ok, reason = directml_available()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(reason, str)

    def test_auto_and_directml_fallback_to_cpu_when_unavailable(self):
        # 模拟"无 DirectML"环境 -> 必须自动 CPU fallback，不能让 AMD 支持破坏 CPU MVP
        with patch.object(dev, "directml_available", return_value=(False, "simulated-unavailable")):
            b_auto = resolve_backend("auto")
            self.assertEqual(b_auto.device_type(), "cpu")
            self.assertIsInstance(b_auto, CPUBackend)
            b_dml = resolve_backend("directml")
            self.assertEqual(b_dml.device_type(), "cpu")
            self.assertIsInstance(b_dml, CPUBackend)

    def test_provider_init_failure_falls_back_to_cpu(self):
        # 即使探测通过，DirectMLBackend 构造失败也必须 fallback（§7 情形 4）
        with patch.object(dev, "directml_available", return_value=(True, "ok")), \
                patch.object(dev, "DirectMLBackend", side_effect=dev.DeviceError("boom")):
            be = resolve_backend("auto")
            self.assertEqual(be.device_type(), "cpu")

    def test_directml_backend_importable_even_without_gpu(self):
        self.assertTrue(callable(DirectMLBackend))

    def test_protocol_conformance_if_available(self):
        if DML_OK:
            self.assertIsInstance(DirectMLBackend(), DeviceBackend)


# --------------------------------------------------------------------------- #
# B. AMD 实机：推理 + 正确性 + FeatureStore 兼容
# --------------------------------------------------------------------------- #
@unittest.skipUnless(DML_OK, f"DirectML not available on this machine: {DML_REASON}")
class DirectMLInferenceTest(unittest.TestCase):
    def setUp(self):
        self.be = DirectMLBackend()

    def test_interface(self):
        self.assertEqual(self.be.device_type(), "amd")
        self.assertEqual(self.be.device_name(), "directml")
        self.assertTrue(self.be.is_available())
        self.assertGreater(self.be.memory_info()["total_gb"], 0)

    def test_embed_shape_dtype_norm_finite(self):
        frames = _bgrs(12)
        out = self.be.embed_frames(frames, batch_size=8)
        self.assertEqual(out.shape, (12, 384))
        self.assertEqual(out.dtype, np.float32)
        norms = np.linalg.norm(out, axis=1)
        self.assertAlmostEqual(float(norms.min()), 1.0, places=4)
        self.assertAlmostEqual(float(norms.max()), 1.0, places=4)
        self.assertTrue(bool(np.all(np.isfinite(out))))

    def test_correctness_vs_cpubackend(self):
        """以 POC 已测 cos≈0.999996 为参考；偏差明显即报警（§6）。"""
        frames = _bgrs(8)
        cpu_out = CPUBackend().embed_frames(frames, batch_size=8)
        dml_out = self.be.embed_frames(frames, batch_size=8)
        self.assertEqual(cpu_out.shape, dml_out.shape)
        self.assertEqual(cpu_out.dtype, dml_out.dtype)
        cn = cpu_out / np.maximum(np.linalg.norm(cpu_out, axis=1, keepdims=True), 1e-8)
        dn = dml_out / np.maximum(np.linalg.norm(dml_out, axis=1, keepdims=True), 1e-8)
        cos_row = np.sum(cn * dn, axis=1)
        self.assertGreater(float(cos_row.min()), 0.999, "DML embedding diverges from CPU")
        self.assertLess(float(np.max(np.abs(cpu_out - dml_out))), 1e-2,
                        "DML max abs diff vs CPU beyond reference range")


@unittest.skipUnless(DML_OK and FFMPEG.exists() and FFPROBE.exists() and SYNTH.exists(),
                     "DirectML or FFmpeg assets not present")
class DirectMLFeatureStoreCompatTest(unittest.TestCase):
    def test_create_load_validate(self):
        """§9：DirectMLBackend 生成的 [N,384] 特征可被 FeatureStore create/load/validate 处理。"""
        from media.ffmpeg import FFmpegIO
        with tempfile.TemporaryDirectory() as td:
            ff = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)
            store = FeatureStore(ff, td)
            meta = store.create_index(SYNTH, DirectMLBackend())
            self.assertEqual(meta.feature_dim, 384)
            self.assertEqual(meta.backend, "directml")
            self.assertEqual(store.validate_index(SYNTH).status.value, "VALID")
            bundle = store.load_index(SYNTH)
            self.assertEqual(bundle.features.shape, (meta.num_frames, 384))
            # 确认 backend 变化不触发失效（§10：只有 feature 语义/版本变化才 invalid）
            store.invalidate_index(SYNTH)
            self.assertFalse(store.index_dir(SYNTH).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
