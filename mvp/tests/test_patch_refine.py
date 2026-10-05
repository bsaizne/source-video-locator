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
    def _run(self, results, q_region, progress_cb=None, grab_grid=None, refine_grid=False):
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
                                  lib_feats=lib_f, progress=progress_cb,
                                  grab_grid=grab_grid, refine_grid=refine_grid)

    def test_progress_reports_per_segment(self):
        # UX-P1（2026-10-01 续35 E2E）：逐段进度回调 (done,total)，含跳过段也计数
        seen: list[tuple[int, int]] = []
        out = self._run([_mk_result(), _mk_result(not_in_source=True)],
                        q_region=1, progress_cb=lambda d, t: seen.append((d, t)))
        self.assertEqual(len(out), 2)
        self.assertEqual(seen, [(1, 2), (2, 2)])

    def test_progress_none_default_no_regression(self):
        out = self._run([_mk_result()], q_region=1)
        self.assertEqual(len(out), 1)

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

    # ---- 续54 补二：候选精排窗网格抽取（旋钮 patch_refine_grid，默认关）----

    def test_grid_off_is_noop_and_never_calls_grid(self):
        """旋钮关（默认）= grab_grid 一次都不调，结果与非网格路径逐位相同。"""
        calls = []

        def grid(path, times):
            calls.append((path, sorted(times)))
            return {round(float(t), 6): float(t) for t in times}

        off = self._run([_mk_result()], q_region=1, grab_grid=grid, refine_grid=False)
        plain = self._run([_mk_result()], q_region=1)
        self.assertEqual(calls, [], "refine_grid=False 时不得走网格路径")
        self.assertEqual(len(off), len(plain))
        for a, b in zip(off, plain):
            self.assertAlmostEqual(a.original.start, b.original.start, places=6)
            self.assertAlmostEqual(a.original.end, b.original.end, places=6)

    def test_grid_on_same_result_and_used_for_source_windows(self):
        """网格抓帧与逐帧抓帧同帧（first_ge 契约）⇒ 结果逐位不变，且确实走了网格路径。"""
        calls = []

        def grid(path, times):
            calls.append((path, sorted(float(t) for t in times)))
            return {round(float(t), 6): float(t) for t in times}

        base = self._run([_mk_result()], q_region=1)
        with_grid = self._run([_mk_result()], q_region=1, grab_grid=grid, refine_grid=True)
        self.assertTrue(calls, "候选精排窗没有调用 grab_grid")
        self.assertTrue(all(p == "y" for p, _ in calls), "只应替换源片窗抓帧")
        self.assertGreaterEqual(len(calls[0][1]), 6, "单窗点数 = REFINE_WIN 网格")
        self.assertEqual(len(base), len(with_grid))
        for a, b in zip(base, with_grid):
            self.assertEqual(a.result_id.split("-")[-1] if "-" in a.result_id else "",
                             b.result_id.split("-")[-1] if "-" in b.result_id else "")
            self.assertAlmostEqual(a.original.start, b.original.start, places=6)
            self.assertAlmostEqual(a.original.end, b.original.end, places=6)
            self.assertEqual(len(a.original_segments), len(b.original_segments))

    def test_grid_missing_frame_falls_back_per_frame(self):
        """grab_grid 漏掉某个 t（超片尾/解码失败）⇒ 逐帧回退，不丢帧不抛错。"""
        def grid(path, times):
            return {round(float(t), 6): float(t) for t in times if float(t) < 114.0}

        out = self._run([_mk_result()], q_region=1, grab_grid=grid, refine_grid=True)
        self.assertEqual(len(out), 1)
        self.assertAlmostEqual(out[0].original.start, 112.0, delta=1.5)

    # ---- 续55：段内候选窗并集（一次批量抓帧，簇间可并行解码）----

    def _run_batched(self, results, q_region, refine_grid=False, grab_grid=None):
        """与 _run 同语义，但传批量抓帧 grab_frames 并记录每次调用的目标表。"""
        lib_t, lib_f = _lib()
        calls: list[list[float]] = []

        def grab(path, t):
            return float(t)

        def grab_batch(path, times):
            times = list(times)
            if str(path) == "y":
                calls.append(sorted(round(float(t), 3) for t in times))
            # 批量返回值 = 逐帧 grab 的同帧（生产契约）
            return [float(t) for t in times]

        def embed_dual(marker):
            t = float(marker)
            if 0 <= t <= 4:
                return _onehot(q_region), _onehot(q_region)[None, :]
            if 99 <= t <= 102:
                return _onehot(0), _onehot(0)[None, :]
            if 112 <= t <= 116:
                return _onehot(1), _onehot(1)[None, :]
            return _onehot(2), _onehot(2)[None, :]

        out = apply_patch_refine(results, edited_path="x", source_path="y",
                                 grab_frame=grab, grab_frames=grab_batch,
                                 grab_grid=grab_grid, refine_grid=refine_grid,
                                 embed_dual=embed_dual, lib_times=lib_t, lib_feats=lib_f)
        return out, calls

    def test_union_batches_all_candidate_windows_into_one_call(self):
        """非网格形态：本段所有候选窗并成一次源片调用，且结果与逐帧路径逐位一致。"""
        r = _mk_result()
        per_frame = self._run([r], q_region=1)
        batched, calls = self._run_batched([r], q_region=1)
        self.assertEqual(len(calls), 1, "一段应只有一次源片批量抓帧")
        self.assertGreater(len(calls[0]), 20, "并集未覆盖多候选窗")
        self.assertEqual(len(per_frame), len(batched))
        for a, b in zip(per_frame, batched):
            self.assertAlmostEqual(a.original.start, b.original.start, places=6)
            self.assertAlmostEqual(a.original.end, b.original.end, places=6)
            self.assertEqual(a.confidence, b.confidence)
            self.assertEqual(len(a.original_segments), len(b.original_segments))

    def test_grid_mode_does_not_union(self):
        """网格形态不并集（select 只服务单一相位）：每个候选窗各自一次网格调用。"""
        grid_calls: list[list[float]] = []

        def grid(path, times):
            ts = sorted(round(float(t), 3) for t in times)
            if str(path) == "y":
                grid_calls.append(ts)
            return {round(float(t), 6): float(t) for t in times}

        _out, batch_calls = self._run_batched([_mk_result()], q_region=1,
                                              refine_grid=True, grab_grid=grid)
        self.assertEqual(batch_calls, [], "网格形态不应走整段并集的批量抓帧")
        self.assertGreater(len(grid_calls), 1, "应逐候选窗调用 grab_grid")
        self.assertLessEqual(max(len(c) for c in grid_calls), 12,
                             "单次网格调用不应跨多个候选窗")



if __name__ == "__main__":
    unittest.main()
