"""app.locator_service — 用例编排（Original 索引 + Edited 分析 + Result 汇总 + 持久化）。

产品胶水层：只做 ``orchestrate / progress / cancellation / error 汇总``，不写视觉算法。
冻结链路（只调用不改语义）：FFmpegIO 抽帧 -> DINOv2 特征 -> FeatureStore 索引 ->
``engine.segment`` 切分 -> ``produce_candidates``(cluster/rank v2_score) ->
``localize_segment``(finloc + confidence) -> ``domain.Result``。

失败隔离（§四）：单个 edited segment 失败 -> unresolved(LOW) Result，带 ``failure_reason``，
完整异常记日志，**继续处理后续 segment**，不让整个 edited task 失败。

错误翻译（§十一）：把底层异常包装为可处理类型（GUI ``except LocatorError``），不解析原始 string。
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np

from device import DeviceBackend, pick_best_available
from domain import (Confidence, ConfidenceLevel, IndexValidationStatus, Result,
                    ResultBatch, ResultSource, TimeSpan)
from engine.candidates import produce_candidates
from engine.feature_store import FeatureStore, FeatureStoreError, IndexBundle
from engine.localization.pipeline import localize_segment
from engine.segment import ShotSegment, detect_shots
from infrastructure import paths
from infrastructure.config import AppConfig, PipelineConfig, load_config
from infrastructure.errors import (ApplicationError, FeatureExtractionError,
                                   IndexError)
from infrastructure.logging import get_logger
from infrastructure.results_repo import (load_results as _load_results,
                                         save_results as _save_results)
from media.ffmpeg import FFmpegIO, MediaError

from .models import CancellationToken, ProgressEvent, ProgressStage

ProgressCb = Callable[[ProgressEvent], None]


class SourceLocatorService:
    """MVP 后台完整链路的编排入口（UI 唯一入口）。

    ``locate(edited, original)`` = 一步跑完 Original 索引 + Edited 分析 + Result 汇总：
    Original -> Index -> Edited Segments -> Candidates -> Localization -> Confidence -> Results。
    """

    def __init__(self, *, config: AppConfig | None = None,
                 ffmpeg: FFmpegIO | None = None,
                 backend: DeviceBackend | None = None,
                 index_root: str | Path | None = None,
                 export_root: str | Path | None = None):
        self.config = config or load_config()
        data_dir = self.config.data_dir
        # ffmpeg / backend / feature_store 惰性构建：仅做纯编排（如 _locate_features）
        # 或未配置二进制时不强制解析，避免构造即失败。
        self._ffmpeg: FFmpegIO | None = ffmpeg
        self._backend: DeviceBackend | None = backend
        self._store: FeatureStore | None = None
        self.index_root = Path(index_root) if index_root else paths.index_root(override=data_dir)
        self.export_root = Path(export_root) if export_root else paths.export_root(override=data_dir)
        self._log = get_logger(__name__)
        # 会话状态（轻量；UI 自身另持状态）
        self._bundle: IndexBundle | None = None
        self._current_batch: ResultBatch | None = None
        self._current_original: Path | None = None
        self._current_edited: Path | None = None

    @property
    def ffmpeg(self) -> FFmpegIO:
        if self._ffmpeg is None:
            self._ffmpeg = FFmpegIO(
                self.config.media.ffmpeg_path, self.config.media.ffprobe_path,
                timeout_s=self.config.media.timeout_s)
        return self._ffmpeg

    @property
    def backend(self) -> DeviceBackend:
        if self._backend is None:
            self._backend = pick_best_available(self.config)
        return self._backend

    @property
    def store(self) -> FeatureStore:
        if self._store is None:
            self._store = FeatureStore(self.ffmpeg, self.index_root,
                                       sampling_fps=self.config.pipeline.index_sampling_fps)
        return self._store

    # ------------------------------------------------------------------ #
    # 用例一：Original 索引（build / reuse）
    # ------------------------------------------------------------------ #
    def build_original_index(self, original: str | Path, *, on_progress: ProgressCb | None = None,
                             cancel_token: CancellationToken | None = None) -> IndexBundle:
        """确保原片特征索引就绪并返回 ``IndexBundle``。已 VALID 则复用，否则 (重)建。"""
        original = Path(original)
        self._check_cancel(cancel_token)
        self._log.info("build_original_index: %s", original)
        try:
            v = self.store.validate_index(original)
            if v.status is IndexValidationStatus.VALID:
                self._notify(on_progress, ProgressStage.INDEX_BUILD,
                             message=f"reuse index: {original.name}")
                bundle = self.store.load_index(original)
            else:
                if v.status is IndexValidationStatus.INVALID and v.reason:
                    self._log.info("rebuild index (%s): %s", original.name, v.reason)
                self._notify(on_progress, ProgressStage.INDEX_BUILD,
                             message=f"building index: {original.name}")
                meta = self.store.create_index(
                    original, self.backend,
                    progress=self._index_progress(on_progress, cancel_token))
                self._notify(on_progress, ProgressStage.INDEX_BUILD,
                             current=meta.num_frames, total=max(meta.num_frames, 1),
                             message=f"index ready: {meta.num_frames} frames")
                bundle = self.store.load_index(original)
        except (MediaError, FeatureStoreError) as exc:
            raise IndexError(f"failed to build/load original index for {original.name}: {exc}") from exc

        self._bundle = bundle
        self._current_original = original
        return bundle

    # ------------------------------------------------------------------ #
    # 用例二：Edited 分析（抽帧 + 切分）
    # ------------------------------------------------------------------ #
    def analyze_edited_video(self, edited: str | Path, *, on_progress: ProgressCb | None = None,
                             cancel_token: CancellationToken | None = None) -> list[ShotSegment]:
        """返回无 GT 查询单元列表（``ShotSegment``）。空帧 -> ApplicationError。"""
        edited = Path(edited)
        self._check_cancel(cancel_token)
        cfg = self.config.pipeline
        try:
            self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                         message="extracting edited frames")
            frames = list(self.ffmpeg.iter_frames(edited, cfg.edited_segment_fps))
            self._check_cancel(cancel_token)
            if not frames:
                raise ApplicationError(f"edited video has no frames extracted: {edited.name}")
            ed_times = np.array([t for t, _ in frames], dtype=np.float32)
            ed_feats = self.backend.embed_frames([f for _, f in frames])
            self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                         current=len(frames), total=max(len(frames), 1),
                         message=f"embedded {len(frames)} edited frames")
        except ApplicationError:
            raise
        except (MediaError, Exception) as exc:
            raise FeatureExtractionError(
                f"failed to extract edited feats from {edited.name}: {exc}") from exc

        self._check_cancel(cancel_token)
        self._notify(on_progress, ProgressStage.SEGMENT_DETECTION, message="detecting shots")
        shots = detect_shots(ed_feats, ed_times,
                             cut_abs=cfg.seg_cut_abs, z_thresh=cfg.seg_z_thresh,
                             min_shot_s=cfg.seg_min_shot_s, smooth=cfg.seg_smooth,
                             fps=cfg.edited_segment_fps)
        self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                     current=len(shots), total=max(len(shots), 1),
                     message=f"{len(shots)} segments")
        self._current_edited = edited
        return shots

    # ------------------------------------------------------------------ #
    # 用例三：主链路（Original + Edited -> ResultBatch）
    # ------------------------------------------------------------------ #
    def locate(self, edited: str | Path, original: str | Path | IndexBundle, *,
               on_progress: ProgressCb | None = None,
               cancel_token: CancellationToken | None = None,
               index_bundle: IndexBundle | None = None) -> ResultBatch:
        """一步编排完整链路，返回 ``ResultBatch``（每条 Result 对应一个 edited segment）。"""
        edited = Path(edited)
        if index_bundle is not None:
            bundle = index_bundle
            orig_path = bundle.meta.source_file
        else:
            bundle = self.build_original_index(original, on_progress=on_progress,
                                               cancel_token=cancel_token)
            orig_path = str(Path(original).resolve())

        shots = self.analyze_edited_video(edited, on_progress=on_progress,
                                          cancel_token=cancel_token)
        results = self._locate_features(shots, bundle,
                                        cfg=self.config.pipeline,
                                        on_progress=on_progress,
                                        cancel_token=cancel_token)
        batch = ResultBatch(schema_version=1, original_video=str(orig_path),
                            edited_video=str(Path(edited).resolve()), results=results)
        self._current_batch = batch
        return batch

    def _locate_features(self, shots: list[ShotSegment], bundle: IndexBundle, *,
                         cfg: PipelineConfig | None = None,
                         on_progress: ProgressCb | None = None,
                         cancel_token: CancellationToken | None = None) -> list[Result]:
        """纯管线（无 IO）：逐 segment 检索/定位/置信度，失败隔离为 unresolved Result。"""
        cfg = cfg or self.config.pipeline
        results: list[Result] = []
        n = len(shots)
        for idx, shot in enumerate(shots):
            self._check_cancel(cancel_token)
            try:
                self._notify(on_progress, ProgressStage.CANDIDATE_RETRIEVAL,
                             current=idx, total=n, message=f"segment {idx + 1}/{n}: retrieval")
                cands = produce_candidates(shot.feats, shot.times, bundle, cfg=cfg)

                self._notify(on_progress, ProgressStage.LOCALIZATION,
                             current=idx, total=n, message=f"segment {idx + 1}/{n}: localize")
                if not cands:
                    results.append(self._unresolved_result(shot, "no_candidates"))
                    continue
                refined = localize_segment(cands, shot.feats, bundle, cfg=cfg)

                self._notify(on_progress, ProgressStage.CONFIDENCE,
                             current=idx, total=n, message=f"segment {idx + 1}/{n}: confidence")
                if refined is None:
                    results.append(self._unresolved_result(shot, "no_span"))
                    continue
                results.append(self._result_from_refined(shot.span, refined))
            except ApplicationError:
                raise  # cancellation 穿透，不做段级隔离
            except Exception as exc:
                self._log.error("segment %d/%d failed: %s", idx + 1, n, exc, exc_info=True)
                results.append(self._unresolved_result(
                    shot, f"segment_error: {type(exc).__name__}: {exc}"))
        return results

    # ------------------------------------------------------------------ #
    # 用例四：持久化
    # ------------------------------------------------------------------ #
    def export_results(self, batch: ResultBatch, *, out_dir: str | Path | None = None,
                       filename: str | None = None,
                       on_progress: ProgressCb | None = None,
                       cancel_token: CancellationToken | None = None) -> Path:
        """落盘一个结果批到 JSON（RESULT schema）。返回写入路径。"""
        self._check_cancel(cancel_token)
        self._notify(on_progress, ProgressStage.EXPORT, message="exporting results")
        path = _save_results(batch, out_dir=out_dir or self.export_root, filename=filename)
        self._notify(on_progress, ProgressStage.EXPORT,
                     current=len(batch.results), total=max(len(batch.results), 1),
                     message=f"exported {path.name}")
        return path

    def load_results(self, path: str | Path) -> ResultBatch:
        """从 JSON 读回一个结果批。"""
        return _load_results(path)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _result_from_refined(edited_span: TimeSpan, refined) -> Result:
        """把 RefinedSegment 汇总为 domain.Result（edited=查询单元 span）。"""
        return Result(
            edited=edited_span,
            original=refined.original,
            confidence=refined.confidence,
            candidate_rank=refined.candidate_rank,
            alternatives=refined.alternatives,
            source=ResultSource.AUTO,
            montage_flag=refined.montage_flag,
        )

    @staticmethod
    def _unresolved_result(shot: ShotSegment, reason: str) -> Result:
        """段级失败/无结果 -> LOW unresolved Result（不中断整段任务）。"""
        return Result(
            edited=shot.span,
            confidence=Confidence(ConfidenceLevel.LOW, 0.0, (reason,)),
            source=ResultSource.AUTO,
            failure_reason=reason,
        )

    @staticmethod
    def _index_progress(on_progress: ProgressCb | None,
                        cancel_token: CancellationToken | None) -> Callable:
        """把 FeatureStore 的 IndexProgress 翻译为 INDEX_BUILD ProgressEvent。"""
        def cb(p) -> None:
            if cancel_token is not None:
                cancel_token.raise_if_cancelled()
            if on_progress is not None:
                on_progress(ProgressEvent(ProgressStage.INDEX_BUILD,
                                          current=p.done, total=p.total,
                                          message=f"index {p.stage}"))
        return cb

    @staticmethod
    def _notify(on_progress: ProgressCb | None, stage: ProgressStage,
                current: int = 0, total: int = 0, message: str = "") -> None:
        if on_progress is not None:
            on_progress(ProgressEvent(stage, current, total, message))

    @staticmethod
    def _check_cancel(cancel_token: CancellationToken | None) -> None:
        if cancel_token is not None:
            cancel_token.raise_if_cancelled()
