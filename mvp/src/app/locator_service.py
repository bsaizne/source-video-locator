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

import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np

from device import DeviceBackend, directml_available, mps_available, pick_best_available
from domain import (Confidence, ConfidenceLevel, IndexValidation,
                    IndexValidationStatus, OriginalSegment, Result, ResultBatch,
                    ResultSource, TimeSpan)
from app.edited_cache import EditedCache, fingerprint as edited_cache_fingerprint
from functools import partial
from concurrent.futures import ThreadPoolExecutor

from engine.confidence import ConfidenceEngine
from engine.feature_store import FeatureStore, FeatureStoreError, IndexBundle
from engine.localization.evidence_localize import EvidenceLocalizer, EvidenceResult
from engine.localization.temporal_repair import (find_overlap_conflicts,
                                                 find_temporal_outliers, relocate_in_window)
from engine.localization.conflict_rerank import (accept_repair, best_free_span,
                                                 find_span_conflicts,
                                                 span_mean_sim)
from engine.localization.seq_align import align_moments
from engine.localization.sequence_rerank import sequence_rerank
from engine.localization.patch_rerank import (PatchReranker, patch_score,
                                              resolve_patch_onnx, resolve_weights)
from engine.localization.text_anchor import OcrEngine, filter_watermark, text_similarity
from engine.common import cosine_similarity, pipeline_map
from engine.segment import (ShotSegment, adjacent_distances,
                            detect_shots, detect_shots_two_level,
                            is_card_frame, max_card_run_ratio,
                            brightness_spike_regions, drop_brightness_spike_cuts,
                            drop_flash_cuts, dynamic_min_shot, frame_mean_brightness,
                            is_flash_frame, merge_flash_segments)
from infrastructure import paths, settings_repo
from infrastructure.config import AppConfig, PipelineConfig, load_config
from infrastructure.errors import (ApplicationError, DeviceError,
                                   FeatureExtractionError, IndexError)
from infrastructure.logging import get_logger, get_session_id, new_session_id
from infrastructure.results_repo import (load_results as _load_results,
                                         save_results as _save_results)
from media.ffmpeg import FFmpegIO, MediaError

from .exporters import (EXPORT_FORMATS, ExportClip, build_export_plan,
                        create_jianying_draft_dir, expand_material_spans,
                        plan_jianying_assets,
                        render_edl, render_fcp7_xml, seconds_to_frames,
                        snap_clips_to_scenes, write_jianying_draft)
from .models import CancellationToken, ProgressEvent, ProgressStage

ProgressCb = Callable[[ProgressEvent], None]


def _moment_dict(m) -> dict:
    """MomentSpan -> 契约 dict（供 OriginalSegment.moments 持久化，向后兼容）。"""
    return {"edited_start": m.edited_interval[0], "edited_end": m.edited_interval[1],
            "original_start": m.original_span[0], "original_end": m.original_span[1],
            "mean_sim": m.mean_sim, "peak_sim": m.peak_sim,
            "n_frames": m.n_frames, "confidence": m.confidence}


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
        # 跨重启保留用户选的推理后端：持久化 preferred 覆盖默认（若存在且合法）。
        persisted_pref = settings_repo.load_device_preferred(data_dir)
        if persisted_pref in settings_repo.VALID_DEVICE_PREFS:
            self.config.device.preferred = persisted_pref
        # ffmpeg / backend / feature_store 惰性构建：仅做纯编排（如 _locate_features）
        # 或未配置二进制时不强制解析，避免构造即失败。
        self._ffmpeg: FFmpegIO | None = ffmpeg
        self._backend: DeviceBackend | None = backend
        self._store: FeatureStore | None = None
        self.index_root = Path(index_root) if index_root else paths.index_root(override=data_dir)
        self.export_root = Path(export_root) if export_root else paths.export_root(override=data_dir)
        self._log = get_logger(__name__)
        # multi-evidence 主定位器（query-axis 逐帧 top1 聚类；无 IO，仅参数，构造即安全）
        p = self.config.pipeline
        sa = p.seq_align
        seq_align = None
        if sa.enabled:
            seq_align = partial(
                align_moments, sim_thresh=sa.sim_thresh, mean_sim_min=sa.global_mean_sim_min,
                min_hits=sa.min_hits, min_moment_s=sa.min_moment_s,
                diag_penalty=sa.diag_penalty, step_penalty=sa.step_penalty,
                max_edited_gap=sa.max_edited_gap, max_orig_gap=sa.max_orig_gap,
                max_cells=sa.max_cells)
        self._evidence_localizer = EvidenceLocalizer(
            min_frames=p.montage_min_frames, min_sim=p.montage_min_sim,
            cluster_gap_s=p.montage_cluster_gap_s,
            weak_cover=p.montage_weak_cover, weak_sim=p.montage_weak_sim,
            max_span_s=p.max_orig_span_s,
            subspan_min_cover=p.subspan_min_cover, subspan_min_sim=p.subspan_min_sim,
            subspan_iou_merge=p.subspan_iou_merge, subspan_max_keep=p.subspan_max_keep,
            seq_align=seq_align,
            seq_pad_s=sa.pad_s, seq_window_max_s=sa.window_max_s,
            seq_global_mean_sim_min=sa.global_mean_sim_min,
            seq_max_query_frames=sa.max_query_frames, seq_moment_half_s=sa.moment_half_s,
            finloc_stable_s=p.confidence.finloc_stable_s,
            seq_mean_sim_min=sa.mean_sim_min,
            scene_recall_enabled=p.scene_recall_enabled, scene_top_k=p.scene_top_k,
            scene_max_expand_frames=p.scene_max_expand_frames,
            event_recall_enabled=p.event_recall_enabled, event_top_k=p.event_top_k,
            event_max_expand_frames=p.event_max_expand_frames,
        )
        self._dense_cache = {}
        self._tr_query_cache: dict = {}
        self._grab_cache: dict = {}  # grab_frame 进程内缓存(patch rerank/text anchor 重复抓同帧)
        self._edited_cache: EditedCache | None = None
        self._edited_cache_key_by_path: dict = {}
        self._ocr_engine: OcrEngine | None = None
        self._patch_reranker: PatchReranker | None = None
        # 会话状态（轻量；UI 自身另持状态）
        self._bundle: IndexBundle | None = None
        self._current_batch: ResultBatch | None = None
        self._current_original: Path | None = None
        self._current_edited: Path | None = None
        self._last_candidates = 0
        self._last_seq_items: list[dict] = []

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
    # 设备后端偏好（唯一会改变运行时推理后端的设置；其余为展示/占位）。
    # ------------------------------------------------------------------ #
    @property
    def device_preference(self) -> str:
        """当前推理后端偏好：``auto`` / ``cpu`` / ``directml``。"""
        return self.config.device.preferred

    def set_device_preference(self, preferred: str) -> None:
        """设置推理后端偏好，重置已构建 backend（下次用新偏好重建），并持久化。

        不改任何冻结算法语义；只改 ``config.device.preferred``。非法值 -> ApplicationError。
        """
        if preferred not in settings_repo.VALID_DEVICE_PREFS:
            raise ApplicationError(f"invalid device preference: {preferred!r} "
                                   f"(expected one of {settings_repo.VALID_DEVICE_PREFS})")
        if preferred != self.config.device.preferred:
            self.config.device.preferred = preferred
            # 若 backend 已构建，重置使其在下次访问时按新偏好重建。
            self._backend = None
            self._log.info("device preference changed to=%s", preferred)
        settings_repo.save_device_preferred(preferred, self.config.data_dir)

    def device_settings(self) -> dict:
        """返回设备偏好 + 实际生效后端（只读；会惰性构建一次 backend，见 self.backend）。

        ``fallback``：请求了 GPU/DML（auto 或 directml）但实际落到 CPU -> True。
        UI 据此区分「期望」与「实际」，不静默。
        """
        b = self.backend
        dml_ok, _ = directml_available()
        available = ["cpu"]
        if dml_ok:
            available.append("directml")
        if sys.platform == "darwin" and mps_available()[0]:
            available.append("mps")
        return {
            "preferred": self.device_preference,
            "actual_device_name": b.device_name(),   # cpu / directml
            "actual_device_type": b.device_type(),   # cpu / amd
            "is_accelerator": b.device_type() != "cpu",
            "fallback": self.device_preference in ("auto", "directml") and b.device_name() == "cpu",
            "available_devices": available,
        }

    # ------------------------------------------------------------------ #
    # 用例一：Original 索引（build / reuse）
    # ------------------------------------------------------------------ #
    def index_status(self, original: str | Path):
        """透传 FeatureStore.validate_index（真实磁盘状态，供 GET /api/index/status 用）。

        前置校验：路径非绝对或文件不存在 → 直接 INVALID "source video missing"，
        避免无谓调用 ffprobe（也避免相对路径误判）。
        """
        p = Path(original)
        if not p.is_absolute() or not p.exists():
            return IndexValidation(IndexValidationStatus.INVALID, "source video missing")
        return self.store.validate_index(p)

    def build_original_index(self, original: str | Path, *, on_progress: ProgressCb | None = None,
                             cancel_token: CancellationToken | None = None) -> IndexBundle:
        """确保原片特征索引就绪并返回 ``IndexBundle``。已 VALID 则复用，否则 (重)建。"""
        original = Path(original)
        # 前置校验：路径必须绝对且文件存在。相对路径/裸名/文件不存在 → 明确可读错误，
        # 不再走到 create_index/ffprobe 才失败（那是"源片只有文件名"导致构建失败的根因）。
        if not original.is_absolute() or not original.exists():
            self._log.warning("index invalid source path=%s", original)
            raise IndexError(
                f"源片路径无效或不存在：{original}。请在项目里点「选择源片文件」选择真实视频文件（需要完整路径）。")
        self._check_cancel(cancel_token)
        self._ensure_session()
        t0 = time.monotonic()
        self._log.info("index started video=%s", original.name)
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
        except IndexError:
            raise
        except (MediaError, FeatureStoreError, DeviceError, OSError) as exc:
            self._log.exception("index failed video=%s", original.name)
            raise IndexError(f"failed to build/load original index for {original.name}: {exc}") from exc
        except Exception as exc:
            # onnxruntime RuntimeError 等兜底：统一包 IndexError，保证日志有 "index failed" 前缀。
            self._log.exception("index failed video=%s (unhandled)", original.name)
            raise IndexError(f"failed to build/load original index for {original.name}: {exc}") from exc

        self._bundle = bundle
        self._current_original = original
        meta = bundle.meta
        self._log.info("index finished video=%s frames=%s backend=%s elapsed=%.1fs",
                       original.name, meta.num_frames, meta.backend, time.monotonic() - t0)
        return bundle

    # ------------------------------------------------------------------ #
    # 用例二：Edited 分析（抽帧 + 切分）
    # ------------------------------------------------------------------ #
    def analyze_edited_video(self, edited: str | Path, *, on_progress: ProgressCb | None = None,
                             cancel_token: CancellationToken | None = None) -> list[ShotSegment]:
        """返回无 GT 查询单元列表（ShotSegment）。空帧 -> ApplicationError。

        seg_twopass_enabled（C 项验证 2026-09-05 用户拍板进 runtime）:
        两级分层切分 + 白闪守卫——粗采样(5-8 帧步长)找候选切点 -> 白闪/亮度尖峰
        邻域切点删除 -> 局部 ±20 帧密帧精修真实边界 -> 最短镜头保护 0.5s
        （白闪邻域动态 1.0-1.2s）-> 业务兜底合并。验证: 四片严格 112/139 (+8)、
        场景级 136/139 (+18)、负例 4/9 持平。关闭开关回退旧 detect_shots_two_level。
        """
        edited = Path(edited)
        self._check_cancel(cancel_token)
        cfg = self.config.pipeline
        self._ensure_session()
        self._log.info("analysis started edited=%s", edited.name)
        cache_key = None
        if cfg.edited_cache_enabled:
            try:
                cache_key = self._edited_fingerprint(edited)
            except OSError:
                cache_key = None  # 文件缺失/不可 stat: 走原路径产生正常错误
        if cache_key:
            cached = self._edited_cache_store().load_shots(cache_key)
            if cached is not None:
                shots = [ShotSegment(span=TimeSpan(s["start"], s["end"]),
                                     feats=s["feats"], times=s["times"],
                                     card_ratio=s["card_ratio"])
                         for s in cached]
                for s, c in zip(shots, cached):
                    s.card_run_ratio = c["card_run_ratio"]
                self._log.info("analysis cache hit edited=%s shots=%d", edited.name, len(shots))
                self._current_edited = edited
                return shots
        try:
            if cfg.seg_twopass_enabled:
                shots = self._segment_twopass_flash(edited, cfg, on_progress, cancel_token)
            else:
                shots = self._segment_legacy(edited, cfg, on_progress, cancel_token)
        except ApplicationError:
            raise
        except (MediaError, Exception) as exc:
            self._log.exception("analysis failed edited=%s", edited.name)
            raise FeatureExtractionError(
                f"failed to extract edited feats from {edited.name}: {exc}") from exc
        if cache_key:
            try:
                self._edited_cache_store().save_shots(cache_key, [{
                    "start": float(s.span.start), "end": float(s.span.end),
                    "card_ratio": float(getattr(s, "card_ratio", 0.0)),
                    "card_run_ratio": float(getattr(s, "card_run_ratio", 0.0)),
                    "feats": np.asarray(s.feats, dtype=np.float32),
                    "times": np.asarray(s.times, dtype=np.float64),
                } for s in shots])
            except Exception:
                self._log.exception("edited cache save failed (non-fatal)")
        self._current_edited = edited
        return shots

    # ------------------------------------------------------------------ #
    # 编辑侧切分: 旧路径（seg_twopass_enabled=False 回退, 保留历史行为）
    # ------------------------------------------------------------------ #
    def _segment_legacy(self, edited: Path, cfg, on_progress, cancel_token) -> list[ShotSegment]:
        """旧路径: 2fps 全片 embed + detect_shots_two_level + card_guard（原 analyze 行为）。"""
        self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                     message="extracting edited frames")
        frames = list(self.ffmpeg.iter_frames(edited, cfg.edited_segment_fps))
        self._check_cancel(cancel_token)
        if not frames:
            raise ApplicationError(f"edited video has no frames extracted: {edited.name}")
        ed_times = np.array([t for t, _ in frames], dtype=np.float32)
        self._log.debug("embedding edited frames=%d fps=%s dim=384",
                        len(frames), cfg.edited_segment_fps)
        embs = []
        _BS = 16
        n = len(frames)
        for i in range(0, n, _BS):
            self._check_cancel(cancel_token)
            batch = frames[i:i + _BS]
            embs.append(self.backend.embed_frames([f for _, f in batch]))
            done = min(i + len(batch), n)
            self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                         current=done, total=n, message=f"特征提取 {done}/{n} 帧")
        ed_feats = np.concatenate(embs, axis=0)
        self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                     current=len(frames), total=max(len(frames), 1),
                     message=f"特征提取 {len(frames)}/{len(frames)} 帧")

        self._check_cancel(cancel_token)
        self._notify(on_progress, ProgressStage.SEGMENT_DETECTION, message="detecting shots")
        shots = detect_shots_two_level(ed_feats, ed_times,
                                       cut_abs=cfg.seg_cut_abs, z_thresh=cfg.seg_z_thresh,
                                       min_shot_s=cfg.seg_min_shot_s, smooth=cfg.seg_smooth,
                                       fps=cfg.edited_segment_fps,
                                       max_shot_s=cfg.seg_max_shot_s,
                                       fine_cut_factor=cfg.seg_fine_cut_factor,
                                       fine_z_factor=cfg.seg_fine_z_factor,
                                       fine_min_shot_s=cfg.seg_fine_min_shot_s)
        return self._apply_card_guard(shots, frames, ed_times, cfg)

    # ------------------------------------------------------------------ #
    # 编辑侧切分: 两级分层切分 + 白闪守卫（C 项验证 2026-09-05 用户拍板）
    # ------------------------------------------------------------------ #
    def _segment_twopass_flash(self, edited: Path, cfg, on_progress,
                               cancel_token) -> list[ShotSegment]:
        """两级切分 + 白闪守卫: 粗采样找候选切点 -> 白闪过滤 -> 局部精修 -> 最短保护。

        与 rerun_twopass_flash.py（研究验证脚本）逻辑一致, 生产化接线:
          - 粗采样 fps = vfps / seg_twopass_coarse_step_frames（6 帧步长 ≈ 4.8fps@29）;
          - 粗特征 detect_shots 得粗切点; 白闪/亮度尖峰邻域切点删除;
          - 每个内部切点 ±seg_twopass_fine_window_frames 帧窗内密帧精修
            （fps = vfps / seg_twopass_fine_step_frames, 白闪邻域回退粗切点）;
          - 最短镜头保护 seg_twopass_min_shot_s（白闪邻域动态 flash_dyn_min_shot_s）;
          - 段内白闪占比高 -> merge_flash_segments 业务兜底。
        """
        meta = getattr(self.ffmpeg, "metadata", None)
        meta = meta(edited) if callable(meta) else None
        vfps = float(meta.fps) if meta and meta.fps else 29.0
        dur = float(meta.duration) if meta and meta.duration else 0.0
        if vfps <= 0:
            vfps = 29.0
        coarse_fps = vfps / max(1, int(cfg.seg_twopass_coarse_step_frames))
        fine_fps = vfps / max(1, int(cfg.seg_twopass_fine_step_frames))
        self._log.info("twopass+flash fps=%s coarse_fps=%.2f fine_fps=%.2f dur=%.1f",
                       vfps, coarse_fps, fine_fps, dur)

        # --- ① 粗采样全片（一次 ffmpeg 遍历; 解码线程与 embed/统计流水重叠, 零语义）---
        self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                     message="twopass coarse sampling")
        emb_chunks: list[np.ndarray] = []
        ed_times_list: list[float] = []
        flash_list: list[bool] = []
        mean_list: list[float] = []
        card_list: list[float] = []
        n_frames = 0

        def _coarse_batches():
            batch: list[tuple[float, np.ndarray]] = []
            for tf in self.ffmpeg.iter_frames(edited, coarse_fps):
                batch.append(tf)
                if len(batch) >= 32:
                    yield batch
                    batch = []
            if batch:
                yield batch

        def _coarse_consume(item):
            nonlocal n_frames
            self._check_cancel(cancel_token)
            ts = [t for t, _ in item]
            fs = [f for _, f in item]
            emb_chunks.append(self.backend.embed_frames(fs))
            flash_list.extend(is_flash_frame(f, cfg.flash_mean_th,
                                             cfg.flash_frac_th)[0] for f in fs)
            mean_list.extend(frame_mean_brightness(f) for f in fs)
            card_list.extend(is_card_frame(f, black_ratio=cfg.card_black_ratio,
                                           bright_lo=cfg.card_bright_lo,
                                           bright_hi=cfg.card_bright_hi,
                                           bright_max_spread=cfg.card_bright_max_spread,
                                           bright_min_area_frac=cfg.card_bright_min_area_frac)
                             for f in fs)
            ed_times_list.extend(ts)
            n_frames += len(item)
            self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                         current=n_frames, message=f"特征提取 {n_frames} 帧")

        pipeline_map(_coarse_batches(), _coarse_consume)
        if n_frames == 0:
            raise ApplicationError(f"edited video has no frames extracted: {edited.name}")
        ed_times = np.array(ed_times_list, dtype=np.float32)
        if dur <= 0 and ed_times.size:
            dur = float(ed_times[-1])   # 兼容无 metadata 的调用方（测试 mock / 极端容器）
        ed_feats = np.concatenate(emb_chunks, axis=0)
        # 白闪前置过滤（flash 帧不参与边界判别, 供后续切点删除/动态阈值用）
        coarse_flash = np.array(flash_list, dtype=bool)
        flash_times = [float(t) for t, fl in zip(ed_times, coarse_flash) if fl]
        self._log.info("twopass+flash coarse frames=%d flash=%d",
                       n_frames, len(flash_times))
        self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                     current=n_frames, total=max(n_frames, 1),
                     message=f"特征提取 {n_frames}/{n_frames} 帧")

        # --- ② 粗切分（语义 detect_shots, fps=coarse_fps 换算帧间隔）---
        self._check_cancel(cancel_token)
        self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                     message="twopass coarse segmentation")
        shots = detect_shots(ed_feats, ed_times,
                             cut_abs=cfg.seg_cut_abs, z_thresh=cfg.seg_z_thresh,
                             min_shot_s=cfg.seg_min_shot_s, smooth=cfg.seg_smooth,
                             fps=coarse_fps)
        self._log.info("twopass+flash coarse segments=%d", len(shots))

        # --- ③ 切点后处理: 白闪/亮度尖峰邻域切点删除（转场非真实切点）---
        cuts = [float(s.span.start) for s in shots[1:]]
        cuts_kept = drop_flash_cuts(cuts, flash_times, cfg.flash_margin_s)
        means = np.array(mean_list, dtype=np.float64)
        spikes = brightness_spike_regions(means, ed_times,
                                          delta=cfg.bright_spike_delta,
                                          peak_th=cfg.bright_spike_peak_th)
        cuts_kept = drop_brightness_spike_cuts(cuts_kept, spikes, cfg.flash_margin_s)
        self._log.info("twopass+flash cuts %d -> %d (flash=%d spikes=%d)",
                       len(cuts), len(cuts_kept), len(flash_times), len(spikes))

        # --- ④ 局部密帧精修每个内部边界 ---
        refined_bounds = [0.0]
        for ct in cuts_kept:
            t = self._refine_cut_twopass(edited, ct, vfps, fine_fps,
                                         int(cfg.seg_twopass_fine_window_frames),
                                         cancel_token, cfg)
            refined_bounds.append(t)
        if dur > 0:
            refined_bounds.append(float(dur))
        refined_bounds = sorted(set(round(x, 4) for x in refined_bounds))

        # --- ⑤ 最短镜头保护 + 动态阈值（白闪邻域段 1.0-1.2s, 普通 0.5s）---
        pts = list(refined_bounds)
        if flash_times:
            seg_tmp = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)]
            ths = dynamic_min_shot(seg_tmp, flash_times,
                                   min_shot_s=cfg.seg_twopass_min_shot_s,
                                   dyn_s=cfg.flash_dyn_min_shot_s,
                                   flash_margin_s=cfg.flash_margin_s)
            changed = True
            while changed:
                changed = False
                i = 1
                while i < len(pts) - 1:
                    gl = pts[i] - pts[i - 1]; gr = pts[i + 1] - pts[i]
                    tl = ths[i - 1]; tr = ths[i]
                    if gl < tl or gr < tr:
                        drop = i if (gl - tl) <= (gr - tr) else i + 1
                        del pts[drop]
                        seg_tmp = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)]
                        ths = dynamic_min_shot(seg_tmp, flash_times,
                                               min_shot_s=cfg.seg_twopass_min_shot_s,
                                               dyn_s=cfg.flash_dyn_min_shot_s,
                                               flash_margin_s=cfg.flash_margin_s)
                        changed = True
                    else:
                        i += 1
        else:
            changed = True
            while changed:
                changed = False
                i = 1
                while i < len(pts) - 1:
                    gl = pts[i] - pts[i - 1]; gr = pts[i + 1] - pts[i]
                    if gl < cfg.seg_twopass_min_shot_s or gr < cfg.seg_twopass_min_shot_s:
                        del pts[i if gl <= gr else i + 1]
                        changed = True
                    else:
                        i += 1
        seg_bounds = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)
                      if pts[j + 1] - pts[j] >= cfg.seg_twopass_min_shot_s]

        # --- ⑥ 业务兜底: 段内白闪占比高 -> 合并相邻镜头（白闪是转场非真实镜头）---
        if flash_times:
            seg_bounds = merge_flash_segments(seg_bounds, flash_times,
                                              merge_frac=cfg.flash_merge_frac)

        # --- ⑦ 用粗网格帧构造 ShotSegment（边界用精修时间戳, 查询特征=粗网格帧）---
        out_shots = []
        for (a, b) in seg_bounds:
            m = (ed_times >= a - 1e-4) & (ed_times <= b + 1e-4)
            idx = np.flatnonzero(m)
            if idx.size == 0:
                continue
            times = ed_times[idx]
            feats = ed_feats[idx]
            out_shots.append(ShotSegment(span=TimeSpan(float(a), float(b)),
                                         feats=feats, times=times))
        # card_guard: 用粗网格帧逐帧像素判别（复用原逻辑; 帧统计已在粗采样消费线程算好）
        card_flags = np.array(card_list, dtype=np.float32)
        for s in out_shots:
            m = (ed_times >= s.span.start - 1e-6) & (ed_times <= s.span.end + 1e-6)
            s.card_ratio = float(card_flags[m].mean()) if bool(m.any()) else 0.0
        for s in out_shots:
            seg_flags = [bool(card_flags[int(round((tt - ed_times[0]) * coarse_fps))])
                         for tt in ed_times
                         if s.span.start - 1e-6 <= tt <= s.span.end + 1e-6]
            s.card_run_ratio = float(max_card_run_ratio(seg_flags))
        n_card = sum(1 for s in out_shots if s.card_ratio >= cfg.card_shot_ratio
                     or getattr(s, "card_run_ratio", 0.0) >= cfg.card_run_ratio)
        self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                     current=len(out_shots), total=max(len(out_shots), 1),
                     message=f"{len(out_shots)} segments")
        self._log.info("twopass+flash final segments=%d card_segments=%d edited=%s",
                       len(out_shots), n_card, edited.name)
        return out_shots

    def _apply_card_guard(self, shots, frames, ed_times, cfg) -> list[ShotSegment]:
        """card_guard 公共逻辑: 段内黑底文字卡/logo 帧占比 + 最长连续 run 占比。"""
        card_flags = np.array([is_card_frame(f, black_ratio=cfg.card_black_ratio,
                                             bright_lo=cfg.card_bright_lo,
                                             bright_hi=cfg.card_bright_hi,
                                             bright_max_spread=cfg.card_bright_max_spread,
                                             bright_min_area_frac=cfg.card_bright_min_area_frac)
                               for _, f in frames], dtype=np.float32)
        for s in shots:
            m = (ed_times >= s.span.start - 1e-6) & (ed_times <= s.span.end + 1e-6)
            s.card_ratio = float(card_flags[m].mean()) if bool(m.any()) else 0.0
        for s in shots:
            seg_flags = [bool(card_flags[int(round((tt - ed_times[0]) * cfg.edited_segment_fps))])
                         for tt in ed_times
                         if s.span.start - 1e-6 <= tt <= s.span.end + 1e-6]
            s.card_run_ratio = float(max_card_run_ratio(seg_flags))
        return shots

    def _embed_batch(self, bgr_list, cancel_token) -> np.ndarray:
        """分批 embed（每批检查取消; 研究脚本同款辅助, 供两级切分路径复用）。"""
        embs = []
        _BS = 16
        n = len(bgr_list)
        for i in range(0, n, _BS):
            self._check_cancel(cancel_token)
            embs.append(self.backend.embed_frames(bgr_list[i:i + _BS]))
        return np.concatenate(embs, axis=0)

    def _refine_cut_twopass(self, edited: Path, cut_t: float, vfps: float,
                            fine_fps: float, window_frames: int, cancel_token,
                            cfg) -> float:
        """局部密帧精修: 切点 ±window 帧窗内 fine_fps 采样, 相邻距离峰 -> 精确切点。

        白闪守卫（相似度衰减）: 若相邻距离峰落在白闪帧邻域（亮度突变假峰）, 回退粗切点
        ——白闪是转场非真实镜头切变, 不把边界移到白闪上。
        """
        f = cut_t * vfps
        t0 = max(0.0, (f - window_frames) / vfps)
        t1 = (f + window_frames) / vfps
        try:
            frames = list(self.ffmpeg.iter_frames(edited, fine_fps, start=t0, end=t1))
        except Exception:
            return cut_t
        if len(frames) < 3:
            return cut_t
        self._check_cancel(cancel_token)
        feats = self._embed_batch([fr for _, fr in frames], cancel_token)
        times = np.array([t for t, _ in frames], dtype=np.float32)
        d = adjacent_distances(feats)
        i = int(np.argmax(d))
        cand = float(times[i + 1])
        fine_flash = [float(t) for (t, fr) in frames
                      if is_flash_frame(fr, cfg.flash_mean_th, cfg.flash_frac_th)[0]]
        if fine_flash:
            if any(abs(cand - ft) <= cfg.flash_margin_s for ft in fine_flash):
                self._log.info("refine_cut flash-guard: cand %.2f near flash -> keep coarse %.2f",
                               cand, cut_t)
                return cut_t
        return cand


    # ------------------------------------------------------------------ #
    # 用例三：主链路（Original + Edited -> ResultBatch）
    # ------------------------------------------------------------------ #
    def locate(self, edited: str | Path, original: str | Path | IndexBundle, *,
               on_progress: ProgressCb | None = None,
               cancel_token: CancellationToken | None = None,
               index_bundle: IndexBundle | None = None) -> ResultBatch:
        """一步编排完整链路，返回 ``ResultBatch``（每条 Result 对应一个 edited segment）。"""
        edited = Path(edited)
        self._ensure_session()
        t0 = time.monotonic()
        self._log.info("locate started edited=%s", edited.name)
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
                                        cancel_token=cancel_token,
                                        edited=edited)
        if self.config.pipeline.text_anchor_enabled:
            try:
                self._apply_text_anchor(results, edited, orig_path,
                                        cfg=self.config.pipeline,
                                        cancel_token=cancel_token)
            except ApplicationError:
                raise
            except Exception:
                self._log.exception("text anchor rerank failed (non-fatal)")
        if self.config.pipeline.seq_dp_enabled and self._last_seq_items:
            try:
                self._apply_sequence_rerank(results, self._last_seq_items,
                                            cfg=self.config.pipeline,
                                            cancel_token=cancel_token)
            except ApplicationError:
                raise
            except Exception:
                self._log.exception("sequence rerank failed (non-fatal)")
        if self.config.pipeline.temporal_repair_enabled:
            try:
                self._apply_temporal_repair(results, bundle, edited,
                                            cfg=self.config.pipeline,
                                            cancel_token=cancel_token)
            except ApplicationError:
                raise
            except Exception:
                self._log.exception("temporal repair failed (non-fatal)")
        if self.config.pipeline.conflict_rerank_enabled:
            try:
                self._apply_conflict_rerank(results, bundle, edited,
                                            cfg=self.config.pipeline,
                                            cancel_token=cancel_token)
            except ApplicationError:
                raise
            except Exception:
                self._log.exception("conflict rerank failed (non-fatal)")
        if self.config.pipeline.temporal_ambiguity_enabled:
            try:
                self._apply_temporal_ambiguity(results,
                                               cfg=self.config.pipeline)
            except ApplicationError:
                raise
            except Exception:
                self._log.exception("temporal ambiguity failed (non-fatal)")
        batch = ResultBatch(schema_version=1, original_video=str(orig_path),
                            edited_video=str(Path(edited).resolve()), results=results)
        self._current_batch = batch
        self._log_locate_summary(edited, batch, time.monotonic() - t0)
        return batch

    def _locate_features(self, shots: list[ShotSegment], bundle: IndexBundle, *,
                         cfg: PipelineConfig | None = None,
                         on_progress: ProgressCb | None = None,
                         cancel_token: CancellationToken | None = None,
                         edited: str | Path | None = None) -> list[Result]:
        """纯管线（无 IO）：逐 segment 检索/定位/置信度，失败隔离为 unresolved Result。"""
        cfg = cfg or self.config.pipeline
        results: list[Result] = []
        seq_items: list[dict] = []   # 时序 DP 候选池(Phase 21 场景身份)
        prev_mid: float | None = None   # 前序段定位中点(单调弱先验锚点; None=前段未定位不触发)
        n = len(shots)
        self._last_candidates = 0
        for idx, shot in enumerate(shots):
            self._check_cancel(cancel_token)
            # 黑底文字卡/logo 守卫:卡片段跳过检索,直接判 not_in_source
            # (GT v3 n04:黑底白 logo 陷阱,纯外观检索必误配,语义不可定位)
            if shot.card_ratio >= cfg.card_shot_ratio \
                    or getattr(shot, "card_run_ratio", 0.0) >= cfg.card_run_ratio:
                self._log.info("segment %d/%d text-card not_in_source ratio=%.2f",
                               idx + 1, n, shot.card_ratio)
                self._notify(on_progress, ProgressStage.CANDIDATE_RETRIEVAL,
                             current=idx, total=n, message=f"segment {idx + 1}/{n}: text card")
                results.append(self._card_not_in_source_result(shot))
                continue
            try:
                self._notify(on_progress, ProgressStage.CANDIDATE_RETRIEVAL,
                             current=idx, total=n, message=f"segment {idx + 1}/{n}: retrieval")
                dense = None
                if edited is not None and self._evidence_localizer.seq_align is not None:
                    dense = self._embed_dense_query(shot, edited)
                # ≤0.5s 超短切(2fps 采样只有 1 帧查询):单帧检索易无证据(no_evidence,
                # test4 实证)→ 用 8fps 密帧(≈4 帧)做查询特征(dense 已有会话缓存)
                q_feats, q_times = shot.feats, shot.times
                if dense is not None and shot.feats.shape[0] < 2:
                    q_feats, q_times = dense
                evidence = self._evidence_localizer.localize(q_feats, q_times, bundle,
                                                             dense_query=dense)
                if (evidence.mode == "empty" or evidence.primary is None) \
                        and dense is not None and q_feats.shape[0] != dense[0].shape[0]:
                    # 密帧重试(test4 38.5-40.5 实证:2s 段压 3 个子镜头,2fps 每簇 1 命中
                    # 全被 min_frames 门掉;8fps 下命中簇 7 帧/0.66 稳过门)。只影响本来
                    # no_evidence 的段(不导出),已定位段零回归风险。
                    self._log.info("segment %d/%d no_evidence -> dense retry", idx + 1, n)
                    evidence = self._evidence_localizer.localize(
                        dense[0], dense[1], bundle, dense_query=dense)
                    # 相似度门槛(test4 r10/r12 实证:全片同质化场景里重试命中的
                    # best_sim 仅 0.53-0.60,是"假定位"——比 no_evidence 更糟;
                    # 门槛以下的弱命中回退 unresolved)
                    best_sim = max((s.best_sim or 0.0) for s in (evidence.all_spans or [])
                                   if s.best_sim is not None) if evidence.all_spans else 0.0
                    if evidence.primary is not None and best_sim < cfg.dense_retry_min_sim:
                        self._log.info("segment %d/%d dense retry sim %.2f < %.2f -> unresolved",
                                       idx + 1, n, best_sim, cfg.dense_retry_min_sim)
                        evidence = EvidenceResult(mode="empty")
                self._last_candidates += evidence.n_clusters

                self._notify(on_progress, ProgressStage.LOCALIZATION,
                             current=idx, total=n, message=f"segment {idx + 1}/{n}: localize")

                # 时序 DP 候选池:门控前全部簇(相似镜头挑错实例的全局修复素材)
                seq_cands = []
                for s in evidence.all_spans or []:
                    if s.original_span is None:
                        continue
                    seq_cands.append({
                        "mid": (s.original_span[0] + s.original_span[1]) / 2.0,
                        "score": (s.cover or 0.0) * (s.best_sim if s.best_sim is not None else 0.0),
                        "is_main": s is evidence.primary,
                        "span": (s.original_span[0], s.original_span[1]),
                    })
                if evidence.mode == "empty" or evidence.primary is None \
                        or evidence.primary.original_span is None:
                    # 定向子镜头回退: 整段定位失败时, 按帧级距离突变拆子镜头逐查, 取最优
                    if getattr(cfg, "subshot_enabled", True):
                        sub_ev, sub_sim = self._subshot_relocalize(shot, bundle, dense, cfg)
                        if sub_ev is not None:
                            self._log.info("segment %d/%d subshot rescue sim %.2f",
                                           idx + 1, n, sub_sim)
                            evidence = sub_ev
                    if evidence.mode == "empty" or evidence.primary is None \
                            or evidence.primary.original_span is None:
                        results.append(self._unresolved_result(shot, "no_evidence"))
                        continue

                # Montage weak-hit subshot rescue: if whole-segment montage primary drifted and weak,
                # try subshot split, adopt only if best_sim improves.
                # (2026-09-05 漂移 gap 触发+合并采纳实验 = 三指标零变化且 oracle 口径证伪
                # max-sim 选子镜头——FINDINGS_SUBSHOT_QUERY「runtime 接入验证」章; 已回退)
                if getattr(cfg, "subshot_enabled", True) and evidence.primary is not None \
                        and evidence.primary.original_span is not None:
                    cur_sim = max((x.best_sim or 0.0) for x in (evidence.all_spans or []) if x.best_sim is not None) if any(x.best_sim is not None for x in (evidence.all_spans or [])) else 0.0
                    if evidence.mode == "montage" and cur_sim < getattr(cfg, "subshot_retry_min_sim", 0.62):
                        sub_ev, sub_sim = self._subshot_relocalize(shot, bundle, dense, cfg)
                        if sub_ev is not None and sub_sim > cur_sim:
                            self._log.info("segment %d/%d subshot rescue (montage weak) sim %.2f > %.2f", idx + 1, n, sub_sim, cur_sim)
                            evidence = sub_ev
                self._notify(on_progress, ProgressStage.CONFIDENCE,
                             current=idx, total=n, message=f"segment {idx + 1}/{n}: confidence")
                # 单调弱先验进候选生成(NEXT_STEPS ②③, 2026-09-02):
                # Ambiguous 型段(>=2 保留证据簇)用前序段定位中点做时间轴锚点, 对
                # "离锚点更近且 cover 落差<=ta_max_cover_drop" 的候选簇弱倾向为 primary
                # (难分才切; 唯一强候选/首段/前段未定位不触发 = 逃生门, 真实回溯 8/29 不误伤)。
                tl_switched = False
                if cfg.timeline_prior_enabled and prev_mid is not None:
                    old_span = evidence.primary.original_span if evidence.primary else None
                    tl_switched = self._apply_timeline_prior(evidence, prev_mid, cfg=cfg)
                    if tl_switched and evidence.primary is not None \
                            and evidence.primary.original_span is not None:
                        self._log.info(
                            "segment %d/%d timeline prior: primary %.0f-%.0f -> %.0f-%.0f (anchor %.0f)",
                            idx + 1, n,
                            (old_span[0] if old_span else 0.0), (old_span[1] if old_span else 0.0),
                            evidence.primary.original_span[0], evidence.primary.original_span[1],
                            prev_mid)
                assessment = ConfidenceEngine(cfg.confidence).assess_evidence(evidence)
                results.append(self._result_from_evidence(shot, evidence, assessment))
                if tl_switched:
                    _rc = results[-1].confidence
                    results[-1].confidence = Confidence(
                        _rc.level, _rc.score,
                        tuple(_rc.reasons) + ("timeline_weak_prior",))
                if seq_cands:
                    seq_items.append({"index": len(results) - 1,
                                      "edited_mid": (shot.span.start + shot.span.end) / 2.0,
                                      "cands": seq_cands})
                # 维护弱先验锚点: 前序段定位中点(未定位/卡片段不更新)
                _r = results[-1]
                if _r.original.end - _r.original.start > 0.01:
                    prev_mid = (_r.original.start + _r.original.end) / 2.0
                if cfg.patch_rerank_enabled and shot.span.width >= 0.6:
                    override = self._patch_rerank_span(evidence, shot, bundle, edited, cfg,
                                                       cancel_token=cancel_token)
                    if override is not None:
                        r = results[-1]
                        old_main = (r.original.start, r.original.end)
                        if all(abs(s.start - old_main[0]) > 0.5 for s in r.original_segments):
                            r.original_segments.insert(0, OriginalSegment(old_main[0], old_main[1], 0.0, None))
                        r.original = TimeSpan(override[0], override[1])
                        self._log.info("patch rerank s%d ed=%.1f main %.0f->%.0f",
                                       len(results) - 1, shot.span.start, old_main[0], override[0])
                    if cfg.patch_v2_enabled:
                        r = results[-1]
                        override2 = self._patch_nearfield_rescue(
                            shot, bundle, edited,
                            (r.original.start, r.original.end), cfg,
                            cancel_token=cancel_token)
                        if override2 is not None:
                            old_main = (r.original.start, r.original.end)
                            if all(abs(s.start - old_main[0]) > 0.5 for s in r.original_segments):
                                r.original_segments.insert(0, OriginalSegment(old_main[0], old_main[1], 0.0, None))
                            r.original = TimeSpan(override2[0], override2[1])
                            self._log.info("patch v2 s%d ed=%.1f main %.0f->%.0f",
                                           len(results) - 1, shot.span.start, old_main[0], override2[0])
            except ApplicationError:
                raise  # cancellation 穿透，不做段级隔离
            except Exception as exc:
                self._log.error("segment %d/%d failed: %s", idx + 1, n, exc, exc_info=True)
                results.append(self._unresolved_result(
                    shot, f"segment_error: {type(exc).__name__}: {exc}"))
        self._last_seq_items = seq_items
        return results

    # ------------------------------------------------------------------ #
    # 用例四：持久化
    # ------------------------------------------------------------------ #
    def last_result_batch(self) -> ResultBatch | None:
        """最近一次 locate 的结果批（同步 /api/results 或异步 /api/tasks/analyze 都会设置）。

        export 端点用它，避免异步任务完成后 ``ctx.current_batch`` 未被设置导致的 no_results。
        """
        return self._current_batch

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
    # 用例五：NLE 工程文件导出（Phase 22：EDL / FCP7 XML / 剪映草稿）
    # ------------------------------------------------------------------ #
    def export_project(self, batch: ResultBatch, *, fmt: str,
                       out_dir: str | Path | None = None, filename: str | None = None,
                       min_confidence: str | None = None, low_policy: str | None = None,
                       snap_scenes: bool | None = None,
                       material_width: str | None = None,
                       on_progress: ProgressCb | None = None,
                       cancel_token: CancellationToken | None = None) -> Path:
        """把结果批导出为 NLE 工程文件，返回写入路径（剪映=草稿文件夹）。

        - ``fmt``：``edl``（CMX3600）/ ``fcp7_xml``（PR 导入）/ ``jianying``
          （剪映 draft 文件夹，beta）。
        - 策略（默认取 ``config.export``，参数可逐次覆盖）：``min_confidence``
          置信门槛；``low_policy``（``exclude``/``backup``）；``snap_scenes`` +
          ``snap_tolerance_s`` 源片侧切点吸附（``scenes.npy``，±tol 秒内才吸附）。
        - clip 来源：``original`` 主 span + ``original_segments`` 子 span，
          按编辑时间排序；``not_in_source`` / 段级失败 / 零宽 original 不导。
        - 源片 fps/timebase：ffprobe 实测（失败回退 25，日志留痕）；timecode 一律
          NDF，按「源片 timecode 原点 = 首帧」换算（与 iter_frames 媒体时间约定
          一致）。索引不可用时吸附静默降级（警告日志），导出照常。
        """
        self._check_cancel(cancel_token)
        if fmt not in EXPORT_FORMATS:
            raise ApplicationError(
                f"invalid export format: {fmt!r} (expected one of {EXPORT_FORMATS})")
        xcfg = self.config.export
        mc = min_confidence or xcfg.min_confidence
        lp = low_policy or xcfg.low_policy
        do_snap = xcfg.snap_scenes if snap_scenes is None else bool(snap_scenes)
        if mc not in ("LOW", "MEDIUM", "HIGH"):
            raise ApplicationError(f"invalid min_confidence: {mc!r}")
        if lp not in ("exclude", "backup"):
            raise ApplicationError(f"invalid low_policy: {lp!r}")
        if not batch.original_video:
            raise ApplicationError("result batch has no original_video; cannot export project")
        orig_path = Path(batch.original_video)

        self._notify(on_progress, ProgressStage.EXPORT, message=f"exporting {fmt}")
        # 计划：门槛 + 不导规则 + 主 span 展平（候选子 span 不进剪辑软件——反馈二轮）
        plan = build_export_plan(batch, min_confidence=mc, low_policy=lp, include_subs=False)
        # 场景切点吸附（TODO 第 2 项）：scenes.npy 边界 ±tol；索引不可用则降级
        scenes, orig_duration, bundle = None, None, None
        try:
            bundle = self.store.load_index(orig_path)
            scenes = bundle.scenes
            orig_duration = float(bundle.meta.duration or 0.0) or None
        except Exception:
            if do_snap:
                self._log.warning("scene snap skipped: index unavailable for %s", orig_path.name)
        # 素材宽度（反馈四轮）：scene=扩到所在完整镜头（默认）/ core=仅核心定位窗口
        width_mode = material_width or "scene"
        if width_mode not in ("scene", "core"):
            raise ApplicationError(f"invalid material_width: {width_mode!r}")
        do_expand = width_mode == "scene"
        n_snapped = 0
        if do_snap and plan:
            n_snapped = snap_clips_to_scenes(
                plan, scenes, tol_s=float(xcfg.snap_tolerance_s),
                orig_duration=orig_duration)
        # 元数据：源片/编辑片 fps（timecode 换算）+ 分辨率（XML/剪映字段）
        meta = self._probe_meta(orig_path)
        rec_meta = self._probe_meta(Path(batch.edited_video)) if batch.edited_video else None
        source_fps = (meta.get("fps") if meta else None) or 25.0
        record_fps = (rec_meta.get("fps") if rec_meta else None) or source_fps

        out_root = Path(out_dir) if out_dir else self.export_root
        stem = Path(batch.edited_video).stem if batch.edited_video else "results"
        self._ensure_session()
        if fmt == "edl":
            text = render_edl(plan, title=f"{stem} located", source_name=orig_path.name,
                              source_fps=source_fps, record_fps=record_fps)
            out_path = out_root / (filename or f"{stem}.loc.edl")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
        elif fmt == "fcp7_xml":
            text = render_fcp7_xml(
                plan, seq_name=f"{stem} located", source_path=orig_path,
                source_fps=source_fps, source_duration=orig_duration or (meta or {}).get("duration"),
                record_fps=record_fps,
                source_size=(meta.get("width"), meta.get("height")) if meta else None)
            out_path = out_root / (filename or f"{stem}.loc.xml")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8")
        else:  # jianying（v2：pyJianYingDraft + 预转码 H.264 MP4 素材，实测修复
            # 「媒体格式不支持/时间线空」——剪映素材须为可解码的 MP4）
            draft_name = filename or f"{stem}.loc.jy_draft"
            draft_dir, script = create_jianying_draft_dir(
                out_root, draft_name, fps=meta.get("fps") if meta else 30.0,
                width=int((meta or {}).get("width") or 1920),
                height=int((meta or {}).get("height") or 1080))
            clips_dir = draft_dir / "clips"
            clips_dir.mkdir(parents=True, exist_ok=True)
            # 取材扩展 v5（反馈四轮）：核心窗口扩成所在完整原片镜头（scenes.npy 定界）
            if xcfg.material_expand and do_expand and bundle is not None:
                n_exp = expand_material_spans(plan, bundle.scenes)
                self._log.info("material expand widened=%d", n_exp)
            assets = plan_jianying_assets(plan)
            n_clips = len(assets)
            for i, asset in enumerate(assets):
                self._check_cancel(cancel_token)
                clip_path = clips_dir / f"{asset.file_stem}.mp4"
                if not clip_path.exists():
                    self.ffmpeg.extract_clip(orig_path, asset.orig_start,
                                             asset.orig_end, clip_path,
                                             preset="veryfast", crf=20)
                asset.clip_path = clip_path
                try:
                    asset.clip_duration = float(self.ffmpeg.metadata(clip_path).duration)
                except Exception:
                    asset.clip_duration = asset.orig_width
                self._notify(on_progress, ProgressStage.EXPORT,
                             current=i + 1, total=max(n_clips, 1),
                             message=f"准备素材 {i + 1}/{n_clips}")
            out_path = write_jianying_draft(script, assets, draft_dir)
        self._log.info("project export fmt=%s clips=%d snapped=%d path=%s",
                       fmt, len(plan), n_snapped, out_path)
        self._notify(on_progress, ProgressStage.EXPORT,
                     current=len(plan), total=max(len(plan), 1),
                     message=f"exported {out_path.name}")
        return out_path

    def _probe_meta(self, video: Path) -> dict | None:
        """ffprobe 元数据（fps/分辨率/时长）；失败返回 None（回退值由调用方定）。"""
        try:
            m = self.ffmpeg.metadata(video)
            return {"fps": float(m.fps or 0.0), "width": int(m.width),
                    "height": int(m.height), "duration": float(m.duration)}
        except Exception:
            self._log.warning("metadata probe failed: %s (fallback fps=25)", video.name)
            return None

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _embed_dense_query(self, shot, edited_path):
        """对 shot 用 seq_edit_fps 密帧重采样（app 层 IO+embed，会话内 memo 防重复）。

        编辑侧 @seq_edit_fps(8) 帧比 product(2fps) 密，给全局对齐 `_dp_path` 足够约束、
        把 scene 定位偏差外的正确 moment(如 seg1 直升机 1319) 浮出。
        """
        sa = self.config.pipeline.seq_align
        key = (str(Path(edited_path).resolve()), round(shot.span.start, 2),
               round(shot.span.end, 2))
        if key in self._dense_cache:
            return self._dense_cache[key]
        dkey = None
        if self.config.pipeline.edited_cache_enabled:
            try:
                dkey = EditedCache.dense_key(shot.span.start, shot.span.end)
                hit = self._edited_cache_store().load_dense(
                    self._edited_fingerprint(Path(edited_path)), dkey)
                if hit is not None and hit[0].shape[0] > 0:
                    dense = (hit[0], hit[1].astype(np.float32))
                    self._dense_cache[key] = dense
                    return dense
            except Exception:
                dkey = None
        frames, times = [], []
        for t, f in self.ffmpeg.iter_frames(edited_path, sa.edit_fps,
                                            start=shot.span.start, end=shot.span.end):
            frames.append(f)
            times.append(t)
        if not frames:
            return None
        feats = self.backend.embed_frames(frames)
        dense = (feats, np.array(times, dtype=np.float32))
        self._dense_cache[key] = dense
        if dkey is not None:
            try:
                self._edited_cache_store().save_dense(
                    self._edited_fingerprint(Path(edited_path)), dkey, feats, times)
            except Exception:
                pass
        return dense
    def _subshot_relocalize(self, shot, bundle, dense, cfg):
        """Targeted subshot fallback when whole-segment localization fails/weak."""
        if dense is not None:
            qfeats, qtimes = dense[0], dense[1]
        else:
            qfeats, qtimes = shot.feats, shot.times
        if qfeats.shape[0] < 6:
            return None, -1.0
        q = qfeats[:-1] / np.maximum(np.linalg.norm(qfeats[:-1], axis=1, keepdims=True), 1e-8)
        r = qfeats[1:] / np.maximum(np.linalg.norm(qfeats[1:], axis=1, keepdims=True), 1e-8)
        d = 1.0 - np.sum(q * r, axis=1)
        cuts = [int(i + 1) for i in range(len(d)) if d[i] > cfg.subshot_cut_thresh]
        merged = []
        for c in cuts:
            if not merged or c - merged[-1] > 1:
                merged.append(c)
        if len(merged) + 1 < max(2, int(getattr(cfg, "subshot_min_sub", 3))):
            return None, -1.0
        bounds = [0] + merged + [int(len(qfeats))]
        best_evidence, best_sim = None, -1.0
        for si in range(len(bounds) - 1):
            a, b = bounds[si], bounds[si + 1]
            if b - a < 1:
                continue
            ev = self._evidence_localizer.localize(qfeats[a:b], qtimes[a:b], bundle)
            if ev.primary is None or ev.primary.original_span is None:
                continue
            s = max((x.best_sim or 0.0) for x in (ev.all_spans or []) if x.best_sim is not None)
            if s > best_sim:
                best_sim, best_evidence = s, ev
        return best_evidence, best_sim

    def _result_from_evidence(self, shot: ShotSegment, evidence, assessment) -> Result:
        """把 EvidenceResult + ConfidenceAssessment 装配为 domain.Result（multi-evidence）。

        - montage（>=2 保留证据簇）-> ``original_segments`` 多段 + ``montage_flag`` + 主 ``original``=最佳簇夹紧；每子 span 塞 ``moments``（帧级视图）。
        - clean -> 单段 ``original``（帧级 moment 优先，无 moment 回退 scene 级 tight_span）+ ``frame_precision``。
        """
        cfg = self.config.pipeline
        prim = evidence.primary
        montage = evidence.mode == "montage" and len(evidence.spans) >= 2
        support = shot.span.width if shot.span.width > 0 else 0.0
        frame_precision = False
        # 场景指纹扩池 span(Phase 21):附加子 span(已在定位器内过严格门+IoU 去重),
        # 只扩池不改主定位/置信——帧级为主的召回扩展。
        scene_segs = [OriginalSegment(s.original_span[0], s.original_span[1],
                                      s.cover, s.best_sim, from_scene_pool=True)
                      for s in (getattr(evidence, "scene_spans", None) or [])
                      if s.original_span is not None]
        # 事件单元扩池 span(方向 A 完整阶段 2026-09-05):与场景扩池同语义,仅作附加展示
        # 子 span,不改主定位/置信(帧级为主;事件级是更粗的身份单元,解决兄弟机位歧义)。
        event_segs = [OriginalSegment(s.original_span[0], s.original_span[1],
                                      s.cover, s.best_sim, from_event_pool=True)
                      for s in (getattr(evidence, "event_spans", None) or [])
                      if s.original_span is not None]
        if montage:
            segments = [OriginalSegment(s.original_span[0], s.original_span[1], s.cover, s.best_sim,
                                        moments=[_moment_dict(m) for m in s.moments])
                        for s in evidence.spans if s.original_span is not None]
            segments += scene_segs
            segments += event_segs
            bp = self._bound_span(prim.original_span, support, cfg)
            original = TimeSpan(bp[0], bp[1])
        else:
            # clean：moment 单答案 ±1s 锚（in-scope 最高 mean_sim，保 scene 主体），无 moment 回退 scene 级
            scene = (prim.original_span[0], prim.original_span[1])
            if prim.moments:
                in_scope = [m for m in prim.moments
                            if m.original_span[1] >= scene[0] and m.original_span[0] <= scene[1]]
                use = (max(in_scope, key=lambda m: m.mean_sim, default=None)
                       or max(prim.moments, key=lambda m: m.mean_sim))
                # 注：out-of-scope moment 回退保留原语义——三案实证它有时对（test3 r6）
                # 有时错（test3 r16），cover/sim 强弱不可分（特征上限边界）；
                # 错配走结果页手动替换，未来修复依赖特征升级（DECISIONS 有记录）。
                core = use.original_span
                frame_precision = True
            else:
                core = (prim.finloc.tight_span if prim.finloc and prim.finloc.tight_span is not None
                        else prim.original_span)
            bp = self._bound_span(core, support, cfg)
            original = TimeSpan(bp[0], bp[1])
            segments = list(scene_segs)
            segments += event_segs
            # 场景级多段输出(2026-08-29):快剪蒙太奇压缩比>1 时,完整覆盖区间超出单窗宽
            # (实测:编辑 8s 对应原片 40s 大战)。把被截掉的覆盖区间按窗宽切块全部展示,
            # 不再丢弃两端——用户审计实证"定位点前后帧"即此截断伪影。
            if core is not None:
                core_w = core[1] - core[0]
                bound_w = bp[1] - bp[0]
                if core_w > bound_w * 1.5:
                    step = max(bound_w, cfg.min_span_s)
                    cur = core[0]
                    while cur < core[1] - 0.5:
                        c1 = min(cur + step, core[1])
                        if not (abs(cur - bp[0]) < 0.5):  # 主 original 已含的块不重复
                            segments.append(OriginalSegment(round(cur, 2), round(c1, 2), 0.0, None))
                        cur = c1
                    segments.sort(key=lambda s: s.start)
        return Result(
            edited=shot.span, original=original, confidence=assessment.confidence,
            candidate_rank=1, alternatives=assessment.alternatives,
            source=ResultSource.AUTO, montage_flag=montage, original_segments=segments,
            frame_precision=frame_precision,
        )

    @staticmethod
    def _bound_span(span: tuple[float, float], support: float, cfg) -> tuple[float, float]:
        """夹紧原始区间宽度到 ``min(max_orig_span_s, max(min_span_s, factor*support))``，居中保持。"""
        if span is None:
            return (0.0, 0.0)
        w = span[1] - span[0]
        if w <= 0:
            return span
        bound = min(cfg.max_orig_span_s, max(cfg.min_span_s, cfg.span_width_factor * support))
        if w <= bound:
            return span
        c = (span[0] + span[1]) / 2.0
        return (round(c - bound / 2.0, 2), round(c + bound / 2.0, 2))

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
    def _card_not_in_source_result(shot: ShotSegment) -> Result:
        """黑底文字卡/logo 段 -> not_in_source 结果(跳检索,不产出误导性原片定位)。

        GT v3 n04:此类版式帧(黑底白 logo/字卡)在 CLS 特征下与任何同版式内容
        高度相似,语义不可定位;诚实输出「非源片内容」而非最像的错误位置。
        """
        return Result(
            edited=shot.span,
            confidence=Confidence(ConfidenceLevel.LOW, 0.0, ("text_card_not_in_source",)),
            source=ResultSource.AUTO,
            failure_reason="text_card_not_in_source",
            not_in_source=True,
        )

    def _patch_rerank_span(self, evidence, shot: ShotSegment, bundle: IndexBundle,
                           edited: Path, cfg: PipelineConfig, *,
                           cancel_token: CancellationToken | None = None) -> tuple[float, float] | None:
        """歧义段 patch 最大匹配重排:返回改写后的 (start, end),无改善返回 None(非致命)。

        候选窗 = 段内证据簇 + CLS top-20 全局帧按 8s 聚簇;每窗抽 1 帧 patch 评分
        (每查询 patch 最大余弦 top-100 均值,E21 验证口径)。
        """
        try:
            return self._patch_rerank_span_impl(evidence, shot, bundle, edited, cfg,
                                                cancel_token=cancel_token)
        except ApplicationError:
            raise
        except Exception:
            self._log.exception("patch rerank failed (non-fatal)")
            return None

    def _patch_rerank_span_impl(self, evidence, shot: ShotSegment, bundle: IndexBundle,
                                edited: Path, cfg: PipelineConfig, *,
                                cancel_token: CancellationToken | None = None) -> tuple[float, float] | None:
        if self._patch_reranker is None:
            self._patch_reranker = PatchReranker(
                resolve_weights(cfg.patch_weights_path or None),
                resolve_patch_onnx((cfg.patch_onnx_model or "").strip() or None),
                dml_device_id=self.config.device.dml_device_id)
            rr = self._patch_reranker
            if rr.ensure():
                self._log.info("patch reranker device=%s", rr.device)
        rr = self._patch_reranker
        if not rr.ensure():
            return None
        self._check_cancel(cancel_token)

        # 候选窗:证据簇 + CLS top-20 全局帧聚簇
        wins: dict[float, tuple[float, float]] = {}
        for s in evidence.all_spans or []:
            if s.original_span is not None:
                wins[round((s.original_span[0] + s.original_span[1]) / 2, 1)] = s.original_span
        q_cls = shot.feats.mean(axis=0)
        q_cls = q_cls / max(np.linalg.norm(q_cls), 1e-8)
        sims = bundle.features @ q_cls
        itimes = bundle.times
        top = np.argsort(-sims)[:20]
        groups: list[list[int]] = []
        for ti in top:
            if groups and itimes[ti] - itimes[groups[-1][-1]] <= 8.0:
                groups[-1].append(int(ti))
            else:
                groups.append([int(ti)])
        for g in groups:
            mid = round(float(itimes[g].mean()), 1)
            if mid not in wins:
                wins[mid] = (float(itimes[g].min()), float(itimes[g].max()) + 1.0)

        # 歧义门:多簇接近 或 主 sim 偏低 或 蒙太奇(在抓帧/embed 之前判,
        # 非歧义且单候选窗直接跳过——抓帧+patch forward 很贵, 判据只依赖 evidence 不依赖帧)
        spans = [s for s in (evidence.all_spans or []) if s.original_span is not None]
        sims_sorted = sorted(((s.best_sim or 0.0) for s in spans), reverse=True)
        ambiguous = (len(sims_sorted) >= 2 and sims_sorted[0] - sims_sorted[1] < 0.10)             or evidence.mode == "montage" or (sims_sorted and sims_sorted[0] < 0.60)
        if not ambiguous and len(wins) <= 1:
            return None

        try:
            q_frames = self._grab_frames_parallel(
                edited, self._rep_times(shot.span.start, shot.span.end, 3))
            q_patches = np.vstack([rr.frame_patches(f) for f in q_frames])
        except Exception:
            return None

        wins_sorted = sorted(wins.items())

        def _win_grab(item):
            mid, (a, b) = item
            try:
                return mid, self._grab_frame_cached(Path(bundle.meta.source_file),
                                                    (a + b) / 2.0)
            except Exception:
                return mid, None

        # 并行抓帧(ffmpeg 进程互相独立), 但 DML forward 保持主线程串行——
        # DirectML EP 多线程并发 Run 同一会话会原生段错误(实测), 且 forward 仅 ~55ms/帧
        with ThreadPoolExecutor(max_workers=4) as ex:
            win_frames = list(ex.map(_win_grab, wins_sorted))
        best_mid, best_s = None, -1.0
        for mid, f in win_frames:
            self._check_cancel(cancel_token)
            if f is None:
                continue
            try:
                s = patch_score(q_patches, rr.frame_patches(f))
            except Exception:
                continue
            if s > best_s:
                best_mid, best_s = mid, s
        if best_mid is None:
            return None
        prim_sim = sims_sorted[0] if sims_sorted else 0.0
        # 与 CLS 主定位一致性:patch 最优窗若与主定位重叠或邻近 → 不改写
        cur = (evidence.primary.original_span[0], evidence.primary.original_span[1])             if evidence.primary and evidence.primary.original_span else (0.0, 0.0)
        if abs(best_mid - (cur[0] + cur[1]) / 2.0) <= max(8.0, cfg.patch_rerank_keep_near):
            return None
        half = max(cfg.min_span_s, min(cfg.max_orig_span_s, 2.0)) / 2.0
        return (round(best_mid - half, 2), round(best_mid + half, 2))

    def _patch_nearfield_rescue(self, shot: ShotSegment, bundle: IndexBundle, edited: Path,
                                current_main: tuple[float, float], cfg: PipelineConfig, *,
                                cancel_token: CancellationToken | None = None,
                                ) -> tuple[float, float] | None:
        """patch v2 近场重排（2026-09-06 立项, 门控数据 probe_patch_gate.py）。

        在主定位 ±patch_v2_radius_s 的近场均匀池（patch_v2_stride_s 步长）上 patch 匹配;
        仅当 {best 与主定位 offset≤radius 且 margin=best_score−score@主定位 > patch_v2_margin}
        才改写主定位为 top1 ±1s（旧主定位由调用方保留为子 span）。门控数据（7 池外案例 +
        12 对照）: 仅放行 p26 型（margin 强+近场）, 挡住 t3r26/p10/t1r02 型（margin 弱或远场）。
        """
        if not cfg.patch_v2_enabled or shot.span.width < 0.6:
            return None
        if self._patch_reranker is None:
            self._patch_reranker = PatchReranker(
                resolve_weights(cfg.patch_weights_path or None),
                resolve_patch_onnx((cfg.patch_onnx_model or "").strip() or None),
                dml_device_id=self.config.device.dml_device_id)
        rr = self._patch_reranker
        if not rr.ensure():
            return None
        self._check_cancel(cancel_token)
        cur_mid = (current_main[0] + current_main[1]) / 2.0
        try:
            q_frames = self._grab_frames_parallel(
                edited, self._rep_times(shot.span.start, shot.span.end, 3))
            q_patches = np.vstack([rr.frame_patches(f) for f in q_frames])
            half = int(cfg.patch_v2_radius_s // cfg.patch_v2_stride_s)
            ts = [max(0.0, round(cur_mid + k * cfg.patch_v2_stride_s, 2))
                  for k in range(-half, half + 1)]
            frames = self._grab_frames_parallel(Path(bundle.meta.source_file), ts)
            main_frame = self._grab_frame_cached(Path(bundle.meta.source_file), cur_mid)
        except Exception:
            return None
        main_score = patch_score(q_patches, rr.frame_patches(main_frame))
        best_t, best_score = None, -1.0
        for t, f in zip(ts, frames):
            self._check_cancel(cancel_token)
            try:
                s = patch_score(q_patches, rr.frame_patches(f))
            except Exception:
                continue
            if s > best_score:
                best_t, best_score = t, s
        if best_t is None:
            return None
        margin = best_score - main_score
        if margin <= cfg.patch_v2_margin or abs(best_t - cur_mid) > cfg.patch_v2_radius_s:
            self._log.info("patch v2 nearfield ed=%.1f margin=%.3f (no adopt)",
                           shot.span.start, margin)
            return None
        self._log.info("patch v2 nearfield rescue ed=%.1f main %.1f->%.1f margin=%.3f",
                       shot.span.start, cur_mid, best_t, margin)
        return (round(best_t - 1.0, 2), round(best_t + 1.0, 2))

    def _apply_text_anchor(self, results: list[Result], edited: Path, original: str,
                           *, cfg: PipelineConfig,
                           cancel_token: CancellationToken | None = None) -> None:
        """OCR 文字锚点重排(Phase 21 首选第二信号,非致命)。

        查询段帧有内容文字(过滤 TikTok 水印)时,对每个候选窗(主 span/子 span ±2s)
        抽 2 帧 OCR,字符 3-gram 相似度显著更高的子 span 晋级为主 ``original``。
        实证:同场景字牌在 CLS 下不可分(ed84.5-86 sim 0.84 vs 错误位置 0.91),文字可判。
        """
        if self._ocr_engine is None:
            self._ocr_engine = OcrEngine()
        ocr = self._ocr_engine
        if not ocr.ensure():
            self._log.info("text anchor disabled: rapidocr unavailable")
            return
        orig = Path(original)
        n_promoted = 0
        for r in results:
            self._check_cancel(cancel_token)
            if r.not_in_source:
                continue
            windows: list[tuple[str, float, float]] = [
                ("main", r.original.start, r.original.end)]
            # 场景/事件扩池 span(Phase 21 / 方向 A)只作展示候选,不作为主定位改写来源:
            # 多模态实测:text anchor 按 OCR 巧合把场景 span 晋级主定位会产生新错误匹配
            # (test2 s7 人物 A→人物 B、test1 s18/test3 s10 跳近黑画面)。
            windows += [("sub", s.start, s.end) for s in r.original_segments
                        if not getattr(s, "from_scene_pool", False)
                        and not getattr(s, "from_event_pool", False)]
            if len(windows) < 2:
                continue
            q_frames = self._grab_frames_parallel(
                edited, self._rep_times(r.edited.start, r.edited.end, 3))
            q_lines = filter_watermark(ocr.lines(q_frames))
            if not q_lines:
                continue
            scored = []
            for kind, a, b in windows:
                # 4 帧/窗:字牌等文字镜头可能只有 1-2s,稀疏采样会整窗错过(实测教训)
                w_frames = self._grab_frames_parallel(
                    orig, self._rep_times(max(0.0, a - 2.0), b + 2.0, 4))
                c_lines = filter_watermark(ocr.lines(w_frames))
                scored.append((text_similarity(q_lines, c_lines), kind, a, b))
            main_sim = next(s for s, k, _, _ in scored if k == "main")
            best_sim, kind, a, b = max(scored, key=lambda x: x[0])
            if kind != "sub" or best_sim < cfg.text_anchor_min_sim \
                    or best_sim < main_sim + cfg.text_anchor_min_gain:
                continue
            r.original = TimeSpan(round(a, 2), round(b, 2))
            n_promoted += 1
            self._log.info("text anchor promoted ed=%.1f-%.1f -> %.0f-%.0f sim=%.2f (main %.2f)",
                           r.edited.start, r.edited.end, a, b, best_sim, main_sim)
        if n_promoted:
            self._log.info("text anchor promoted=%d", n_promoted)

    def _apply_sequence_rerank(self, results: list[Result], seq_items: list[dict],
                               *, cfg: PipelineConfig,
                               cancel_token: CancellationToken | None = None) -> None:
        """全局时序一致性 DP 重排(Phase 21 场景身份):相似镜头挑错实例的全局修复。

        DP 在每段候选窗里选一条与编辑顺序一致(允许有限倒退/SKIP)的路径;
        被改写的段:原主定位挪入 original_segments 留痕,新位置成为主 original。
        """
        assignments = sequence_rerank(
            seq_items, order_lambda=cfg.seq_dp_order_lambda,
            skip_penalty=cfg.seq_dp_skip_penalty)
        n_changed = 0
        for a in assignments:
            self._check_cancel(cancel_token)
            if not a.get("changed") or a.get("chosen_mid") is None:
                continue
            if a.get("chosen_score", 0.0) < cfg.seq_dp_min_score:
                continue
            chosen_span = None
            for it in seq_items:
                if it["index"] != a["index"]:
                    continue
                for c in it["cands"]:
                    if abs(c["mid"] - a["chosen_mid"]) < 0.5:
                        chosen_span = c["span"]
                        break
                break
            if chosen_span is None:
                continue
            r = results[a["index"]]
            old_main = (r.original.start, r.original.end)
            if abs(old_main[0] - chosen_span[0]) < 0.5:
                continue
            r.original = TimeSpan(round(chosen_span[0], 2), round(chosen_span[1], 2))
            if all(abs(s.start - old_main[0]) > 0.5 for s in r.original_segments):
                r.original_segments.insert(0, OriginalSegment(old_main[0], old_main[1], 0.0, None))
            n_changed += 1
            self._log.info("sequence rerank s%d ed=%.1f main %.0f->%.0f",
                           a["index"], r.edited.start, old_main[0], chosen_span[0])
        if n_changed:
            self._log.info("sequence rerank changed=%d", n_changed)

    def _apply_temporal_repair(self, results: list[Result], bundle: IndexBundle,
                               edited: str | Path, *,
                               cfg: PipelineConfig,
                               cancel_token: CancellationToken | None = None) -> None:
        """时序离群修复（test1 r18 实证）：定位与前后两段同时严重冲突的段，
        在前后段定位窗口内重新检索拉回；原定位挪入 original_segments 留痕。
        严格触发条件见 temporal_repair.find_temporal_outliers（防误伤闪回/乱序）。"""
        if len(results) < 3:
            return
        positions: list[tuple[float, float] | None] = []
        for r in results:
            if r.not_in_source or r.failure_reason or r.original.end - r.original.start <= 0:
                positions.append(None)
            else:
                positions.append((r.original.start, r.original.end))
        outliers = find_temporal_outliers(
            positions, neighbor_gap_s=cfg.tr_neighbor_gap_s,
            outlier_min_dist_s=cfg.tr_outlier_min_dist_s)
        # 注：相邻段定位区间部分重叠在"连续场景内切多镜头"里是正常现象
        # （test3 实测 7 段重叠中 6 段目检正确），重叠几何无法区分真错配，
        # 不做自动修复——错配交由结果页手动替换（预览/设为主定位）。
        if not outliers:
            return
        feats, times = bundle.features, bundle.times
        n_fixed = 0
        for i in outliers:
            self._check_cancel(cancel_token)
            r = results[i]
            prev_p, next_p = positions[i - 1], positions[i + 1]
            width = r.original.end - r.original.start
            window = (min(prev_p[0], next_p[0]) - 2.0, max(prev_p[1], next_p[1]) + 2.0)
            # 查询特征必须来自编辑段本身（离群段的原位特征是错误内容，不可用作查询）
            query = self._edited_segment_query(edited, r.edited.start, r.edited.end)
            if query is None:
                continue
            new_span = relocate_in_window(query, feats, times, window, width)
            if new_span is None:
                continue
            old_mid = self._mid_of(r.original)
            new_mid = self._mid_of(TimeSpan(*new_span))
            if abs(new_mid - old_mid) < 1.0:
                continue
            self._log.info("temporal repair seg%d ed=%.1f-%.1f %.0f-%.0f -> %.0f-%.0f",
                           i + 1, r.edited.start, r.edited.end,
                           r.original.start, r.original.end, new_span[0], new_span[1])
            if all(abs(s.start - r.original.start) > 0.5 for s in r.original_segments):
                r.original_segments.insert(
                    0, OriginalSegment(r.original.start, r.original.end, 0.0, None))
            r.original = TimeSpan(*new_span)
            r.confidence = Confidence(
                r.confidence.level, r.confidence.score,
                tuple(r.confidence.reasons) + ("temporal_outlier_repair",))
            n_fixed += 1
            positions[i] = new_span
        if n_fixed:
            self._log.info("temporal repair fixed=%d", n_fixed)

    def _apply_conflict_rerank(self, results: list[Result], bundle: IndexBundle,
                               edited: str | Path, *,
                               cfg: PipelineConfig,
                               cancel_token: CancellationToken | None = None) -> None:
        """相邻重叠冲突修复(Phase 24 非外观第二信号)。

        触发 = 编辑序相邻段定位区间重叠(几何);接受 = 空隙内候选有实质内容证据且
        与当前定位落差有限(内容门槛)。只看相邻段——非相邻的源区间复用是正常剪辑
        现象(test3 r6/r8 合法重叠),这正是纯几何先验不可分而本机制可分的关键。
        修复:原主定位挪入 original_segments 留痕,新定位成为主 original,
        置信档位不变、追加 reason ``conflict_rerank``。
        """
        if len(results) < 3:
            return
        positions: list[tuple[float, float] | None] = []
        for r in results:
            if r.not_in_source or r.failure_reason or r.original.end - r.original.start <= 0:
                positions.append(None)
            else:
                positions.append((r.original.start, r.original.end))
        conflicts = find_span_conflicts(
            positions,
            max_mover_width_s=cfg.conflict_max_mover_width_s,
            overlap_min_s=cfg.conflict_overlap_min_s,
            scores=[r.confidence.score for r in results])
        if not conflicts:
            return
        feats, times = bundle.features, bundle.times
        n_fixed = 0
        # 弱主张先让位:按 mover 置信分升序处理;修复会改写 positions,
        # 因此每次处理时用**当前** positions 重算空隙窗(级联安全)
        conflicts = sorted(conflicts, key=lambda c: results[c[0]].confidence.score)
        for i, _window0 in conflicts:
            self._check_cancel(cancel_token)
            prev_p, next_p = positions[i - 1], positions[i + 1]
            if prev_p is None or next_p is None or prev_p[1] > next_p[0]:
                continue
            window = (prev_p[1], next_p[0])
            r = results[i]
            width = r.original.end - r.original.start
            if window[1] - window[0] < width:
                continue
            query = self._edited_segment_query(edited, r.edited.start, r.edited.end)
            if query is None:
                continue
            cur_sim = span_mean_sim(query, feats, times,
                                    (r.original.start, r.original.end))
            # 空隙窗扣除其他段 claim(含非相邻段的合法复用重叠)后的无主张子区间里
            # 重定位,取最优;整窗 relocate 会被非相邻 claim 整单否决(test3-r10 实证)
            claims = [p for j, p in enumerate(positions) if j != i and p is not None]
            alt_span, alt_sim = best_free_span(query, feats, times, window,
                                               claims, width)
            if alt_span is None:
                continue
            if not accept_repair(cur_sim, alt_sim,
                                 alt_min_sim=cfg.conflict_alt_min_sim,
                                 max_drop=cfg.conflict_max_drop):
                continue
            self._log.info(
                "conflict rerank seg%d ed=%.1f-%.1f %.1f-%.1f -> %.1f-%.1f (sim %.2f->%.2f)",
                i + 1, r.edited.start, r.edited.end,
                r.original.start, r.original.end, alt_span[0], alt_span[1],
                cur_sim or 0.0, alt_sim or 0.0)
            if all(abs(s.start - r.original.start) > 0.5 for s in r.original_segments):
                r.original_segments.insert(
                    0, OriginalSegment(r.original.start, r.original.end, 0.0, None))
            r.original = TimeSpan(alt_span[0], alt_span[1])
            r.confidence = Confidence(
                r.confidence.level, r.confidence.score,
                tuple(r.confidence.reasons) + ("conflict_rerank",))
            positions[i] = alt_span
            n_fixed += 1
        if n_fixed:
            self._log.info("conflict rerank fixed=%d", n_fixed)

    def _apply_temporal_ambiguity(self, results: list[Result], *,
                                    cfg: PipelineConfig) -> None:
        """时间轴→Ambiguity（NEXT_STEPS ⑥，2026-09-01 拍板执行序第 2 项）。

        背景: Ambiguity 原型(2026-09-01)证明内部置信信号(margin/similar/multiple)
        无法分离「正确 HIGH」与「错配 HIGH」(内部无分歧)。时间轴是外部独立信号:
        某段定位与前后段严重冲突(离群) = "可疑", 即使它内部 margin 很高。

        动作: 不改定位(那是 temporal_repair 的职责), 只把最终仍离群的段
        降置信档位(HIGH→MEDIUM, 转人工提示) + 追加 reason temporal_outlier_ambiguous。
        放在 temporal_repair/conflict_rerank 之后运行——被修复的段已不再离群,
        只剩"修不动且时序冲突"的段被降档, 零误伤已修复段。触发条件与 temporal_repair
        相同(find_temporal_outliers: 前后段接近 ≤ neighbor_gap_s 且本段远离 ≥
        outlier_min_dist_s), 真实跳切(8/29 倒退)多为编辑片故意打乱, 前后段不满足
        "彼此接近", 不会误伤。
        """
        if not cfg.temporal_ambiguity_enabled or len(results) < 3:
            return
        positions: list[tuple[float, float] | None] = []
        for r in results:
            if r.not_in_source or r.failure_reason or r.original.end - r.original.start <= 0:
                positions.append(None)
            else:
                positions.append((r.original.start, r.original.end))
        outliers = find_temporal_outliers(
            positions, neighbor_gap_s=cfg.tr_neighbor_gap_s,
            outlier_min_dist_s=cfg.tr_outlier_min_dist_s)
        if not outliers:
            return
        try:
            downgrade = ConfidenceLevel(cfg.ta_max_downgrade)
        except ValueError:
            downgrade = ConfidenceLevel.MEDIUM
        n = 0
        for i in outliers:
            r = results[i]
            if r.confidence.level != ConfidenceLevel.HIGH:
                continue
            r.confidence = Confidence(
                downgrade, r.confidence.score,
                tuple(r.confidence.reasons) + ("temporal_outlier_ambiguous",))
            self._log.info("temporal ambiguity s%d ed=%.1f HIGH->%s (outlier %.0f-%.0f)",
                           i + 1, r.edited.start, downgrade.value,
                           r.original.start, r.original.end)
            n += 1
        if n:
            self._log.info("temporal ambiguity flagged=%d", n)

    def _apply_timeline_prior(self, evidence, prev_mid: float | None, *,
                               cfg: PipelineConfig) -> bool:
        """单调弱先验进候选生成(NEXT_STEPS ②③, 2026-09-02 拍板实施)。

        把「编辑序≈原片序」作为候选生成阶段的弱倾向(而非仅事后修复):
        对 Ambiguous 型段(>=2 保留证据簇, 即 montage 多候选难分), 用前序段定位中点
        prev_mid 做时间轴锚点——若 primary 在时序合理带外(> ta_band_s)而存在一个
        带内且 cover 落差 <= ta_max_cover_drop 的竞争候选, 则切换 primary 到带内候选
        (提前压制兄弟机位/同质场景误配; 只作倾向不作强制)。

        逃生门(真实回溯 8/29 不误伤):
          - 首段 / 前段未定位: prev_mid=None → 不触发;
          - 唯一强候选: 竞争候选 cover 落差超过 ta_max_cover_drop → 不切(可靠命中不碰);
          - primary 已在带内: 不切换(带内候选不做微小偏向, 防噪声抖动);
          - 全部候选都在带外: 不强行拉进带内(真实倒叙/闪回保留原位)。

        返回是否切换了 primary(切换时 secondary 同步指向旧 primary, 供 alternatives 留痕)。
        """
        if not cfg.timeline_prior_enabled or prev_mid is None:
            return False
        prim = evidence.primary
        if prim is None or prim.original_span is None:
            return False
        spans = [s for s in (evidence.spans or []) if s.original_span is not None]
        if len(spans) < 2:
            return False                       # 唯一候选=可靠命中, 不碰
        mid = lambda s: (s.original_span[0] + s.original_span[1]) / 2.0
        prim_in_band = abs(mid(prim) - prev_mid) <= cfg.ta_band_s
        if prim_in_band:
            return False                       # primary 已时序合理, 不做带内偏向
        for s in spans:
            if s is prim:
                continue
            if abs(mid(s) - prev_mid) > cfg.ta_band_s:
                continue                       # 候选也在带外: 不强行拉进
            gap = (prim.cover or 0.0) - (s.cover or 0.0)
            if gap > cfg.ta_max_cover_drop:
                continue                       # primary 显著更强: 不切(唯一强候选)
            old = prim
            evidence.primary = s
            evidence.secondary = old
            return True
        return False

    def _edited_cache_store(self) -> EditedCache:
        if self._edited_cache is None:
            from infrastructure.paths import app_data_dir
            self._edited_cache = EditedCache(app_data_dir() / "edited_cache")
        return self._edited_cache

    def _edited_fingerprint(self, edited: Path) -> str:
        """编辑侧缓存键: 文件身份 + 特征口径 + 管线配置 + 设备数值口径（batch 在内）。"""
        key = self._edited_cache_key_by_path.get(str(edited))
        if key is not None:
            return key
        be = self.backend
        device_tag = (f"{type(be).__name__}:{getattr(be, 'device_type', lambda: '?')()}:"
                      f"b{self.config.device.dml_batch_size}")
        from dataclasses import asdict
        key = edited_cache_fingerprint(
            edited, self.store.feature_version, asdict(self.config.pipeline), device_tag)
        self._edited_cache_key_by_path[str(edited)] = key
        return key

    def _edited_segment_query(self, edited: str | Path, start: float, end: float) -> np.ndarray | None:
        """编辑段的均值查询特征（2fps 抽帧嵌入，会话内缓存）。离群/冲突修复专用。"""
        key = ("tr", str(Path(edited).resolve()), round(start, 2), round(end, 2))
        if key in self._tr_query_cache:
            return self._tr_query_cache[key]
        try:
            frames = [f for _, f in self.ffmpeg.iter_frames(edited, 2.0, start=start, end=end)]
        except Exception:
            self._log.exception("temporal repair: edited frame extraction failed")
            return None
        if not frames:
            return None
        embs = self.backend.embed_frames(frames)
        q = embs.mean(axis=0)
        q /= max(float(np.linalg.norm(q)), 1e-8)
        self._tr_query_cache[key] = q
        return q

    def _grab_frames_parallel(self, path, times, *, max_workers: int = 4):
        """多帧并行抓取（每帧独立 ffmpeg 进程, 线程池并发; grab 是纯 IO+解码,
        帧结果与串行逐字节一致）。patch rerank 358 帧 spawn 占 111s(探针实测),
        并发 4 → 逼近 /4。"""
        from concurrent.futures import ThreadPoolExecutor

        times = list(times)
        if len(times) <= 1:
            return [self._grab_frame_cached(path, t) for t in times]
        with ThreadPoolExecutor(max_workers=min(max_workers, len(times))) as ex:
            return list(ex.map(lambda t: self._grab_frame_cached(path, t), times))

    def _grab_frame_cached(self, path, t: float):
        """grab_frame 带进程内缓存（patch rerank/text anchor 相邻段反复抓同一候选窗帧）。

        纯缓存零语义变化；上限 FIFO 清空防内存膨胀（单帧 ~1.5MB, 512 帧 ≈ 0.8GB 上限）。
        """
        key = (str(Path(path).resolve()), round(float(t), 3))
        hit = self._grab_cache.get(key)
        if hit is not None:
            return hit
        frame = self.ffmpeg.grab_frame(path, t)
        if len(self._grab_cache) >= 512:
            self._grab_cache.clear()
        self._grab_cache[key] = frame
        return frame

    @staticmethod
    def _mid_of(span: TimeSpan) -> float:
        return (span.start + span.end) / 2.0

    @staticmethod
    def _rep_times(a: float, b: float, n: int) -> list[float]:
        """n 个代表时间点(块中心),供抽帧。"""
        return [round(a + (b - a) * (i + 0.5) / n, 2) for i in range(n)]

    @staticmethod
    def _ensure_session() -> str:
        """若当前上下文尚无 session id，生成一个新的。返回生效值。"""
        sid = get_session_id()
        if not sid:
            sid = new_session_id()
        return sid

    def _log_locate_summary(self, edited: Path, batch: ResultBatch, elapsed: float) -> None:
        """locate 汇总：segments / candidates / confidence 三档 / unresolved / 耗时。"""
        conf = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
        unresolved = 0
        for r in batch.results:
            if r.failure_reason:
                unresolved += 1
            else:
                level = r.confidence.level.value if r.confidence else "LOW"
                conf[level] = conf.get(level, 0) + 1
        self._log.info(
            "locate finished edited=%s segments=%d candidates=%d results=%d "
            "high=%d medium=%d low=%d unresolved=%d elapsed=%.1fs",
            edited.name, len(batch.results), self._last_candidates, len(batch.results),
            conf["HIGH"], conf["MEDIUM"], conf["LOW"], unresolved, elapsed)

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
