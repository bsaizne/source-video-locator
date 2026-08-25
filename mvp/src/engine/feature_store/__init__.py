"""engine.feature_store — Original Video 特征索引（create/load/validate/...）。

冻结约束（INDEX_SPEC）：落盘 ``index.json`` + ``features.npy`` + ``times.npy``；
把 numpy/cache 封装在 :class:`FeatureStore` 之后，不直接暴露给 UI。
"""
from .feature_store import FeatureStore, FeatureStoreError
from .index_bundle import IndexBundle

__all__ = ["FeatureStore", "FeatureStoreError", "IndexBundle"]
