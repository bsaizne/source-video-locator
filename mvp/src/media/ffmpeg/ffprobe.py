"""ffprobe metadata parsing -> :class:`VideoMetadata`.

Key correctness rule discovered on the real 2h MKV original: MATROSKA containers
report ``duration=N/A`` on the video/audio streams, so duration MUST be read from
``format.duration`` (which is reliable), with a fallback to the max stream
duration only if format.duration is absent. FPS is read from ``avg_frame_rate``
(``r_frame_rate`` is ``0/0`` on some sources).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ._runner import MediaError, check_run


@dataclass(frozen=True)
class VideoMetadata:
    """Read-only description of a video file, filled by ffprobe."""

    path: Path
    duration: float          # seconds, from format.duration (reliable on MKV)
    size_bytes: int          # container size, from format.size
    format_name: str         # e.g. "matroska,webm" / "mov,mp4,m4a,..."
    width: int               # video stream 0 resolution
    height: int
    fps: float               # avg_frame_rate parsed to float (0 if unknown)
    video_codec: str         # e.g. "hevc" / "h264"
    has_video: bool
    has_audio: bool

    @property
    def aspect(self) -> float:
        return (self.width / self.height) if self.height else 0.0


def _parse_rate(rate: str | None) -> float:
    """'24000/1001' -> 23.976; '29/1' -> 29.0; '0/0' | 'N/A' | None -> 0.0."""
    if not rate:
        return 0.0
    rate = rate.strip()
    if rate in ("0/0", "N/A"):
        return 0.0
    if "/" in rate:
        num, _, den = rate.partition("/")
        try:
            num_f, den_f = float(num), float(den)
        except ValueError:
            return 0.0
        return num_f / den_f if den_f else 0.0
    try:
        return float(rate)
    except ValueError:
        return 0.0


def _first_float(value) -> float | None:
    if value in (None, "N/A", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def probe_metadata(path: Path, ffprobe: str, *, timeout: float = 600.0) -> dict:
    """Run ffprobe -show_format -show_streams -of json and parse to a dict."""
    args = [str(ffprobe), "-show_format", "-show_streams", "-of", "json", str(path)]
    out = check_run(args, timeout=timeout)
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        raise MediaError(f"ffprobe returned non-JSON for {path.name}") from exc


def build_metadata(path: Path, raw: dict) -> VideoMetadata:
    """Convert a raw ffprobe dict into a :class:`VideoMetadata`."""
    fmt = raw.get("format") or {}
    streams = raw.get("streams") or []
    vstream = next((s for s in streams if s.get("codec_type") == "video"), None)
    astream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    # Duration: prefer format.duration; fall back to max stream duration.
    duration = _first_float(fmt.get("duration"))
    if duration is None:
        stream_durs = [
            d for s in streams
            if (d := _first_float(s.get("duration"))) is not None
        ]
        duration = max(stream_durs) if stream_durs else 0.0

    fps = _parse_rate((vstream or {}).get("avg_frame_rate"))
    width = int((vstream or {}).get("width") or 0)
    height = int((vstream or {}).get("height") or 0)
    size_bytes = int(fmt.get("size") or 0)

    return VideoMetadata(
        path=Path(path),
        duration=float(duration),
        size_bytes=size_bytes,
        format_name=str(fmt.get("format_name") or ""),
        width=width,
        height=height,
        fps=fps,
        video_codec=str((vstream or {}).get("codec_name") or ""),
        has_video=vstream is not None,
        has_audio=astream is not None,
    )


def metadata_from(path: Path, ffprobe: str, *, timeout: float = 600.0) -> VideoMetadata:
    """Convenience: probe a file and return its :class:`VideoMetadata`."""
    return build_metadata(path, probe_metadata(path, ffprobe, timeout=timeout))
