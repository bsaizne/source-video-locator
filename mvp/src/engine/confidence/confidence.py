"""engine.confidence — 工程化置信度（REWRITE/NEW，产品核心）。

唯一生产入口是 :meth:`ConfidenceEngine.assess_evidence`，输入 = ``EvidenceLocalizer``
的 ``EvidenceResult``（证据簇产物）：主/次证据簇差距、证据时序覆盖、簇内 coverage、
精定位稳定性与单峰集中度。输出 = 三档置信（HIGH/MEDIUM/LOW）+ ``score`` + ``reasons``
+ ``hard_flags`` + ``montage_flag`` + ``alternatives``（+ ``confidence_v2`` 诊断）。

> 历史：本模块曾另有一条 single-answer 编排（``assess()`` 吃已排序 ``Candidate`` 列表，
> 由 ``engine.localization.pipeline.localize_segment`` 调用）。该链路自证据簇上线后
> **无任何生产调用者**，2026-09-28 经用户拍板删除（连带 3 个只被它消费的旋钮）。

设计来源：CONFIDENCE_DESIGN.md。**关键纪律**（§5/§6/§7 + 研究护栏）：
- ``score`` 是工程 confidence score，**不是**模型概率，禁止展示为百分比概率。
- **不使用** start_err / end_err / IoU（运行时无 GT）。
- **不使用**余弦相似度直接当置信度（错误场景 CLS 可能高于正确来源）。
- 阈值/权重均为**结构占位**（CONFIDENCE_DESIGN §6 诚实声明：未标定），本阶段**禁止调阈值/禁 sweep**。
  例外：``conf_v2_*`` 一组是竞品字节确证常量（豁免口径见 DECISIONS.md 2026-09-28）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain import Alternative, Confidence, ConfidenceLevel, TimeSpan
from infrastructure.config import ConfidenceConfig

from .confidence_v2 import confidence_v2

# 软信号权重索引（顺序与 ConfidenceConfig.weights 对应）
W_RANK = 0
W_MARGIN = 1
W_NREPS = 2
W_COVERAGE = 3
W_CONSISTENCY = 4
W_FINLOC = 5

# conf_v2 并行通道的降档表（只降不升，护栏豁免口径见 DECISIONS.md 2026-09-28）
_DOWNGRADE = {ConfidenceLevel.HIGH: ConfidenceLevel.MEDIUM,
              ConfidenceLevel.MEDIUM: ConfidenceLevel.LOW,
              ConfidenceLevel.LOW: ConfidenceLevel.LOW}


@dataclass
class ConfidenceAssessment:
    """一条候选的置信评估结果。"""

    confidence: Confidence
    montage_flag: bool
    alternatives: list[Alternative]
    hard_flags: tuple[str, ...]
    confidence_v2: dict | None = None  # 竞品四项加权诊断（仅 conf_v2_enabled 时非 None）


class ConfidenceEngine:
    """工程化置信度：候选排名 + 定位结构 -> 三档置信 + 原因 + 硬 flag。"""

    def __init__(self, cfg: ConfidenceConfig | None = None):
        self.cfg = cfg or ConfidenceConfig()

    # ------------------------------------------------------------------ #
    # multi-evidence 置信评估（EvidenceLocalizer 产物；产品主路径）
    # ------------------------------------------------------------------ #
    def assess_evidence(self, evidence) -> ConfidenceAssessment:
        """对 ``EvidenceResult`` 做 multi-evidence 置信评估（多证据一致性）。

        旧 ``assess``（single-answer 候选窗）保留为 legacy。``evidence`` 是
        ``EvidenceLocalizer.localize`` 产物（EvidenceResult）。信号全部来自证据
        簇（非裸相似度），守住「不用余弦直接当置信」纪律。
        """
        prim = evidence.primary
        if prim is None or prim.original_span is None:
            return ConfidenceAssessment(
                Confidence(ConfidenceLevel.LOW, 0.0, ("no_evidence",)),
                montage_flag=False, alternatives=[], hard_flags=("no_evidence",))

        montage = evidence.mode == "montage"
        n_kept = len(evidence.spans)

        purity_norm = 1.0 / max(n_kept, 1)                              # 单证据=1，多证据降纯度
        margin_norm = self._evidence_margin(prim, evidence.secondary)   # 主 vs 次证据簇
        qcov_norm = float(np.clip(evidence.evidence_qcov, 0.0, 1.0))    # 时序覆盖（n_reps 类比）
        cover_norm = float(np.clip((prim.finloc.best_cover if prim.finloc else 0.0)
                                   or prim.cover, 0.0, 1.0))           # 主簇 coverage
        consist_norm = float(np.clip(prim.best_sim or 0.0, 0.0, 1.0))  # 结构信号（覆盖均值，非裸相似度）
        stability_norm = float(np.clip(prim.finloc.span_stability if prim.finloc else 0.0,
                                       0.0, 1.0))

        w = list(self.cfg.weights)
        raw = (w[W_RANK] * purity_norm + w[W_MARGIN] * margin_norm
               + w[W_NREPS] * qcov_norm + w[W_COVERAGE] * cover_norm
               + w[W_CONSISTENCY] * consist_norm + w[W_FINLOC] * stability_norm)

        flags = self._evidence_flags(evidence, prim, cover_norm, margin_norm, qcov_norm)
        dark = self._evidence_dark(evidence, prim, cover_norm)
        score = float(np.clip(raw, 0.0, 1.0))
        if dark:
            score *= max(0.0, float(self.cfg.dark_penalty))
            score = float(np.clip(score, 0.0, 1.0))

        level = self._level(flags, score, dark)
        reasons = self._evidence_reasons(evidence, prim, flags, dark, margin_norm,
                                         qcov_norm, stability_norm)

        v2_diag = None
        if self.cfg.conf_v2_enabled:
            level, reasons, v2_diag = self._apply_conf_v2(evidence, level, reasons)

        return ConfidenceAssessment(
            Confidence(level, round(score, 4), tuple(reasons)),
            montage_flag=montage,
            alternatives=self._evidence_alternatives(prim, evidence.spans),
            hard_flags=tuple(sorted(flags)),
            confidence_v2=v2_diag)

    def _apply_conf_v2(self, evidence, level: ConfidenceLevel,
                       reasons: list[str]) -> tuple[ConfidenceLevel, list[str], dict]:
        """竞品四项加权并行通道：``score_v2`` 低于门限时**降一档**（永不升档）。

        只改档位与 reasons，**不改现行 ``score``**（两值并存，便于四片 A/B 对照）。
        硬 flag 一票 LOW 的语义在现行链路保留，故本通道对已 LOW 的段只是补充原因。
        """
        cfg = self.cfg
        score_v2, gate_reasons, signals = confidence_v2(
            evidence, local_w=cfg.conf_v2_local_weight, coarse_w=cfg.conf_v2_coarse_weight,
            consistency_w=cfg.conf_v2_consistency_weight, margin_w=cfg.conf_v2_margin_weight,
            min_valid_samples=cfg.conf_v2_min_valid_samples,
            min_support_ratio=cfg.conf_v2_min_support_ratio,
            min_local_score=cfg.conf_v2_min_local_score,
            min_candidate_margin=cfg.conf_v2_min_candidate_margin)
        signals["min_score"] = cfg.conf_v2_min_score
        signals["stable"] = score_v2 >= cfg.conf_v2_min_score
        if score_v2 >= cfg.conf_v2_min_score:
            return level, reasons, signals
        downgraded = _DOWNGRADE[level]
        out = list(reasons) + (list(gate_reasons) or ["weighted_confidence_low"])
        if downgraded is not level:
            out.append("confidence_v2_downgraded")
        return downgraded, out, signals

    def _evidence_margin(self, prim, secondary) -> float:
        """主 vs 次证据簇的 best_sim 边际（无 secondary -> 1.0）。"""
        if secondary is None:
            return 1.0
        p = prim.best_sim or 0.0
        s = secondary.best_sim or 0.0
        denom = max(abs(p), 1e-6)
        return float(np.clip((p - s) / denom, 0.0, 1.0))

    def _evidence_flags(self, evidence, prim, cover_norm, margin_norm, qcov_norm):
        cfg, flags = self.cfg, set()
        montage = evidence.mode == "montage"
        if montage:
            flags.add("montage")
        fl = prim.finloc
        if fl is None or fl.span is None or fl.run_len_frames <= 1 or fl.run_len_s < cfg.min_run_s:
            flags.add("finloc_unstable")
        if prim.original_span is not None:
            w = prim.original_span[1] - prim.original_span[0]
            if w >= cfg.window_width_max_s or w < cfg.window_width_min_s:
                flags.add("source_window_anomaly")
        if qcov_norm < cfg.qcov_dispersed or evidence.dispersion >= cfg.sim_std_high:
            flags.add("query_coverage_dispersed")
        if evidence.n_strong_clusters >= 2 and margin_norm < cfg.margin_low:
            flags.add("low_candidate_margin")
        if evidence.n_strong_clusters >= 2:
            flags.add("multiple_similar_candidates")
        return flags

    def _evidence_dark(self, evidence, prim, cover_norm) -> bool:
        """暗内容语义混淆（镜像 _dark_confusion）：相似度高但覆盖低或多证据。"""
        return (prim.best_sim or 0.0) >= self.cfg.sim_high \
            and (cover_norm < self.cfg.cov_low or evidence.mode == "montage")

    def _evidence_reasons(self, evidence, prim, flags, dark, margin_norm,
                          qcov_norm, stability_norm) -> list[str]:
        cfg, r = self.cfg, []
        r.append("multiple_evidence_regions" if evidence.mode == "montage"
                 else "single_evidence_region")
        if prim.moments:
            r.append("frame_precise_moment")
        if qcov_norm >= cfg.qcov_dispersed:
            r.append("high_query_coverage")
        else:
            r.append("low_query_coverage")
        if "query_coverage_dispersed" in flags:
            r.append("query_coverage_dispersed")
        if stability_norm >= 0.6:
            r.append("stable_temporal_localization")
        elif "finloc_unstable" in flags:
            r.append("finloc_unstable")
        if margin_norm < cfg.margin_low:
            r.append("low_candidate_margin")
        if "multiple_similar_candidates" in flags:
            r.append("multiple_similar_candidates")
        if "montage" in flags:
            r.append("possible_montage")
        if "source_window_anomaly" in flags:
            r.append("source_window_anomaly")
        if dark:
            r.append("dark_scene_semantic_confusion")
        seen, out = set(), []
        for reason in r:
            if reason not in seen:
                seen.add(reason)
                out.append(reason)
        return out

    def _evidence_alternatives(self, prim, spans) -> list[Alternative]:
        """非 primary 的保留证据簇 -> Alternative（clean 无 secondary -> []）。"""
        if prim is None:
            return []
        p = prim.best_sim or 0.0
        denom = max(abs(p), 1e-6)
        alts = []
        for s in spans:
            if s is prim or s.original_span is None:
                continue
            ss = s.best_sim or 0.0
            rel = float(np.clip(ss / denom, 0.0, 1.0))
            near = (p - ss) <= self.cfg.similar_band * denom
            alts.append(Alternative(TimeSpan(s.original_span[0], s.original_span[1]),
                                    ConfidenceLevel.MEDIUM if near else ConfidenceLevel.LOW,
                                    round(rel, 3)))
        return alts

    # ------------------------------------------------------------------ #
    # 档位 / reasons / alternatives
    # ------------------------------------------------------------------ #
    def _level(self, flags, score, dark_confusion) -> ConfidenceLevel:
        if flags:
            return ConfidenceLevel.LOW
        if score >= self.cfg.high_threshold:
            # 暗混淆不冒 HIGH（避免"看似高置信、实际错"）
            return ConfidenceLevel.MEDIUM if dark_confusion else ConfidenceLevel.HIGH
        if score >= self.cfg.medium_threshold:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

