"""Unit tests for engine.localization.degradation_gate (2026-09-28 续19, T1-1).

Covers: duplicate-ratio math, gate off = zero mutation, degenerate segment
rejection (failure_reason + LOW + reason tag), skip rules (manual_override /
not_in_source / excluded / zero width), sub-span coverage floor, export-side
fragment warnings, and that rejected segments are dropped from the export plan.
Also pins the config JSON override generalisation (previously-ignored pipeline
knobs now take effect; unknown keys are ignored without crashing).

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_degradation_gate -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app.exporters import build_export_plan
from domain import (Confidence, ConfidenceLevel, OriginalSegment, Result,
                    ResultBatch, TimeSpan)
from engine.localization.degradation_gate import (apply_degradation_gate,
                                                  duplicate_claim_groups,
                                                  duplicate_claim_warnings,
                                                  duplicate_ratio, fragment_warnings)
from infrastructure.config import load_config


def _result(ed=(0.0, 2.0), orig=(10.0, 12.0), level="HIGH", score=0.9, *,
            segments=(), not_in_source=False, failure=None, manual=False,
            excluded=False) -> Result:
    conf = Confidence(ConfidenceLevel(level), score)
    r = Result(edited=TimeSpan(*ed), original=TimeSpan(*orig), confidence=conf,
               original_segments=list(segments), failure_reason=failure,
               not_in_source=not_in_source, excluded=excluded, manual_override=manual)
    return r


class DuplicateRatioTest(unittest.TestCase):
    def test_full_containment_is_one(self):
        self.assertEqual(duplicate_ratio((10.0, 20.0), [(0.0, 100.0)]), 1.0)

    def test_partial_and_capped(self):
        # 5s of a 10s span covered once, plus a fully overlapping second claim -> capped 1.0
        self.assertEqual(duplicate_ratio((10.0, 20.0), [(5.0, 15.0)]), 0.5)
        self.assertEqual(duplicate_ratio((10.0, 20.0), [(5.0, 15.0), (9.0, 21.0)]), 1.0)

    def test_overlapping_others_are_not_double_counted(self):
        # 续31 修正：两个邻居的 overlap 相加 = 0.9，但并集只盖住 6/10 = 0.6。
        # 实测该缺陷砍掉 test3 承重三条 GT 的宽 span（seg17, 源 425-437.6），
        # 分腿复测并集形态比累加形态回收 严格 +2 / 场景 +1。
        self.assertEqual(duplicate_ratio((10.0, 20.0), [(10.0, 15.0), (12.0, 16.0)]), 0.6)
        self.assertEqual(duplicate_ratio((10.0, 20.0), [(10.0, 15.0), (10.0, 15.0)]), 0.5)

    def test_nested_others_sum_capped_but_union_below_threshold(self):
        # 三段各盖 4s、彼此完全重叠 -> 相加 1.2（旧）截成 1.0 触发拒识；并集 0.4 不触发
        self.assertLess(duplicate_ratio((0.0, 10.0), [(0.0, 4.0)] * 3), 0.8)

    def test_zero_width_is_zero(self):
        self.assertEqual(duplicate_ratio((10.0, 10.0), [(0.0, 100.0)]), 0.0)


class DegradationGateTest(unittest.TestCase):
    def _run(self, results, **kw):
        opts = dict(enabled=True, max_duplicate_scene_ratio=0.8, min_scene_coverage=0.2)
        opts.update(kw)
        return apply_degradation_gate(results, **opts)

    def test_gate_off_is_zero_mutation(self):
        r = _result(orig=(10.0, 12.0))
        other = _result(ed=(2.0, 4.0), orig=(10.0, 12.0))
        stats = self._run([r, other], enabled=False)
        self.assertEqual(stats.rejected, [])
        self.assertIsNone(r.failure_reason)
        self.assertEqual(r.confidence.level, ConfidenceLevel.HIGH)

    def test_degenerate_duplicate_rejected(self):
        # 后者完全落在前者已认领的源区间内 = 匹配器卡位；0.8 边界的段不拒（严格大于才拒）
        a = _result(ed=(0.0, 2.0), orig=(100.0, 110.0))
        b = _result(ed=(2.0, 4.0), orig=(101.0, 109.0))
        stats = self._run([a, b])
        self.assertEqual(stats.rejected, [1])
        self.assertEqual(a.failure_reason, None)   # dup = 8/10 = 0.8 = 阈值，不拒
        self.assertEqual(b.failure_reason, "degenerate_duplicate")
        self.assertEqual(b.confidence.level, ConfidenceLevel.LOW)
        self.assertIn("degenerate_duplicate_rejected", b.confidence.reasons)

    def test_below_threshold_kept(self):
        # 两段只是首尾相接 5 秒（各自宽 100）：dup = 0.05，远低于 0.8 -> 都不拒
        a = _result(ed=(0.0, 2.0), orig=(100.0, 200.0))
        b = _result(ed=(2.0, 4.0), orig=(195.0, 295.0))
        stats = self._run([a, b])
        self.assertEqual(stats.rejected, [])
        self.assertIsNone(b.failure_reason)

    def test_user_conclusions_are_never_rejected(self):
        a = _result(ed=(0.0, 2.0), orig=(100.0, 110.0), manual=True)
        b = _result(ed=(2.0, 4.0), orig=(100.0, 110.0), manual=True)
        self.assertEqual(self._run([a, b]).rejected, [])

    def test_skip_rules(self):
        claim = _result(ed=(0.0, 2.0), orig=(100.0, 110.0))            # 健康占位者
        base = _result(ed=(2.0, 4.0), orig=(100.0, 110.0))              # 与之全重叠 -> 应被拒
        already_failed = _result(ed=(4.0, 6.0), orig=(100.0, 110.0), failure="unresolved")
        nir = _result(ed=(6.0, 8.0), orig=(100.0, 110.0), not_in_source=True)
        excl = _result(ed=(8.0, 10.0), orig=(100.0, 110.0), excluded=True)
        zero = _result(ed=(10.0, 12.0), orig=(100.0, 100.0))
        stats = self._run([base, already_failed, nir, excl, zero, claim])
        self.assertEqual(stats.rejected, [0])   # 只有健康段被判定（并被拒）
        self.assertEqual(already_failed.failure_reason, "unresolved")
        self.assertTrue(nir.not_in_source)
        self.assertIsNone(nir.failure_reason)
        self.assertFalse(excl.failure_reason)
        self.assertEqual(zero.failure_reason, None)

    def test_min_scene_coverage_drops_weak_subs(self):
        subs = [OriginalSegment(10.0, 20.0, 0.55), OriginalSegment(30.0, 40.0, 0.10)]
        r = _result(segments=subs)
        stats = self._run([r])
        self.assertEqual(stats.subs_dropped, 1)
        self.assertEqual(stats.subs_kept, 1)
        self.assertEqual(len(r.original_segments), 1)
        self.assertEqual(r.original_segments[0].cover, 0.55)

    def test_rejected_segment_leaves_export_plan(self):
        a = _result(ed=(0.0, 2.0), orig=(100.0, 110.0))
        b = _result(ed=(2.0, 4.0), orig=(100.0, 110.0))
        self._run([a, b])
        batch = ResultBatch(original_video="D:/src/o.mkv", edited_video="D:/src/e.mp4",
                            results=[a, b])
        clips = build_export_plan(batch, min_confidence="MEDIUM", include_subs=False)
        self.assertEqual(len(clips), 1)          # 强认领者留，重复交答案者不进工程
        self.assertEqual(clips[0].seg_index, 0)

    def test_stronger_claim_survives_regardless_of_edit_order(self):
        weak = _result(ed=(0.0, 2.0), orig=(100.0, 110.0), level="MEDIUM", score=0.4)
        strong = _result(ed=(2.0, 4.0), orig=(100.0, 110.0), level="HIGH", score=0.9)
        stats = self._run([weak, strong])
        self.assertEqual(stats.rejected, [0])     # 弱的那条被拒
        self.assertIsNone(strong.failure_reason)


class DuplicateClaimWarningTest(unittest.TestCase):
    """续31 同构安全形态：只指出「多段指向同一原片区」，不删任何答案。"""

    def _clip(self, seg, a, b):
        return type("C", (), {"orig_start": a, "orig_end": b, "seg_index": seg})()

    def test_transitive_grouping(self):
        # A~B 0.85、B~C 0.85、A~C 只有 0.70：靠并查集的传递性合成一个团
        clips = [self._clip(0, 0.0, 10.0), self._clip(1, 1.5, 11.5),
                 self._clip(2, 3.0, 13.0), self._clip(3, 900.0, 902.0)]
        self.assertEqual(duplicate_claim_groups(clips, min_ratio=0.8), [[0, 1, 2]])

    def test_half_overlap_is_not_a_claim(self):
        # 100-102 与 101-103：重叠 1s / 窄侧 2s = 0.5，属相邻不同内容，不算重复认领
        clips = [self._clip(0, 100.0, 102.0), self._clip(1, 101.0, 103.0)]
        self.assertEqual(duplicate_claim_groups(clips, min_ratio=0.8), [])

    def test_wide_containing_narrow_is_not_a_claim(self):
        # 续31 读图复核加的下限：8s 场景池宽 span 含住 2s 帧级窄 span 是我方分层输出的常态，
        # 不是重复素材（实测 test3 第 30/31 段被此误判，而两条画面是不同角色的不同镜头）。
        clips = [self._clip(0, 425.0, 437.6), self._clip(1, 430.0, 432.0)]
        self.assertEqual(duplicate_claim_groups(clips, min_ratio=0.8), [])
        # 放宽宽度比下限才成立（证明该判据确实由 min_width_ratio 把关，而非碰巧不重叠）
        self.assertEqual(duplicate_claim_groups(clips, min_ratio=0.8, min_width_ratio=0.1),
                         [[0, 1]])

    def test_same_width_inside_wide_is_a_claim(self):
        # 宽度可比（4s vs 2s = 0.5）且窄段几乎全在宽段内 = 用户能感知的重复素材
        clips = [self._clip(0, 3276.6, 3280.6), self._clip(1, 3278.6, 3280.6)]
        self.assertEqual(duplicate_claim_groups(clips, min_ratio=0.8), [[0, 1]])

    def test_adjacent_but_distinct_not_grouped(self):
        clips = [self._clip(0, 100.0, 105.0), self._clip(1, 105.0, 110.0)]
        self.assertEqual(duplicate_claim_groups(clips, min_ratio=0.8), [])

    def test_zero_width_clips_ignored(self):
        clips = [self._clip(0, 100.0, 100.0), self._clip(1, 100.0, 102.0),
                 self._clip(2, 100.5, 102.0)]
        self.assertEqual(duplicate_claim_groups(clips, min_ratio=0.8), [[1, 2]])

    def test_warning_text_and_no_mutation(self):
        clips = [self._clip(0, 100.0, 102.0), self._clip(1, 100.2, 102.2),
                 self._clip(2, 500.0, 501.0)]
        before = [(c.orig_start, c.orig_end, c.seg_index) for c in clips]
        w = duplicate_claim_warnings(clips, min_ratio=0.8)
        self.assertEqual(len(w), 1)
        self.assertIn("LOC-2002", w[0])
        self.assertIn("第 1、2 段", w[0])           # 1-based，与结果页序号一致
        self.assertIn("100.0-102.2s", w[0])
        self.assertEqual([(c.orig_start, c.orig_end, c.seg_index) for c in clips], before)

    def test_no_warning_when_all_distinct(self):
        clips = [self._clip(0, 100.0, 102.0), self._clip(1, 200.0, 202.0)]
        self.assertEqual(duplicate_claim_warnings(clips, min_ratio=0.8), [])


class FragmentWarningTest(unittest.TestCase):
    def test_no_warning_when_all_wide(self):
        clips = [type("C", (), {"orig_start": 0.0, "orig_end": 5.0})()]
        self.assertEqual(fragment_warnings(clips), [])

    def test_tiny_clip_warns_with_code(self):
        clips = [type("C", (), {"orig_start": 0.0, "orig_end": 0.04})()]
        w = fragment_warnings(clips, min_clip_s=0.15)
        self.assertEqual(len(w), 1)
        self.assertIn("LOC-2001", w[0])
        self.assertIn("1", w[0])


class ConfigOverrideGeneralisationTest(unittest.TestCase):
    """曾被我方 JSON 白名单漏掉、静默忽略的旋钮，现在必须真的生效。"""

    def _load(self, pipeline: dict) -> object:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cfg.json"
            p.write_text(json.dumps({"pipeline": pipeline}), encoding="utf-8")
            return load_config(p)

    def test_formerly_ignored_knobs_now_apply(self):
        cfg = self._load({"vote_prior_enabled": True, "subshot_min_sub": 7,
                          "dense_recheck_margin_s": 9.5, "patch_v2_margin": 0.05,
                          "degradation_gate_enabled": True,
                          "max_duplicate_scene_ratio": 0.42,
                          "edited_cache_enabled": False})
        p = cfg.pipeline
        self.assertTrue(p.vote_prior_enabled)
        self.assertEqual(p.subshot_min_sub, 7)
        self.assertEqual(p.dense_recheck_margin_s, 9.5)
        self.assertEqual(p.patch_v2_margin, 0.05)
        self.assertTrue(p.degradation_gate_enabled)
        self.assertEqual(p.max_duplicate_scene_ratio, 0.42)
        self.assertFalse(p.edited_cache_enabled)

    def test_string_bool_is_parsed_as_words_not_truthiness(self):
        # 旧代码 bool("false") == True 的坑
        cfg = self._load({"seg_twopass_enabled": "false", "seg_min_shot_s": "1.5"})
        self.assertFalse(cfg.pipeline.seg_twopass_enabled)
        self.assertEqual(cfg.pipeline.seg_min_shot_s, 1.5)

    def test_unknown_key_ignored_without_crash(self):
        cfg = self._load({"not_a_real_knob": 1, "retrieval_top_k": 33})
        self.assertEqual(cfg.pipeline.retrieval_top_k, 33)

    def test_export_min_clip_s_override(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cfg.json"
            p.write_text(json.dumps({"export": {"min_clip_s": 0.5}}), encoding="utf-8")
            self.assertEqual(load_config(p).export.min_clip_s, 0.5)

    def test_duplicate_claim_knobs_override(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "cfg.json"
            p.write_text(json.dumps({"export": {"duplicate_claim_warn": False,
                                                "duplicate_claim_min_ratio": 0.65,
                                                "duplicate_claim_min_width_ratio": 0.4}}),
                         encoding="utf-8")
            x = load_config(p).export
            self.assertFalse(x.duplicate_claim_warn)
            self.assertEqual(x.duplicate_claim_min_ratio, 0.65)
            self.assertEqual(x.duplicate_claim_min_width_ratio, 0.4)


if __name__ == "__main__":
    unittest.main()
