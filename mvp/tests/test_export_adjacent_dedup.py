# -*- coding: utf-8 -*-
"""相邻贴接段源区间去重叠单测（2026-10-06 修「成片里相邻段重复出现同一画面」）。

背景：定位段源窗宽度有 ``min_span_s=2.0`` 地板，剪辑段常 0.7~1.5s ⇒ 贴接相邻两段源区间
必然交叠，逐段取材再拼接的成片/EDL/XML 出现重复画面。修法 = 交叠区按中点切开。

运行: venv python -m unittest mvp.tests.test_export_adjacent_dedup -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.exporters import ExportClip, trim_adjacent_source_overlaps

FPS = 25.0
FRAME = 1.0 / FPS


def _clip(edited_s: float, edited_e: float, orig_s: float, orig_e: float,
          kind: str = "main") -> ExportClip:
    return ExportClip(kind=kind, edited_start=edited_s, edited_end=edited_e,
                      orig_start=orig_s, orig_end=orig_e, confidence="HIGH")


def _overlap(plan: list[ExportClip]) -> float:
    """按编辑序遍历 main/low，返回最大相邻源区间交叠秒数（>0 即会重复画面）。"""
    ordered = sorted((c for c in plan if c.kind in ("main", "low")),
                     key=lambda c: (c.edited_start, c.edited_end))
    worst = 0.0
    for a, b in zip(ordered, ordered[1:]):
        if b.edited_start - a.edited_end > 0.05:
            continue
        worst = max(worst, min(a.orig_end, b.orig_end) - max(a.orig_start, b.orig_start))
    return worst


class TrimAdjacentOverlapTest(unittest.TestCase):
    def test_partial_overlap_split_at_midpoint(self):
        """典型形态：两段各被撑到 2s 宽、贴接、正序重叠 1.38s ⇒ 中点切开。"""
        a = _clip(0.0, 0.86, 433.6, 435.6)
        b = _clip(0.86, 1.86, 434.2, 436.2)
        n = trim_adjacent_source_overlaps([a, b], fps=FPS)
        self.assertEqual(n, 1)
        self.assertEqual(a.orig_end, 434.9)
        self.assertEqual(b.orig_start, 434.9)
        self.assertAlmostEqual(_overlap([a, b]), 0.0, places=6)

    def test_union_content_preserved(self):
        """裁重叠不丢画面：两段并集覆盖范围裁前后一致。"""
        a = _clip(0.0, 1.0, 100.0, 102.0)
        b = _clip(1.0, 2.0, 101.0, 103.0)
        before = (min(a.orig_start, b.orig_start), max(a.orig_end, b.orig_end))
        trim_adjacent_source_overlaps([a, b], fps=FPS)
        after = (min(a.orig_start, b.orig_start), max(a.orig_end, b.orig_end))
        self.assertEqual(after, before)
        self.assertAlmostEqual((a.orig_end - a.orig_start) + (b.orig_end - b.orig_start),
                               before[1] - before[0], places=6)

    def test_contained_clip_holes_out_without_losing_footage(self):
        """一段整个被前段包住（扩宽到整镜头 vs 短段）⇒ 外层**挖洞**，内层完整保留。

        中点裁尾会把外层独占的右尾巴丢掉（真实四片回放实测少 6.58s），所以这里必须
        拆成头段 + 尾段两条 clip，同属一个编辑段（记录槽按源宽比例分）。
        """
        a = _clip(0.0, 2.48, 1785.0, 1794.9)
        b = _clip(2.48, 4.81, 1787.1, 1789.4)
        plan = [a, b]
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=FPS), 1)
        self.assertEqual(len(plan), 3)                    # 头段 + 新尾段 + 内层
        self.assertEqual((a.orig_start, a.orig_end), (1785.0, 1787.1))
        tail = plan[1]
        self.assertEqual((tail.orig_start, tail.orig_end), (1789.4, 1794.9))
        self.assertEqual(tail.seg_index, a.seg_index)      # 同属该编辑段
        self.assertEqual((b.orig_start, b.orig_end), (1787.1, 1789.4))   # 内层不动
        # 画面一块不丢：三段源区间互不重叠，且并集 = 原来的整镜头
        spans = sorted((c.orig_start, c.orig_end) for c in plan)
        for (s1, e1), (s2, e2) in zip(spans, spans[1:]):
            self.assertLessEqual(e1, s2 + 1e-9)
        self.assertAlmostEqual(sum(e - s for s, e in spans), 1794.9 - 1785.0, places=6)
        # 记录槽总量不变（该编辑段仍占 2.48s）
        self.assertAlmostEqual(a.edited_end + (tail.edited_end - tail.edited_start)
                               + (b.edited_end - b.edited_start),
                               2.48 + (4.81 - 2.48), places=6)

    def test_contained_flush_right_just_trims(self):
        """外层右端与内层右端齐平（无尾巴）⇒ 只裁外层尾，不产生新段。"""
        a = _clip(0.0, 1.0, 100.0, 102.0)
        b = _clip(1.0, 2.0, 101.0, 102.0)
        plan = [a, b]
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=FPS), 1)
        self.assertEqual(len(plan), 2)
        self.assertEqual((a.orig_start, a.orig_end), (100.0, 101.0))

    def test_contained_flush_left_moves_start(self):
        """外层左端与内层左端齐平 ⇒ 外层只剩右半（起点后移），不丢尾巴。"""
        a = _clip(0.0, 1.0, 100.0, 103.0)
        b = _clip(1.0, 2.0, 100.0, 101.0)
        plan = [a, b]
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=FPS), 1)
        self.assertEqual((a.orig_start, a.orig_end), (101.0, 103.0))
        self.assertEqual((b.orig_start, b.orig_end), (100.0, 101.0))

    def test_reverse_source_order_keeps_tail(self):
        """源序倒挂（后段起点更早）：谁独占左半谁取左半，前段的尾巴不能被裁掉。"""
        a = _clip(0.0, 3.03, 2043.0, 2045.0)
        b = _clip(3.03, 4.69, 2042.0, 2044.0)
        n = trim_adjacent_source_overlaps([a, b], fps=FPS)
        self.assertEqual(n, 1)
        self.assertEqual(b.orig_end, 2043.5)            # b 取左半（含其独占 2042 起）
        self.assertEqual(a.orig_start, 2043.5)
        self.assertEqual(a.orig_end, 2045.0)            # a 独占的尾巴必须保住
        self.assertAlmostEqual(_overlap([a, b]), 0.0, places=6)

    def test_non_adjacent_reuse_untouched(self):
        """编辑时间轴上不相邻（中间还有内容）的重叠 = 真实复用，不裁。"""
        a = _clip(0.0, 1.0, 100.0, 102.0)
        b = _clip(5.0, 6.0, 101.0, 103.0)
        self.assertEqual(trim_adjacent_source_overlaps([a, b], fps=FPS), 0)
        self.assertEqual((b.orig_start, b.orig_end), (101.0, 103.0))

    def test_subs_not_trimmed(self):
        """子 span 不参与（渲染/EDL 只用主 span，裁它没有意义）。"""
        a = _clip(0.0, 1.0, 100.0, 102.0)
        s = _clip(1.0, 2.0, 101.0, 103.0, kind="sub")
        self.assertEqual(trim_adjacent_source_overlaps([a, s], fps=FPS), 0)
        self.assertEqual((a.orig_start, a.orig_end), (100.0, 102.0))

    def test_single_frame_guard_skips_tiny_union(self):
        """交叠并集不足 2 帧 ⇒ 跳过（重复量不可见，也不能切出 1 帧闪烁段）。"""
        a = _clip(0.0, 1.0, 100.0, 100.04)
        b = _clip(1.0, 2.0, 100.02, 100.06)
        self.assertEqual(trim_adjacent_source_overlaps([a, b], fps=FPS), 0)
        self.assertEqual((a.orig_start, a.orig_end), (100.0, 100.04))

    def test_single_frame_guard_clamps_cut(self):
        """一侧仅剩不足 1 帧时把切点夹回，保证两侧各 ≥1 帧。"""
        a = _clip(0.0, 1.0, 100.0, 100.10)
        b = _clip(1.0, 2.0, 100.06, 100.14)
        self.assertEqual(trim_adjacent_source_overlaps([a, b], fps=FPS), 1)
        self.assertGreaterEqual(a.orig_end - a.orig_start, FRAME - 1e-6)
        self.assertGreaterEqual(b.orig_end - b.orig_start, FRAME - 1e-6)
        self.assertAlmostEqual(_overlap([a, b]), 0.0, places=6)

    def test_chain_three_clips_fully_deduped(self):
        """三段连叠（2s 地板下连续短段的常态）：处理后相邻对全部不重叠。"""
        a = _clip(0.0, 0.9, 300.0, 302.0)
        b = _clip(0.9, 1.8, 300.7, 302.7)
        c = _clip(1.8, 2.7, 301.4, 303.4)
        plan = [a, b, c]
        n = trim_adjacent_source_overlaps(plan, fps=FPS)
        self.assertEqual(n, 2)
        self.assertAlmostEqual(_overlap(plan), 0.0, places=6)
        for cl in plan:
            self.assertGreater(cl.orig_end - cl.orig_start, 0.0)

    def test_record_side_untouched(self):
        """只动源片侧；记录（编辑）时间轴逐字段不变。"""
        a = _clip(0.0, 0.86, 433.6, 435.6)
        b = _clip(0.86, 1.86, 434.2, 436.2)
        before = [(c.edited_start, c.edited_end) for c in (a, b)]
        trim_adjacent_source_overlaps([a, b], fps=FPS)
        self.assertEqual([(c.edited_start, c.edited_end) for c in (a, b)], before)

    def test_idempotent(self):
        a = _clip(0.0, 1.0, 100.0, 102.0)
        b = _clip(1.0, 2.0, 101.0, 103.0)
        plan = [a, b]
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=FPS), 1)
        snap = [(c.orig_start, c.orig_end) for c in plan]
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=FPS), 0)
        self.assertEqual([(c.orig_start, c.orig_end) for c in plan], snap)

    def test_disjoint_plan_noop(self):
        """无重叠（现役常态）⇒ 返回 0 且逐字段不变（零语义面）。"""
        a = _clip(0.0, 1.0, 100.0, 101.0)
        b = _clip(1.0, 2.0, 101.0, 103.0)
        c = _clip(2.0, 3.0, 90.0, 92.0)
        plan = [a, b, c]
        before = [(x.orig_start, x.orig_end) for x in plan]
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=FPS), 0)
        self.assertEqual([(x.orig_start, x.orig_end) for x in plan], before)

    def test_unsorted_input_still_pairs_by_edited_order(self):
        """plan 里顺序不按编辑轴排列时仍按编辑序配对的。"""
        a = _clip(0.0, 1.0, 100.0, 102.0)
        b = _clip(1.0, 2.0, 101.0, 103.0)
        plan = [b, a]
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=FPS), 1)
        self.assertEqual(a.orig_end, 101.5)
        self.assertEqual(b.orig_start, 101.5)

    def test_bad_fps_falls_back(self):
        """fps 未知（0）时按 0.04s 帧长守卫，不抛不崩。"""
        a = _clip(0.0, 1.0, 100.0, 102.0)
        b = _clip(1.0, 2.0, 101.0, 103.0)
        self.assertEqual(trim_adjacent_source_overlaps([a, b], fps=0.0), 1)
        self.assertAlmostEqual(_overlap([a, b]), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
