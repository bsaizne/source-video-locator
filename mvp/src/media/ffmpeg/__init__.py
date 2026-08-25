"""Production-grade FFmpeg I/O for the Source Video Locator.

Replaces the research ``cv2.VideoCapture`` frame sampling (``sample_frames`` in
``src/experiments/dinov2_features.py``), which is NOT production-safe for random
access on MKV (``CAP_PROP_POS_MSEC`` can trigger a full decode from the start).
All time-accurate work here goes through ffmpeg / ffprobe binaries.

Decoded frames are BGR uint8 at original resolution, matching the frozen pipeline
contract (``DeviceBackend.embed_frames`` + ``_imagenet_preprocess``). We do NOT
scale in the feature path.

Never import from ``src/experiments`` / ``src/diagnostics`` — the MVP is
physically isolated from the research codebase.
"""
from ._runner import MediaError, resolve_binaries
from .ffmpeg_io import FFmpegIO
from .ffprobe import VideoMetadata

__all__ = ["FFmpegIO", "VideoMetadata", "MediaError", "resolve_binaries"]
