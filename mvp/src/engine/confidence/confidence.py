"""engine.confidence — 工程化置信度（REWRITE/NEW，产品核心）。

输入：已排序候选（``rank`` / ``rank_margin``）+ best candidate 字段（``n_reps`` /
``qcov`` / ``consistency`` / ``sim_std`` / ``scene_div``）+ 精定位信号（``best_cover`` /
``span_stability`` / ``coverage_quality`` / ``multi_island``）；输出：三档置信
（HIGH/MEDIUM/LOW）+ ``score`` + ``reasons`` + ``hard_flags`` + ``montage_flag`` +
``alternatives``。

设计来源：CONFIDENCE_DESIGN.md。**关键纪律**（§5/§6/§7 + 研究护栏）：
- ``score`` 是工程 confidence score，**不是**模型概率，禁止展示为百分比概率。
- **不使用** start_err / end_err / IoU（运行时无 GT）。
- **不使用**余弦相似度直接当置信度（错误场景 CLS 可能高于正确来源）。
- 阈值/权重均为**结构占位**（CONFIDENCE_DESIGN §6 诚实声明：未标定），本阶段**禁止调阈值/禁 sweep**。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain import Alternative, Candidate, Confidence, ConfidenceLevel, TimeSpan
from engine.localization.finloc import LocalizationResult
from infrastructure.config import ConfidenceConfig

# 软信号权重索引（顺序与 ConfidenceConfig.weights 对应）
W_RANK = 0
W_MARGIN = 1
W_NREPS = 2
W_COVERAGE = 3
W_CONSISTENCY = 4
W_FINLOC = 5


@dataclass
class ConfidenceAssessment:
    """一条候选的置信评估结果。"""

    confidence: Confidence
    montage_flag: bool
    alternatives: list[Alternative]
    hard_flags: tuple[str, ...]


class ConfidenceEngine:
    """工程化置信度：候选排名 + 定位结构 -> 三档置信 + 原因 + 硬 flag。"""

    def __init__(self, cfg: ConfidenceConfig | None = None):
        self.cfg = cfg or ConfidenceConfig()

    # ------------------------------------------------------------------ #
    # 主入口
    # ------------------------------------------------------------------ #
    def assess(self, candidates: list[Candidate], loc: LocalizationResult, *,
               best: Candidate | None = None) -> ConfidenceAssessment:
        """对被定位的候选 ``best``（默认 ``candidates[0]``）评估置信。

        ``candidates`` 应为已按 ``v2_score`` 降序的结果（``produce_candidates`` 输出）；
        ``loc`` 是对 ``best`` 跑 ``finloc_window`` 的结果。
        """
        cands = list(candidates)
        if best is None:
            best = cands[0] if cands else None
        if best is None:
            return ConfidenceAssessment(
                Confidence(ConfidenceLevel.LOW, 0.0, ("no_candidate",)),
                montage_flag=False, alternatives=[], hard_flags=("no_candidate",))

        rank = (cands.index(best) + 1) if (best in cands) else 1
        best_score = float(best.rank_score)
        margin, margin_norm = self._margin(cands, best, best_score)

        # ---- 软信号归一化（占位，待标定） ----
        rank_norm = 1.0 / max(rank, 1)
        n_reps_norm = best.n_reps / max(max((c.n_reps for c in cands), default=1), 1)
        coverage_norm = float(np.clip(loc.best_cover, 0.0, 1.0))
        consistency_norm = float(np.clip(best.consistency, 0.0, 1.0))
        finloc_norm = float(np.clip(loc.span_stability, 0.0, 1.0))

        w = list(self.cfg.weights)
        raw = (w[W_RANK] * rank_norm + w[W_MARGIN] * margin_norm
               + w[W_NREPS] * n_reps_norm + w[W_COVERAGE] * coverage_norm
               + w[W_CONSISTENCY] * consistency_norm + w[W_FINLOC] * finloc_norm)

        # ---- 硬 flag / 暗场景降险 ----
        flags = self._hard_flags(best, loc, cands, best_score, margin, margin_norm)
        dark_confusion = self._dark_confusion(best, loc)
        montage_flag = self._montage_flag(best, loc, margin_norm)

        score = float(np.clip(raw, 0.0, 1.0))
        if dark_confusion:
            score *= max(0.0, float(self.cfg.dark_penalty))
            score = float(np.clip(score, 0.0, 1.0))

        level = self._level(flags, score, dark_confusion)
        reasons = self._reasons(rank, best, loc, margin_norm, flags, dark_confusion,
                                n_reps_norm, finloc_norm)

        return ConfidenceAssessment(
            Confidence(level, round(score, 4), tuple(reasons)),
            montage_flag=montage_flag,
            alternatives=self._alternatives(cands, best, best_score),
            hard_flags=tuple(sorted(flags)))

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
        return ConfidenceAssessment(
            Confidence(level, round(score, 4), tuple(reasons)),
            montage_flag=montage,
            alternatives=self._evidence_alternatives(prim, evidence.spans),
            hard_flags=tuple(sorted(flags)))

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
    # 信号计算
    # ------------------------------------------------------------------ #
    def _margin(self, cands, best, best_score):
        if len(cands) < 2:
            return None, 1.0
        second = max((c.rank_score for c in cands if c is not best), default=0.0)
        margin = best_score - second
        denom = max(abs(best_score), 1e-6)
        return float(margin), float(np.clip(margin / denom, 0.0, 1.0))

    def _hard_flags(self, best, loc, cands, best_score, margin, margin_norm):
        cfg, flags = self.cfg, set()

        if self._montage_flag(best, loc, margin_norm):
            flags.add("montage")
        if loc.span is None or loc.run_len_frames <= 1 or loc.run_len_s < cfg.min_run_s:
            flags.add("finloc_unstable")
        if best.width >= cfg.window_width_max_s or best.width < cfg.window_width_min_s:
            flags.add("source_window_anomaly")

        if self._query_dispersed(best):
            flags.add("query_coverage_dispersed")
        if margin is not None and margin_norm < cfg.margin_low:
            flags.add("low_candidate_margin")

        denom = max(abs(best_score), 1e-6)
        similar = sum(1 for c in cands if c is not best
                      and (best_score - c.rank_score) <= cfg.similar_band * denom)
        if len(cands) >= 2 and similar >= cfg.max_similar:
            flags.add("multiple_similar_candidates")

        return flags

    def _query_dispersed(self, best) -> bool:
        cfg = self.cfg
        return (best.n_reps < cfg.nreps_dispersed and best.qcov < cfg.qcov_dispersed) \
            or best.sim_std >= cfg.sim_std_high

    def _dark_confusion(self, best, loc) -> bool:
        """暗内容语义混淆（CONFIDENCE_DESIGN §5）：外观相似度高但结构异常。"""
        return best.mean_sim >= self.cfg.sim_high \
            and (loc.best_cover < self.cfg.cov_low or loc.multi_island)

    def _montage_flag(self, best, loc, margin_norm) -> bool:
        """多岛（结构）或"覆盖分散 且 margin 低"（CONFIDENCE_DESIGN §6 路径）。"""
        query_dispersed = (best.n_reps < self.cfg.nreps_dispersed
                           or best.qcov < self.cfg.qcov_dispersed
                           or best.scene_div >= self.cfg.scene_div_montage)
        return loc.multi_island or (query_dispersed and margin_norm < self.cfg.margin_low)

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

    def _reasons(self, rank, best, loc, margin_norm, flags, dark_confusion,
                 n_reps_norm, finloc_norm) -> list[str]:
        cfg, r = self.cfg, []

        r.append("rank1" if rank == 1 else f"rank{rank}")

        if best.n_reps >= cfg.nreps_dispersed:
            r.append("high_query_coverage")
        else:
            r.append("low_query_coverage")
        if "query_coverage_dispersed" in flags:
            r.append("query_coverage_dispersed")

        if finloc_norm >= 0.6:
            r.append("stable_temporal_localization")
        elif "finloc_unstable" in flags:
            r.append("finloc_unstable")

        if margin_norm < cfg.margin_low:
            r.append("low_candidate_margin")
        elif margin_norm >= 0.5:
            r.append("large_candidate_margin")
        if "multiple_similar_candidates" in flags:
            r.append("multiple_similar_candidates")

        if "montage" in flags:
            r.append("possible_montage")
        if "source_window_anomaly" in flags:
            r.append("source_window_anomaly")
        if dark_confusion:
            r.append("dark_scene_semantic_confusion")

        # 去重且保持确定性顺序
        seen, out = set(), []
        for reason in r:
            if reason not in seen:
                seen.add(reason)
                out.append(reason)
        return out

    def _alternatives(self, cands, best, best_score) -> list[Alternative]:
        cfg, alts, denom = self.cfg, [], max(abs(best_score), 1e-6)
        for c in cands:
            if c is best:
                continue
            rel = float(np.clip(c.rank_score / denom, 0.0, 1.0))
            near = (best_score - c.rank_score) <= cfg.similar_band * denom
            level = ConfidenceLevel.MEDIUM if near else ConfidenceLevel.LOW
            alts.append(Alternative(TimeSpan(c.start, c.end), level, round(rel, 3)))
        return alts
