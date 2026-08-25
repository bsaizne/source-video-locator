"""engine.retrieval — Global Candidate Retrieval（REUSE Phase 14A 检索逻辑）。

输入：editted feature 序列（``ed_feats`` [Nq,384]、``ed_times`` [Nq]，L2 归一化）
+ ``IndexBundle``（original 特征 [T,384]、``times`` [T]）。输出：flat hits。

- 余弦相似度用 ``engine.common.cosine_similarity``（冻结）。
- 每个 edited 查询帧取 Top-K（K=20，冻结，禁调）个原片命中；**批量**（整个
  查询序列一次 ``np.argsort(sim, axis=1)``，无逐帧循环）。
- ``orig_t = orig_times[top_idx]``：用 FeatureStore 落盘的时间轴（等价于
  ``top_idx / ORIG_FPS``，但解耦硬编码 fps）。sim 用 ``take_along_axis`` 取回。

无 ANN/FAISS（K 在全体原片特征上穷举余弦后截取；对 MVP 的 ~3.8k 特征规模无需索引）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from engine.common import cosine_similarity

FROZEN_TOP_K = 20   # 冻结（Phase 14A / 16B 采纳，禁调）


@dataclass
class Hits:
    """检索层扁平命中：edited 查询时间 / 原片时间 / 相似度，行一一对应。"""

    ed_t: np.ndarray    # [Nq*K] float32  命中的 edited 时间
    orig_t: np.ndarray  # [Nq*K] float32  对应原片时间
    sims: np.ndarray    # [Nq*K] float32  对应余弦相似度
    nq: int             # edited 查询帧数


def retrieve_hits(ed_feats: np.ndarray, ed_times: np.ndarray,
                  orig_feats: np.ndarray, orig_times: np.ndarray,
                  top_k: int = FROZEN_TOP_K) -> Hits:
    """Cosine + 批量 Top-K 检索，展开为 flat hits。

    ``ed_feats`` [Nq,384] 与 ``orig_feats`` [T,384] 均应为 L2 归一化特征。
    ``top_k`` 超过原片特征数时自动截断到 T。
    """
    nq = len(ed_times)
    if nq == 0 or orig_feats.shape[0] == 0:
        return Hits(np.zeros(0, np.float32), np.zeros(0, np.float32),
                    np.zeros(0, np.float32), nq)

    sim = cosine_similarity(ed_feats, orig_feats)          # [Nq, T]
    k = min(int(top_k), sim.shape[1])
    top_idx = np.argsort(sim, axis=1)[:, -k:][:, ::-1]     # (Nq, k) 降序

    ed_t = np.repeat(ed_times, k).astype(np.float32)
    orig_t = orig_times[top_idx.reshape(-1)].astype(np.float32)
    sims = np.take_along_axis(sim, top_idx, axis=1).reshape(-1).astype(np.float32)
    return Hits(ed_t, orig_t, sims, nq)
