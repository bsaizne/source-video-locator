# -*- coding: utf-8 -*-
"""竞品四项加权置信公式（并行通道；2026-09-28 护栏豁免, 移植形态=用户拍板「只降不升」）。

竞品 ``fast_timeline/confidence.py`` docstring：「按**采样、偏移支持、局部一致性和候选差距**
给出稳定置信度结论」。四项权重与门限全部为 profile_v1 字节确证常量
（``cutmatch.matching.fast_timeline.options``, blob 0x174bb2ea）::

    score = 0.4*local + 0.3*coarse + 0.2*consistency + 0.1*margin
    稳定门限 min_confidence_score = 0.6
    四类低置信原因: insufficient_samples(<3) / weak_offset_support(<0.35) /
                    weak_local_consistency(<0.55) / small_candidate_margin(<0.03)

信号映射（口径差与不可外推纪律见 ``.agent/DECISIONS.md`` 2026-09-28）：

=================  ================================  ==================================
竞品项              我方信号                          定级
=================  ================================  ==================================
local（局部精排）    ``EvidenceSpan.best_sim``         语义近似（finloc run 内平滑 cover 均值）
coarse（采样）      ``EvidenceResult.evidence_qcov``  **推断级代理**（我方无「粗召回分」原生量）
consistency（一致性）``LocalizationResult.coverage_quality``  **推断级代理**（单峰集中度）
margin（候选差距）  primary vs secondary best_sim     与现行 ``_evidence_margin`` 同式
=================  ================================  ==================================

两个刻意避开的映射（避免单位错配系统性误杀）：不用簇内 ``timestamp_std``/
``EvidenceResult.dispersion`` 承载 consistency——它们是**原片 best_t 尺度**（随段长自然
增大），而竞品的 offset_dispersion 是**逐样本投影偏移尺度**，借 0.35s 锚会把长段一律判死。
同理，本模块的 consistency 门 ``min_support_ratio`` 作用在 ``coverage_quality`` 上，
是「证据是否收敛到单一 run」的判据，不等价于竞品的跨样本投票支持率。

纯函数、无 IO、不改现行档位语义：本模块只产出 ``score_v2`` + 命中的低置信原因，
是否降档由调用方（``ConfidenceEngine.assess_evidence``）决定。
"""
from __future__ import annotations

__all__ = ["confidence_v2"]


def _clip01(x: float) -> float:
    return 0.0 if x < 0.0 else (1.0 if x > 1.0 else float(x))


def confidence_v2(evidence, *, local_w: float = 0.4, coarse_w: float = 0.3,
                  consistency_w: float = 0.2, margin_w: float = 0.1,
                  min_valid_samples: int = 3, min_support_ratio: float = 0.35,
                  min_local_score: float = 0.55,
                  min_candidate_margin: float = 0.03,
                  ) -> tuple[float, tuple[str, ...], dict]:
    """按竞品四项加权算 ``score_v2``，返回 ``(score, 低置信原因, 信号诊断)``。

    ``evidence`` 为 ``EvidenceResult``。无主证据簇时返回 ``(0.0, ("no_evidence",), {})``。
    信号全部取自证据簇产物，不使用 GT 字段、不使用裸余弦（护栏保留项）。
    """
    prim = evidence.primary
    if prim is None or prim.original_span is None:
        return 0.0, ("no_evidence",), {}

    local = _clip01(prim.best_sim or 0.0)
    coarse = _clip01(evidence.evidence_qcov)
    consistency = _clip01(prim.finloc.coverage_quality if prim.finloc else 0.0)
    margin = _clip01(_margin(prim, evidence.secondary))

    score = _clip01(local_w * local + coarse_w * coarse
                    + consistency_w * consistency + margin_w * margin)

    reasons: list[str] = []
    if prim.query_frames < min_valid_samples:
        reasons.append("insufficient_samples")
    if consistency < min_support_ratio:
        reasons.append("weak_offset_support")
    if local < min_local_score:
        reasons.append("weak_local_consistency")
    if margin < min_candidate_margin:
        reasons.append("small_candidate_margin")

    signals = {"local": round(local, 4), "coarse": round(coarse, 4),
               "consistency": round(consistency, 4), "margin": round(margin, 4),
               "score": round(score, 4),
               "samples": int(prim.query_frames),
               "n_kept_spans": len(evidence.spans)}
    return score, tuple(reasons), signals


def _margin(prim, secondary) -> float:
    """主 vs 次证据簇的 best_sim 相对差距（无 secondary -> 1.0，与现行同式）。

    注: clean 单证据簇恒饱和 1.0——竞品同样只有多候选才给小 margin，故此信号
    不是本通道降档的主力（DECISIONS 2026-09-28「已知风险」条）。
    """
    if secondary is None:
        return 1.0
    p = prim.best_sim or 0.0
    s = secondary.best_sim or 0.0
    denom = max(abs(p), 1e-6)
    return _clip01((p - s) / denom)
