"""Unit tests for mvp.device.MPSBackend + resolver mps 路径。

分两类（同 test_directml_backend §11 约定）：
  A. 普通环境测试——无 MPS 也能跑（Windows）：能力探测结构、非 darwin 平台 mps 偏好
     fallback CPU、batch 上限钳制。
  B. MPS 实机测试——仅当 ``mps_available()`` 时执行（macOS CI）：构造成功、embed
     shape/dtype/L2 norm、batch cap 生效。

运行: venv python -m unittest mvp.tests.test_mps_backend -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

import device as dev
from device import CPUBackend, DeviceError, mps_available, resolve_backend
from device.mps_backend import _cap_batch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # -> mvp


class AClassTests(unittest.TestCase):
    """A 类：任何平台都能跑（不依赖 MPS 硬件）。"""

    def test_mps_available_returns_tuple(self):
        ok, reason = mps_available()
        self.assertIsInstance(ok, bool)
        self.assertIsInstance(reason, str)

    def test_cap_batch_clamps_to_four(self):
        self.assertEqual(_cap_batch(None), 4)
        self.assertEqual(_cap_batch(1), 1)
        self.assertEqual(_cap_batch(4), 4)
        self.assertEqual(_cap_batch(8), 4)     # H3 POC: batch≥8 触发 buffer 限制
        self.assertEqual(_cap_batch(0), 4)

    @unittest.skipIf(mps_available()[0], "MPS present — fallback path not applicable")
    def test_mps_backend_raises_without_mps(self):
        with self.assertRaises(DeviceError):
            dev.MPSBackend(weights_path=self._any_weights())

    @unittest.skipIf(mps_available()[0], "MPS present — fallback path not applicable")
    def test_resolve_mps_falls_back_to_cpu_on_non_darwin(self):
        with patch("sys.platform", "win32"):
            backend = resolve_backend("mps")
        self.assertIsInstance(backend, CPUBackend)

    @unittest.skipIf(not mps_available()[0], "MPS required")
    def test_resolve_mps_prefers_mps_on_darwin(self):
        backend = resolve_backend("mps")
        self.assertEqual(backend.device_type(), "mps")

    # -- helpers ------------------------------------------------------- #

    @staticmethod
    def _any_weights() -> Path:
        """拿一个存在的权重路径（或返回占位路径——仅用于构造失败测试）。"""
        try:
            return dev.resolve_dinov2_weights(None)
        except DeviceError:
            return Path("unused.pth")


class BClassTests(unittest.TestCase):
    """B 类：MPS 实机测试（macOS CI / Apple Silicon 本机）。"""

    @classmethod
    def setUpClass(cls):
        cls.ok, cls.reason = mps_available()
        if not cls.ok:
            raise unittest.SkipTest(f"MPS unavailable: {cls.reason}")

    def _backend(self):
        return dev.MPSBackend(batch_size=4)

    def test_device_type(self):
        be = self._backend()
        self.assertEqual(be.device_type(), "mps")
        self.assertEqual(be.device_name(), "mps")

    def test_embed_frames_shape_and_l2(self):
        be = self._backend()
        frames = [np.random.RandomState(i).randint(0, 255, (32, 32, 3), dtype=np.uint8)
                  for i in range(9)]     # 9 帧 > cap 4, 验证分块
        feats = be.embed_frames(frames)
        self.assertEqual(feats.shape, (9, 384))
        self.assertEqual(feats.dtype, np.float32)
        np.testing.assert_allclose(np.linalg.norm(feats, axis=1), 1.0, rtol=1e-5)

    def test_batch_cap_enforced(self):
        be = self._backend()
        self.assertEqual(be.batch_size, 4)
        self.assertEqual(_cap_batch(64), 4)

    def test_empty_input(self):
        be = self._backend()
        out = be.embed_frames([])
        self.assertEqual(out.shape, (0, 384))


if __name__ == "__main__":
    unittest.main()
