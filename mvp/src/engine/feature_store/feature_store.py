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
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from device import DeviceBackend
from domain import (ExtractorConfig, IndexMeta, IndexProgress, IndexValidation,
                    IndexValidationStatus)
from engine.common import pipeline_map
from engine.segment import detect_shots
from engine.segment.scene_detect import PixelStream, SceneDetectConfig, build_scene_table
from infrastructure.errors import LocatorError
from media.ffmpeg import FFmpegIO, MediaError
from .index_bundle import IndexBundle

ProgressFn = Callable[[IndexProgress], None]

# --- 场景表（Phase 21 召回扩展层,索引侧派生缓存）---
# scn1 = 旧口径：纯 CLS 局部 z-score 切分（边界尺子实测召回 0.232，见 FINDINGS_SHOT_DETECTION_A1）。
# scn2 = 像素/颜色通道 + CLS 证据融合（同尺 P 0.70 / R 0.92 / F1 0.796）。
# scn3 = scn2 判据**一格未动**，只是把边界时刻从 1fps 网格换成像素腿的 10fps 原始时刻
#   （+ 场景起始边界强度侧车表 ``scene_strength.npy``）。为什么：现役吸附实测有符号位移中位
#   +0.215s、绝对中位 0.28s；同批候选唯一变量=是否 snap ⇒ abs_med 0.250→0.050、le0.12 27.6%→77.9%
#   （FINDINGS_BOUNDARY_PRECISION §2/§3）。下游 exporters.snap_clips_to_scenes 直接吃这张表 ⇒
#   精度提升会落到成片端点。判定口径未变，所以场景数与 scene_feats 与 scn2 逐字节相同。
# scn4 = scn3 + **CLS 腿独立语义门**（立项② 方案 A2，2026-10-18）：CLS 腿的持续性门从
#   灰度直方图 ``block_*`` 改为「像素门 **OR** 语义门」。为什么：正反打换人时直方图几乎不变，
#   旧门把它误杀（读图证 test1 5411.46/5415.46：红毛衣女子↔灰衣男子，现役偏差 2.85s/6.85s，
#   新门 0.46s 命中）。门取 OR 不取换——换成纯语义门会丢 test2 4573.3/test3 6682.4 两处图证真切点。
#   尺子：TP 109→111、FP 25 持平、FN 16→14；全片边界 942→912（−3.2%，导出不膨胀）。
#   ⚠️ ``cls_cut_abs`` 0.30→0.40 是**与语义门耦合**的一对：只提 cut_abs 会让尺子 FP 25→38；
#   只在 0.30 加语义门会让**全片边界 +10.9%**。两者必须一起改（见 SceneDetectConfig 注释）。
#   参数与判据实现见 ``engine/segment/scene_detect.py``；换判据必须重过边界尺子。
SCENE_CUT_ABS = 0.15       # （scn1 旧参数，仅 refresh 失败兜底路径与历史测试引用）
SCENE_Z_THRESH = 1.5
SCENE_MIN_SHOT_S = 3.0
SCENE_SMOOTH = 1
SCENE_TABLE_VERSION = "scn4"
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


def _version_base(fps: float) -> str:
    """**特征语义**版本位（改了它 = CLS 向量本身不可比 = 必须重抽特征）。"""
    return f"handwritten_vits14_cls_384d@{fps:g}_l2"


def _version_derived() -> str:
    """**派生表**版本位（改了它 = 只需按已存特征重算场景表/事件表，不必重抽特征）。

    +scn2：场景表含像素通道; +evt1：含事件表（方向 A 完整阶段）。
    +b1 曾试做后回退: 生产实测 batch=1 建索引 10.1fps < batch8 11.2fps（2026-09-05）, 无收益;
    数值口径纪律保留——任何改动 embed 数值口径的参数（如 batch）必须 bump 基座版本并全程统一。
    """
    return f"{SCENE_TABLE_VERSION}+{EVENT_TABLE_VERSION}"


def _feature_version(fps: float) -> str:
    return f"{_version_base(fps)}+{_version_derived()}"


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
                 feature_version: str | None = None,
                 scene_cfg: SceneDetectConfig | None = None,
                 parallel_passes: bool = False):
        self.ffmpeg = ffmpeg
        self.index_root = Path(index_root)
        self.sampling_fps = sampling_fps
        self.chunk_frames = chunk_frames
        self.scene_cfg = scene_cfg or SceneDetectConfig()
        self.feature_version = feature_version or _feature_version(sampling_fps)
        self.parallel_passes = parallel_passes

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
        # 两遍全片解码（像素预扫 10fps 低分辨率 / 特征嵌入 1fps 全分辨率）互相独立，
        # 并发执行不改变任何产物（同一 ffmpeg 过滤器链、同一帧集），只省墙钟。
        # 默认关：并发会让两阶段进度消息交错，等四片等价性验收后再决定是否翻默认。
        scan_thread = None
        scan_holder: dict[str, object] = {}
        if self.parallel_passes:
            def _run_scan() -> None:
                try:
                    scan_holder["pixel"] = self._scan_pixel_boundaries(video, vmeta, progress)
                except BaseException as exc:       # 线程内异常必须回传主线程，不能静默吞
                    scan_holder["error"] = exc
            scan_thread = threading.Thread(target=_run_scan, name="pixel-scan", daemon=True)
            scan_thread.start()

        feats, times = self._embed_stream(video, backend, vmeta, progress)

        _notify(progress, IndexProgress("writing"))
        np.save(d / "features.npy", feats)
        np.save(d / "times.npy", times)
        if scan_thread is not None:
            scan_thread.join()
            if "error" in scan_holder:
                raise scan_holder["error"]           # type: ignore[misc]
            pixel = scan_holder.get("pixel")         # type: ignore[assignment]
        else:
            pixel = self._scan_pixel_boundaries(video, vmeta, progress)
        scenes, scene_feats = self._build_scene_table(feats, times, pixel=pixel)
        np.save(d / "scenes.npy", scenes)
        np.save(d / "scene_feats.npy", scene_feats)
        self._save_scene_strength(d, scenes)
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

    def _scan_pixel_boundaries(self, video: Path, vmeta, progress: ProgressFn | None,
                               ) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
        """像素通道预扫：低分辨率 ``pixel_fps`` 逐帧算相邻帧颜色/灰度差 + 每帧直方图。

        返回 ``(新镜头首帧时间[], 差分数[], 每帧直方图[n,32])``。直方图供 A-B-A 持续性门
        判断「切过去之后有没有待住」——闪电/爆白/甩镜这类瞬时尖峰靠它拦。

        成本判据（FINDINGS §5 实测）：300s 片段整段解码 17~18s，**与输出 300 帧还是 3000 帧几乎无关**
        ⇒ 成本主体是解码本身，直方图是零头；且纯 CPU，可与 DML/MPS 推理并发。
        失败（解码异常等）返回 ``None`` ⇒ 场景表退回「只有 CLS 证据」，不阻塞索引构建。
        """
        cfg = self.scene_cfg
        if not cfg.pixel_enabled:
            return None
        stream = PixelStream(hist_weight=cfg.pixel_hist_weight)
        total_est = int(float(vmeta.duration) * cfg.pixel_fps) + 1
        try:
            for t, frame in self.ffmpeg.iter_frames(
                    video, cfg.pixel_fps, scale=(cfg.pixel_width, cfg.pixel_height),
                    meta=vmeta):
                stream.push(float(t), frame)
                if len(stream.times) % 512 == 0:
                    _notify(progress, IndexProgress("pixel_scan", done=len(stream.times),
                                                    total=total_est))
        except (MediaError, OSError, ValueError) as exc:
            self._log_pixel_scan_failure(exc)
            return None
        times, scores = stream.arrays()
        if times.size < 3:
            return None
        return times, scores, stream.hist_matrix()

    @staticmethod
    def _log_pixel_scan_failure(exc: Exception) -> None:
        """像素预扫失败只降级不致命，但必须留痕（否则 scn2 静默退回 scn1 行为没人知道）。"""
        import logging
        logging.getLogger("engine.feature_store").warning(
            "pixel boundary scan failed, scene table falls back to CLS evidence only: %s: %s",
            type(exc).__name__, exc)

    def _save_scene_strength(self, d: Path, scenes: np.ndarray) -> None:
        """落盘 ``scene_strength.npy``（scn3 侧车）。**失败只降级不留毒**。

        侧车是**可选信息**：写不出来就当没有（下游按「未知强度」处理），绝不因为一个附属表
        让整次建索引失败。长度必须与 scenes 行数严格对齐，否则同样丢弃——
        下游依赖「有侧车 ⇒ 长度相等」这条约定（``load_index`` 会校验）。
        """
        try:
            stg = getattr(self, "_last_scene_strength", None) or {}
            n = int(scenes.shape[0])
            if n == 0:
                return
            arr = np.ones(n, dtype=np.float32)
            for k, v in stg.items():
                if 0 <= int(k) < n:
                    arr[int(k)] = float(v)
            np.save(d / "scene_strength.npy", arr)
        except Exception as exc:                     # noqa: BLE001
            import logging
            logging.getLogger("engine.feature_store").warning(
                "scene_strength sidecar skipped (non-fatal): %s: %s",
                type(exc).__name__, exc)

    @staticmethod
    def _load_scene_strength(d: Path, scenes: np.ndarray | None) -> np.ndarray | None:
        """读 ``scene_strength.npy`` 侧车；**任何不一致都返回 None**（= 强度未知）。

        为什么宁可丢也不修：侧车是可选信息，错位的强度比没有强度更危险——
        下游会拿它去标「低置信边界」，长度/类型不对就等于把强度贴到错的场景上。
        约定（与 ``_save_scene_strength`` 对齐）：有侧车 ⇒ 长度严格等于 scenes 行数。
        """
        p = d / "scene_strength.npy"
        if not p.exists() or scenes is None or getattr(scenes, "size", 0) == 0:
            return None
        try:
            arr = np.load(p)
            n = int(scenes.shape[0])
            if arr.ndim != 1 or int(arr.shape[0]) != n:
                return None
            return arr.astype(np.float32, copy=False)
        except Exception:                            # noqa: BLE001
            return None

    def _build_scene_table(self, feats: np.ndarray, times: np.ndarray,
                           pixel: tuple[np.ndarray, np.ndarray] | None = None,
                           ) -> tuple[np.ndarray, np.ndarray]:
        """从索引特征派生场景表（scn3：scn2 判据 + 10fps 原始边界时刻 + 强度侧车）。

        - ``scenes.npy``：[S,2] float32（场景起止秒；start 闭 / end 开，覆盖全部帧）。
        - ``scene_feats.npy``：[S,384] float32 L2，与 scenes 行对齐（与 features.npy 同 schema）。
        - ``scene_strength.npy``（scn3 新增，侧车）：[S] float32 每个场景**起始边界**的融合强度；
          第 0 个恒为 1.0（文件起点不是切分）。缺失时下游行为必须与本表未引入时逐字相同。
        场景切分为派生缓存（确定性），失败不阻塞索引构建（返回单场景兜底）。
        ``self._last_scene_strength`` = 最近一次派生的强度表（供落盘侧车用，避免改返回值签名）。
        """
        fps = self.sampling_fps
        raw: dict[int, float] = {}
        stg: dict[int, float] = {}
        self._last_scene_strength = {}
        try:
            scenes, fp = build_scene_table(feats, times, pixel, self.scene_cfg, float(fps),
                                           boundary_time_out=raw, strength_out=stg)
            self._last_scene_strength = {int(k): float(v) for k, v in stg.items()}
            return scenes, fp
        except Exception:
            pass
        # 兜底一：旧 scn1 口径（纯 CLS 局部 z-score），至少不是「整片一个场景」
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
        self._last_scene_strength = {k: 1.0 for k in range(len(spans))}
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
    # Derived-table refresh (scn1 -> scn2 这类「基座语义未变」的升级)
    # ------------------------------------------------------------------ #
    def refresh_derived(self, original_video: str | Path,
                        progress: ProgressFn | None = None) -> IndexMeta:
        """只重算派生表（``scenes`` / ``scene_feats`` / ``events`` / ``event_feats``），**不重抽特征**。

        为什么单独有这条路：派生判据（怎么定镜头边界）变了，而 CLS 向量本身没变——
        走 ``create_index`` 等于把全片 1fps 全分辨率抓帧 + 推理（建索引墙钟的大头）白付一遍。
        这里只付一遍低分辨率像素预扫（实测成本主体是解码，与帧数几乎无关）。

        前提（由 ``validate_index`` 的 ``derived_stale`` 判据保证）：文件哈希/大小/时长/
        sampling_fps/基座版本都已核对通过。四张表**全部算完才落盘**，
        中途失败不会留下「新场景表 + 旧事件表」的混搭。
        """
        video = Path(original_video)
        d = self.index_dir(video)
        meta = self._read_meta(d)
        for need in ("features.npy", "times.npy"):
            if not (d / need).exists():
                raise FeatureStoreError(f"cannot refresh derived tables without {need}: {d}")
        feats = np.load(d / "features.npy")
        times = np.load(d / "times.npy")
        _notify(progress, IndexProgress("pixel_scan"))
        vmeta = self.ffmpeg.metadata(video)
        pixel = self._scan_pixel_boundaries(video, vmeta, progress)
        scenes, scene_feats = self._build_scene_table(feats, times, pixel=pixel)
        events, event_feats = self._build_event_table(scenes, scene_feats)
        np.save(d / "scenes.npy", scenes)
        np.save(d / "scene_feats.npy", scene_feats)
        self._save_scene_strength(d, scenes)
        np.save(d / "events.npy", events)
        np.save(d / "event_feats.npy", event_feats)
        meta.feature_version = self.feature_version
        # 预处理指纹覆盖「基座版本 + fps + dim + 真实预处理行为」；这里基座行为逐字未动，
        # 变的只有派生表版本位，所以按当前口径重写它（不重写的话下次校验会报
        # "preprocess changed"，把一条本来省掉全量推理的升级又打回全重建）。
        meta.extractor = ExtractorConfig(**{**meta.extractor.to_dict(),
                                            "preprocess_sha": self.preprocess_sha(
                                                int(meta.feature_dim))})
        (d / "index.json").write_text(
            json.dumps(meta.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return meta

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
        scene_strength = self._load_scene_strength(d, scenes)
        return IndexBundle(meta, feats, times, scenes=scenes, scene_feats=scene_feats,
                           events=events, event_feats=event_feats,
                           scene_strength=scene_strength)

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
            # 只有**派生表**版本位变了（基座语义没动）=> 特征可复用，走 refresh_derived。
            # 基座位变了 => CLS 向量不可比，只能全量重建。
            # 比的是**两条版本串各自的基座段**，不是拿 sampling_fps 反推——
            # FeatureStore 可以被显式传入任意 feature_version（测试与历史索引比对都这么用），
            # 那时反推出来的基座会把「基座变了」误判成「只有派生过期」，把该重建的放过去。
            stored_base = str(meta.feature_version).split("+", 1)[0]
            cur_base = str(self.feature_version).split("+", 1)[0]
            if stored_base != cur_base:
                return IndexValidation(IndexValidationStatus.INVALID, "feature version changed")
            derived_stale = True
        else:
            derived_stale = False

        # 硬检：内容哈希（仅在快检通过时，确实保护同 size/duration 不同内容）
        # 注意：派生表过期这条也必须过内容哈希——特征对应的必须是**同一份内容**才允许复用。
        cur_hash = "sha256:" + self.ffmpeg.hash_file(video)
        if cur_hash != meta.file_hash:
            return IndexValidation(IndexValidationStatus.INVALID, "content hash changed")

        if derived_stale:
            return IndexValidation(
                IndexValidationStatus.INVALID,
                f"derived table version changed ({meta.feature_version} -> {self.feature_version})",
                derived_stale=True)

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
