"""Unit tests for the conf_v2 parallel channel (competitor four-item weighted confidence).

移植口径见 .agent/DECISIONS.md 2026-09-28：并行通道、只降不升、默认关。
Deterministic: synthetic EvidenceResult/EvidenceSpan, no DINOv2 / real video / GPU.

Run with the venv python:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_confidence_v2 -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from domain import ConfidenceLevel
from engine.confidence import ConfidenceEngine, confidence_v2
from engine.localization import EvidenceResult, LocalizationResult
from engine.localization.evidence_localize import EvidenceSpan

from infrastructure.config import ConfidenceConfig


def _loc(best_cover=0.9, span=(100.0, 110.0), run_len_s=8.0, span_stability=1.0,
         coverage_quality=1.0, multi_island=False):
    return LocalizationResult(
        span=span, best_cover=best_cover, run_len_s=run_len_s, run_len_frames=16,
        num_runs=2 if multi_island else 1, significant_runs=2 if multi_island else 1,
        largest_gap_s=6.0 if multi_island else 0.0, span_coverage=1.0,
        coverage_quality=coverage_quality, span_stability=span_stability,
        multi_island=multi_island, window_width=18.0, mean_sim=0.8, peak_sim=0.95,
        n_query=10)


def _span(best_sim=0.8, cover=0.9, query_frames=10, finloc=None, span=(100.0, 110.0)):
    return EvidenceSpan(edited_interval=(0.0, 5.0), edited_frames=[0.0, 1.0, 2.0],
                        original_span=span, cover=cover, best_sim=best_sim,
                        cluster_frames=query_frames, query_frames=query_frames,
                        finloc=finloc or _loc(best_cover=cover))


def _evidence(primary=None, secondary=None, mode="clean", qcov=1.0, n_strong=1):
    spans = [s for s in (primary, secondary) if s is not None]
    return EvidenceResult(mode=mode, spans=spans, n_clusters=len(spans),
                          n_strong_clusters=n_strong, n_query=10,
                          evidence_qcov=qcov, primary=primary, secondary=secondary)


def _cfg(**overrides):
    cfg = ConfidenceConfig()
    cfg.conf_v2_enabled = True
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


class ConstantsTest(unittest.TestCase):
    """竞品 profile_v1 字节确证常量不得被当作可调占位乱改。"""

    def test_weights_match_competitor(self):
        cfg = ConfidenceConfig()
        self.assertEqual((cfg.conf_v2_local_weight, cfg.conf_v2_coarse_weight,
                          cfg.conf_v2_consistency_weight, cfg.conf_v2_margin_weight),
                         (0.4, 0.3, 0.2, 0.1))
        self.assertAlmostEqual(sum([cfg.conf_v2_local_weight, cfg.conf_v2_coarse_weight,
                                    cfg.conf_v2_consistency_weight,
                                    cfg.conf_v2_margin_weight]), 1.0, places=9)

    def test_gates_match_competitor(self):
        cfg = ConfidenceConfig()
        self.assertEqual(cfg.conf_v2_min_score, 0.6)              # min_confidence_score
        self.assertEqual(cfg.conf_v2_min_valid_samples, 3)        # min_valid_samples
        self.assertEqual(cfg.conf_v2_min_support_ratio, 0.35)     # min_support_ratio
        self.assertEqual(cfg.conf_v2_min_local_score, 0.55)       # min_local_score
        self.assertEqual(cfg.conf_v2_min_candidate_margin, 0.03)  # min_candidate_margin

    def test_disabled_by_default(self):
        self.assertFalse(ConfidenceConfig().conf_v2_enabled)


class PureFunctionTest(unittest.TestCase):

    def test_weighted_sum_matches_hand_calculation(self):
        prim = _span(best_sim=0.8)
        ev = _evidence(primary=prim, qcov=1.0)
        score, reasons, sig = confidence_v2(ev)
        self.assertAlmostEqual(score, 0.4 * 0.8 + 0.3 * 1.0 + 0.2 * 1.0 + 0.1 * 1.0, places=6)
        self.assertEqual(reasons, ())
        self.assertEqual(sig["score"], 0.92)

    def test_no_primary(self):
        score, reasons, sig = confidence_v2(_evidence(primary=None))
        self.assertEqual((score, reasons), (0.0, ("no_evidence",)))
        self.assertEqual(sig, {})

    def test_each_gate_fires(self):
        cases = {
            "insufficient_samples": _evidence(primary=_span(query_frames=2)),
            "weak_offset_support": _evidence(primary=_span(finloc=_loc(coverage_quality=0.1))),
            "weak_local_consistency": _evidence(primary=_span(best_sim=0.4)),
            "small_candidate_margin": _evidence(
                primary=_span(best_sim=0.80),
                secondary=_span(best_sim=0.80 - 0.80 * 0.02),   # margin 0.02 < 0.03
                n_strong=2, mode="montage"),
        }
        for expected, ev in cases.items():
            _, reasons, _ = confidence_v2(ev)
            self.assertIn(expected, reasons, f"{expected} should be reported")

    def test_clean_single_cluster_saturates_margin(self):
        """护栏记录：clean 无 secondary 时 margin 恒 1.0，不是本通道的降档主力。"""
        _, _, sig = confidence_v2(_evidence(primary=_span(best_sim=0.8)))
        self.assertEqual(sig["margin"], 1.0)


class EngineIntegrationTest(unittest.TestCase):

    def test_disabled_is_byte_identical_to_current_behaviour(self):
        prim = _span(best_sim=0.45, cover=0.9, query_frames=2,
                     finloc=_loc(best_cover=0.9, coverage_quality=0.2))
        ev = _evidence(primary=prim, qcov=0.5)
        off = ConfidenceEngine(ConfidenceConfig()).assess_evidence(ev)
        on = ConfidenceEngine(_cfg()).assess_evidence(ev)
        self.assertIsNone(off.confidence_v2)
        self.assertEqual(off.confidence.level, ConfidenceLevel.HIGH)  # 现行链路判 HIGH
        self.assertEqual(on.confidence.level, ConfidenceLevel.MEDIUM)  # 只降一档
        self.assertEqual(on.confidence.score, off.confidence.score)   # 不改 score 数值

    def test_stable_segment_unchanged_when_enabled(self):
        ev = _evidence(primary=_span(best_sim=0.85))
        base = ConfidenceEngine(ConfidenceConfig()).assess_evidence(ev)
        on = ConfidenceEngine(_cfg()).assess_evidence(ev)
        self.assertEqual(on.confidence.level, base.confidence.level)
        self.assertEqual(on.confidence.reasons, base.confidence.reasons)
        self.assertTrue(on.confidence_v2["stable"])

    def test_downgrade_adds_reasons_and_marks_downgraded(self):
        ev = _evidence(primary=_span(best_sim=0.45, cover=0.9, query_frames=2,
                                     finloc=_loc(best_cover=0.9, coverage_quality=0.2)),
                       qcov=0.5)
        on = ConfidenceEngine(_cfg()).assess_evidence(ev)
        for expected in ("insufficient_samples", "weak_offset_support",
                         "weak_local_consistency", "confidence_v2_downgraded"):
            self.assertIn(expected, on.confidence.reasons)
        self.assertEqual(on.confidence_v2["score"], 0.47)
        self.assertFalse(on.confidence_v2["stable"])

    def test_never_upgrades_a_flagged_low(self):
        """硬 flag 判 LOW 的段即使 v2 稳定也不升档。"""
        prim = _span(best_sim=0.8, finloc=_loc(best_cover=0.9, multi_island=True))
        ev = _evidence(primary=prim, qcov=1.0, mode="montage")
        base = ConfidenceEngine(ConfidenceConfig()).assess_evidence(ev)
        self.assertEqual(base.confidence.level, ConfidenceLevel.LOW)
        on = ConfidenceEngine(_cfg()).assess_evidence(ev)
        self.assertEqual(on.confidence.level, ConfidenceLevel.LOW)
        self.assertNotIn("confidence_v2_downgraded", on.confidence.reasons)

    def test_already_low_only_appends_gate_reasons(self):
        prim = _span(best_sim=0.45, finloc=_loc(best_cover=0.9, multi_island=True,
                                                coverage_quality=0.2),
                     query_frames=2)
        ev = _evidence(primary=prim, qcov=0.5, mode="montage")
        on = ConfidenceEngine(_cfg()).assess_evidence(ev)
        self.assertEqual(on.confidence.level, ConfidenceLevel.LOW)
        self.assertIn("weak_local_consistency", on.confidence.reasons)
        self.assertNotIn("confidence_v2_downgraded", on.confidence.reasons)

    def test_threshold_is_configurable(self):
        ev = _evidence(primary=_span(best_sim=0.8))
        strict = ConfidenceEngine(_cfg(conf_v2_min_score=0.95)).assess_evidence(ev)
        self.assertEqual(strict.confidence.level, ConfidenceLevel.MEDIUM)
        self.assertIn("weighted_confidence_low", strict.confidence.reasons)


if __name__ == "__main__":
    unittest.main(verbosity=2)
