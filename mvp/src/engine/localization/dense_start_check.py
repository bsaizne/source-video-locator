# -*- coding: utf-8 -*-
"""P0 密集起点复核（2026-09-26 续10i/k, 竞品 dense_alignment 语义重建, DECISIONS 2026-09-26 豁免裁决）。

对已定位主 span 的起点做 ±margin @10fps 密集窗复核：
  - 查询侧取段内采样帧的 3 个均匀代表帧（对齐竞品每场景 5 关键帧取前 3 的形态）;
  - 段级得分 = 3 帧按各自 ED 时间差对齐到窗内位置的余弦均值（多帧首段证据）;
  - 采纳门（终版, 沙盒四片 89/139 净 +6 零退化）:
      ① 增益 >= min_gain（"仅在实际帧复核分数有明确增益时覆盖"）;
      ② 位移 <= max_shift（offset_refine_max_shift 语义, 防一致但错的远漂移）;
      ③ 距离平局裁决（与最优分差 <= tie_margin 的位置中取离当前起点最近者, 再取更早帧号）。
    投票/分散度结构不进采纳门（续10k 三连败: 该结构属检索阶段全片域, 精修窗内不成立）。

纯函数无 IO; 解码/embed 由调用方注入（locator_service 用 FFmpegIO + backend.embed_frames）。
护栏豁免记录: DECISIONS 2026-09-26（豁免「禁 per-query argmax/temporal align」对本模块的适用）。
"""
from __future__ import annotations

import numpy as np

__all__ = ["dense_start_shift"]


def _select_query_indices(n: int) -> list[int]:
    """段内采样帧选 3 个均匀代表帧: 5 均匀位取前 3（竞品 keyframes 形态）; n<3 时用全部。"""
    if n <= 0:
        return []
    if n <= 3:
        return list(range(n))
    uniform5 = np.round(np.linspace(0, n - 1, 5)).astype(int)
    return sorted({int(i) for i in uniform5[:3]})


def dense_start_shift(q_feats: np.ndarray, q_times: np.ndarray,
                      win_feats: np.ndarray, win_times: np.ndarray,
                      *, span_start: float,
                      margin_s: float = 4.0,
                      min_gain: float = 0.04,
                      max_shift_s: float = 2.0,
                      tie_margin: float = 0.03) -> tuple[float | None, dict]:
    """对主 span 起点做密集复核, 返回 (new_start | None, info)。

    q_feats/win_feats 须为 L2 归一化 CLS [n,384]; q_times/win_times 为秒。
    win 覆盖 [span_start-margin, span_start+margin]。返回 None 表示不采纳（info 含门控诊断）。
    """
    info: dict = {"applied": False}
    n_q = q_feats.shape[0]
    if n_q == 0 or win_feats.shape[0] < 3:
        info["reason"] = "insufficient_frames"
        return None, info
    sel = _select_query_indices(n_q)
    if len(sel) < 1:
        info["reason"] = "no_query_frames"
        return None, info
    qs = q_feats[sel]                          # [K,384] 已 L2
    ts = [float(q_times[i]) for i in sel]
    deltas = np.array([(t - ts[0]) for t in ts], dtype=np.float64)
    d_t = np.asarray(win_times, dtype=np.float64)
    C = qs.astype(np.float32) @ win_feats.T.astype(np.float32)   # [K, M] 余弦

    def nearest_j(pos: float) -> int:
        return int(np.argmin(np.abs(d_t - pos)))

    def seg_score(pos: float) -> float:
        return float(np.mean([C[k, nearest_j(pos + deltas[k])] for k in range(len(qs))]))

    base_s = seg_score(span_start)
    scores = [seg_score(float(p)) for p in d_t]
    best_s = max(scores)
    # 门③ 距离平局裁决: 与最优分差 <= tie_margin 的位置中取离当前起点最近者, 平手取更早帧
    band = [j for j in range(len(d_t)) if scores[j] >= best_s - tie_margin]
    best_j = min(band, key=lambda j: (abs(float(d_t[j]) - span_start), float(d_t[j])))
    best_pos = float(d_t[best_j])
    gain = scores[best_j] - base_s
    move = abs(best_pos - span_start)
    gain_ok = gain >= min_gain
    shift_ok = move <= max_shift_s
    info.update({"gain": round(gain, 4), "move_s": round(move, 3),
                 "gain_ok": gain_ok, "shift_ok": shift_ok,
                 "base": round(base_s, 4), "best": round(scores[best_j], 4)})
    if best_pos == span_start:
        info["reason"] = "no_move"
        return None, info
    if not gain_ok:
        info["reason"] = "gain_below_threshold"
        return None, info
    if not shift_ok:
        info["reason"] = "move_exceeds_max_shift"
        return None, info
    info["applied"] = True
    info["before_start"] = round(span_start, 3)
    return round(best_pos, 3), info


def coarse_skip(coarse_info: dict, *, min_gain: float, gain_factor: float,
                max_shift_s: float) -> bool:
    """分级复核的跳过判定（2026-10-26 续97, 纯函数）。

    输入 = 用原片 **1fps 全片索引特征**跑同一 ``dense_start_shift`` 的诊断字典。
    跳过 10fps 细窗的条件（经验保守阈值, 非可证上界——10fps 峰可能高于 1fps 峰）：
      粗增益 < min_gain × gain_factor（放宽半档, 给细峰留余量）
      且 粗位移 <= max_shift_s（粗峰跑出位移帽的段照跑细窗, 防量化假象）。
    语义不变的最终裁决 = 四片 A/B 零差（locator_service 接线处）。
    """
    gain = float(coarse_info.get("gain", 0.0))
    move = float(coarse_info.get("move_s", 0.0))
    return (gain < min_gain * float(gain_factor)
            and move <= float(max_shift_s))
