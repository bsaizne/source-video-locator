"""单调弱先验进候选生成(NEXT_STEPS ②③)单测: Ambiguous 型段用前序锚点弱倾向。

触发: primary 在时序带外(>ta_band_s) + 存在带内竞争候选(cover 落差<=ta_max_cover_drop) → 切换。
逃生门: 唯一强候选(落差大)/primary 已在带内/全部带外/首段(prev_mid=None)/禁用 → 不切。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app.locator_service import SourceLocatorService
from engine.localization.evidence_localize import EvidenceResult, EvidenceSpan


def _span(span, cover, sim):
    return EvidenceSpan((0.0, 1.0), [0.0], span, cover, sim, 2, query_frames=1)


class TimelinePriorSwitchTest(unittest.TestCase):
    """切换路径: primary 带外 + 带内竞争候选。"""

    def _srv(self):
        return SourceLocatorService()

    def test_switches_to_inband_competitive(self):
        """primary(100-102, cover0.9) 带外; 候选(45-47, cover0.85) 在锚点 46±45s 带内 → 切。"""
        srv = self._srv()
        prim = _span((100.0, 102.0), 0.90, 0.80)
        alt = _span((45.0, 47.0), 0.85, 0.80)
        ev = EvidenceResult(mode="montage", spans=[prim, alt], primary=prim, secondary=None,
                            n_strong_clusters=2)
        ok = srv._apply_timeline_prior(ev, prev_mid=46.0, cfg=srv.config.pipeline)
        self.assertTrue(ok)
        self.assertIs(ev.primary, alt)          # 切到带内候选
        self.assertIs(ev.secondary, prim)       # 旧 primary 留痕为 secondary

    def test_no_switch_strong_primary(self):
        """primary 显著更强(cover 0.95 vs 0.60, 落差>0.10) → 不切(唯一强候选)。"""
        srv = self._srv()
        prim = _span((100.0, 102.0), 0.95, 0.80)
        alt = _span((45.0, 47.0), 0.60, 0.80)
        ev = EvidenceResult(mode="montage", spans=[prim, alt], primary=prim, secondary=alt,
                            n_strong_clusters=2)
        ok = srv._apply_timeline_prior(ev, prev_mid=46.0, cfg=srv.config.pipeline)
        self.assertFalse(ok)
        self.assertIs(ev.primary, prim)

    def test_no_switch_primary_in_band(self):
        """primary 已在带内(44-46, 锚点46) → 不做带内偏向。"""
        srv = self._srv()
        prim = _span((44.0, 46.0), 0.85, 0.80)
        alt = _span((100.0, 102.0), 0.80, 0.80)
        ev = EvidenceResult(mode="montage", spans=[prim, alt], primary=prim, secondary=alt,
                            n_strong_clusters=2)
        ok = srv._apply_timeline_prior(ev, prev_mid=46.0, cfg=srv.config.pipeline)
        self.assertFalse(ok)
        self.assertIs(ev.primary, prim)

    def test_no_switch_all_out_of_band(self):
        """全部候选带外(真实倒叙/闪回) → 不强行拉进带内。"""
        srv = self._srv()
        prim = _span((800.0, 802.0), 0.85, 0.80)
        alt = _span((900.0, 902.0), 0.80, 0.80)
        ev = EvidenceResult(mode="montage", spans=[prim, alt], primary=prim, secondary=alt,
                            n_strong_clusters=2)
        ok = srv._apply_timeline_prior(ev, prev_mid=46.0, cfg=srv.config.pipeline)
        self.assertFalse(ok)
        self.assertIs(ev.primary, prim)

    def test_no_switch_single_span(self):
        """唯一候选(可靠命中) → 不碰。"""
        srv = self._srv()
        prim = _span((100.0, 102.0), 0.90, 0.80)
        ev = EvidenceResult(mode="clean", spans=[prim], primary=prim, secondary=None,
                            n_strong_clusters=1)
        ok = srv._apply_timeline_prior(ev, prev_mid=46.0, cfg=srv.config.pipeline)
        self.assertFalse(ok)

    def test_no_switch_no_prev(self):
        """首段/前段未定位(prev_mid=None) → 不触发。"""
        srv = self._srv()
        prim = _span((100.0, 102.0), 0.90, 0.80)
        alt = _span((45.0, 47.0), 0.85, 0.80)
        ev = EvidenceResult(mode="montage", spans=[prim, alt], primary=prim, secondary=alt,
                            n_strong_clusters=2)
        ok = srv._apply_timeline_prior(ev, prev_mid=None, cfg=srv.config.pipeline)
        self.assertFalse(ok)

    def test_disabled_noop(self):
        srv = self._srv()
        cfg = srv.config.pipeline
        cfg.timeline_prior_enabled = False
        prim = _span((100.0, 102.0), 0.90, 0.80)
        alt = _span((45.0, 47.0), 0.85, 0.80)
        ev = EvidenceResult(mode="montage", spans=[prim, alt], primary=prim, secondary=alt,
                            n_strong_clusters=2)
        ok = srv._apply_timeline_prior(ev, prev_mid=46.0, cfg=cfg)
        self.assertFalse(ok)
        self.assertIs(ev.primary, prim)

    def test_no_switch_candidate_out_of_band(self):
        """primary 带外(100-102) 但唯一候选也在带外(500-502) → 不切。"""
        srv = self._srv()
        prim = _span((100.0, 102.0), 0.85, 0.80)
        alt = _span((500.0, 502.0), 0.84, 0.80)
        ev = EvidenceResult(mode="montage", spans=[prim, alt], primary=prim, secondary=alt,
                            n_strong_clusters=2)
        ok = srv._apply_timeline_prior(ev, prev_mid=46.0, cfg=srv.config.pipeline)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
