"""Standalone smoke test for mvp.media.ffmpeg.FFmpegIO against real sources.

Validates FFmpegIO against the 2h08m MKV original (which stresses random access
-- MKV video streams report duration=N/A) and the small edited clip. This is the
acceptance harness for Stage 1 item 1 (media/ffmpeg).

Run (absolute python per AGENTS.md):
  "D:/clauework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/smoke_ffmpeg_io.py
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from media.ffmpeg import FFmpegIO, MediaError

BENCH = Path(__file__).resolve().parents[2]  # D:/claudework/benchmark
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
# ffprobe is NOT in tools/ on this machine; use the documented static_ffmpeg path.
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
ORIG = BENCH / "datasets" / "real" / "originals" / "2.mkv"
EDITED = BENCH / "datasets" / "real" / "edited" / "1.mp4"
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"

_checks = 0


def check(cond: bool, label: str) -> None:
    global _checks
    assert cond, f"FAIL: {label}"
    _checks += 1
    print(f"  [ok] {label}")


def timed(label: str, fn, *a, **k):
    t0 = time.time()
    r = fn(*a, **k)
    dt = time.time() - t0
    print(f"  [{label}] {dt:.2f}s")
    return r


def main() -> int:
    io = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE, timeout_s=600.0)
    print("binaries:", io)

    print("\n=== 1. metadata (long MKV: duration must come from format, not streams) ===")
    mo = timed("orig", io.metadata, ORIG)
    print(f"  orig: dur={mo.duration:.3f}s fps={mo.fps:.4f} {mo.width}x{mo.height} "
          f"codec={mo.video_codec} size={mo.size_bytes} fmt={mo.format_name!r}")
    check(abs(mo.duration - 7667.535) < 0.1, f"orig duration ~7667.5 (got {mo.duration:.3f})")
    check(abs(mo.fps - 23.976) < 0.05, f"orig fps ~23.976 (got {mo.fps:.4f})")
    check((mo.width, mo.height) == (1280, 688), "orig resolution 1280x688")
    check(mo.video_codec == "hevc", "orig codec hevc")
    check(mo.size_bytes == 1020168298, "orig size")

    me = timed("edited", io.metadata, EDITED)
    print(f"  edited: dur={me.duration:.3f}s fps={me.fps:.4f} {me.width}x{me.height} codec={me.video_codec}")
    check(abs(me.duration - 126.793) < 0.1, "edited duration ~126.79")
    check(abs(me.fps - 29.0) < 0.05, "edited fps ~29")

    print("\n=== 2. iter_frames: small clip, full pass (0.5 fps) ===")
    frames = list(timed("a1", io.iter_frames, SYNTH, 0.5))
    print(f"  a1 -> {len(frames)} frames, t0={frames[0][0]:.3f}, "
          f"shape={frames[0][1].shape}, dtype={frames[0][1].dtype}")
    check(2 <= len(frames) <= 5, f"a1 frame count in [2,5] (got {len(frames)})")
    check(frames[0][0] == 0.0, "a1 first timestamp == 0")
    check(frames[0][1].shape == (720, 1280, 3), "a1 frame shape 720x1280x3")
    check(frames[0][1].dtype == np.uint8, "a1 frame dtype uint8")
    ts = [t for t, _ in frames]
    check(all(b > a for a, b in zip(ts, ts[1:])), "timestamps strictly increase")

    print("\n=== 3. iter_frames: long MKV sub-range via fast seek (no decode-from-start) ===")
    sub = list(timed("orig", io.iter_frames, ORIG, 0.5, start=1000.0, end=1006.0))
    print(f"  orig[1000..1006] -> {len(sub)} frames, t0={sub[0][0]:.3f}, shape={sub[0][1].shape}")
    check(len(sub) >= 2, "orig sub-range produced >=2 frames")
    check(sub[0][1].shape == (688, 1280, 3), "orig sub-range frame shape 688x1280x3")
    check(abs(sub[0][0] - 1000.0) < 0.01, "sub-range first timestamp ~1000")

    print("\n=== 4. grab_frame: single frame-accurate seek on huge MKV ===")
    gf = timed("orig", io.grab_frame, ORIG, 1237.0)
    print(f"  grab_frame(1237) shape={gf.shape} mean={gf.mean():.1f}")
    check(gf.shape == (688, 1280, 3), "grab_frame shape 688x1280x3")
    check(gf.mean() > 5.0, "grab_frame is not black (mean>5)")

    print("\n=== 5. extract_clip: precise re-encode of a known GT interval ===")
    out_dir = Path(tempfile.mkdtemp(prefix="ffmpegio_smoke_"))
    out = out_dir / "precise_clip.mp4"
    clip = timed("clip", io.extract_clip, ORIG, 1237.0, 1251.0, out)
    cm = io.metadata(clip)
    print(f"  clip: dur={cm.duration:.3f}s res={cm.width}x{cm.height} codec={cm.video_codec} "
          f"size={cm.size_bytes}")
    check(abs(cm.duration - 14.0) < 0.5, f"clip duration ~14s (got {cm.duration:.3f})")
    check(cm.video_codec == "h264", "clip re-encoded to h264")
    check((cm.width, cm.height) == (1280, 688), "clip resolution preserved 1280x688")

    # Frame-precision acceptance: clip's first frame vs source frame at `start`.
    clip_first = io.grab_frame(clip, 0.0)
    src_first = io.grab_frame(ORIG, 1237.0)
    mae = float(np.abs(clip_first.astype(np.int16) - src_first.astype(np.int16)).mean())
    print(f"  clip-first vs src-first mean-abs-diff = {mae:.2f}")
    check(mae < 12.0, f"clip start is frame-accurate (mae {mae:.2f} < 12)")

    print("\n=== 6. hash_file (streaming, 1GB) ===")
    h = timed("hash", io.hash_file, ORIG)
    print(f"  sha256={h}")
    check(len(h) == 64 and all(c in "0123456789abcdef" for c in h), "sha256 64-hex")

    print("\n=== 7. error handling ===")
    try:
        io.extract_clip(ORIG, 1250.0, 1237.0, out_dir / "bad.mp4")
        check(False, "extract_clip with end<start should raise")
    except MediaError:
        check(True, "extract_clip end<start raised MediaError")

    print(f"\nALL {_checks} CHECKS PASSED")
    print(f"  (output clip kept at {out})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
