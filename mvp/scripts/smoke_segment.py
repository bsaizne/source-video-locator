"""Standalone smoke test for engine.segment (无 GT 编辑侧 shot 切分).

Builds a short 3-solid-color edited clip with ffmpeg lavender (no external asset),
then runs real DINOv2 CPU inference on the edited frames @edited_segment_fps and
calls ``detect_shots``. Only asserts *structural* invariants (never GT correctness
— synthetic solid color is a known DINOv2 CLS confusion scenario), and reports the
diagnostic stats requested by the product (segment_count / min|median|max_duration
/ boundary_count) for inspection, NOT for auto-tuning. Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/smoke_segment.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from device import CPUBackend
from engine.segment import detect_shots
from infrastructure.config import AppConfig
from media.ffmpeg import FFmpegIO

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")

_checks = 0


def check(cond, label):
    global _checks
    assert cond, f"FAIL: {label}"
    _checks += 1
    print(f"  [ok] {label}")


def build_edited(out_path: Path) -> None:
    """3×2s solid-color segments -> 6s multi-shot clip (no external asset)."""
    colors = ["0x993333", "0x339933", "0x333399"]
    ins = []
    for c in colors:
        ins += ["-f", "lavfi", "-i", f"color=c={c}:s=320x240:d=2"]
    cmd = [str(FFMPEG), "-y", *ins,
           "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
           "-map", "[v]", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(out_path)]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)


def main() -> int:
    cfg = AppConfig()
    fps = cfg.pipeline.edited_segment_fps
    ffmpeg = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)
    backend = CPUBackend()

    print(f"=== build multi-shot edited clip (3×2s solid color) ===")
    with tempfile.TemporaryDirectory() as td:
        edited = Path(td) / "edited.mp4"
        build_edited(edited)

        print(f"=== extract edited feats @{fps}fps (scale=None) ===")
        frames = list(ffmpeg.iter_frames(edited, fps))          # 特征路径必须 scale=None
        times = np.array([t for t, _ in frames], dtype=np.float32)
        feats = backend.embed_frames([f for _, f in frames])
        print(f"  edited: {len(frames)} frames, times[{times[0]:.2f}..{times[-1]:.2f}]")
        check(len(frames) >= 8, f"edited has >=8 frames (got {len(frames)})")
        check(feats.shape[1] == 384, f"edited feature dim 384 (got {feats.shape[1]})")

        print(f"=== detect_shots (seg=cut_abs={cfg.pipeline.seg_cut_abs} "
              f"z={cfg.pipeline.seg_z_thresh} min_shot_s={cfg.pipeline.seg_min_shot_s} "
              f"smooth={cfg.pipeline.seg_smooth}) ===")
        shots = detect_shots(
            feats, times,
            cut_abs=cfg.pipeline.seg_cut_abs,
            z_thresh=cfg.pipeline.seg_z_thresh,
            min_shot_s=cfg.pipeline.seg_min_shot_s,
            smooth=cfg.pipeline.seg_smooth,
        )
        for i, s in enumerate(shots):
            print(f"    #{i+1} span=[{s.span.start:.2f},{s.span.end:.2f}] "
                  f"dur={s.span.width:.2f}s nq={s.nq}")

        # -- 结构不变式（不断言 GT 正确性）--
        check(len(shots) >= 1, "at least one segment")
        for s in shots:
            check(0.0 <= s.span.start <= s.span.end,
                  f"valid span [{s.span.start:.2f},{s.span.end:.2f}]")
            check(s.feats.shape[0] == s.times.shape[0], "feats rows == times rows")
            check(np.all(np.diff(s.times) > 0), "times strictly ascending")

        # -- 诊断统计（用户产品约束 #4：仅输出诊断，不用于自动调参）--
        durations = sorted(s.span.width for s in shots)
        stats = {
            "segment_count": len(shots),
            "min_duration": round(durations[0], 3) if durations else 0.0,
            "median_duration": (round(float(np.median(durations)), 3)
                                if durations else 0.0),
            "max_duration": round(durations[-1], 3) if durations else 0.0,
            "boundary_count": max(len(shots) - 1, 0),
        }
        print("\n  segment diagnostics (informational, not for tuning):")
        for k, v in stats.items():
            print(f"    {k}: {v}")

    print(f"\nALL {_checks} CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
