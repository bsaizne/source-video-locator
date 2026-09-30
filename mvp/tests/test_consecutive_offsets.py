"""Unit tests for engine.localization.consecutive_offsets (2026-09-28 E1).

Covers: duplicate-start shift (width preserved), tolerance boundary, manual
segment protection, source-range guard, chained consecutive shifts, unlocated
segments not breaking "consecutive", already-after pair left alone, and the
config JSON override wiring for the new knobs.

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_consecutive_offsets -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from domain import Confidence, ConfidenceLevel, Result, TimeSpan
from engine.localization.consecutive_offsets import resolve_consecutive_offsets
from infrastructure.config import load_config


def _r(ed=(0.0, 2.0), orig=(10.0, 12.0), *, manual=False, not_in_source=False,
       failure=None) -> Result:
    return Result(edited=TimeSpan(*ed), original=TimeSpan(*orig),
                  confidence=Confidence(ConfidenceLevel.HIGH, 0.9),
                  failure_reason=failure, not_in_source=not_in_source,
                  manual_override=manual)


class ResolveConsecutiveTest(unittest.TestCase):
    def test_duplicate_start_shifts_to_prev_end(self):
        a, b = _r(orig=(10.0, 12.0)), _r(ed=(2.0, 5.0), orig=(10.5, 15.0))
        st = resolve_consecutive_offsets([a, b], dup_tol_s=1.0)
        self.assertEqual((b.original.start, b.original.end), (12.0, 16.5))  # 宽度 4.5 保持
        self.assertEqual(len(st.shifted), 1)
        self.assertEqual(st.shifted[0]["index"], 1)

    def test_beyond_tolerance_untouched(self):
        a, b = _r(orig=(10.0, 12.0)), _r(ed=(2.0, 5.0), orig=(11.5, 15.0))
        st = resolve_consecutive_offsets([a, b], dup_tol_s=1.0)
        self.assertEqual(b.original.start, 11.5)
        self.assertEqual(st.shifted, [])

    def test_manual_b_is_skipped_not_moved(self):
        a, b = _r(orig=(10.0, 12.0)), _r(ed=(2.0, 5.0), orig=(10.2, 14.0), manual=True)
        st = resolve_consecutive_offsets([a, b], dup_tol_s=1.0)
        self.assertEqual((b.original.start, b.original.end), (10.2, 14.0))
        self.assertEqual(st.skipped[0]["reason"], "manual")

    def test_exceeds_source_range_skipped(self):
        a, b = _r(orig=(10.0, 12.0)), _r(ed=(2.0, 5.0), orig=(10.0, 14.0))
        st = resolve_consecutive_offsets([a, b], dup_tol_s=1.0, source_duration_s=15.0)
        self.assertEqual((b.original.start, b.original.end), (10.0, 14.0))
        self.assertEqual(st.skipped[0]["reason"], "exceeds_source_range")

    def test_chain_shifts_sequentially(self):
        a = _r(orig=(10.0, 12.0))
        b = _r(ed=(2.0, 5.0), orig=(10.0, 15.0))    # -> [12,17]
        c = _r(ed=(5.0, 6.5), orig=(12.5, 14.0))    # vs b.new start 12: |0.5|<=1 -> [17,18.5]
        st = resolve_consecutive_offsets([a, b, c], dup_tol_s=1.0)
        self.assertEqual((b.original.start, b.original.end), (12.0, 17.0))
        self.assertEqual((c.original.start, c.original.end), (17.0, 18.5))
        self.assertEqual(len(st.shifted), 2)

    def test_unlocated_segment_does_not_break_consecutive(self):
        a = _r(orig=(10.0, 12.0))
        x = _r(ed=(2.0, 3.0), orig=(0.0, 0.0), not_in_source=True)
        b = _r(ed=(3.0, 6.0), orig=(10.4, 13.0))
        st = resolve_consecutive_offsets([a, x, b], dup_tol_s=1.0)
        self.assertEqual((b.original.start, b.original.end), (12.0, 14.6))
        self.assertEqual(len(st.shifted), 1)

    def test_already_after_prev_end_untouched(self):
        a = _r(orig=(10.0, 10.2))
        b = _r(ed=(2.0, 5.0), orig=(10.5, 12.0))  # 起点差 0.5<=tol 但 a.end<=b.start
        st = resolve_consecutive_offsets([a, b], dup_tol_s=1.0)
        self.assertEqual(b.original.start, 10.5)
        self.assertEqual(st.shifted, [])

    def test_failure_segment_ignored_as_anchor(self):
        a = _r(orig=(10.0, 12.0), failure="not_found")
        b = _r(ed=(2.0, 5.0), orig=(10.0, 13.0))
        st = resolve_consecutive_offsets([a, b], dup_tol_s=1.0)
        self.assertEqual(b.original.start, 10.0)  # a 未定位不当锚
        self.assertEqual(st.shifted, [])


class ConfigWiringTest(unittest.TestCase):
    def test_json_override_generalized_knobs(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_file = Path(td) / "c.json"
            cfg_file.write_text(json.dumps({"pipeline": {
                "resolve_consecutive_enabled": True,
                "resolve_consecutive_dup_tol_s": 0.5}}), encoding="utf-8")
            cfg = load_config(cfg_file)
            self.assertTrue(cfg.pipeline.resolve_consecutive_enabled)
            self.assertEqual(cfg.pipeline.resolve_consecutive_dup_tol_s, 0.5)

    def test_default_off(self):
        cfg = load_config()
        self.assertFalse(cfg.pipeline.resolve_consecutive_enabled)
        self.assertEqual(cfg.pipeline.resolve_consecutive_dup_tol_s, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
