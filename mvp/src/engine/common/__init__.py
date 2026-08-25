"""engine.common — 引擎共享工具（相似度等；冻结语义，不研究）。
"""
from .similarity import cosine_similarity

__all__ = ["cosine_similarity"]
