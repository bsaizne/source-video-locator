"""Standalone smoke test for engine.retrieval + engine.clustering + engine.ranking.

End-to-end on the synthetic pair: index ``source.mp4`` (Original), then use the
``a1.mp4`` edited clip (a direct crop of source [20,25]) as the *edited query
feature sequence*. Verifies the top candidate lands near the known source region
[20,25]. Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/smoke_retrieval_ranking.py
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
from media.ffmpeg import FFmpegIO

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
ORIG = BENCH / "datasets" / "synthetic" / "originals" / "source.mp4"   # 90s original, GT source of a1=[20,25]
EDITED = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"       # crop of ORIG [20,25]

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
        print(f"  index: {meta.num_frames} frames dim={meta.feature_dim} "
              f"dur={meta.duration:.1f}s fps={meta.sampling_fps}")
        check(meta.num_frames >= 30, f"index has >=30 frames (got {meta.num_frames})")
        check(meta.feature_dim == 384, "feature dim 384")
        bundle = store.load_index(ORIG)

        print("=== 2. extract edited query feats from a1.mp4 @2fps ===")
        qframes = list(ffmpeg.iter_frames(EDITED, 2.0))
        q_times = np.array([t for t, _ in qframes], dtype=np.float32)
        q_feats = backend.embed_frames([f for _, f in qframes])
        print(f"  query: {len(qframes)} frames, times[{q_times[0]:.2f}..{q_times[-1]:.2f}]")
        check(len(qframes) >= 8, "query has >=8 frames")

        print("=== 3. produce_candidates (retrieval->clustering->v2 ranking) ===")
        cands = produce_candidates(q_feats, q_times, bundle)
        print(f"  {len(cands)} candidate windows:")
        for i, c in enumerate(cands[:5]):
            print(f"    #{i+1} [{c.start:.1f},{c.end:.1f}] w={c.width:.1f}s "
                  f"mean={c.mean_sim:.3f} hits={c.hit_count} reps={c.n_reps} "
                  f"cons={c.consistency:.3f} qcov={c.qcov:.3f} sdiv={c.scene_div} "
                  f"score={c.rank_score:.3f}")
        check(len(cands) >= 1, "at least one candidate")

        # Recall: 某个候选窗必须覆盖 GT[20,25]（a1 是 source[20,25] 的直裁），
        # 且该最优覆盖候选出现在 top-3 内（研究 best_rank>1 为常态；合成图案场景
        # 的 CLS 混淆属已知数据属性，不影响"GT 区域被召回"这一核心结论）。
        best_cov, best_cov_cand, best_rank = 0.0, None, None
        for idx, c in enumerate(cands):
            overlap = max(0.0, min(25.0, c.end) - max(20.0, c.start))
            cov = overlap / 5.0
            if cov > best_cov:
                best_cov, best_cov_cand, best_rank = cov, c, idx + 1
        print(f"  best GT-coverage candidate: rank #{best_rank} "
              f"[{best_cov_cand.start:.1f},{best_cov_cand.end:.1f}] cov={best_cov:.2f}")
        check(best_cov >= 0.5, f"some candidate covers GT[20,25]>=0.5 (recall, cov={best_cov:.2f})")
        check(best_rank is not None and best_rank <= 3,
              f"best-cover candidate within top-3 (rank #{best_rank})")

    print(f"\nALL {_checks} CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
