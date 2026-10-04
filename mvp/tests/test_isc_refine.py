# -*- coding: utf-8 -*-
"""isc_refine 单测（2026-10-02 续44 runtime 化）。合成向量，无 GPU。"""
import unittest

import numpy as np

from domain.enums import ConfidenceLevel
from domain.models import Confidence, Result, TimeSpan
from engine.localization.isc_refine import apply_isc_refine


def _onehot(i, n=3):
    v = np.zeros(n, dtype=np.float64)
    v[i] = 1.0
    return v


def _mk_result(**kw):
    d = dict(edited=TimeSpan(0.0, 4.0), original=TimeSpan(100.0, 104.0),
             confidence=Confidence(ConfidenceLevel.HIGH, 0.9))
    d.update(kw)
    return Result(**d)


def _lib():
    """lib_times 90..130；99-102=E1, 112-116=E2, 其余=E3。"""
    lib_t = np.arange(90.0, 131.0, 1.0)
    feats = np.stack([
        _onehot(0) if 99 <= t <= 102 else (_onehot(1) if 112 <= t <= 116 else _onehot(2))
        for t in lib_t])
    return lib_t, feats


# ISC 受控向量：q=(1,0)；V_LOW·q=0.60（主定位区）；V_HIGH·q=0.62（E2 区，小 margin 用）
V_Q = np.array([1.0, 0.0])
V_LOW = np.array([0.60, -0.80]) / np.linalg.norm([0.60, -0.80])
V_HIGH = np.array([0.62, 0.785]) / np.linalg.norm([0.62, 0.785])


def _make_isc(mode):
    """mode='switch': E2 区=q 本体(sim 1.0) 其余 V_LOW；mode='small': E2=V_HIGH(0.62) 其余 V_LOW。"""
    def _isc_vec(marker):
        t = float(marker)
        if 0 <= t <= 4:
            return V_Q
        if 112 <= t <= 116:
            return V_Q if mode == "switch" else V_HIGH
        return V_LOW
    return _isc_vec


class ApplyIscRefineTest(unittest.TestCase):
    def _run(self, results, q_region, margin=0.05, progress_cb=None, isc_mode="switch",
             scan_radius_s=0.0, ladder_s=0.0, grab_grid=None):
        """q_region: CLS 查询区域 id（0=E1,1=E2,2=E3）。embed_isc 由 _make_isc(isc_mode)。"""
        lib_t, lib_f = _lib()

        def grab(path, t):
            return float(t)

        def embed_cls(marker):
            t = float(marker)
            if 0 <= t <= 4:
                return _onehot(q_region)
            if 99 <= t <= 102:
                return _onehot(0)
            if 112 <= t <= 116:
                return _onehot(1)
            return _onehot(2)

        return apply_isc_refine(
            results, edited_path="x", source_path="y", grab_frame=grab,
            embed_isc=_make_isc(isc_mode), embed_cls=embed_cls, lib_times=lib_t,
            lib_feats=lib_f, margin=margin, progress=progress_cb,
            scan_radius_s=scan_radius_s, ladder_s=ladder_s, grab_grid=grab_grid)

    def test_progress_reports_per_segment(self):
        seen: list[tuple[int, int]] = []
        out = self._run([_mk_result()], q_region=1, progress_cb=lambda d, t: seen.append((d, t)))
        self.assertEqual(seen, [(1, 1)])
        self.assertEqual(len(out), 1)

    def test_ambiguous_switch_carries_old_main_as_sub(self):
        # q_region=E2：top1 簇远离主(102) → 过歧义门；ISC 大 margin → 切到 E2 区某候选
        # （区内各帧 sim 同分，np.argsort 平局顺序不定 ⇒ 只断言落进 E2 区、宽度不变、老主降子）
        r = _mk_result()
        out = self._run([r], q_region=1)
        self.assertEqual(len(out), 1)
        o = out[0]
        self.assertTrue(o.result_id.endswith("-isc"))
        self.assertAlmostEqual(o.original.end - o.original.start, 4.0, places=6)
        self.assertGreaterEqual(o.original.start, 109.5)
        self.assertLessEqual(o.original.end, 118.5)
        self.assertEqual(o.original_segments[0].start, 100.0)
        self.assertEqual(o.original_segments[0].end, 104.0)
        # 入参不被修改
        self.assertAlmostEqual(r.original.start, 100.0, places=6)

    def test_below_margin_no_switch(self):
        # margin 0.02 < 门 0.05 → 不动
        r = _mk_result()
        out = self._run([r], q_region=1, margin=0.05, isc_mode="small")
        self.assertAlmostEqual(out[0].original.start, 100.0, places=6)
        self.assertFalse(out[0].result_id.endswith("-isc"))

    def test_clear_case_skipped(self):
        # q_region=E1 且主 100.5 营造「top1 必近主」（区内 top1 平局任意 ∈{99..102}，
        # 距 100.5 全部 ≤2s）：s1=1 领先 s2=0 ≥0.03 → 歧义门跳过（零 churn）
        r = _mk_result(original=TimeSpan(98.5, 102.5))
        out = self._run([r], q_region=0)
        self.assertAlmostEqual(out[0].original.start, 98.5, places=6)
        self.assertFalse(out[0].result_id.endswith("-isc"))

    def test_wide_scan_bypasses_gate(self):
        # v2（续45）：同 clear 夹具（歧义门本会跳过），radius=20 时宽扫仍跑——
        # ISC 在 E2 区成峰（sim 1.0）领先主（0.6）→ 切到宽扫峰，id 后缀 "-iscw"
        r = _mk_result(original=TimeSpan(98.5, 102.5))
        out = self._run([r], q_region=0, scan_radius_s=20.0)
        self.assertEqual(len(out), 1)
        o = out[0]
        self.assertTrue(o.result_id.endswith("-iscw"))
        self.assertAlmostEqual(o.original.end - o.original.start, 4.0, places=6)
        self.assertGreaterEqual(o.original.start, 109.0)
        self.assertLessEqual(o.original.end, 119.0)
        self.assertEqual(o.original_segments[0].start, 98.5)

    def test_ladder_early_stop_inner_hit(self):
        # v3 阶梯：内圈（±5s）就有过门峰（E2 距主 102 约 10s，在 radius=20 的内圈外…
        # 用 ladder=15 内圈覆盖 E2）→ 与全域扫同结果，且不再扩外圈
        r = _mk_result(original=TimeSpan(98.5, 102.5))
        out = self._run([r], q_region=0, scan_radius_s=20.0, ladder_s=15.0)
        self.assertTrue(out[0].result_id.endswith("-iscw"))
        self.assertGreaterEqual(out[0].original.start, 109.0)

    def test_ladder_extends_when_inner_misses(self):
        # v3 阶梯：ladder=5 内圈只有主定位区（E1, 0.6 分不过门）→ 扩展外圈 ±20 救回 E2
        r = _mk_result(original=TimeSpan(98.5, 102.5))
        out = self._run([r], q_region=0, scan_radius_s=20.0, ladder_s=5.0)
        self.assertTrue(out[0].result_id.endswith("-iscw"))
        self.assertGreaterEqual(out[0].original.start, 109.0)
        self.assertEqual(out[0].original_segments[0].start, 98.5)

    def test_ladder_off_equals_v2(self):
        # ladder_s=0（默认）= 现役全域扫行为：与不带阶梯的 v2 同结果
        r1 = _mk_result(original=TimeSpan(98.5, 102.5))
        r2 = _mk_result(original=TimeSpan(98.5, 102.5))
        o1 = self._run([r1], q_region=0, scan_radius_s=20.0)[0]
        o2 = self._run([r2], q_region=0, scan_radius_s=20.0, ladder_s=0.0)[0]
        self.assertEqual(o1.result_id.endswith("-iscw"), o2.result_id.endswith("-iscw"))
        self.assertAlmostEqual(o1.original.start, o2.original.start, places=6)
        self.assertAlmostEqual(o1.original.end, o2.original.end, places=6)

    def test_wide_scan_below_margin_no_switch(self):
        # v2：宽扫峰 E2=0.62 vs 主 0.60，margin 0.02 < 门 0.05 → 不动
        r = _mk_result(original=TimeSpan(98.5, 102.5))
        out = self._run([r], q_region=0, isc_mode="small", scan_radius_s=20.0)
        self.assertAlmostEqual(out[0].original.start, 98.5, places=6)
        self.assertFalse(out[0].result_id.endswith("-isc"))

    def test_not_in_source_skipped(self):
        r = _mk_result(not_in_source=True)
        out = self._run([r], q_region=1)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].not_in_source)

    def test_excluded_and_manual_skipped(self):
        r1 = _mk_result(excluded=True)
        r2 = _mk_result(manual_override=True)
        out = self._run([r1, r2], q_region=1)
        self.assertTrue(out[0].excluded)
        self.assertTrue(out[1].manual_override)

    def test_no_candidates_beyond_main_no_switch(self):
        # 簇提案全被门内吸收（q_region=E1 会被门跳过）——构造 q=E2 但 ISC 各候选同分：
        # 全部候选与主同分（v_low）→ others 最高分 = main 分 → margin 0 < 门
        lib_t, lib_f = _lib()
        r = _mk_result(original=TimeSpan(112.0, 116.0))  # 主在 E2 区内

        def grab(path, t):
            return float(t)

        def embed_cls(marker):
            t = float(marker)
            if 0 <= t <= 4:
                return _onehot(1)  # q=E2，top1 在主附近 → 可能过门；不依赖该分支
            if 99 <= t <= 102:
                return _onehot(0)
            if 112 <= t <= 116:
                return _onehot(1)
            return _onehot(2)

        def embed_isc(marker):
            t = float(marker)
            return V_HIGH if (0 <= t <= 4 or 112 <= float(t) <= 116) else V_LOW

        out = apply_isc_refine([r], edited_path="x", source_path="y", grab_frame=grab,
                               embed_isc=embed_isc, embed_cls=embed_cls,
                               lib_times=lib_t, lib_feats=lib_f, margin=0.05)
        self.assertAlmostEqual(out[0].original.start, 112.0, places=6)


    def test_wide_scan_grid_grabber_same_result(self):
        """续50 L1：粗扫走 grab_grid（网格抽取）时，结果须与旧抓帧路径逐位一致（同帧语义）。"""
        calls = []

        def grid(path, times):
            calls.append(sorted(times))
            return {round(float(t), 6): float(t) for t in times}

        base = self._run([_mk_result(original=TimeSpan(98.5, 102.5))], q_region=0,
                         scan_radius_s=20.0)
        with_grid = self._run([_mk_result(original=TimeSpan(98.5, 102.5))], q_region=0,
                              scan_radius_s=20.0, grab_grid=grid)
        self.assertTrue(calls, "粗扫没有调用 grab_grid")
        self.assertGreater(len(calls[0]), 10)          # 粗扫点数（±20s / 2s 步长）
        self.assertEqual(len(base), len(with_grid))
        for a, b in zip(base, with_grid):
            # result_id 是每次运行新生成的 uuid ⇒ 比后缀（-isc / -iscw / 无）
            self.assertEqual(a.result_id.split("-")[-1] if "-" in a.result_id else "",
                             b.result_id.split("-")[-1] if "-" in b.result_id else "")
            self.assertAlmostEqual(a.original.start, b.original.start, places=6)
            self.assertAlmostEqual(a.original.end, b.original.end, places=6)
            self.assertEqual(len(a.original_segments), len(b.original_segments))

    def test_grid_grabber_missing_frame_falls_back(self):
        """grab_grid 未覆盖某个 t（超片尾/解码失败）⇒ 逐帧回退，不得丢帧或抛错。"""
        def grid(path, times):
            return {round(float(t), 6): float(t) for t in times if float(t) < 110.0}

        out = self._run([_mk_result(original=TimeSpan(98.5, 102.5))], q_region=0,
                        scan_radius_s=20.0, grab_grid=grid)
        self.assertEqual(len(out), 1)
        self.assertTrue(out[0].result_id.endswith("-iscw"))


if __name__ == "__main__":
    unittest.main()
