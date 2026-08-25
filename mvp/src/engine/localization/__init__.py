"""engine.localization — 精定位（REUSE Phase 13A/14C longest_run）+ montage 检测分支。

- ``finloc_window``：候选窗内 per-orig max-over-query coverage + longest_run -> 精确 span。
- ``LocalizationResult``：定位质量信号（best_cover / span_stability / coverage_quality /
  multi_island），供 ConfidenceEngine 使用。

编排（``pipeline.localize_segment``：候选 -> 精定位 -> 置信）作为**显式子模块**，
不从本包顶层导入 —— 避免 ``engine.confidence`` <-> ``engine.localization`` 循环导入
（confidence 只依赖 finloc；pipeline 才同时依赖两者）。
"""
from .finloc import (FINLOC_STABLE_S, FINLOC_THRESH, MIN_RUN_FRAMES, MONTAGE_GAP_S,
                     LocalizationResult, finloc_window, longest_run)

__all__ = [
    "LocalizationResult",
    "finloc_window",
    "longest_run",
    "FINLOC_THRESH",
    "FINLOC_STABLE_S",
    "MIN_RUN_FRAMES",
    "MONTAGE_GAP_S",
]
