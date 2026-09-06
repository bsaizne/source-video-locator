"""temporal_repair — 时序离群定位修复（app 层后处理，纯函数可单测）。

实证（test1 r18，2026-08-30 29 段人工裁决 28/29）：暗夜相似场景跨场景误配——
某段定位与前后两段同时严重冲突（前后段彼此接近、本段远离两者），而其正确位置
几乎必然落在前后段定位之间的原片窗口内。本模块在该窗口内重新检索（整个窗口
都是候选，绕过"候选池天花板"），把离群段拉回时序一致的位置。

触发条件（全部满足才修，严格防误伤闪回/乱序剪辑）：
  1. 相邻三段（按编辑时间）都有定位；
  2. 前后两段定位彼此接近：|mid_next - mid_prev| ≤ ``neighbor_gap_s``；
  3. 本段定位与两者都远：min(|mid - mid_prev|, |mid - mid_next|) ≥ ``outlier_min_dist_s``；
  4. 窗口非空。

修复方式：原定位挪入 ``original_segments`` 留痕，新定位（窗口内与查询段均值
特征余弦最高的连续覆盖位置，宽度=原定位宽度）成为主定位。不改置信度档位，
仅追加 reason ``temporal_outlier_repair``（诚实留痕，UI 可见）。
"""
from __future__ import annotations

import numpy as np


def _mid(t0: float, t1: float) -> float:
    return (t0 + t1) / 2.0


def find_temporal_outliers(positions: list[tuple[float, float] | None], *,
                           neighbor_gap_s: float = 180.0,
                           outlier_min_dist_s: float = 600.0) -> list[int]:
    """按编辑顺序给出每段定位区间（None=未定位）→ 离群段的下标列表。

    只考虑同时拥有"前定位与后定位"的段（首尾段无从三角验证，不动）。
    """
    out: list[int] = []
    for i in range(1, len(positions) - 1):
        prev_p, cur_p, next_p = positions[i - 1], positions[i], positions[i + 1]
        if prev_p is None or cur_p is None or next_p is None:
            continue
        mid_prev = _mid(*prev_p)
        mid_cur = _mid(*cur_p)
        mid_next = _mid(*next_p)
        if abs(mid_next - mid_prev) > neighbor_gap_s:
            continue
        if min(abs(mid_cur - mid_prev), abs(mid_cur - mid_next)) >= outlier_min_dist_s:
            out.append(i)
    return out


def relocate_in_window(plan_query: np.ndarray, feats: np.ndarray, times: np.ndarray,
                       window: tuple[float, float], width: float) -> tuple[float, float] | None:
    """在原片窗口内为查询段（均值特征）重定位：滑窗（步长=采样间隔）均值余弦
    最高的连续覆盖位置，宽度=``width``。无可用帧返回 None。"""
    if feats is None or times is None or len(times) == 0 or width <= 0:
        return None
    f = np.asarray(feats, dtype=np.float32)
    t = np.asarray(times, dtype=np.float64)
    q = np.asarray(plan_query, dtype=np.float32)
    q /= max(float(np.linalg.norm(q)), 1e-8)
    sims = f @ q
    lo, hi = float(window[0]), float(window[1])
    if hi <= lo:
        return None
    inside = (t >= lo) & (t <= hi)
    if not inside.any():
        return None
    idx = np.nonzero(inside)[0]
    # 窗口内滑窗均值（窗宽=核心定位宽度，帧数按采样密度估计）
    step = float(np.median(np.diff(t[idx]))) if len(idx) > 1 else 1.0
    n_frames = max(1, int(round(width / max(step, 1e-6))))
    best_s, best_i = -2.0, idx[0]
    for j in range(len(idx) - n_frames + 1):
        block = idx[j:j + n_frames]
        if t[block[-1]] - t[block[0]] > width + 2.0:   # 跨大空洞跳过
            continue
        s = float(sims[block].mean())
        if s > best_s:
            best_s, best_i = s, int(block[0])
    if best_s <= -2.0:
        return None
    start = float(t[best_i])
    return (round(start, 2), round(start + width, 2))


def find_overlap_conflicts(positions: list[tuple[float, float] | None]) -> list[int]:
    """第二种触发（test3 r10 实证）：本段定位区间与相邻段定位区间**重叠**——
    两个不同编辑段被定位到几乎同一源区间，其中必有一段错（相邻编辑段的内容
    不会占用完全相同的源区间）。返回与相邻段重叠的段下标（配合 relocate 使用，
    修复窗口 = 前后相邻段定位之间的空隙）。"""
    out: list[int] = []
    for i in range(1, len(positions) - 1):
        prev_p, cur_p, next_p = positions[i - 1], positions[i], positions[i + 1]
        if prev_p is None or cur_p is None or next_p is None:
            continue
        overlap_prev = min(cur_p[1], prev_p[1]) - max(cur_p[0], prev_p[0])
        overlap_next = min(cur_p[1], next_p[1]) - max(cur_p[0], next_p[0])
        if overlap_prev > 0.5 or overlap_next > 0.5:
            out.append(i)
    return out
