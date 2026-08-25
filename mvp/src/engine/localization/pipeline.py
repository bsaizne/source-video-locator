"""engine.localization.pipeline — 候选 -> 精定位 -> 置信 的产品级编排（第 5 项入口）。

输入：``produce_candidates`` 已排序的候选列表 + Edited 查询特征 + ``IndexBundle``；
输出：``RefinedSegment``（含精确 Original TimeSpan、置信度、montage 标记、备选）。

规则（MVP_ARCHITECTURE §6）：
- 对最佳候选（``candidates[0]``）跑 ``finloc_window`` 拿精确 span，并**回填** ``best_cover``。
- 若命中 montage（``montage_flag``）或没有可达的精确 span（``loc.span is None``），
  **不输出虚假精确单边界**：``original`` 退化为候选窗范围，置信度由 ConfidenceEngine 定。
- 编排**不改** similarity / ranking / 定位语义（只调用冻结的 finloc + confidence）。

与第 7 项 application service 的边界：本层不拼装 ``domain.Result`` 的 edited 段 /
extracted_path / manual 轨道 —— 那些由 app service 负责。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain import Alternative, Candidate, Confidence, TimeSpan
from engine.confidence import ConfidenceEngine
from engine.feature_store import IndexBundle
from infrastructure.config import PipelineConfig

from .finloc import LocalizationResult, finloc_window


@dataclass
class RefinedSegment:
    """一个 edited 查询单元的定位 + 置信产物（engine 内部中间结构）。"""

    candidate: Candidate            # 被定位的最佳候选（best_cover 已回填）
    loc: LocalizationResult
    original: TimeSpan              # 精确 span；montage/无 span 时退化为候选窗范围
    confidence: Confidence
    montage_flag: bool
    alternatives: list[Alternative]
    candidate_rank: int
    hard_flags: tuple[str, ...]


def localize_segment(candidates: list[Candidate], ed_feats: np.ndarray,
                     bundle: IndexBundle, *, cfg: PipelineConfig | None = None) -> RefinedSegment | None:
    """已排序候选 + Edited 查询特征 + Original 索引 -> ``RefinedSegment``。

    无候选时返回 ``None``（app service 按"无匹配"处理）。
    """
    if not candidates:
        return None

    best = candidates[0]
    loc = finloc_window(best, ed_feats, bundle.features, bundle.times)
    best.best_cover = loc.best_cover                      # 回填 per-orig coverage

    conf_cfg = cfg.confidence if cfg else None
    assess = ConfidenceEngine(conf_cfg).assess(candidates, loc, best=best)

    # 不输出虚假精确边界：montage（多岛）或精定位不稳定（无数值 span / run 过短）时，
    # original 退化为候选窗范围，交由用户确认；否则用精确 span。
    degrade = (assess.montage_flag or loc.span is None
               or "finloc_unstable" in assess.hard_flags)
    if degrade:
        original = TimeSpan(float(best.start), float(best.end))   # 候选窗范围
    else:
        original = TimeSpan(float(loc.span[0]), float(loc.span[1]))

    return RefinedSegment(
        candidate=best,
        loc=loc,
        original=original,
        confidence=assess.confidence,
        montage_flag=assess.montage_flag,
        alternatives=assess.alternatives,
        candidate_rank=1,
        hard_flags=assess.hard_flags,
    )
