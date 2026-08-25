"""FFmpegIO — production video random-access I/O.

Replaces the research ``cv2.VideoCapture`` frame sampling
(``src/experiments/dinov2_features.sample_frames``), which is NOT safe for random
access on MKV (``CAP_PROP_POS_MSEC`` can trigger a full decode from the start).
Everything time-accurate here goes through ffmpeg / ffprobe subprocesses.

Frame contract (frozen): decoded frames are **BGR uint8 at original resolution**,
matching ``DeviceBackend.embed_frames(bgr_frames: list[np.ndarray])`` and
``dinov2_features._imagenet_preprocess`` (which itself resizes to 518x518). We
therefore do NOT scale frames in the feature path; ``scale=`` is only for
preview / thumbnails where the exact resize interpolation does not matter.

Sampling convention (time-based, differs from the research frame-index grid):
``iter_frames(fps=f)` outputs one frame every ``1/f`` seconds and yields the
timestamp ``t = i / f`` (absolute, relative to ``start`` when ``start`` given).
This is deterministic and aligned with the FeatureStore ``t = row / fps``.
"""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Iterator

import numpy as np

from ._runner import BASE_ARGS, CREATE_NO_WINDOW, MediaError, check_run, popen, resolve_binaries
from .ffprobe import VideoMetadata, metadata_from

# Default encoder used for precise clip extraction. Re-encoding (not stream copy)
# is required for frame-accurate output: `-c copy` is keyframe-aligned and loses
# the sub-goP precision that the product promises. libx264 is a GPL encoder; see
# TECH_STACK_DECISION.md §6 — the LGPL FFmpeg build decision is a packaging task.
_DEFAULT_CODEC = "libx264"
_DEFAULT_PRESET = "veryfast"
_DEFAULT_CRF = 18


class FFmpegIO:
    """Injected-binary video I/O. Never hard-codes a machine-specific path."""

    def __init__(self, ffmpeg: str | Path | None = None,
                 ffprobe: str | Path | None = None, *, timeout_s: float = 600.0):
        self.ffmpeg, self.ffprobe = resolve_binaries(ffmpeg, ffprobe)
        self.timeout_s = timeout_s

    # ------------------------------------------------------------------ #
    # Metadata
    # ------------------------------------------------------------------ #
    def metadata(self, path: str | Path) -> VideoMetadata:
        return metadata_from(Path(path), str(self.ffprobe), timeout=self.timeout_s)

    # ------------------------------------------------------------------ #
    # Frame sampling (streaming)
    # ------------------------------------------------------------------ #
    def iter_frames(self, path: str | Path, fps: float = 0.5, *,
                    start: float | None = None, end: float | None = None,
                    scale: tuple[int, int] | None = None,
                    meta: VideoMetadata | None = None) -> Iterator[tuple[float, np.ndarray]]:
        """Yield ``(timestamp, bgr_frame)`` at ``fps`` frames/sec.

        - ``start``/``end`` (seconds, absolute) restrict the decoded range; they are
          implemented with ``-ss`` before ``-i`` (fast input seek) so a long source
          is never decoded from the start.
        - ``timestamp = (start or 0) + i / fps`` — an absolute time grid. Sub-frame
          skew (<= one source frame) is possible after a seek.
        - ``scale`` is ONLY for preview; the feature path must leave it None so the
          frozen resize semantics in ``_imagenet_preprocess`` are preserved.

        Memory bounded: frames are read from the rawvideo pipe one at a time.
        """
        path = Path(path)
        info = meta or self.metadata(path)
        if not info.has_video:
            raise MediaError(f"{path.name}: no video stream to sample")
        width, height = self._output_size(info, scale)
        frame_bytes = width * height * 3

        vf = f"fps={fps:g}"
        if scale is not None:
            vf += f",scale={scale[0]}:{scale[1]}"
        base = start if start is not None else 0.0

        args = [str(self.ffmpeg), *BASE_ARGS]
        if start is not None:
            args += ["-ss", f"{start:.6f}"]
        args += ["-i", str(path)]
        if start is not None and end is not None:
            args += ["-t", f"{end - start:.6f}"]
        elif end is not None:
            # seek-to-start with an absolute end: use -to relative to input
            args += ["-to", f"{end:.6f}"]
        args += ["-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]

        proc = popen(args)
        try:
            i = 0
            while True:
                buf = proc.stdout.read(frame_bytes)
                if len(buf) < frame_bytes:
                    break  # EOF (or final partial frame) — nothing more to emit
                frame = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3)
                yield base + i / fps, frame
                i += 1
        finally:
            proc.stdout.close()
            rc = proc.wait()
            err = proc.stderr.read().decode("utf-8", errors="replace")
            proc.stderr.close()
        if rc != 0:
            raise MediaError(
                f"frame extraction failed (rc={rc}): {path.name}\n{err[-1500:]}"
            )

    def grab_frame(self, path: str | Path, t: float, *, scale: tuple[int, int] | None = None) -> np.ndarray:
        """Return one decoded BGR frame at time ``t`` (frame-accurate single seek).

        Uses ``-ss`` before ``-i`` (fast input seek, decode-and-discard up to
        ``t``) then ``-frames:v 1``. Used for previews and QA.
        """
        path = Path(path)
        info = self.metadata(path)
        if not info.has_video:
            raise MediaError(f"{path.name}: no video stream")
        width, height = self._output_size(info, scale)
        frame_bytes = width * height * 3

        args = [str(self.ffmpeg), *BASE_ARGS, "-ss", f"{t:.6f}", "-i", str(path),
                "-frames:v", "1"]
        if scale is not None:
            args += ["-vf", f"scale={scale[0]}:{scale[1]}"]
        args += ["-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]

        try:
            proc = subprocess.run(
                args, capture_output=True, timeout=self.timeout_s,
                check=False, creationflags=CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise MediaError(f"grab_frame timed out at t={t:.3f} for {path.name}") from exc
        if proc.returncode != 0:
            raise MediaError(
                f"grab_frame failed (rc={proc.returncode}) at t={t:.3f}: {path.name}\n"
                f"{proc.stderr.decode(errors='replace')[-1000:]}"
            )
        if len(proc.stdout) < frame_bytes:
            raise MediaError(f"grab_frame returned no frame at t={t:.3f}: {path.name}")
        return np.frombuffer(proc.stdout[:frame_bytes], dtype=np.uint8).reshape(height, width, 3)

    # ------------------------------------------------------------------ #
    # Clip extraction
    # ------------------------------------------------------------------ #
    def extract_clip(self, path: str | Path, start: float, end: float,
                     out_path: str | Path, *, codec: str = _DEFAULT_CODEC,
                     preset: str = _DEFAULT_PRESET, crf: int = _DEFAULT_CRF,
                     include_audio: bool = True, overwrite: bool = True) -> Path:
        """Extract the exact ``[start, end]`` interval into a re-encoded file.

        Frame-accurate via ``-ss <start> -i ... -t <len>`` (fast input seek) plus
        re-encode. ``-c copy`` would be keyframe-aligned and NOT precise — rejected
        per MVP product spec. Returns the output ``out_path``.
        """
        path = Path(path)
        out_path = Path(out_path)
        if end <= start:
            raise MediaError(
                f"extract_clip end must be > start ({start} -> {end}) for {path.name}"
            )

        # Range sanity against known duration (warn only; never silently clamp).
        info = self.metadata(path)
        if info.duration and start >= info.duration:
            raise MediaError(
                f"extract_clip start {start}s is beyond duration {info.duration:.1f}s"
            )
        if info.duration and end > info.duration + 0.5:
            raise MediaError(
                f"extract_clip end {end}s exceeds duration {info.duration:.1f}s"
            )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        args = [str(self.ffmpeg), *BASE_ARGS]
        if overwrite:
            args += ["-y"]
        args += ["-ss", f"{start:.6f}", "-i", str(path), "-t", f"{end - start:.6f}",
                 "-map", "0:v:0"]
        if include_audio:
            args += ["-map", "0:a:0?"]          # audio optional (source may lack it)
        args += ["-c:v", codec, "-preset", preset, "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-avoid_negative_ts", "make_zero"]
        if include_audio:
            args += ["-c:a", "aac"]
        args += [str(out_path)]

        check_run(args, timeout=self.timeout_s)
        return out_path

    # ------------------------------------------------------------------ #
    # File hashing (for index validation)
    # ------------------------------------------------------------------ #
    def hash_file(self, path: str | Path, algo: str = "sha256") -> str:
        """Streaming file hash. Bounded memory; 1 MiB chunks.

        NOTE: for a multi-GB original a full hash costs a few seconds. The
        FeatureStore may do a fast validation (size + duration + mtime + model
        version) and only compute this full hash when a fast check is ambiguous.
        """
        path = Path(path)
        hasher = hashlib.new(algo)
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _output_size(info: VideoMetadata, scale: tuple[int, int] | None) -> tuple[int, int]:
        if scale is not None:
            return int(scale[0]), int(scale[1])
        return info.width, info.height

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"FFmpegIO(ffmpeg={self.ffmpeg.name}, ffprobe={self.ffprobe.name}, "
            f"timeout_s={self.timeout_s})"
        )
