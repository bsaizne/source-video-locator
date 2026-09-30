"""engine.localization — 精定位（REUSE Phase 13A/14C longest_run）+ montage 检测分支。

- ``finloc_window``：候选窗内 per-orig max-over-query coverage + longest_run -> 精确 span。
- ``LocalizationResult``：定位质量信号（best_cover / span_stability / coverage_quality /
  multi_island），供 ConfidenceEngine 使用。

> 曾有 ``pipeline.localize_segment``（候选 -> 精定位 -> ``assess()`` 置信）作为单答案编排；
> 该链路无生产调用者，2026-09-28 经用户拍板删除。生产路径 = ``EvidenceLocalizer`` 产
> ``EvidenceResult`` -> ``ConfidenceEngine.assess_evidence``。
"""
from .finloc import (FINLOC_STABLE_S, FINLOC_THRESH, MIN_RUN_FRAMES, MONTAGE_GAP_S,
                     LocalizationResult, finloc_window, longest_run)
from .evidence_localize import EvidenceLocalizer, EvidenceResult, EvidenceSpan
from .seq_align import MomentSpan, SeqAlignResult
from .temporal_repair import (find_overlap_conflicts, find_temporal_outliers,
                              relocate_in_window)
from .conflict_rerank import (accept_repair, best_free_span, find_span_conflicts,
                              span_mean_sim)

__all__ = [
    "LocalizationResult",
    "finloc_window",
    "longest_run",
    "FINLOC_THRESH",
    "FINLOC_STABLE_S",
    "MIN_RUN_FRAMES",
    "MONTAGE_GAP_S",
    "EvidenceLocalizer",
    "EvidenceResult",
    "EvidenceSpan",
    "MomentSpan",
    "SeqAlignResult",
    "find_temporal_outliers",
    "find_overlap_conflicts",
    "relocate_in_window",
    "find_span_conflicts",
    "span_mean_sim",
    "accept_repair",
    "best_free_span",
]
