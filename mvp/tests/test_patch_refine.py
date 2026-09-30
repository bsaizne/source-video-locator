# -*- coding: utf-8 -*-
"""patch_refine 单测（2026-09-30 续32 形态6 runtime 化）。合成向量，无 GPU。"""
import unittest

import numpy as np

from domain.enums import ConfidenceLevel
from domain.models import Confidence, Result, TimeSpan
from engine.localization.patch_refine import apply_patch_refine


def _onehot(i, n=4):
    v = np.zeros(n, dtype=np.float64)
    v[i] = 1.0
    return v


def _mk_result(**kw):
    d = dict(edited=TimeSpan(0.0, 4.0), original=TimeSpan(100.0, 104.0),
             confidence=Confidence(ConfidenceLevel.HIGH, 0.9))
    d.update(kw)
    return Result(**d)


def _lib():
    """lib_times 90..130；99-102=E1, 103-105=E3, 112-116=E2, 其余=E3。"""
    lib_t = np.arange(90.0, 131.0, 1.0)
    feats = np.stack([
        _onehot(0) if 99 <= t <= 102 else (_onehot(1) if 112 <= t <= 116 else _onehot(2))
        for t in lib_t])
    return lib_t, feats


class ApplyPatchRefineTest(unittest.TestCase):
    def _run(self, results, q_region):
        """q_region: 查询帧内容区域 id（0=E1,1=E2,2=E3）。grab 返回时间标记，
        embed_dual 按时间轴分支：编辑轴 [0,4] → 查询区域；源片轴按 lib 区域。"""
        lib_t, lib_f = _lib()

        def grab(path, t):
            return float(t)

        def embed_dual(marker):
            t = float(marker)
            if 0 <= t <= 4:
                return _onehot(q_region), _onehot(q_region)[None, :]
            if 99 <= t <= 102:
                return _onehot(0), _onehot(0)[None, :]
            if 112 <= t <= 116:
                return _onehot(1), _onehot(1)[None, :]
            return _onehot(2), _onehot(2)[None, :]

        return apply_patch_refine(results, edited_path="x", source_path="y",
                                  grab_frame=grab,
                                  embed_dual=embed_dual, lib_times=lib_t,
                                  lib_feats=lib_f)

    def test_ambiguous_switch_carries_old_main_as_sub(self):
        # 查询=E2，现主在 E1 区(102) → 歧义；patch 峰在 E2 区(≈114) → 切换
        out = self._run([_mk_result()], q_region=1)
        self.assertEqual(len(out), 1)
        child = out[0]
        self.assertAlmostEqual(child.original.start, 112.0, delta=1.5)
        self.assertGreater(child.original.start, 106.0)
        # 宽 span 保全：老主降为首子 span
        self.assertEqual(len(child.original_segments), 1)
        self.assertAlmostEqual(child.original_segments[0].start, 100.0, delta=1e-6)
        self.assertAlmostEqual(child.original_segments[0].end, 104.0, delta=1e-6)

    def test_clear_case_skipped(self):
        # 查询=E1，top1 簇就在现主旁且唯一强 → 明确段不动
        out = self._run([_mk_result()], q_region=0)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].original.start, 100.0, delta=1e-6)
        self.assertEqual(out[0].original_segments, [])

    def test_not_in_source_skipped(self):
        r = _mk_result(not_in_source=True)
        out = self._run([r], q_region=1)
        self.assertIs(out[0], r)

    def test_input_not_mutated(self):
        r = _mk_result()
        before = (r.original.start, r.original.end, len(r.original_segments))
        self._run([r], q_region=1)
        after = (r.original.start, r.original.end, len(r.original_segments))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
