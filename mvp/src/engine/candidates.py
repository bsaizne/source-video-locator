"""engine.candidates — 检索→聚类→排序 编排（Stage 1 第 4 项产品入口）。

输入：edited 特征序列 + ``IndexBundle``；输出：按 ``v2_score`` 降序的候选窗列表
（位置 0 = 首选）。本图不 finloc / 不置信 / 不切段——那些属第 5/6 项。

研究护栏：不改 cosine / 不改 v2_score / 不调 top_k / 不 sweep / 无 ANN。参数默认
取冻结值，可显式覆盖。仅当 ``cfg``（PipelineConfig）给出时从配置读 K/alpha/max_window。
"""
from __future__ import annotations

from domain import Candidate
from engine.feature_store import IndexBundle
from infrastructure.config import PipelineConfig

from .clustering import (BASE_GAP_S, BRIDGE_S, MAX_WINDOW_S, SIM_FLOOR, build_candidates)
from .ranking import FROZEN_ALPHA, rank_candidates
from .retrieval import FROZEN_TOP_K, retrieve_hits


def produce_candidates(ed_feats, ed_times, index_bundle: IndexBundle, *,
                       cfg: PipelineConfig | None = None) -> list[Candidate]:
    """<edited 特征, edited 时间轴, Original 索引> -> 有序候选窗列表（最佳在前）。

    参数来源：
    - ``top_k``：cfg.pipeline.retrieval_top_k（冻结=20），否则冻结 20。
    - ``alpha``：cfg.pipeline.ranking_alpha（冻结=0.5），否则冻结 0.5。
    - ``max_window_s``：cfg.pipeline.clustering_max_window_s（冻结=60）。
    - base_gap / bridge / sim_floor：冻结聚类常量（10 / 15 / 0.45）。
    """
    top_k = cfg.retrieval_top_k if cfg else FROZEN_TOP_K
    alpha = cfg.ranking_alpha if cfg else FROZEN_ALPHA
    max_window = cfg.clustering_max_window_s if cfg else MAX_WINDOW_S

    hits = retrieve_hits(ed_feats, ed_times,
                         index_bundle.features, index_bundle.times, top_k)
    cands = build_candidates(hits, base_gap_s=BASE_GAP_S, bridge_s=BRIDGE_S,
                             max_window_s=max_window, sim_floor=SIM_FLOOR)
    return rank_candidates(cands, alpha)
