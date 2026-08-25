"""engine.common.similarity — 冻结相似度定义（REUSE from research ``ta.py``）。

``cosine_similarity`` 是全部检索/定位的相似度语义，逐字搬自研究 ``ta.py``，不修改。
输入特征应为 L2 归一化（本函数也会重归一化以保证正确性，double-normalize 无害）。
"""
from __future__ import annotations

import numpy as np


def cosine_similarity(q_feats, r_feats):
    """[Nq, D] x [Nr, D] -> [Nq, Nr] cosine similarity matrix."""
    qn = q_feats / np.maximum(np.linalg.norm(q_feats, axis=1, keepdims=True), 1e-8)
    rn = r_feats / np.maximum(np.linalg.norm(r_feats, axis=1, keepdims=True), 1e-8)
    return qn @ rn.T
