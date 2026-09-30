# -*- coding: utf-8 -*-
"""展示层两件套单测（2026-09-29）: split_clips_at_boundaries（竞品
boundary_guard._record_boundary_split + segments/builder 单帧守卫语义重建）。

运行: venv python -m unittest mvp.tests.test_export_boundary_split -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.exporters import (ExportClip, expand_material_spans, plan_jianying_assets,
                           split_clips_at_boundaries)


def _scenes(table):
    return np.asarray(table, dtype=np.float64)


def _clip(s=100.0, e=110.0, kind="main", seg=0):
    return ExportClip(kind=kind, edited_start=0.0, edited_end=e - s,
                      orig_start=s, orig_end=e, confidence="HIGH",
                      seg_index=seg)


class BoundarySplitTest(unittest.TestCase):
    def test_no_scenes_noop(self):
        plan = [_clip()]
        self.assertEqual(split_clips_at_boundaries(plan, None), 0)
        self.assertEqual(split_clips_at_boundaries(plan, np.zeros((0, 2))), 0)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].split_index, -1)

    def test_span_without_interior_boundary_unchanged(self):
        # 内部无切点（切点都在 span 外）→ 原样
        plan = [_clip(100.0, 104.0)]
        n = split_clips_at_boundaries(plan, _scenes([[90.0, 100.0], [104.0, 120.0]]))
        self.assertEqual(n, 0)
        self.assertEqual(len(plan), 1)

    def test_split_at_interior_boundary(self):
        # span 100-110, 内部切点 104 → 两段 [100,104)+[104,110), 记录侧等比 4:6
        plan = [_clip(100.0, 110.0)]
        n = split_clips_at_boundaries(
            plan, _scenes([[90.0, 104.0], [104.0, 120.0]]), min_piece_s=0.5)
        self.assertEqual(n, 1)
        self.assertEqual([c.split_index for c in plan], [0, 1])
        self.assertEqual((plan[0].orig_start, plan[0].orig_end), (100.0, 104.0))
        self.assertEqual((plan[1].orig_start, plan[1].orig_end), (104.0, 110.0))
        # 记录侧等比: 记录总宽 10 → 4 与 6
        self.assertAlmostEqual(plan[0].record_width, 4.0, places=6)
        self.assertAlmostEqual(plan[1].record_width, 6.0, places=6)
        self.assertAlmostEqual(plan[1].edited_start, 4.0, places=6)

    def test_short_interior_piece_merged_into_previous(self):
        # 内部两个切点 103 与 103.4（0.4s 碎片镜头）→ 0.4s 段并入前段,
        # 结果两段: [100,103.4) + [103.4,110), 绝不出 <min_piece 碎片（单帧守卫）。
        plan = [_clip(100.0, 110.0)]
        n = split_clips_at_boundaries(
            plan, _scenes([[90.0, 103.0], [103.0, 103.4], [103.4, 120.0]]),
            min_piece_s=0.5)
        self.assertEqual(n, 1)
        self.assertEqual(len(plan), 2)
        self.assertEqual((plan[0].orig_start, plan[0].orig_end), (100.0, 103.4))
        self.assertEqual((plan[1].orig_start, plan[1].orig_end), (103.4, 110.0))
        for c in plan:
            self.assertGreaterEqual(c.orig_width, 0.5)

    def test_edge_cut_within_margin_not_used(self):
        # 切点 100.3 距 span 起点仅 0.3s(< min_piece) → 不用, 不产生边缘碎片
        plan = [_clip(100.0, 110.0)]
        n = split_clips_at_boundaries(
            plan, _scenes([[90.0, 100.3], [100.3, 120.0]]), min_piece_s=0.5)
        self.assertEqual(n, 0)
        self.assertEqual(len(plan), 1)

    def test_subs_and_tiny_clips_untouched(self):
        # 子 span / 宽度 <= 2*min_piece 的 clip 不展开
        sub = _clip(100.0, 110.0, kind="sub")
        tiny = _clip(100.0, 102.0)
        plan = [sub, tiny]
        n = split_clips_at_boundaries(
            plan, _scenes([[90.0, 105.0], [105.0, 120.0]]), min_piece_s=0.5)
        self.assertEqual(n, 0)
        self.assertEqual([c.split_index for c in plan], [-1, -1])

    def test_expand_skips_split_pieces(self):
        # 切点展开段不再被素材扩展撑宽（防轨道重叠）; 未切段照常扩展
        plan = [_clip(100.0, 104.0), _clip(104.0, 110.0)]
        plan[0].split_index = 0
        plan[1].split_index = 1
        scenes = _scenes([[99.0, 104.0], [104.0, 111.0]])
        changed = expand_material_spans(plan, scenes)
        self.assertEqual(changed, 0)
        self.assertEqual((plan[0].orig_start, plan[0].orig_end), (100.0, 104.0))

    def test_jianying_assets_keep_split_pieces_separate(self):
        # 展开段首尾贴接不得回并成一条素材（时间线要呈现真实切点）;
        # 未切分的重叠 clip 仍回并（既有去重语义）。
        p1, p2 = _clip(100.0, 104.0), _clip(104.0, 110.0)
        p1.split_index, p2.split_index = 0, 1
        assets = plan_jianying_assets([p1, p2])
        self.assertEqual(len(assets), 2)
        # 未切段: 重叠回并
        a, b = _clip(100.0, 106.0), _clip(104.0, 110.0)
        assets2 = plan_jianying_assets([a, b])
        self.assertEqual(len(assets2), 1)
        self.assertEqual((assets2[0].orig_start, assets2[0].orig_end), (100.0, 110.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
