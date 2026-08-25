"""engine.ranking — Candidate Rerank（REUSE Phase 16B ExpA，==n_reps^alpha）。

唯一新增排序信号 = ``n_reps ** alpha``（查询时序覆盖度）。``v2_score`` 逐字对齐
research ``phase16b_rerank.v2_score``（冻结排名基线）：

    v2_score = mean_sim * sqrt(hit_count) * (0.5 + 0.5 * consistency) * (n_reps ** alpha)

其余排序字段（mean/hit/consistency）沿用 14A/14A.1 冻结基线。``alpha=0.5`` 冻结。
"""
from __future__ import annotations

import numpy as np

from domain import Candidate

FROZEN_ALPHA = 0.5   # 冻结（Phase 16B ExpA 采纳，禁调）


def v2_score(c: Candidate, alpha: float = FROZEN_ALPHA) -> float:
    """新 rank score：基线 * n_reps**alpha（reward 覆盖更宽 edited 查询的候选窗）。"""
    base = c.mean_sim * np.sqrt(c.hit_count) * (0.5 + 0.5 * c.consistency)
    return float(base * (c.n_reps ** alpha))


def rank_candidates(candidates: list[Candidate], alpha: float = FROZEN_ALPHA) -> list[Candidate]:
    """回填 ``rank_score``，按 v2_score 降序排序。返回新列表（位置 = rank，0 最佳）。

    不改变排序所依赖的语义（共排序仅用于选最佳/列举 alternative）。
    """
    for c in candidates:
        c.rank_score = v2_score(c, alpha)
    ordered = sorted(candidates, key=lambda c: c.rank_score, reverse=True)
    return ordered
