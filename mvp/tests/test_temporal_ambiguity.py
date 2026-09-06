"""temporal_ambiguity 单测(NEXT_STEPS ⑥):时间轴→Ambiguity——外部时序信号降档。

背景: Ambiguity 原型(2026-09-01)证明内部置信信号无法分离正确/错配 HIGH;
时间轴是外部独立信号: 定位与前后段严重冲突(离群) = 可疑 → 离群段降档转人工。
只改置信档位, 不改定位; 被 temporal_repair 修复的段不再离群 → 零误伤。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from app.locator_service import SourceLocatorService
from domain import Confidence, ConfidenceLevel, Result, TimeSpan


def _result(edited, orig_span, level=ConfidenceLevel.HIGH, score=0.8):
    return Result(edited=TimeSpan(*edited), original=TimeSpan(*orig_span),
                  confidence=Confidence(level, score))


class TemporalAmbiguityFlagTest(unittest.TestCase):
    """纯逻辑:离群段 HIGH→MEDIUM + reason; 非离群/未定位/已修复段不动。"""

    def _srv(self):
        return SourceLocatorService()

    def test_outlier_high_downgraded(self):
        """三段:首尾接近(100-102/104-106), 中段远离(900-902)→ 中段 HIGH 降 MEDIUM。"""
        srv = self._srv()
        results = [
            _result((0.0, 1.0), (100.0, 102.0)),
            _result((1.5, 2.5), (900.0, 902.0), level=ConfidenceLevel.HIGH, score=0.9),
            _result((3.0, 4.0), (104.0, 106.0)),
        ]
        srv._apply_temporal_ambiguity(results, cfg=srv.config.pipeline)
        r = results[1]
        self.assertEqual(r.confidence.level, ConfidenceLevel.MEDIUM)
        self.assertIn("temporal_outlier_ambiguous", r.confidence.reasons)
        # 定位未被改动(只改置信)
        self.assertEqual((r.original.start, r.original.end), (900.0, 902.0))

    def test_inline_segments_untouched(self):
        """前后段远离(非"彼此接近")→ 本段即使不同也不触发(真实跳切不误伤)。"""
        srv = self._srv()
        results = [
            _result((0.0, 1.0), (100.0, 102.0)),
            _result((1.5, 2.5), (900.0, 902.0), level=ConfidenceLevel.HIGH, score=0.9),
            _result((3.0, 4.0), (1500.0, 1502.0)),  # 前后段 gap > neighbor_gap_s
        ]
        srv._apply_temporal_ambiguity(results, cfg=srv.config.pipeline)
        self.assertEqual(results[1].confidence.level, ConfidenceLevel.HIGH)
        self.assertNotIn("temporal_outlier_ambiguous", results[1].confidence.reasons)

    def test_low_level_not_upgraded(self):
        """离群但已是 MEDIUM/LOW 的段不升不降(只对 HIGH 生效)。"""
        srv = self._srv()
        results = [
            _result((0.0, 1.0), (100.0, 102.0)),
            _result((1.5, 2.5), (900.0, 902.0), level=ConfidenceLevel.MEDIUM, score=0.6),
            _result((3.0, 4.0), (104.0, 106.0)),
        ]
        srv._apply_temporal_ambiguity(results, cfg=srv.config.pipeline)
        self.assertEqual(results[1].confidence.level, ConfidenceLevel.MEDIUM)
        self.assertNotIn("temporal_outlier_ambiguous", results[1].confidence.reasons)

    def test_not_in_source_and_failures_skipped(self):
        """未定位(not_in_source/失败/零宽)段不参与三角判定。"""
        srv = self._srv()
        r0 = _result((0.0, 1.0), (100.0, 102.0))
        r1 = _result((1.5, 2.5), (900.0, 902.0), level=ConfidenceLevel.HIGH)
        r1.not_in_source = True
        r2 = _result((3.0, 4.0), (104.0, 106.0))
        srv._apply_temporal_ambiguity([r0, r1, r2], cfg=srv.config.pipeline)
        self.assertEqual(r1.confidence.level, ConfidenceLevel.HIGH)  # 不参与 → 不动

    def test_len_less_than_3_noop(self):
        srv = self._srv()
        results = [_result((0.0, 1.0), (100.0, 102.0)),
                   _result((1.5, 2.5), (900.0, 902.0), level=ConfidenceLevel.HIGH)]
        srv._apply_temporal_ambiguity(results, cfg=srv.config.pipeline)
        self.assertEqual(results[1].confidence.level, ConfidenceLevel.HIGH)

    def test_disabled_noop(self):
        srv = self._srv()
        results = [
            _result((0.0, 1.0), (100.0, 102.0)),
            _result((1.5, 2.5), (900.0, 902.0), level=ConfidenceLevel.HIGH, score=0.9),
            _result((3.0, 4.0), (104.0, 106.0)),
        ]
        cfg = srv.config.pipeline
        cfg.temporal_ambiguity_enabled = False
        srv._apply_temporal_ambiguity(results, cfg=cfg)
        self.assertEqual(results[1].confidence.level, ConfidenceLevel.HIGH)


class TemporalAmbiguityConfigTest(unittest.TestCase):
    """ta_max_downgrade 配置生效。"""

    def test_downgrade_to_low_when_configured(self):
        srv = self._srv = SourceLocatorService()
        results = [
            _result((0.0, 1.0), (100.0, 102.0)),
            _result((1.5, 2.5), (900.0, 902.0), level=ConfidenceLevel.HIGH, score=0.9),
            _result((3.0, 4.0), (104.0, 106.0)),
        ]
        cfg = srv.config.pipeline
        cfg.ta_max_downgrade = "LOW"
        srv._apply_temporal_ambiguity(results, cfg=cfg)
        self.assertEqual(results[1].confidence.level, ConfidenceLevel.LOW)

    def test_invalid_downgrade_falls_back_medium(self):
        srv = SourceLocatorService()
        results = [
            _result((0.0, 1.0), (100.0, 102.0)),
            _result((1.5, 2.5), (900.0, 902.0), level=ConfidenceLevel.HIGH, score=0.9),
            _result((3.0, 4.0), (104.0, 106.0)),
        ]
        cfg = srv.config.pipeline
        cfg.ta_max_downgrade = "BOGUS"
        srv._apply_temporal_ambiguity(results, cfg=cfg)
        self.assertEqual(results[1].confidence.level, ConfidenceLevel.MEDIUM)


if __name__ == "__main__":
    unittest.main()
