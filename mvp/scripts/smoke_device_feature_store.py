"""Standalone smoke test for mvp.device.CPUBackend + mvp.engine.feature_store.

Validates that DINOv2 can actually run on CPU and that the FeatureStore
create/load/validate/invalidate/delete lifecycle works end-to-end on the small
synthetic a1.mp4. Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/smoke_device_feature_store.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from device import CPUBackend, pick_best_available
from domain import IndexValidationStatus
from engine.feature_store import FeatureStore

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"

_checks = 0


def check(cond, label):
    global _checks
    assert cond, f"FAIL: {label}"
    _checks += 1
    print(f"  [ok] {label}")


def main() -> int:
    from media.ffmpeg import FFmpegIO
    ffmpeg = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)

    print("=== 1. CPUBackend ===")
    backend = pick_best_available()
    print(f"  backend={backend!r} available={backend.is_available()} type={backend.device_type()}")
    check(backend.is_available(), "CPU backend available")
    check(backend.device_name() == "cpu", "device_name == cpu")
    check(backend.device_type() == "cpu", "device_type == cpu")
    mem = backend.memory_info()
    print(f"  memory_info={mem}")
    check(mem["total_gb"] > 0, "memory_info total>0")

    frames = list(ffmpeg.iter_frames(SYNTH, 0.5))
    feats = backend.embed_frames([f for _, f in frames])
    print(f"  embed {len(frames)} frames -> {feats.shape}")
    check(feats.shape == (len(frames), 384), "embed shape [N,384]")
    norms = np.linalg.norm(feats, axis=1)
    check(abs(norms.mean() - 1.0) < 1e-3, f"L2 norm ~1 (mean={norms.mean():.4f})")
    check(np.all(np.isfinite(feats)), "all feats finite")

    print("=== 2. FeatureStore lifecycle on a1.mp4 ===")
    with tempfile.TemporaryDirectory() as td:
        store = FeatureStore(ffmpeg, td, sampling_fps=0.5)
        v = store.validate_index(SYNTH)
        print(f"  validate (before create) = {v.status} reason={v.reason}")
        check(v.status == IndexValidationStatus.MISSING, "MISSING before create")

        idx_dir = store.index_dir(SYNTH)
        check(idx_dir.parent == Path(td), f"index under given root")

        progress = []
        meta = store.create_index(SYNTH, backend, progress=progress.append)
        print(f"  created meta: fps={meta.sampling_fps} frames={meta.num_frames} "
              f"dim={meta.feature_dim} backend={meta.backend} hash={meta.file_hash[:12]}...")
        check(meta.num_frames >= 2, f"num_frames>=2 (got {meta.num_frames})")
        check(meta.feature_dim == 384, "feature_dim 384")
        check(meta.backend == "cpu", "backend recorded as cpu")
        check((idx_dir / "index.json").exists() and (idx_dir / "features.npy").exists()
              and (idx_dir / "times.npy").exists(), "3 index files written")
        check(len(progress) > 0, "progress callback invoked")

        v = store.validate_index(SYNTH)
        print(f"  validate (after create) = {v.status}")
        check(v.status == IndexValidationStatus.VALID, "VALID after create")

        bundle = store.load_index(SYNTH)
        check(bundle.features.shape == (meta.num_frames, 384), "load features [T,384]")
        check(bundle.times.shape == (meta.num_frames,), "load times [T]")
        check(np.allclose(bundle.times, np.linspace(0, (meta.num_frames - 1) * 2.0, meta.num_frames),
                          atol=0.1), "times are a 2s grid")
        gm = store.get_metadata(SYNTH)
        check(gm.file_hash == meta.file_hash, "get_metadata matches")

        store.invalidate_index(SYNTH)
        v = store.validate_index(SYNTH)
        print(f"  validate (after invalidate) = {v.status}")
        check(v.status == IndexValidationStatus.MISSING, "MISSING after invalidate")
        check((Path(str(idx_dir) + ".stale")).exists(), "stale dir created")

        store.create_index(SYNTH, backend)   # rebuild
        check(store.validate_index(SYNTH).status == IndexValidationStatus.VALID, "rebuilt VALID")
        store.delete_index(SYNTH)
        check(not idx_dir.exists(), "deleted idx dir")
        check(not (Path(str(idx_dir) + ".stale")).exists(), "stale dir also deleted")

        # negative: MISSING for a video never indexed
        check(store.validate_index(BENCH.parent / "does_not_exist.mp4").status
              == IndexValidationStatus.MISSING, "MISSING for un-indexed video")

    print(f"\nALL {_checks} CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
