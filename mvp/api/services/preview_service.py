"""preview_service — 把原片的一段时间区间抽取为独立小文件（预览用）。

独立能力，只封装 "对某视频抽取 [start, end] 区间成 mp4"，并落到一个预览缓存目录。
**不触碰** ``SourceLocatorService`` / domain / engine / FeatureStore / DeviceBackend / 算法。

- ``extract_segment(video_path, start, end)`` -> ``PreviewResult{path, duration}``：
  复用 ``SourceLocatorService`` 的 ``FFmpegIO.extract_clip``（精确重编码，非 stream copy）。
- 异常统一走 :class:`PreviewError`（``LocatorError`` 子类）——桥的 ``LocatorError -> 500``
  处理器会 ``logger.exception()`` 并返回 500 ``{error, detail}``。
- 产物目录默认 ``<app-data>/previews``，可用 ``preview_dir`` 覆盖（测试注入临时目录）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from infrastructure import paths
from infrastructure.errors import LocatorError
from infrastructure.logging import get_logger
from media.ffmpeg import FFmpegIO, MediaError

__all__ = ["PreviewError", "PreviewResult", "PreviewService"]


class PreviewError(LocatorError):
    """预览抽取失败（文件缺失 / 时间非法 / ffmpeg 失败）。桥映射为 HTTP 500。"""


@dataclass(frozen=True)
class PreviewResult:
    """一次成功抽取的结果。``path`` 是产物文件，``duration`` 是区间长度（秒）。"""

    path: Path
    duration: float


def _slug(name: str) -> str:
    """把文件名压成安全的 token（保留 . 与 -，其余非字母数字替换为 _）。"""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


class PreviewService:
    """视频片段抽取。单独可测：注入任意 ``ffmpeg``（FFmpegIO 或 fake）。

    ``ffmpeg`` 缺省时惰性构建 ``FFmpegIO()``（读取二进制环境/默认路径）；产品路径由
    route 注入 ``ctx.service.ffmpeg``（已按配置解析），因此预览与主链路共用同一 ffmpeg。
    """

    def __init__(self, *, ffmpeg: FFmpegIO | None = None,
                 preview_dir: str | Path | None = None):
        self._ffmpeg = ffmpeg
        self.preview_dir = Path(preview_dir) if preview_dir else (paths.app_data_dir() / "previews")
        self.preview_dir.mkdir(parents=True, exist_ok=True)
        self._log = get_logger(__name__)

    @property
    def ffmpeg(self) -> FFmpegIO:
        if self._ffmpeg is None:
            self._ffmpeg = FFmpegIO()
        return self._ffmpeg

    def extract_segment(self, video_path: str | Path, start: float, end: float) -> PreviewResult:
        """抽取 ``[start, end]`` 区间为 mp4，落盘到 ``preview_dir``。

        任何失败（文件缺失 / 时间非法 / 超时长 / ffmpeg 错误）都抛 :class:`PreviewError`；
        ffmpeg 侧失败额外 ``logger.exception`` 记录上下文。
        """
        video = Path(video_path)

        # 文件存在性（最清楚的尽早报错，避免依赖 ffprobe 对缺失文件的报错文本）。
        if not video.exists():
            raise PreviewError(f"video file not found: {video_path}")

        # 时间区间合法性。
        if end <= start:
            raise PreviewError(f"invalid time range: start={start} end={end}")

        # 对已知时长做一次越界校验（给出清晰的 PreviewError；extract_clip 会再校验一遍）。
        try:
            info = self.ffmpeg.metadata(video)
        except MediaError as exc:
            self._log.exception("preview metadata failed for %s", video)
            raise PreviewError(f"failed to probe video: {exc}") from exc
        if info.duration:
            if start >= info.duration:
                raise PreviewError(
                    f"start {start}s beyond duration {info.duration:.1f}s: {video.name}")
            if end > info.duration + 0.5:
                raise PreviewError(
                    f"end {end}s exceeds duration {info.duration:.1f}s: {video.name}")

        out = self._outpath(video, start, end)
        try:
            self.ffmpeg.extract_clip(video, start, end, out)
        except MediaError as exc:
            self._log.exception("preview extract failed video=%s start=%s end=%s",
                                video, start, end)
            raise PreviewError(f"ffmpeg extract failed for {video.name}: {exc}") from exc
        return PreviewResult(path=out, duration=end - start)

    def cleanup(self) -> None:
        """清空预览缓存目录（导出后调用，避免磁盘累积）。幂等；目录缺失/单文件失败不报错。"""
        if not self.preview_dir.exists():
            return
        for f in self.preview_dir.iterdir():
            try:
                if f.is_file():
                    f.unlink()
            except OSError:
                self._log.warning("preview cleanup failed: %s", f)

    def _outpath(self, video: Path, start: float, end: float) -> Path:
        """产物路径：``<stem>__<start>-<end>.mp4``，同区间重复调用会覆盖（幂等）。"""
        stem = _slug(video.stem)
        return self.preview_dir / f"{stem}__{round(start)}-{round(end)}.mp4"
