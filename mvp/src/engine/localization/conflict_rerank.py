"""conflict_rerank — 相邻重叠冲突的邻域扩池修复（Phase 24 非外观第二信号,纯函数可单测）。

实证（test3 r10,2026-08-30 全量裁决 + 预研探针）：编辑段 r10（55.5-57s）被定位到
447-449，与编辑序相邻的 r11（447.5-452.4）重叠 1.5s——两个不同编辑段被定位到几乎
同一源区间,其中必有一段错。预研量化结论（`mvp/benchmark/user_case/second_signal/
FINDINGS.md`）：

- 纯几何先验不可分：r10(错)与 r11 重叠占比 0.75,r6(对)与 r8(非相邻)合法复用
  重叠 0.76,几何同构,任何"移入空隙"阈值修一伤一。
- 但 r10 真值区（441-443,处于前后 claim 的空隙内）有**被压制的独立证据峰**
  （CLS 0.73 vs 错位区 0.87）——"真值无证据"不成立,是兄弟实例得分压制。

因此触发用**几何**（只信编辑序相邻重叠;非相邻的合法复用重叠不触发）,
接受用**内容证据门槛**（空隙内候选须有实质相似度、与当前定位的落差须有限）：

  1. mover 宽度 ≤ ``max_mover_width_s``（复合蒙太奇宽 span 不作 mover）;
  2. 与编辑序相邻段的定位区间重叠 ≥ ``overlap_min_s``（非相邻重叠不触发——
     这正是 r6(对)/r8(对) 与 r10(错)/r11(对) 的可分点）;
  3. 前后相邻 claim 有序（prev.end < next.start）,空隙宽 ≥ mover 宽度;
  4. 空隙内重定位候选 sim ≥ ``alt_min_sim`` 且 cur_sim − alt_sim ≤ ``max_drop``
     （证据底线:空隙候选只是"次强",太弱或落差太大都说明该段内容真的在当前位
     置,不动——防误伤 r4 这类宽复合段覆盖相邻 claim 的合法情形）。

修复方式与 temporal_repair 一致:原主定位挪入 ``original_segments`` 留痕,
新定位成为主 original,置信档位不变、追加 reason ``conflict_rerank``。
"""
from __future__ import annotations

from engine.localization.temporal_repair import relocate_in_window


def find_span_conflicts(
    positions: list[tuple[float, float] | None], *,
    max_mover_width_s: float = 8.0,
    overlap_min_s: float = 0.5,
    scores: list[float] | None = None,
) -> list[tuple[int, tuple[float, float]]]:
    """按编辑顺序给出每段主定位（None=未定位）→ [(段下标, 空隙修复窗)]。

    触发（全部满足）：mover 宽度受限;与 i-1 或 i+1 的定位重叠 ≥ ``overlap_min_s``;
    ``scores`` 给定时,mover 置信分须 ≤ 重叠邻居（低分一方才是错位嫌疑,高分段
    保持）;前后 claim 有序（prev.end ≤ next.start）且空隙 (prev.end, next.start)
    能容纳 mover 宽度。只看编辑序相邻段——非相邻的源区间复用是正常剪辑现象。
    """
    out: list[tuple[int, tuple[float, float]]] = []
    for i in range(1, len(positions) - 1):
        prev_p, cur_p, next_p = positions[i - 1], positions[i], positions[i + 1]
        if prev_p is None or cur_p is None or next_p is None:
            continue
        width = cur_p[1] - cur_p[0]
        if width <= 0 or width > max_mover_width_s:
            continue
        overlap_prev = min(cur_p[1], prev_p[1]) - max(cur_p[0], prev_p[0])
        overlap_next = min(cur_p[1], next_p[1]) - max(cur_p[0], next_p[0])
        cand_j = None
        if overlap_prev >= overlap_min_s:
            cand_j = i - 1
        if overlap_next >= overlap_min_s:
            if cand_j is None or overlap_next >= overlap_prev:
                cand_j = i + 1
        if cand_j is None:
            continue
        if scores is not None and i < len(scores) and cand_j < len(scores) \
                and scores[i] > scores[cand_j]:
            continue  # 高分段保持,低分段才是 mover
        if prev_p[1] > next_p[0]:
            continue  # 前后 claim 交叉/无空隙,拓扑异常不修
        gap_lo, gap_hi = prev_p[1], next_p[0]
        if gap_hi - gap_lo < width:
            continue
        out.append((i, (gap_lo, gap_hi)))
    return out


def span_mean_sim(plan_query, feats, times, span: tuple[float, float]) -> float | None:
    """查询均值特征在给定原片 span 内的帧均余弦（证据底线用）。无帧返回 None。"""
    import numpy as np

    f = np.asarray(feats, dtype=np.float32)
    t = np.asarray(times, dtype=np.float64)
    q = np.asarray(plan_query, dtype=np.float32)
    q /= max(float(np.linalg.norm(q)), 1e-8)
    inside = (t >= span[0]) & (t <= span[1])
    if not inside.any():
        return None
    return float((f[inside] @ q).mean())


def best_free_span(plan_query, feats, times, window: tuple[float, float],
                   claims: list[tuple[float, float]],
                   width: float) -> tuple[tuple[float, float] | None, float | None]:
    """在 ``window`` 内扣除其他段 claim 后的无主张子区间里,为查询重定位最优 span。

    返回 (最优 span, 其均值 sim)——子区间不足以容纳 ``width`` 则跳过;全部不可用
    返回 (None, None)。这是对"整窗 relocate + 事后跨段查重"的修正:实机 test3-r10
    中整窗最优块 (446,448) 落在非相邻段 r5 的合法 claim (445,447) 上被整单否决,
    而真正可容纳 mover 的无主张区 (443,445) 恰是真值位置。
    """
    import numpy as np

    lo_w, hi_w = float(window[0]), float(window[1])
    clipped = sorted((max(a, lo_w), min(b, hi_w)) for a, b in claims
                     if b > lo_w and a < hi_w)
    free: list[tuple[float, float]] = []
    cur = lo_w
    for a, b in clipped:
        if a > cur:
            free.append((cur, a))
        cur = max(cur, b)
    if cur < hi_w:
        free.append((cur, hi_w))
    best: tuple[float, float] | None = None
    best_sim: float | None = None
    for lo, hi in free:
        if hi - lo < width:
            continue
        span = relocate_in_window(plan_query, feats, times, (lo, hi), width)
        if span is None:
            continue
        s = span_mean_sim(plan_query, feats, times, span)
        if s is not None and (best_sim is None or s > best_sim):
            best, best_sim = span, s
    return best, best_sim


def accept_repair(cur_sim: float | None, alt_sim: float | None, *,
                  alt_min_sim: float = 0.60, max_drop: float = 0.25) -> bool:
    """内容证据门槛:空隙候选须有实质相似度,且与当前定位的落差有限。

    cur_sim/alt_sim 任一为 None（窗口无帧）→ 不修。
    """
    if cur_sim is None or alt_sim is None:
        return False
    if alt_sim < alt_min_sim:
        return False
    return (cur_sim - alt_sim) <= max_drop
