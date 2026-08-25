"""Standalone smoke test for engine.localization + engine.confidence.

End-to-end on the synthetic pair (real ffmpeg + DINOv2 CPU): index ``source.mp4``,
extract ``a1.mp4`` edited query feats @2fps, then ``produce_candidates`` ->
``localize_segment``. Verifies the localization/confidence chain runs and produces a
structurally valid ``RefinedSegment``.

NOTE: synthetic-pattern scenes are a KNOWN DINOv2-CLS confusion case (see STATE.md) —
the top-ranked candidate is not guaranteed to be the true source region. This smoke
asserts pipeline validity (not GT correctness); GT-correctness is covered by the
deterministic unittest ``test_localization_confidence``. Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/smoke_localization_confidence.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from device import CPUBackend
from engine.candidates import produce_candidates
from engine.feature_store import FeatureStore
from engine.localization.pipeline import localize_segment
from media.ffmpeg import FFmpegIO

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
ORIG = BENCH / "datasets" / "synthetic" / "originals" / "source.mp4"
EDITED = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"

_checks = 0


def check(cond, label):
    global _checks
    assert cond, f"FAIL: {label}"
    _checks += 1
    print(f"  [ok] {label}")


def main() -> int:
    ffmpeg = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)
    backend = CPUBackend()

    print("=== 1. index the synthetic Original (90s, 0.5fps) ===")
    with tempfile.TemporaryDirectory() as td:
        store = FeatureStore(ffmpeg, td, sampling_fps=0.5)
        meta = store.create_index(ORIG, backend)
        print(f"  index: {meta.num_frames} frames dim={meta.feature_dim}")
        check(meta.num_frames >= 30, f"index has >=30 frames (got {meta.num_frames})")
        bundle = store.load_index(ORIG)

        print("=== 2. extract edited query feats from a1.mp4 @2fps ===")
        qframes = list(ffmpeg.iter_frames(EDITED, 2.0))
        q_times = np.array([t for t, _ in qframes], dtype=np.float32)
        q_feats = backend.embed_frames([f for _, f in qframes])
        print(f"  query: {len(qframes)} frames")
        check(len(qframes) >= 8, "query has >=8 frames")

        print("=== 3. produce_candidates -> localize_segment ===")
        cands = produce_candidates(q_feats, q_times, bundle)
        check(len(cands) >= 1, "at least one candidate")
        refined = localize_segment(cands, q_feats, bundle)
        check(refined is not None, "produced a RefinedSegment")
        r = refined.original
        print(f"  best [{r.start:.1f},{r.end:.1f}] "
              f"cand_w={refined.candidate.width:.1f}s "
              f"best_cover={refined.candidate.best_cover:.3f} "
              f"span={refined.loc.span} multi_island={refined.loc.multi_island}")
        print(f"  confidence={refined.confidence.level.value} "
              f"score={refined.confidence.score} montage={refined.montage_flag}")
        print(f"  reasons={list(refined.confidence.reasons)}")
        print(f"  hard_flags={refined.hard_flags}")
        print(f"  alternatives={[(a.interval.start, a.interval.end, a.confidence_level.value) for a in refined.alternatives]}")
        check(r.start <= r.end, "original.Start <= original.End")
        check(refined.confidence.level.value in ("HIGH", "MEDIUM", "LOW"),
              "confidence level is HIGH/MEDIUM/LOW")
        check(refined.candidate.best_cover >= 0.0, "best_cover backfilled (>=0)")
        check(isinstance(refined.alternatives, list), "alternatives is a list")
        check(isinstance(refined.hard_flags, tuple), "hard_flags is a tuple")

    print(f"\nALL {_checks} CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
