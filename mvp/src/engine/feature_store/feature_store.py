"""engine.feature_store.FeatureStore — Original Video 特征索引抽象。

冻结基线（INDEX_SPEC）：索引按绝对时间（秒）存，``features.npy`` 与 ``times.npy``
行对齐；创建/加载/校验/失效/删除分离；**禁止**把 numpy/npy/cache 直接暴露给 UI
——一切经本类。原片 seek/decode 走 ``FFmpegIO``（不得用 cv2.CAP_PROP_POS_MSEC）。

落盘（INDEX_SPEC §2）：
``<index_root>/<stem>__<hash8>.idx/{index.json,features.npy,times.npy}``
- ``index.json``：IndexMeta（§3）。
- ``features.npy``：[T, 384] float32 L2 归一化 CLS。
- ``times.npy``：[T] float32 每帧绝对时间。与 features 行对齐。

失效判定（§4）：size/duration/model/dim/sampling_fps/feature_version 快检 +
内容 hash 硬检。任一不满足 -> INVALID；无索引 -> MISSING。失效旧索引入
``.stale`` 隔离命名空间（§4），不静默覆盖。
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from device import DeviceBackend
from domain import (ExtractorConfig, IndexMeta, IndexProgress, IndexValidation,
                    IndexValidationStatus)
from infrastructure.errors import LocatorError
from media.ffmpeg import FFmpegIO, MediaError
from .index_bundle import IndexBundle

ProgressFn = Callable[[IndexProgress], None]


class FeatureStoreError(LocatorError):
    """FeatureStore 操作失败（索引缺失/损坏/无法读取等）。"""


def _feature_version(fps: float) -> str:
    return f"handwritten_vits14_cls_384d@{fps:g}_l2"


class FeatureStore:
    """Original Video 特征索引的生命周期管理。"""

    def __init__(self, ffmpeg: FFmpegIO, index_root: str | Path, *,
                 sampling_fps: float = 0.5, chunk_frames: int = 32,
                 feature_version: str | None = None):
        self.ffmpeg = ffmpeg
        self.index_root = Path(index_root)
        self.sampling_fps = sampling_fps
        self.chunk_frames = chunk_frames
        self.feature_version = feature_version or _feature_version(sampling_fps)

    # ------------------------------------------------------------------ #
    # Index location
    # ------------------------------------------------------------------ #
    def index_dir(self, original_video: str | Path) -> Path:
        """``<stem>__<hash8>.idx``，hash 来自绝对路径以消除同名不同源冲突。"""
        p = Path(original_video).resolve()
        h = hashlib.sha256(str(p).encode("utf-8")).hexdigest()[:8]
        return self.index_root / f"{p.stem}__{h}.idx"

    # ------------------------------------------------------------------ #
    # Create
    # ------------------------------------------------------------------ #
    def create_index(self, original_video: str | Path, backend: DeviceBackend,
                     progress: ProgressFn | None = None) -> IndexMeta:
        video = Path(original_video)
        _notify(progress, IndexProgress("probing"))
        vmeta = self.ffmpeg.metadata(video)
        file_hash = "sha256:" + self.ffmpeg.hash_file(video)

        d = self.index_dir(video)
        if d.exists():
            self._move_aside(d)      # 不静默覆盖已有索引
        d.mkdir(parents=True, exist_ok=True)

        _notify(progress, IndexProgress("extracting_frames"))
        feats, times = self._embed_stream(video, backend, vmeta, progress)

        _notify(progress, IndexProgress("writing"))
        np.save(d / "features.npy", feats)
        np.save(d / "times.npy", times)
        meta = IndexMeta(
            source_file=str(video),
            file_size=vmeta.size_bytes,
            duration=vmeta.duration,
            file_hash=file_hash,
            sampling_fps=self.sampling_fps,
            num_frames=int(times.shape[0]),
            feature_version=self.feature_version,
            feature_dim=int(feats.shape[1]),
            backend=backend.device_name(),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
        (d / "index.json").write_text(
            json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return meta

    def _embed_stream(self, video: Path, backend: DeviceBackend, vmeta,
                      progress: ProgressFn | None) -> tuple[np.ndarray, np.ndarray]:
        chunks, times_all = [], []
        batch, batch_ts = [], []
        total_est = int(vmeta.duration * self.sampling_fps) + 1
        for t, frame in self.ffmpeg.iter_frames(video, self.sampling_fps, meta=vmeta):
            batch.append(frame)
            batch_ts.append(t)
            if len(batch) >= self.chunk_frames:
                chunks.append(backend.embed_frames(batch))
                times_all.extend(batch_ts)
                _notify(progress, IndexProgress("embedding", done=len(times_all), total=total_est))
                batch, batch_ts = [], []
        if batch:
            chunks.append(backend.embed_frames(batch))
            times_all.extend(batch_ts)
        if not chunks:
            raise FeatureStoreError(
                f"No frames extracted from {video.name} at fps={self.sampling_fps}")
        feats = np.concatenate(chunks, axis=0).astype(np.float32)
        times = np.asarray(times_all, dtype=np.float32)
        return feats, times

    # ------------------------------------------------------------------ #
    # Load
    # ------------------------------------------------------------------ #
    def load_index(self, original_video: str | Path) -> IndexBundle:
        d = self.index_dir(original_video)
        meta = self._read_meta(d)
        feats = np.load(d / "features.npy")
        times = np.load(d / "times.npy")
        return IndexBundle(meta, feats, times)

    # ------------------------------------------------------------------ #
    # Validate / invalidate
    # ------------------------------------------------------------------ #
    def validate_index(self, original_video: str | Path) -> IndexValidation:
        video = Path(original_video)
        d = self.index_dir(video)
        if not (d / "index.json").exists() or not (d / "features.npy").exists():
            return IndexValidation(IndexValidationStatus.MISSING)
        if not video.exists():
            return IndexValidation(IndexValidationStatus.INVALID, "source video missing")

        meta = self._read_meta(d)
        # 快检（避免不必要的 1GB 哈希）：size -> duration -> model/dim/fps/version
        if video.stat().st_size != meta.file_size:
            return IndexValidation(IndexValidationStatus.INVALID, "file size changed")
        try:
            cur_dur = self.ffmpeg.metadata(video).duration
        except MediaError:
            return IndexValidation(IndexValidationStatus.INVALID, "cannot read source video")
        if abs(cur_dur - meta.duration) > 0.5:
            return IndexValidation(IndexValidationStatus.INVALID, "duration changed")
        if meta.feature_model != "dinov2_vits14":
            return IndexValidation(IndexValidationStatus.INVALID, "feature model changed")
        if meta.feature_dim != 384:
            return IndexValidation(IndexValidationStatus.INVALID, "feature dim changed")
        if meta.sampling_fps != self.sampling_fps:
            return IndexValidation(IndexValidationStatus.INVALID, "sampling fps changed")
        if meta.feature_version != self.feature_version:
            return IndexValidation(IndexValidationStatus.INVALID, "feature version changed")

        # 硬检：内容哈希（仅在快检通过时，确实保护同 size/duration 不同内容）
        cur_hash = "sha256:" + self.ffmpeg.hash_file(video)
        if cur_hash != meta.file_hash:
            return IndexValidation(IndexValidationStatus.INVALID, "content hash changed")
        return IndexValidation(IndexValidationStatus.VALID)

    def invalidate_index(self, original_video: str | Path) -> None:
        """把现有索引移入 ``.stale`` 隔离命名空间（可恢复，不删除）。"""
        d = self.index_dir(original_video)
        if d.exists():
            self._move_aside(d)

    # ------------------------------------------------------------------ #
    # Metadata / delete
    # ------------------------------------------------------------------ #
    def get_metadata(self, original_video: str | Path) -> IndexMeta:
        """只读 index.json（不要求源视频存在，不哈希）。"""
        return self._read_meta(self.index_dir(original_video))

    def delete_index(self, original_video: str | Path) -> None:
        d = self.index_dir(original_video)
        if d.exists():
            shutil.rmtree(d, ignore_errors=True)
        stale = Path(str(d) + ".stale")
        if stale.exists():
            shutil.rmtree(stale, ignore_errors=True)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _read_meta(self, d: Path) -> IndexMeta:
        p = d / "index.json"
        if not p.exists():
            raise FeatureStoreError(f"index metadata missing: {p}")
        return IndexMeta.from_dict(json.loads(p.read_text(encoding="utf-8")))

    @staticmethod
    def _move_aside(d: Path) -> None:
        stale = Path(str(d) + ".stale")
        if stale.exists():
            shutil.rmtree(stale, ignore_errors=True)
        d.rename(stale)


def _notify(progress: ProgressFn | None, event: IndexProgress) -> None:
    if progress is not None:
        progress(event)
