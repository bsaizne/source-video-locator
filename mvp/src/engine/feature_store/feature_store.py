"""engine.feature_store.FeatureStore — Original Video 特征索引抽象。

冻结基线（INDEX_SPEC）：索引按绝对时间（秒）存，``features.npy`` 与 ``times.npy``
行对齐；创建/加载/校验/失效/删除分离；**禁止**把 numpy/npy/cache 直接暴露给 UI
——一切经本类。原片 seek/decode 走 ``FFmpegIO``（不得用 cv2.CAP_PROP_POS_MSEC）。

落盘（INDEX_SPEC §2）：
``<index_root>/<stem>__<hash8>.idx/{index.json,features.npy,times.npy,scenes.npy,scene_feats.npy}``
- ``index.json``：IndexMeta（§3）。
- ``features.npy``：[T, 384] float32 L2 归一化 CLS。
- ``times.npy``：[T] float32 每帧绝对时间。与 features 行对齐。
- ``scenes.npy``：[S,2] float32 场景起止秒（Phase 21 召回扩展层派生缓存）。
- ``scene_feats.npy``：[S,384] float32 L2 场景指纹（场景内帧均值），与 scenes 行对齐。

失效判定（§4）：size/duration/model/dim/sampling_fps/feature_version 快检 +
内容 hash 硬检 + **预处理指纹**（``extractor.preprocess_sha``，INDEX_SPEC §4 判据的实装）。
任一不满足 -> INVALID；无索引 -> MISSING。失效旧索引入
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
from engine.common import pipeline_map
from engine.segment import detect_shots
from infrastructure.errors import LocatorError
from media.ffmpeg import FFmpegIO, MediaError
from .index_bundle import IndexBundle

ProgressFn = Callable[[IndexProgress], None]

# --- 场景表（Phase 21 召回扩展层,索引侧派生缓存）---
# 参数来自 research_scene_retrieval.py 验证口径（349 场景 / p26 救回）。
SCENE_CUT_ABS = 0.15
SCENE_Z_THRESH = 1.5
SCENE_MIN_SHOT_S = 3.0
SCENE_SMOOTH = 1
SCENE_TABLE_VERSION = "scn1"
# --- 事件表（方向 A 完整阶段, 2026-09-05 用户拍板立项; 探针 POSITIVE）---
# 场景 -> 事件单元归并: 时序近邻(中心时间差<=EVENT_T_GAP_S) + 场景指纹相似(>=EVENT_S_SIM)
# 联合连通分量。参数固化在探针网格最优区(60-120s / 0.55-0.60)取 60s/0.60 保守值。
EVENT_T_GAP_S = 60.0
EVENT_S_SIM = 0.60
EVENT_TABLE_VERSION = "evt1"


class FeatureStoreError(LocatorError):
    """FeatureStore 操作失败（索引缺失/损坏/无法读取等）。"""

    code = "LOC-1103"   # 与 IndexError 同一对外码族：客户侧都是"索引问题"
    user_message = "原片索引不可用，请重新建立该原片的索引后再试。"


def _feature_version(fps: float) -> str:
    # +scn1：索引含场景表（scenes.npy + scene_feats.npy）; +evt1：含事件表
    # （events.npy + event_feats.npy, 方向 A 完整阶段）。+b1 曾试做后回退: 生产实测 batch=1
    # 建索引 10.1fps < batch8 11.2fps（2026-09-05）, 无收益; 数值口径纪律保留——任何改动
    # embed 数值口径的参数（如 batch）必须 bump 此版本号并全程（索引+查询）统一。
    return (f"handwritten_vits14_cls_384d@{fps:g}_l2"
            f"+{SCENE_TABLE_VERSION}+{EVENT_TABLE_VERSION}")


_PROBE_SEED = 20260928          # 固定输入 -> 固定指纹（改种子等于换口径，会让全部索引失效）


def preprocess_probe_bytes() -> bytes:
    """固定合成帧跑一遍**真实** ``_imagenet_preprocess``，取其输出张量字节当指纹。

    为什么测而不声明：``preprocess_sha`` 若只是把 resize/mean/std 抄成字符串，抄的人一旦
    漏改就成了假保险。直接对真实函数取行为指纹，则 resize 尺寸、均值/方差、插值方式、
    归一化顺序任何一处改动都会改变摘要（STATE 里「518→384」那类性能杠杆正是此型改动）。
    不碰标注 frozen 的模型文件，成本 = 一次 60x80 帧的 numpy 变换（微秒级）。
    """
    from device.dinov2_model import _imagenet_preprocess

    rng = np.random.RandomState(_PROBE_SEED)
    frame = rng.randint(0, 256, (60, 80, 3), dtype=np.uint8)
    t = _imagenet_preprocess(frame)
    return t.detach().cpu().numpy().astype(np.float32).tobytes()


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
        scenes, scene_feats = self._build_scene_table(feats, times)
        np.save(d / "scenes.npy", scenes)
        np.save(d / "scene_feats.npy", scene_feats)
        events, event_feats = self._build_event_table(scenes, scene_feats)
        np.save(d / "events.npy", events)
        np.save(d / "event_feats.npy", event_feats)
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
            extractor=ExtractorConfig(
                normalize="l2", resize="518x518", mean_std="imagenet",
                preprocess_sha=self.preprocess_sha(int(feats.shape[1]))),
        )
        (d / "index.json").write_text(
            json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return meta

    def _embed_stream(self, video: Path, backend: DeviceBackend, vmeta,
                      progress: ProgressFn | None) -> tuple[np.ndarray, np.ndarray]:
        chunks, times_all = [], []
        total_est = int(vmeta.duration * self.sampling_fps) + 1

        def _batches():
            batch, batch_ts = [], []
            for t, frame in self.ffmpeg.iter_frames(video, self.sampling_fps, meta=vmeta):
                batch.append(frame)
                batch_ts.append(t)
                if len(batch) >= self.chunk_frames:
                    yield batch, batch_ts
                    batch, batch_ts = [], []
            if batch:
                yield batch, batch_ts

        def _embed(item):
            batch, batch_ts = item
            chunk = backend.embed_frames(batch)
            times_all.extend(batch_ts)
            _notify(progress, IndexProgress("embedding", done=len(times_all), total=total_est))
            return chunk

        # 解码线程与 embed 重叠(零语义; chunk 顺序保持)
        chunks = pipeline_map(_batches(), _embed)
        if not chunks:
            raise FeatureStoreError(
                f"No frames extracted from {video.name} at fps={self.sampling_fps}")
        feats = np.concatenate(chunks, axis=0).astype(np.float32)
        times = np.asarray(times_all, dtype=np.float32)
        return feats, times

    def _build_scene_table(self, feats: np.ndarray,
                           times: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """从索引特征派生场景表：detect_shots 切场景 → 场景内帧均值 L2 作场景指纹。

        - ``scenes.npy``：[S,2] float32（场景起止秒；start 闭 / end 开，覆盖全部帧）。
        - ``scene_feats.npy``：[S,384] float32 L2，与 scenes 行对齐（与 features.npy 同 schema）。
        场景切分为派生缓存（确定性），失败不阻塞索引构建（返回单场景兜底）。
        """
        fps = self.sampling_fps
        try:
            shots = detect_shots(feats, times, cut_abs=SCENE_CUT_ABS,
                                 z_thresh=SCENE_Z_THRESH, min_shot_s=SCENE_MIN_SHOT_S,
                                 smooth=SCENE_SMOOTH, fps=fps)
        except Exception:
            shots = []
        # shots 连续覆盖 [0,n)：由各段帧数恢复边界帧索引。
        bounds = [0]
        for s in shots:
            bounds.append(min(bounds[-1] + s.nq, int(feats.shape[0])))
        if bounds[-1] < int(feats.shape[0]):
            bounds.append(int(feats.shape[0]))
        spans = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)
                 if bounds[i + 1] > bounds[i]]
        scenes = np.zeros((len(spans), 2), dtype=np.float32)
        rows = []
        for k, (a, b) in enumerate(spans):
            scenes[k, 0] = float(times[a])
            scenes[k, 1] = float(times[b - 1]) + 1.0 / float(fps)
            rows.append(feats[a:b].mean(axis=0))
        fp = np.vstack(rows).astype(np.float32)
        fp = fp / np.maximum(np.linalg.norm(fp, axis=1, keepdims=True), 1e-8)
        return scenes, fp

    def _build_event_table(self, scenes: np.ndarray,
                             scene_feats: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """从场景表派生事件单元（方向 A 完整阶段, 2026-09-05 用户拍板）。

        events.npy: [E,2] float32 事件单元起止秒（单元内 min 场景 start / max 场景 end）。
        event_feats.npy: [E,384] float32 L2 事件代表指纹（单元内场景指纹均值）。
        归并规则 = 场景中心时间差 <= EVENT_T_GAP_S AND 指纹余弦 >= EVENT_S_SIM 连通分量
        （时序近邻 + 指纹联合；与 research_event_identity.merge_events 一致）。
        事件表为派生缓存（确定性），失败不阻塞索引构建（返回单事件兜底）。
        """
        try:
            n = len(scenes)
            if n == 0:
                return np.zeros((0, 2), dtype=np.float32), np.zeros((0, 384), dtype=np.float32)
            centers = (scenes[:, 0] + scenes[:, 1]) / 2.0
            parent = list(range(n))

            def _find(x: int) -> int:
                while parent[x] != x:
                    parent[x] = parent[parent[x]]
                    x = parent[x]
                return x

            def _union(a: int, b: int) -> None:
                ra, rb = _find(a), _find(b)
                if ra != rb:
                    parent[ra] = rb

            for i in range(n):
                j = i + 1
                while j < n and centers[j] - centers[i] <= EVENT_T_GAP_S:
                    if float(scene_feats[i] @ scene_feats[j]) >= EVENT_S_SIM:
                        _union(i, j)
                    j += 1
            comps: dict[int, list[int]] = {}
            for i in range(n):
                comps.setdefault(_find(i), []).append(i)
            units = [sorted(m) for m in comps.values()]
            events = np.zeros((len(units), 2), dtype=np.float32)
            rows = []
            for k, u in enumerate(units):
                events[k, 0] = float(scenes[u[0], 0])
                events[k, 1] = float(scenes[u[-1], 1])
                rows.append(scene_feats[u].mean(axis=0))
            ef = np.vstack(rows).astype(np.float32)
            ef = ef / np.maximum(np.linalg.norm(ef, axis=1, keepdims=True), 1e-8)
            return events, ef
        except Exception:
            # 兜底：单事件（整片一个单元），不阻塞索引构建
            return (np.array([[float(scenes[0, 0]), float(scenes[-1, 1])]], dtype=np.float32),
                    np.array([scene_feats.mean(axis=0)], dtype=np.float32))

    # ------------------------------------------------------------------ #
    # Load
    # ------------------------------------------------------------------ #
    def load_index(self, original_video: str | Path) -> IndexBundle:
        d = self.index_dir(original_video)
        meta = self._read_meta(d)
        feats = np.load(d / "features.npy")
        times = np.load(d / "times.npy")
        scenes = np.load(d / "scenes.npy") if (d / "scenes.npy").exists() else None
        scene_feats = np.load(d / "scene_feats.npy") if (d / "scene_feats.npy").exists() else None
        events = np.load(d / "events.npy") if (d / "events.npy").exists() else None
        event_feats = np.load(d / "event_feats.npy") if (d / "event_feats.npy").exists() else None
        return IndexBundle(meta, feats, times, scenes=scenes, scene_feats=scene_feats,
                           events=events, event_feats=event_feats)

    # ------------------------------------------------------------------ #
    # Validate / invalidate
    # ------------------------------------------------------------------ #
    def preprocess_sha(self, feature_dim: int = 384) -> str:
        """当前预处理口径的摘要（INDEX_SPEC §4 的 ``extractor.preprocess_sha`` 判据）。

        覆盖：feature_version + sampling_fps + feature_dim + normalize 标记 + **真实预处理
        行为指纹**。注意 L2 归一发生在 ``backend.embed_frames`` 而非 ``_imagenet_preprocess``，
        故 normalize 一项仍是声明式标记（诚实边界：换后端若改了归一顺序，靠 feature_version
        bump 兜底，本摘要测不到）。
        """
        h = hashlib.sha256()
        h.update(json.dumps({"fv": self.feature_version, "fps": self.sampling_fps,
                             "dim": int(feature_dim), "normalize": "l2"},
                            sort_keys=True, ensure_ascii=False).encode("utf-8"))
        h.update(preprocess_probe_bytes())
        return h.hexdigest()[:16]

    def _backfill_preprocess_sha(self, d: Path, meta: IndexMeta, sha: str) -> None:
        """历史索引（该字段为空）在快检全通过后回填一次摘要，避免为补保险而全量重建。

        回填前提是 size/duration/model/dim/fps/feature_version/内容 hash 均已核对通过，
        即这些维度上确实没有漂移；写回后该索引才纳入预处理指纹保护。
        """
        meta.extractor = ExtractorConfig(**{**meta.extractor.to_dict(), "preprocess_sha": sha})
        (d / "index.json").write_text(json.dumps(meta.to_dict(), indent=2, ensure_ascii=False),
                                      encoding="utf-8")

    def validate_index(self, original_video: str | Path) -> IndexValidation:
        video = Path(original_video)
        d = self.index_dir(video)
        if not (d / "index.json").exists() or not (d / "features.npy").exists():
            return IndexValidation(IndexValidationStatus.MISSING)
        if not (d / "scenes.npy").exists() or not (d / "scene_feats.npy").exists():
            return IndexValidation(IndexValidationStatus.INVALID, "scene table missing")
        if not (d / "events.npy").exists() or not (d / "event_feats.npy").exists():
            return IndexValidation(IndexValidationStatus.INVALID, "event table missing")
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

        # 预处理指纹（INDEX_SPEC §4）：空值 = 该字段实装前建的历史索引 -> 回填后放行（不重建）
        sha = self.preprocess_sha(meta.feature_dim)
        stored = meta.extractor.preprocess_sha
        if not stored:
            self._backfill_preprocess_sha(d, meta, sha)
        elif stored != sha:
            return IndexValidation(IndexValidationStatus.INVALID,
                                   f"preprocess changed ({stored} -> {sha})")
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
