"""engine.clustering — Candidate Clustering（REUSE Phase 14A.1 连续性感知聚类）。

把检索层的 flat ``Hits`` 聚成【多个小而合理的候选窗】：
- ``gap <= base_gap(10s)``：按原片时间近邻直接合并。
- ``base_gap < gap <= bridge(15s)``：须通过连续性检查（``_merged_ok``：相似度≥sim_floor
  / 原片~编辑片单调 / 局部速度带 [speed_lo,speed_hi]）才合并。
- ``gap > bridge`` 或 cluster 跨度 > ``max_window(60s)``：切分（绝不产生 869s 巨窗）。

输出：``domain.Candidate`` 列表（未排序；排序/rank 由 ``engine.ranking`` 负责）。
``best_cover`` 留 0.0 占位——真正的 per-original max-over-query coverage 由
fine localization（Stage 1 第 5 项 longest_run）在候选窗上计算并回填。

研究代码依赖（``_recall`` 量 GT coverage、``_hits`` 读缓存、``_metrics`` 旧版字段、
GT_ORDER/PAD 等）均 RESEARCH_ONLY，不进 runtime。
"""
from __future__ import annotations

from typing import Sequence

import numpy as np

from domain import Candidate
from engine.retrieval import Hits

# 冻结聚类常量（Phase 14A.1，禁调）
BASE_GAP_S = 10.0      # gap<=这 按时间近邻直接合并
BRIDGE_S = 15.0        # (base_gap, bridge] 须过连续性检查
MAX_WINDOW_S = 60.0    # 硬上限；超限强制切分（无巨窗）
SIM_FLOOR = 0.45       # 合并候选的编辑帧代表相似度下限
SPEED_LO, SPEED_HI = 0.0, 90.0   # 局部速度带（orig-s / edited-s）
MIN_HITS = 2           # 一个候选窗至少需要这么多命中


# --------------------------------------------------------------------------- #
# 连续性判定（REUSE 14a1）
# --------------------------------------------------------------------------- #
def _reps(ids: Sequence[int], ed_t, orig_t, sims) -> dict:
    """把一组命中归约为每-编辑帧代表：dict ed_time -> (best_sim, orig)。"""
    rep = {}
    for i in ids:
        et, ot, s = float(ed_t[i]), float(orig_t[i]), float(sims[i])
        if et not in rep or s > rep[et][0]:
            rep[et] = (float(s), float(ot))
    return rep


def _merged_ok(cluster_ids, k, ed_t, orig_t, sims, sim_floor=SIM_FLOOR):
    """连续性检查：cluster + 新命中 k 是否仍构成合理拷贝轨迹。

    要求：编辑帧代表相似度均值 >= sim_floor；orig~edit 顺序单调；每段局部速度
    (d_orig/d_ed) 落在 [SPEED_LO, SPEED_HI]。跳到远处相似场景 -> 速度巨大 -> 拒绝。
    """
    rep = _reps(list(cluster_ids) + [k], ed_t, orig_t, sims)
    keys = sorted(rep)
    if len(keys) == 1:
        ok = rep[keys[0]][0] >= sim_floor
        return ok, (None if ok else "sim")
    ots = [rep[e][1] for e in keys]
    for a, b in zip(ots[:-1], ots[1:]):
        if b < a - 1e-6:
            return False, "non-monotonic"
    if float(np.mean([rep[e][0] for e in keys])) < sim_floor:
        return False, "sim"
    for a, b in zip(keys[:-1], keys[1:]):
        de = b - a
        if de <= 0.01:
            continue
        sp = (rep[b][1] - rep[a][1]) / de
        if sp < SPEED_LO or sp > SPEED_HI:
            return False, f"speed({sp:.0f}s/s)"
    return True, None


def cluster_continuous(ed_t, orig_t, sims, *,
                       base_gap_s: float = BASE_GAP_S,
                       bridge_s: float = BRIDGE_S,
                       max_window_s: float = MAX_WINDOW_S,
                       sim_floor: float = SIM_FLOOR) -> list[list[int]]:
    """贪心、按原片时间排序的连续性聚类。返回 cluster 列表（每个 = 命中索引列表）。"""
    order = np.argsort(orig_t, kind="stable")
    clusters, cur = [], []
    for k in order:
        if not cur:
            cur = [k]
            continue
        gap = orig_t[k] - orig_t[cur[-1]]
        span = orig_t[k] - orig_t[cur[0]]
        if gap <= base_gap_s:
            merge = True
        elif gap <= bridge_s:
            merge, _ = _merged_ok(cur, k, ed_t, orig_t, sims, sim_floor)
        else:
            merge = False
        if merge and span <= max_window_s:
            cur.append(k)
        else:
            clusters.append(cur)
            cur = [k]
    if cur:
        clusters.append(cur)
    return clusters


def _bridges(clu, orig_t) -> list[float]:
    """cluster 内部相邻 orig 时间 gap > base_gap(需连续性桥接) 的 gap 值。"""
    ids = sorted(clu, key=lambda i: orig_t[i])
    return [round(float(orig_t[b] - orig_t[a]), 1)
            for a, b in zip(ids[:-1], ids[1:]) if orig_t[b] - orig_t[a] > BASE_GAP_S]


# --------------------------------------------------------------------------- #
# Candidate 生成
# --------------------------------------------------------------------------- #
def _metrics_to_candidate(clu, hits: Hits, sim_floor: float) -> Candidate:
    """从 cluster（命中索引）计算候选指标，映射到 domain.Candidate。

    字段语义对齐 research ``metrics_v2``：
    mean=rep_sims 均值（此处用 cluster 内 sim 均值，同 studies metric）、
    consistency=编辑帧代表 orig 单调比例、n_reps=不同编辑帧数（查询时序覆盖度）、
    qcov=编辑帧代表 sim>=sim_floor 的比例、sim_std=编辑帧代表 sim 标准差、
    scene_div=内部 orig 桥接段数+1（montage 指示）。
    """
    ed_t, orig_t, sims = hits.ed_t, hits.orig_t, hits.sims
    ots, ss = orig_t[clu], sims[clu]
    start, end = float(ots.min()), float(ots.max())
    width = max(end - start, 0.0)

    rep = {}
    for i in clu:
        et, ot, s = float(ed_t[i]), float(orig_t[i]), float(sims[i])
        if et not in rep or s > rep[et][0]:
            rep[et] = (s, ot)
    keys = sorted(rep)
    ots_seq = [rep[e][1] for e in keys]
    rep_sims = [rep[e][0] for e in keys]
    nseq = len(ots_seq)
    cons = (sum(1 for i in range(1, nseq) if ots_seq[i] >= ots_seq[i - 1]) / (nseq - 1)
            if nseq > 1 else 0.0)
    n_reps = len(keys)
    qcov = float(np.mean([s >= sim_floor for s in rep_sims])) if rep_sims else 0.0
    sim_std = float(np.std(rep_sims)) if len(rep_sims) > 1 else 0.0
    scene_div = len(_bridges(clu, orig_t)) + 1

    return Candidate(
        start=round(start, 1), end=round(end, 1), width=round(width, 1),
        peak_sim=round(float(ss.max()), 3), mean_sim=round(float(ss.mean()), 3),
        consistency=round(cons, 3), hit_count=len(clu), n_reps=n_reps,
        qcov=round(qcov, 3), sim_std=round(sim_std, 3),
        rank_score=0.0,            # 由 engine.ranking.v2_score 回填
        best_cover=0.0,            # 占位：per-orig coverage 由 finloc(第5项) 回填
        scene_div=scene_div,
    )


def build_candidates(hits: Hits, *,
                     base_gap_s: float = BASE_GAP_S,
                     bridge_s: float = BRIDGE_S,
                     max_window_s: float = MAX_WINDOW_S,
                     sim_floor: float = SIM_FLOOR,
                     min_hits: int = MIN_HITS) -> list[Candidate]:
    """``Hits`` -> 未排序的 ``domain.Candidate`` 列表（每窗一个候选）。"""
    clusters = cluster_continuous(hits.ed_t, hits.orig_t, hits.sims,
                                  base_gap_s=base_gap_s, bridge_s=bridge_s,
                                  max_window_s=max_window_s, sim_floor=sim_floor)
    return [_metrics_to_candidate(c, hits, sim_floor)
            for c in clusters if len(c) >= min_hits]
