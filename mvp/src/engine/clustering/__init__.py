"""engine.clustering — Candidate Clustering（REUSE Phase 14A.1）。
"""
from .clustering import (BASE_GAP_S, BRIDGE_S, MAX_WINDOW_S, SIM_FLOOR, build_candidates,
                         cluster_continuous)

__all__ = ["build_candidates", "cluster_continuous",
           "BASE_GAP_S", "BRIDGE_S", "MAX_WINDOW_S", "SIM_FLOOR"]
