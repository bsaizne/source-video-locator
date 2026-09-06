"""engine.localization.seq_align — 帧级 moment 定位（时序单调 DP）。

序列对齐：对给定「编辑子序列 vs 原片候选窗」，用单调 DP 把编辑序列精确对齐到原片序列的
连续 moment（可多段），输出帧级 ``MomentSpan``（区分同 scene 内不同拍摄单元）。

**突破 finloc 研究护栏「禁 temporal alignment」，用户已授权产品化（2026-08-28）。**
语义逐字节复刻 research ``src/experiments/ta.py``（REUSE 冻结），引擎层不 import research
（先例 ``engine/common/similarity.py``：拷贝冻结函数）。

产品语义：evidence 定位「哪个场景」（scene 级），本层「这个场景里的哪一帧」（moment 级）。
moment 精修为空/失败 → 调用方回退 scene 级，零回归。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from engine.common import cosine_similarity


@dataclass
class MomentSpan:
    """一个帧级 moment（编辑子区间 ↔ 原片精确区间，时序对齐产物）。"""

    edited_interval: tuple[float, float]   # [q0_time, q1_time] 编辑秒
    original_span: tuple[float, float]     # [r0_time, r1_time] 原片秒（帧级精确）
    mean_sim: float                        # path 内相似度均值（质量信号）
    peak_sim: float                        # path 内最大相似度
    n_frames: int                          # path 内命中帧数
    confidence: str                        # "high" | "medium" | "low"


@dataclass
class SeqAlignResult:
    """一次序列对齐的产出（无 IO、确定性）。"""

    segments: list[MomentSpan] = field(default_factory=list)
    path_len: int = 0                      # DP path 长度
    nq: int = 0                            # 编辑序列帧数
    nr: int = 0                            # 原片候选窗帧数
    skipped: bool = False                  # 超过 max_cells 被跳过（性能护栏）


def _zero_runs(arr):
    """Return start/end indices of consecutive zeros in a bool/int array."""
    iszero = np.concatenate(([0], np.equal(arr, 0).view(np.int8), [0]))
    absdiff = np.abs(np.diff(iszero))
    return np.where(absdiff == 1)[0].reshape(-1, 2)


def _cut_path(path, diagonal_thres=3):
    """Remove long vertical/horizontal drift runs from an aligned path.

    path: (P, 2) int array of (q_idx, r_idx). Returns list of keep ranges
    [start, end). (REUSE ta.cut_path, unchanged.)"""
    if len(path) == 0:
        return []
    vertical_ranges = _zero_runs(np.diff(path[:, 0]))
    vertical_ranges[:, 1] += 1
    horizontal_ranges = _zero_runs(np.diff(path[:, 1]))
    horizontal_ranges[:, 1] += 1
    vertical_ranges = vertical_ranges[np.diff(vertical_ranges, axis=-1).squeeze(-1) > diagonal_thres]
    horizontal_ranges = horizontal_ranges[np.diff(horizontal_ranges, axis=-1).squeeze(-1) > diagonal_thres]
    discard = np.concatenate([vertical_ranges, horizontal_ranges], axis=0)
    if len(discard) == 0:
        discard = discard.reshape(0, 2)
    endpoints = discard.ravel() if len(discard) else np.array([], dtype=np.int64)
    if len(endpoints) == 0:
        return [np.array([0, len(path)], dtype=np.int32)]
    endpoints = endpoints[1:] if endpoints[0] == 0 else np.concatenate([[0], endpoints])
    endpoints = endpoints[:-1] if endpoints[-1] == len(path) else np.concatenate([endpoints, [len(path)]])
    return [r for r in endpoints.reshape(-1, 2) if r[1] > r[0]]


def _dp_path(sim_matrix, sim_thresh=0.5, diag_penalty=0.5, step_penalty=1.0):
    """Monotonic DP over the similarity matrix (REUSE ta._dp_path, unchanged).

    Maximize accumulated similarity along a down/right/diagonal monotone path.
    Returns optimal path as (P, 2) int array."""
    nq, nr = sim_matrix.shape
    S = np.zeros((nq + 1, nr + 1), dtype=np.float64)
    trace = np.zeros((nq + 1, nr + 1), dtype=np.int8)  # 1=diag, 2=up, 3=left
    for i in range(1, nq + 1):
        for j in range(1, nr + 1):
            s = sim_matrix[i - 1, j - 1]
            v_diag = S[i - 1, j - 1] + s
            v_up = S[i - 1, j] - diag_penalty * (1.0 if s < sim_thresh else step_penalty)
            v_left = S[i, j - 1] - diag_penalty * (1.0 if s < sim_thresh else step_penalty)
            best = v_diag
            tr = 1
            if v_up > best:
                best, tr = v_up, 2
            if v_left > best:
                best, tr = v_left, 3
            S[i, j] = best
            trace[i, j] = tr
    path = []
    i, j = nq, nr
    while i > 0 and j > 0:
        tr = trace[i, j]
        if tr == 1:
            path.append((i - 1, j - 1))
            i -= 1
            j -= 1
        elif tr == 2:
            i -= 1
        else:
            j -= 1
    path = path[::-1]
    return np.array(path, dtype=np.int32) if path else np.zeros((0, 2), dtype=np.int32)


def _merge_segments(segs, max_edited_gap=3, max_orig_gap=8):
    """Merge consecutive segments whose edited gap and original gap are both small."""
    if len(segs) <= 1:
        return segs
    merged = [segs[0]]
    for seg in segs[1:]:
        last = merged[-1]
        gap_q = seg["q0"] - last["q1"]
        gap_r = seg["r0"] - last["r1"]
        if 0 <= gap_q <= max_edited_gap and 0 <= gap_r <= max_orig_gap:
            merged[-1] = {"q0": last["q0"], "q1": seg["q1"],
                          "r0": last["r0"], "r1": seg["r1"],
                          "sims": last["sims"] + seg["sims"]}
        else:
            merged.append(seg)
    return merged


def align_moments(ed_feats, ed_times, orig_feats, orig_times, *,
                  sim_thresh: float = 0.40, min_hits: int = 2, min_moment_s: float = 1.0,
                  diag_penalty: float = 0.5, step_penalty: float = 1.0,
                  mean_sim_min: float = 0.40, max_edited_gap: int = 3,
                  max_orig_gap: int = 8, max_cells: int = 20000,
                  moment_half_s: float = 1.0) -> SeqAlignResult:
    """编辑子序列 → 原片候选窗 的帧级 moment 对齐。纯 numpy、确定性。

    ``ed_feats``/``ed_times`` [Nq,384]/[Nq]，``orig_feats``/``orig_times`` [Nr,384]/[Nr]。
    编辑序列内部须时间有序（调用方先排序；DP 期望单调编辑轴）。超 ``max_cells`` 直接
    ``skipped=True``（性能护栏，调用方回退 scene 级）。
    """
    q = np.asarray(ed_feats, dtype=np.float32)
    r = np.asarray(orig_feats, dtype=np.float32)
    tq = np.asarray(ed_times, dtype=np.float32)
    tr = np.asarray(orig_times, dtype=np.float32)
    nq, nr = q.shape[0], r.shape[0]
    if nq == 0 or nr == 0:
        return SeqAlignResult(nq=nq, nr=nr)
    if int(nq) * int(nr) > max_cells:
        return SeqAlignResult(nq=nq, nr=nr, skipped=True)

    sim = cosine_similarity(q, r)                       # [Nq, Nr]
    path = _dp_path(sim, sim_thresh=sim_thresh, diag_penalty=diag_penalty,
                    step_penalty=step_penalty)
    if len(path) < 2:
        return SeqAlignResult(path_len=len(path), nq=nq, nr=nr)

    keep_ranges = _cut_path(path, diagonal_thres=3)
    segments = []
    for s, e in keep_ranges:
        sub = path[s:e]
        if len(sub) < min_hits:
            continue
        mean_sim = float(np.mean(sim[sub[:, 0], sub[:, 1]]))
        if mean_sim < mean_sim_min:
            continue
        # 段时长按原片 span 算（moment 至少 min_moment_s）
        dur = float(tr[sub[-1, 1]] - tr[sub[0, 1]])
        if dur < min_moment_s:
            continue
        segments.append({
            "q0": int(sub[0, 0]), "q1": int(sub[-1, 0]) + 1,
            "r0": int(sub[0, 1]), "r1": int(sub[-1, 1]) + 1,
            "sims": [mean_sim],
        })

    segments = _merge_segments(segments, max_edited_gap, max_orig_gap)

    moments = []
    for seg in segments:
        q0, q1, r0, r1 = seg["q0"], seg["q1"], seg["r0"], seg["r1"]
        sub_sims = sim[q0:q1, r0:r1]                   # 块内相似度（用于 peak）
        mean_s = float(np.mean(seg["sims"]))
        peak_s = float(sub_sims.max()) if sub_sims.size else mean_s
        conf = "high" if mean_s >= 0.8 else ("medium" if mean_s >= 0.6 else "low")
        # moment ±moment_half_s 收窄：用段内最佳原片帧时刻作峰锚（用户"正负1秒"，不用整段连续区）
        best_col = int(np.argmax(sub_sims.sum(axis=0))) if sub_sims.size else 0
        best_t = float(tr[min(r0 + best_col, nr - 1)])
        os0 = max(0.0, best_t - moment_half_s)
        os1 = best_t + moment_half_s
        moments.append(MomentSpan(
            edited_interval=(round(float(tq[q0]), 2), round(float(tq[min(q1, nq) - 1]), 2)),
            original_span=(round(os0, 2), round(os1, 2)),
            mean_sim=round(mean_s, 4), peak_sim=round(float(peak_s), 4),
            n_frames=int(q1 - q0), confidence=conf))

    return SeqAlignResult(segments=moments, path_len=len(path), nq=nq, nr=nr)
