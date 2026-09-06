"""编辑侧持久缓存单测（A4, 2026-09-05）。纯 numpy/临时目录, 无真实视频。

运行: venv python -m unittest mvp.tests.test_edited_cache -v
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.edited_cache import EditedCache, fingerprint


class EditedCacheTest(unittest.TestCase):
    def _mkvideo(self, tmp: Path) -> Path:
        p = tmp / "ed.mp4"
        p.write_bytes(b"0" * 1024)
        return p

    def test_shots_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            c = EditedCache(Path(td) / "ec")
            shots = [{"start": 1.0, "end": 2.5, "card_ratio": 0.1, "card_run_ratio": 0.2,
                      "feats": np.random.rand(3, 384).astype(np.float32),
                      "times": np.array([1.0, 1.5, 2.0])},
                     {"start": 2.5, "end": 4.0, "card_ratio": 0.0, "card_run_ratio": 0.0,
                      "feats": np.random.rand(4, 384).astype(np.float32),
                      "times": np.array([2.5, 3.0, 3.5, 4.0])}]
            c.save_shots("k1", shots)
            got = c.load_shots("k1")
            self.assertEqual(len(got), 2)
            np.testing.assert_array_equal(got[0]["feats"], shots[0]["feats"])
            np.testing.assert_array_equal(got[1]["times"], shots[1]["times"])
            self.assertEqual(got[1]["card_ratio"], 0.0)

    def test_dense_roundtrip_and_incremental(self):
        with tempfile.TemporaryDirectory() as td:
            c = EditedCache(Path(td) / "ec")
            f1, t1 = np.random.rand(5, 384).astype(np.float32), np.arange(5.0)
            c.save_dense("k", c.dense_key(1.0, 2.0), f1, t1)
            f2, t2 = np.random.rand(7, 384).astype(np.float32), np.arange(7.0)
            c.save_dense("k", c.dense_key(3.0, 4.0), f2, t2)  # 不覆盖第一条
            g1 = c.load_dense("k", c.dense_key(1.0, 2.0))
            g2 = c.load_dense("k", c.dense_key(3.0, 4.0))
            self.assertIsNone(c.load_dense("k", c.dense_key(9.0, 9.5)))
            np.testing.assert_array_equal(g1[0], f1)
            np.testing.assert_array_equal(g2[0], f2)

    def test_corrupt_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            c = EditedCache(Path(td) / "ec")
            c.save_shots("k", [{"start": 0.0, "end": 1.0, "card_ratio": 0.0,
                                "card_run_ratio": 0.0,
                                "feats": np.zeros((2, 384), np.float32),
                                "times": np.zeros(2)}])
            p = c._shots_path("k")
            p.write_bytes(b"garbage")
            self.assertIsNone(c.load_shots("k"))
            self.assertIsNone(c.load_shots("missing"))

    def test_fingerprint_sensitivity(self):
        with tempfile.TemporaryDirectory() as td:
            v = self._mkvideo(Path(td))
            k1 = fingerprint(v, "fv1", {"a": 1}, "dml:8")
            self.assertEqual(k1, fingerprint(v, "fv1", {"a": 1}, "dml:8"))
            self.assertNotEqual(k1, fingerprint(v, "fv2", {"a": 1}, "dml:8"))
            self.assertNotEqual(k1, fingerprint(v, "fv1", {"a": 2}, "dml:8"))
            self.assertNotEqual(k1, fingerprint(v, "fv1", {"a": 1}, "dml:1"))
            # 内容变化(size) → 键变化
            v.write_bytes(b"1" * 2048)
            self.assertNotEqual(k1, fingerprint(v, "fv1", {"a": 1}, "dml:8"))


if __name__ == "__main__":
    unittest.main()
