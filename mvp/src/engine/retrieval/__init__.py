"""engine.retrieval — Global Candidate Retrieval（REUSE Phase 14A）。
"""
from .retrieval import FROZEN_TOP_K, Hits, retrieve_hits

__all__ = ["Hits", "retrieve_hits", "FROZEN_TOP_K"]
