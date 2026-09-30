# -*- coding: utf-8 -*-
"""shot_split 单测（2026-09-30 续32 形态4 runtime 化）。

纯函数 + 合成数据（假 grab_frame/embed/lib），不依赖 GPU / 真实索引。
"""
import unittest

import numpy as np

from domain.enums import ConfidenceLevel
from domain.models import Confidence, Result, TimeSpan
from engine.localization.shot_split import detect_shots, split_results


def _vec(dir_vec):
    v = np.asarray(dir_vec, dtype=np.float64)
    return v / np.linalg.norm(v)


E1 = _vec([1, 0, 0, 0, 0, 0, 0, 0])
E2 = _vec([0, 1, 0, 0, 0, 0, 0, 0])
E3 = _vec([0, 0, 1, 0, 0, 0, 0, 0])


def _lib(times_dirs):
    """times_dirs: [(t, dir)] -> (times 90..130 整秒网格, feats)。"""
    lib_t = np.arange(90.0, 131.0, 1.0)
    lookup = {t: d for t, d in times_dirs}
    feats = np.stack([_vec(lookup.get(int(t), [0, 0, 0, 0, 0, 0, 0, 1]))
                      for t in lib_t])
    return lib_t, feats


def _mk_result(**kw):
    d = dict(edited=TimeSpan(0.0, 4.0), original=TimeSpan(100.0, 104.0),
             confidence=Confidence(ConfidenceLevel.HIGH, 0.9))
    d.update(kw)
    return Result(**d)


class DetectShotsTest(unittest.TestCase):
    def test_hard_cut_splits(self):
        ets = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25]
        embs = [E1, E1, E1, E2, E2, E2]
        shots = detect_shots(ets, embs)
        self.assertEqual(len(shots), 2)

    def test_valley_detects_soft_cut(self):
        # 同景软切：余弦整体高但有局部深谷
        ets = [0.0, 0.25, 0.5, 0.75, 1.0, 1.25]
        e1 = _vec([1, 0, 0, 0, 0, 0, 0, 0])
        e1b = _vec([0.95, 0.31, 0, 0, 0, 0, 0, 0])   # cos(e1,e1b)≈0.95
        e2 = _vec([0.6, 0.8, 0, 0, 0, 0, 0, 0])      # 谷: cos(e1b,e2)≈0.63
        e2b = _vec([0.54, 0.84, 0, 0, 0, 0, 0, 0])   # cos(e2,e2b)≈0.997
        embs = [e1, e1b, e2, e2b, e2, e2b]
        self.assertEqual(len(detect_shots(ets, embs)), 2)

    def test_no_cut_single_shot(self):
        ets = [0.0, 0.25, 0.5, 0.75]
        embs = [E1, E1, E1, E1]
        self.assertEqual(len(detect_shots(ets, embs)), 1)


class SplitResultsTest(unittest.TestCase):
    """两镜段：前半 E1（投影位即正确, delta≈0 不精化），后半 E2（真实内容在
    lib E2 区 = 投影位 +4 偏移处, margin 门通过精化采纳）。"""

    def _setup(self):
        edited_dirs = {0.5: E1, 1.0: E1, 1.5: E1, 1.75: E2,
                       2.0: E2, 2.5: E2, 3.0: E2, 3.5: E2}
        times_dirs = ([(t, [1, 0, 0, 0, 0, 0, 0, 0]) for t in range(99, 103)]
                      + [(t, [0, 0, 1, 0, 0, 0, 0, 0]) for t in range(103, 106)]
                      + [(t, [0, 1, 0, 0, 0, 0, 0, 0]) for t in range(106, 111)]
                      + [(t, [0, 0, 1, 0, 0, 0, 0, 0]) for t in range(111, 130)])
        return edited_dirs, times_dirs

    def _run(self, results, edited_dirs, times_dirs):
        lib_t, lib_f = _lib(times_dirs)
        rng = np.random.default_rng(7)
        keys = sorted(edited_dirs)

        def grab(path, t):
            key = min(keys, key=lambda k: abs(k - t))
            return _vec(edited_dirs[key]) + rng.normal(0, 1e-6, 8)

        return split_results(results, edited_path="x", grab_frame=grab,
                             embed=lambda f: f, lib_times=lib_t, lib_feats=lib_f)

    def test_multishot_split_projection_and_refined(self):
        edited_dirs, times_dirs = self._setup()
        out = self._run([_mk_result()], edited_dirs, times_dirs)
        self.assertEqual(len(out), 2)
        c1, c2 = out
        # 镜 1：投影位即正确（E1 区）, delta≈0 → 保持投影
        self.assertAlmostEqual(c1.original.start, 100.0, delta=0.6)
        # 镜 2：真实内容在 E2 区（≈106 起）, 精化采纳
        self.assertGreater(c2.original.start, 104.5)
        self.assertLess(c2.original.start, 107.5)
        # 宽 span 保全：每子段携带父主 span 作子 span
        for o in (c1, c2):
            self.assertTrue(any(abs(s.start - 100.0) < 1e-6 and
                                abs(s.end - 104.0) < 1e-6
                                for s in o.original_segments))
        # 子段编辑窗无缝覆盖父窗
        self.assertAlmostEqual(c1.edited.start, 0.0, places=2)
        self.assertAlmostEqual(c2.edited.end, 4.0, places=2)
        self.assertAlmostEqual(sum(o.edited.width for o in out), 4.0, places=2)

    def test_children_unique_ids(self):
        edited_dirs, times_dirs = self._setup()
        out = self._run([_mk_result()], edited_dirs, times_dirs)
        self.assertEqual(len({o.result_id for o in out}), len(out))
        self.assertNotEqual(out[0].result_id, "")

    def test_single_shot_untouched(self):
        edited_dirs = {0.5: E1, 1.0: E1, 1.5: E1, 2.0: E1,
                       2.5: E1, 3.0: E1, 3.5: E1}
        times_dirs = [(t, [1, 0, 0, 0, 0, 0, 0, 0]) for t in range(95, 115)]
        r = _mk_result()
        out = self._run([r], edited_dirs, times_dirs)
        self.assertEqual(len(out), 1)
        self.assertIs(out[0], r)

    def test_not_in_source_skipped(self):
        r = _mk_result(not_in_source=True)
        edited_dirs = {0.5: E1, 1.0: E2}
        times_dirs = [(t, [1, 0, 0, 0, 0, 0, 0, 0]) for t in range(95, 115)]
        out = self._run([r], edited_dirs, times_dirs)
        self.assertIs(out[0], r)


if __name__ == "__main__":
    unittest.main()
