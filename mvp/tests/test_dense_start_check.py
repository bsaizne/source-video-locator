# -*- coding: utf-8 -*-
"""P0 密集起点复核 单测（2026-09-26 续10i 移植）。

合成特征验证采纳门: ①增益门 ②max_shift 门 ③距离平局裁决 ④失败隔离输入。
护栏豁免: DECISIONS 2026-09-26（本模块判据获准, 豁免范围仅限 dense_start_check）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))          # mvp/src
sys.path.insert(0, str(SRC.parent))   # mvp 包

from engine.localization.dense_start_check import dense_start_shift, _select_query_indices  # noqa: E402


def _rng(seed: int) -> np.random.Generator:
    return np.random.default_rng(seed)


def _unit(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.maximum(n, 1e-8)


def _make_window(seed: int, true_start: float | None, deltas: list[float],
                 dim: int = 64):
    """窗 0..8s @10fps; 若 true_start 非 None, 在 t*+delta_k 处放查询向量(强证据), 其余随机。"""
    rng = _rng(seed)
    times = np.round(np.arange(0, 8.0 + 1e-9, 0.1), 3)
    win = rng.normal(size=(len(times), dim)).astype(np.float32)
    qs = rng.normal(size=(len(deltas), dim)).astype(np.float32)
    qs = _unit(qs)
    if true_start is not None:
        for k, d in enumerate(deltas):
            j = int(np.argmin(np.abs(times - (true_start + d))))
            win[j] = _unit(qs[k] + rng.normal(size=dim) * 0.01).astype(np.float32)
    return _unit(qs), np.array([0.0] + list(np.cumsum([0.5] * (len(deltas) - 1))),
                               dtype=np.float64), _unit(win), times


class SelectQueryIndicesTest(unittest.TestCase):
    def test_counts(self):
        self.assertEqual(_select_query_indices(1), [0])
        self.assertEqual(_select_query_indices(2), [0, 1])
        self.assertEqual(_select_query_indices(3), [0, 1, 2])
        sel = _select_query_indices(10)
        self.assertEqual(len(sel), 3)
        self.assertEqual(sel[0], 0)


class DenseStartShiftTest(unittest.TestCase):
    def test_shift_applied_on_clear_gain(self):
        qs, qt, win, wt = _make_window(1, true_start=1.0, deltas=[0.0, 0.5, 1.0])
        new_start, info = dense_start_shift(qs, qt, win, wt, span_start=0.0)
        self.assertIsNotNone(new_start)
        self.assertLessEqual(abs(new_start - 1.0), 0.11)
        self.assertTrue(info["applied"])
        self.assertTrue(info["gain_ok"] and info["shift_ok"])
        self.assertGreater(info["gain"], 0.04)

    def test_no_shift_when_gain_below_threshold(self):
        # 增益门: 强证据在 +1.0 但 min_gain 压到 10(不可达) → 拒绝
        qs, qt, win, wt = _make_window(2, true_start=1.0, deltas=[0.0, 0.5, 1.0])
        new_start, info = dense_start_shift(qs, qt, win, wt, span_start=0.0, min_gain=10.0)
        self.assertIsNone(new_start)
        self.assertEqual(info.get("reason"), "gain_below_threshold")

    def test_no_shift_when_move_exceeds_max_shift(self):
        # 强证据在 +3.5s(> max_shift 2.0): 必须拒绝(防"一致但错"远漂移, 2mkv p01 型)
        qs, qt, win, wt = _make_window(3, true_start=3.5, deltas=[0.0, 0.5, 1.0])
        new_start, info = dense_start_shift(qs, qt, win, wt, span_start=0.0, max_shift_s=2.0)
        self.assertIsNone(new_start)
        self.assertEqual(info.get("reason"), "move_exceeds_max_shift")

    def test_tie_band_prefers_closer_position(self):
        # 两个等强峰 +0.8 与 +2.0: 平局裁决取离当前起点更近者(非分数并列时取远者)
        rng = _rng(4)
        times = np.round(np.arange(0, 8.0 + 1e-9, 0.1), 3)
        deltas = [0.0, 0.5, 1.0]
        qs = _unit(rng.normal(size=(3, 64)).astype(np.float32))
        win = rng.normal(size=(len(times), 64)).astype(np.float32)
        for t0 in (0.8, 2.0):
            for k, d in enumerate(deltas):
                j = int(np.argmin(np.abs(times - (t0 + d))))
                win[j] = _unit(qs[k]).astype(np.float32)
        win = _unit(win)
        qt = np.array([0.0, 0.5, 1.0], dtype=np.float64)   # 与种植间隔一致(deltas=qt 差分)
        new_start, info = dense_start_shift(qs, qt, win, times, span_start=0.0)
        self.assertIsNotNone(new_start)
        self.assertLessEqual(abs(new_start - 0.8), 0.11)

    def test_short_query_frames_use_all(self):
        rng = _rng(5)
        times = np.round(np.arange(0, 8.0 + 1e-9, 0.1), 3)
        qs = _unit(rng.normal(size=(2, 64)).astype(np.float32))
        win = rng.normal(size=(len(times), 64)).astype(np.float32)
        for k, d in enumerate([0.0, 0.5]):
            j = int(np.argmin(np.abs(times - (1.0 + d))))
            win[j] = _unit(qs[k]).astype(np.float32)
        win = _unit(win)
        new_start, info = dense_start_shift(qs, np.arange(2, dtype=np.float64), win, times,
                                            span_start=0.0)
        self.assertIsNotNone(new_start)
        self.assertTrue(info["applied"])

    def test_insufficient_window_frames(self):
        qs = _unit(_rng(6).normal(size=(3, 64)).astype(np.float32))
        win2 = _unit(_rng(8).normal(size=(2, 64)).astype(np.float32))
        new_start, info = dense_start_shift(qs, np.arange(3, dtype=np.float64),
                                            win2, np.arange(2, dtype=np.float64),
                                            span_start=0.0)
        self.assertIsNone(new_start)
        self.assertEqual(info.get("reason"), "insufficient_frames")

    def test_no_move_when_best_is_current_position(self):
        # 强证据恰在当前起点: 不动(采纳需 best != span_start)
        qs, qt, win, wt = _make_window(7, true_start=0.0, deltas=[0.0, 0.5, 1.0])
        new_start, info = dense_start_shift(qs, qt, win, wt, span_start=0.0)
        self.assertIsNone(new_start)
        self.assertEqual(info.get("reason"), "no_move")


if __name__ == "__main__":
    unittest.main()
