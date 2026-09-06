"""engine.localization.evidence_localize — multi-evidence 主定位器（2026-08-28）。

把「一个可能含多个子镜头的 edited 查询单元」定位成「多个证据聚集区（原片区）」：
  1. 证据提取：逐编辑帧取全索引 argmax Top1 原片时间 + 相似度（query-axis；每帧 = 一条证据）。
  2. 证据聚类 ``cluster_by_gap`` -> 时间连续证据簇。
  3. 显著簇门控：``cluster_frames >= min_frames`` 且 簇均值 ``best_sim >= min_sim``。
  4. 每簇精化（**保留 finloc_window**）-> 子 span + best_cover/mean_sim + 完整 finloc 诊断。
  5. 输出 ``EvidenceResult``（含 multi-evidence 置信诊断：primary/secondary/evidence_qcov/dispersion）。

与 ``MontageLocalizer``（montage_localize.py）语义一致（research parity）：>=2 显著簇=montage /
1=clean / 0=empty。差别仅在本层携带更丰富的置信诊断字段，且把「是否 >=2 kept 才算 montage」
的判定放到 app 层（本层 mode 不覆写，保持与 MontageLocalizer 完全一致）。

产品语义：multi evidence localization（single answer -> multi evidence）。研究护栏：
**不改** cosine_similarity / 特征 / finloc_window 语义；finloc 仅作簇内 span 精化 + 质量信号。

Phase 21 场景指纹召回扩展层（2026-08-30）：索引侧场景表（FeatureStore scenes.npy/scene_feats.npy）
+ 查询均值 vs 场景指纹 top-K（``scene_top_k``）场景内帧（``scene_max_expand_frames`` 预算）扩池。
**帧级为主，场景级只扩池**——场景单元独立精化与门控（``_gate_scene_spans``），不参与帧级
聚类/montage 计数/primary 竞争/置信信号（p27 型「帧级已对」不被场景噪声翻车）；产出只作
附加子 span（``scene_spans``）与重排候选池（``all_spans``）；帧级零证据时场景 span 才晋级
主定位（救回路径，诚实 LOW）。第一版实现（扩池并入同一证据池重聚类）实测 25/29 段被改写、
HIGH→LOW 塌陷，已废弃（教训：扩池帧桥接簇边界 + 稀释簇均值门控）。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from domain import Candidate
from engine.common import cosine_similarity
from engine.feature_store import IndexBundle
from engine.localization.finloc import FINLOC_STABLE_S, LocalizationResult, finloc_window
from engine.localization.montage_localize import cluster_by_gap
from engine.localization.seq_align import MomentSpan


@dataclass
class EvidenceSpan:
    """一个证据簇（子镜头）的定位结果。"""

    edited_interval: tuple[float, float]       # 子镜头在编辑片的时间区间（簇帧 min/max）
    edited_frames: list[float]                 # 簇内查询帧的编辑时间（集合）
    original_span: tuple[float, float] | None  # 对应原片区（簇范围 ∪ finloc run）
    cover: float                               # finloc best_cover（质量信号）
    best_sim: float | None                     # finloc run 内平滑覆盖率均值（质量信号）
    cluster_frames: int                        # 簇内证据帧数（含场景扩池帧,Phase 21）
    dropped_weak: bool = False                 # 是否被弱簇过滤丢弃
    query_frames: int = 0                      # 簇内查询帧数（qcov 口径;扩池帧不计）
    # ---- multi-evidence 置信诊断 ----
    finloc: LocalizationResult | None = None
    peak_sim: float | None = None              # finloc run 内 raw cover 峰值
    span_stability: float = 0.0
    timestamp_mean: float | None = None        # 簇 best_t 均值（分散度）
    timestamp_std: float = 0.0                 # 簇 best_t 标准差（分散度）
    moments: list[MomentSpan] = field(default_factory=list)  # 帧级 moment（seq_align 精修）


@dataclass
class EvidenceResult:
    """一个 edited 查询单元的 multi-evidence 定位结果。"""

    mode: str                     # "montage" | "clean" | "empty"（与 MontageLocalizer 一致）
    spans: list[EvidenceSpan] = field(default_factory=list)
    n_clusters: int = 0
    n_strong_clusters: int = 0    # 弱簇过滤前满足门控的簇数
    n_dropped_weak: int = 0
    n_query: int = 0
    n_moments: int = 0                  # 全部保留 span 的 moments 总数（帧级精修量）
    # ---- multi-evidence 置信信号聚合 ----
    evidence_qcov: float = 0.0    # 保留 span 覆盖的编辑帧数 / n_query（时序覆盖 = n_reps 类比）
    primary: EvidenceSpan | None = None      # cover 最高的保留 span
    secondary: EvidenceSpan | None = None    # 次高 cover 保留 span（clean=None）
    dispersion: float = 0.0                  # 全部保留 span 的 best_t 全局分散度（占位）
    all_spans: list[EvidenceSpan] = field(default_factory=list)  # 门控前的全部簇(时序重排候选池,Phase 21)
    # ---- 场景指纹扩池（Phase 21 召回扩展层）----
    # 帧级为主:场景扩池 span 不参与 montage 计数/primary 竞争/置信信号,仅作附加子 span
    # 与重排候选池;帧级零证据时它们才作为救回主定位（spans=scene_spans）。
    scene_spans: list[EvidenceSpan] = field(default_factory=list)
    # ---- 事件单元扩池（方向 A 完整阶段 2026-09-05:场景实例身份建模）----
    # 与场景扩池同语义:事件扩池 span 仅作附加子 span 与重排候选池,不参与帧级聚类/
    # montage 计数/primary 竞争/置信信号;帧级+场景均零证据时才救回主定位。
    event_spans: list[EvidenceSpan] = field(default_factory=list)


class EvidenceLocalizer:
    """multi-evidence 主定位器（query-axis 逐帧 top1 聚类 + 每簇 finloc 精化）。"""

    def __init__(self, *, cluster_gap_s: float = 15.0, min_frames: int = 2,
                 min_sim: float = 0.40, pad_s: float = 15.0,
                 weak_cover: float = 0.30, weak_sim: float = 0.45,
                 max_span_s: float = 15.0,
                 subspan_min_cover: float = 0.45, subspan_min_sim: float = 0.50,
                 subspan_iou_merge: float = 0.60, subspan_max_keep: int = 4,
                 seq_align=None,
                 seq_pad_s: float = 15.0, seq_window_max_s: float = 45.0,
                 seq_global_mean_sim_min: float = 0.20,
                 seq_max_query_frames: int = 64, seq_moment_half_s: float = 1.0,
                 seq_mean_sim_min: float = 0.40,
                 scene_recall_enabled: bool = True, scene_top_k: int = 5,
                 scene_max_expand_frames: int = 120,
                 event_recall_enabled: bool = True, event_top_k: int = 3,
                 event_max_expand_frames: int = 240,
                 finloc_stable_s: float = FINLOC_STABLE_S):
        self.cluster_gap_s = cluster_gap_s
        self.min_frames = min_frames
        self.min_sim = min_sim
        self.pad_s = pad_s
        self.weak_cover = weak_cover
        self.weak_sim = weak_sim
        self.max_span_s = max_span_s
        self.finloc_stable_s = finloc_stable_s
        # 子 span 严格门 + IoU 去重(GT v3 实证:暗色外观巧合子 span 如 1303/3654 混入结果)
        self.subspan_min_cover = subspan_min_cover
        self.subspan_min_sim = subspan_min_sim
        self.subspan_iou_merge = subspan_iou_merge
        self.subspan_max_keep = subspan_max_keep
        self.seq_align = seq_align   # 可调用 (qc_s,tq_s,rfeats,rtimes)->SeqAlignResult；None=关闭 moment 精修
        # 全局对齐 moment 参数（config SeqAlignConfig 驱动）
        self.seq_pad_s = seq_pad_s
        self.seq_window_max_s = seq_window_max_s
        self.seq_global_mean_sim_min = seq_global_mean_sim_min
        self.seq_max_query_frames = seq_max_query_frames
        self.seq_moment_half_s = seq_moment_half_s
        self.seq_mean_sim_min = seq_mean_sim_min
        # 场景指纹召回扩展层（Phase 21）:帧级 top-K 为主,场景级只扩池。
        # 查询均值与场景指纹 top-5 场景的场景内全部帧并入 best_t 证据集（上限 scene_max_expand_frames）。
        self.scene_recall_enabled = scene_recall_enabled
        self.scene_top_k = scene_top_k
        self.scene_max_expand_frames = scene_max_expand_frames
        # 事件单元扩池（方向 A 完整阶段 2026-09-05:场景实例身份建模）
        self.event_recall_enabled = event_recall_enabled
        self.event_top_k = event_top_k
        self.event_max_expand_frames = event_max_expand_frames

    def localize(self, ed_feats: np.ndarray, ed_times: np.ndarray,
                 bundle: IndexBundle, *, dense_query=None) -> EvidenceResult:
        """对单个 edited 查询单元做 multi-evidence 定位。无 IO、确定性。

        ``dense_query``：(feats[Nq,384], times[Nq]) @ seq_edit_fps（app 层密帧重采样），
        None=不进全局对齐（旧调用方/测试零回归）。
        """
        q = np.asarray(ed_feats, dtype=np.float32)
        tq = np.asarray(ed_times, dtype=np.float32)
        if q.shape[0] == 0 or bundle.features.shape[0] == 0:
            return EvidenceResult(mode="empty")

        sim = cosine_similarity(q, bundle.features)
        best = np.argmax(sim, axis=1)
        best_t = bundle.times[best]
        best_s = sim[np.arange(q.shape[0]), best]

        # ---- 场景指纹扩池单元（Phase 21 召回扩展层:帧级 top-K 为主,场景级只扩池）----
        # 查询均值与场景指纹 top-K 场景匹配 → 场景内帧(预算内)作候选扩池单元。每个场景 =
        # 一个单元（时间相邻的场景不互相桥接）;场景内帧均值须过 min_sim 门(噪声场景丢弃)。
        # 场景单元不参与帧级聚类/montage 计数/primary 竞争/置信信号（p27 型「帧级已对」
        # 不被场景噪声翻车）,仅作附加子 span 与重排候选池;帧级零证据时才作救回主定位。
        qf = None
        scene_units: list[tuple[float, float, np.ndarray]] = []
        event_units: list[tuple[float, float, np.ndarray]] = []
        if self.scene_recall_enabled and bundle.scenes is not None \
                and bundle.scene_feats is not None \
                and len(bundle.scenes) and len(bundle.scene_feats) == len(bundle.scenes):
            qf = q.mean(axis=0)
            qf = qf / max(float(np.linalg.norm(qf)), 1e-8)
            ssims = bundle.scene_feats @ qf
            order = np.argsort(-ssims)[:max(1, self.scene_top_k)]
            budget = max(0, int(self.scene_max_expand_frames))
            for k in order:
                if budget <= 0:
                    break
                a, b = float(bundle.scenes[k, 0]), float(bundle.scenes[k, 1])
                fidx = np.where((bundle.times >= a) & (bundle.times < b))[0]
                if fidx.size == 0:
                    continue
                if fidx.size > budget:
                    fidx = fidx[np.linspace(0, fidx.size - 1, budget).astype(int)]
                budget -= int(fidx.size)
                if fidx.size < self.min_frames:
                    continue
                if float((bundle.features[fidx] @ qf).mean()) < self.min_sim:
                    continue
                scene_units.append((a, b, bundle.times[fidx]))

        # ---- 事件单元扩池（方向 A 完整阶段 2026-09-05:场景实例身份建模）----
        # 查询均值 vs 事件指纹 top-K 事件匹配 → 事件时间窗内帧(预算内)作候选扩池单元。
        # 事件 = 时序近邻+指纹联合归并的场景组(同场对话戏/兄弟机位),比单场景更粗的
        # 身份单元——p08 兄弟机位(场景134/128)在事件指纹下聚为同一事件,查询均值命中
        # 正确事件 → 事件内帧(含两机位)全部进证据池,解决帧级 argmax 只落单机位的歧义。
        # 与场景扩池同语义:事件单元不参与帧级聚类/montage 计数/primary 竞争/置信信号,
        # 仅作附加子 span 与重排候选池;帧级+场景均零证据时才救回主定位。
        if self.event_recall_enabled and bundle.events is not None                 and bundle.event_feats is not None                 and len(bundle.events) and len(bundle.event_feats) == len(bundle.events):
            if qf is None:
                qf = q.mean(axis=0)
                qf = qf / max(float(np.linalg.norm(qf)), 1e-8)
            esims = bundle.event_feats @ qf
            order = np.argsort(-esims)[:max(1, self.event_top_k)]
            budget = max(0, int(self.event_max_expand_frames))
            for k in order:
                if budget <= 0:
                    break
                a, b = float(bundle.events[k, 0]), float(bundle.events[k, 1])
                fidx = np.where((bundle.times >= a) & (bundle.times < b))[0]
                if fidx.size == 0:
                    continue
                if fidx.size > budget:
                    fidx = fidx[np.linspace(0, fidx.size - 1, budget).astype(int)]
                budget -= int(fidx.size)
                if fidx.size < self.min_frames:
                    continue
                # 门控用事件指纹相似度(查询均值 vs 事件代表) —— 事件窗跨多场景、帧异构,
                # 全窗帧均值会被稀释 < min_sim 导致事件单元整组丢弃(与探针 P2 排序口径一致)。
                if float(esims[k]) < self.min_sim:
                    continue
                event_units.append((a, b, bundle.times[fidx]))

        # ---- 帧级聚类 + 门控（原语义,不与扩池混算）----
        clusters = cluster_by_gap(best_t, self.cluster_gap_s)
        sig = []
        for (c0, c1, cnt) in clusters:
            qidx = np.where((best_t >= c0) & (best_t <= c1))[0]
            if cnt >= self.min_frames and float(best_s[qidx].mean()) >= self.min_sim:
                sig.append((c0, c1, qidx))

        if len(sig) >= 2:
            mode = "montage"
        elif len(sig) == 1:
            mode = "clean"
        elif scene_units or event_units:
            mode = "clean"        # 场景/事件救回:帧级零证据,扩池 span 晋级主定位(诚实 LOW)
        else:
            return EvidenceResult(mode="empty", n_clusters=len(clusters))

        if mode == "clean" and sig:
            sig = [max(sig, key=lambda s: s[2].size)]

        built = []
        for (c0, c1, qidx) in sig:
            built.append(self._locate_cluster(
                qidx, best_t[qidx], best_t[qidx], q, tq, qf, bundle,
                max(0.0, c0 - self.pad_s), c1 + self.pad_s, dense_query=dense_query))
        kept = [s for s in built if not s.dropped_weak]
        kept, n_gated = self._gate_subspans(kept)

        # ---- 场景扩池 span(独立精化 + 门控,与帧级完全解耦)----
        scene_built = []
        for (a, b, ut) in scene_units:
            scene_built.append(self._locate_cluster(
                np.empty(0, dtype=np.int64), ut, np.empty(0, dtype=np.float32),
                q, tq, qf, bundle,
                max(0.0, a - self.pad_s), b + self.pad_s, dense_query=dense_query))
        scene_kept = [s for s in scene_built if not s.dropped_weak]
        scene_kept = self._gate_scene_spans(scene_kept, kept)

        # ---- 事件扩池 span(独立精化 + 门控,与帧级/场景完全解耦)----
        # span_mode="run": 事件身份命中 → 事件窗内帧级精修, 只输出 finloc 精确 run
        # (不 ∪ 事件窗全范围, 避免粗跨度假命中; 无精确 run 则 span=None 诚实淘汰)。
        event_built = []
        for (a, b, ut) in event_units:
            event_built.append(self._locate_cluster(
                np.empty(0, dtype=np.int64), ut, np.empty(0, dtype=np.float32),
                q, tq, qf, bundle,
                max(0.0, a - self.pad_s), b + self.pad_s, dense_query=dense_query,
                span_mode="run"))
        event_kept = [s for s in event_built if not s.dropped_weak]
        # 事件 span 与帧级 kept + 场景 span 都做 IoU 去重: 事件是场景的父级身份单元,
        # 事件 span 常与其中某个场景 span 重叠, 不去重会导致结果页/导出重复候选。
        event_kept = self._gate_scene_spans(event_kept, kept + scene_kept)

        if not kept and not scene_kept and not event_kept:
            return EvidenceResult(mode="empty", n_clusters=len(clusters),
                                  n_strong_clusters=len(sig),
                                  n_dropped_weak=len(built) + len(scene_built)
                                  + len(event_built))

        if kept:
            primary = max(kept, key=lambda s: s.cover)
            secondary = max((s for s in kept if s is not primary), key=lambda s: s.cover,
                            default=None)
        elif scene_kept:   # 场景救回:无帧级证据,场景 span 即主定位
            primary = max(scene_kept, key=lambda s: s.cover)
            secondary = max((s for s in scene_kept if s is not primary),
                            key=lambda s: s.cover, default=None)
        else:   # 事件救回:帧级+场景均零证据,事件 span 即主定位
            primary = max(event_kept, key=lambda s: s.cover)
            secondary = max((s for s in event_kept if s is not primary),
                            key=lambda s: s.cover, default=None)
        qcov = (sum(s.query_frames for s in kept) / q.shape[0]) if q.shape[0] else 0.0
        tmeans = [s.timestamp_mean for s in kept if s.timestamp_mean is not None]
        disp = float(np.std(np.array(tmeans))) if len(tmeans) > 1 else 0.0

        if kept:
            _spans = kept
            _scene_spans = list(scene_kept)
            _event_spans = list(event_kept)
        elif scene_kept:
            _spans = list(scene_kept)
            _scene_spans = []
            _event_spans = list(event_kept)
        else:
            _spans = list(event_kept)
            _scene_spans = []
            _event_spans = []
        return EvidenceResult(
            mode=mode, spans=_spans,
            scene_spans=_scene_spans,
            event_spans=_event_spans,
            n_clusters=len(clusters), n_strong_clusters=len(sig),
            n_dropped_weak=(sum(1 for s in built if s.dropped_weak) + n_gated
                            + sum(1 for s in scene_built if s.dropped_weak)
                            + sum(1 for s in event_built if s.dropped_weak)),
            n_query=int(q.shape[0]),
            n_moments=sum(len(s.moments) for s in kept),
            evidence_qcov=round(float(qcov), 3), primary=primary, secondary=secondary,
            dispersion=round(disp, 3),
            # 重排候选池(seq DP/patch)保持帧级语义:扩池 span 不进池
            # (实测:进池后 DP 会把 p27 型已对的帧级主定位改写成场景 span=翻车)。
            # 仅帧级零证据的救回段(无帧级池可用)才以扩池 span 进池,此时基线本无结果,
            # 不存在翻车对象。
            all_spans=list(built) if built else (
                list(scene_built) if scene_built else list(event_built)))

    def _gate_subspans(self, spans: list[EvidenceSpan]) -> tuple[list[EvidenceSpan], int]:
        """子 span 严格门 + IoU 去重 + 数量上限(GT v3 加固实证驱动)。

        1. 严格门:cover < subspan_min_cover 且 best_sim < subspan_min_sim(双低)→ 丢。
           比弱簇过滤(weak_cover/weak_sim)严一档,拦"暗色外观巧合"假阳性子 span
           (实测:s4-sub1303 山地士兵、s9-sub3654 接吻镜头)。
        2. IoU 去重:original_span 交并比 > subspan_iou_merge 的重叠 span 合并,留排序分高者
           (排序分 = cover × best_sim;同场景多次命中时避免同区重复展示)。
        3. 数量上限:按排序分保留 top subspan_max_keep。
        返回 (保留列表, 被门控/合并丢弃数)。全部丢光时保底留最优一条(空结果交上层语义)。
        """
        if not spans:
            return spans, 0
        n0 = len(spans)

        def rank(s: EvidenceSpan) -> float:
            return (s.cover or 0.0) * (s.best_sim if s.best_sim is not None else 0.0)

        strict = [s for s in spans
                  if not ((s.cover or 0.0) < self.subspan_min_cover
                          and (s.best_sim is None or s.best_sim < self.subspan_min_sim))]
        if not strict:
            strict = [max(spans, key=rank)]  # 全被门掉时保底留最优一条

        def iou(x: EvidenceSpan, y: EvidenceSpan) -> float:
            if x.original_span is None or y.original_span is None:
                return 0.0
            a0, a1 = x.original_span
            b0, b1 = y.original_span
            inter = max(0.0, min(a1, b1) - max(a0, b0))
            union = max(a1, b1) - min(a0, b0)
            return inter / union if union > 0 else 0.0

        strict.sort(key=rank, reverse=True)
        kept: list[EvidenceSpan] = []
        for s in strict:
            if all(iou(s, k) <= self.subspan_iou_merge for k in kept):
                kept.append(s)
        kept = kept[:max(1, self.subspan_max_keep)]
        kept.sort(key=lambda s: s.edited_interval[0])  # 恢复时间轴顺序
        return kept, n0 - len(kept)

    def _gate_scene_spans(self, spans: list[EvidenceSpan],
                          frame_kept: list[EvidenceSpan]) -> list[EvidenceSpan]:
        """场景扩池 span 门（Phase 21）:与子 span 门同口径的严格门 + 与帧级保留 span/
        相互之间的 IoU 去重 + 数量上限。**无保底**——全被门掉即无场景扩池 span,
        帧级结果不受任何影响（场景级只扩池）。"""
        if not spans:
            return []

        def rank(s: EvidenceSpan) -> float:
            return (s.cover or 0.0) * (s.best_sim if s.best_sim is not None else 0.0)

        def iou(x: EvidenceSpan, y: EvidenceSpan) -> float:
            if x.original_span is None or y.original_span is None:
                return 0.0
            a0, a1 = x.original_span
            b0, b1 = y.original_span
            inter = max(0.0, min(a1, b1) - max(a0, b0))
            union = max(a1, b1) - min(a0, b0)
            return inter / union if union > 0 else 0.0

        strict = [s for s in spans
                  if not ((s.cover or 0.0) < self.subspan_min_cover
                          and (s.best_sim is None or s.best_sim < self.subspan_min_sim))]
        out: list[EvidenceSpan] = []
        for s in sorted(strict, key=rank, reverse=True):
            if all(iou(s, k) <= self.subspan_iou_merge for k in out) \
                    and all(iou(s, k) <= self.subspan_iou_merge for k in frame_kept):
                out.append(s)
        return out[:max(1, self.subspan_max_keep)]

    def _locate_cluster(self, qidx, cluster_pool_t, q_best_t, q, tq, qf, bundle, low, high,
                        dense_query=None, *, span_mode: str = "union") -> EvidenceSpan:
        """簇['original_span'] = 簇证据范围[min,max] ∪ finloc run；finloc 作精化 + 质量信号。

        ``qidx``：簇内查询帧行号（帧级为主）；``cluster_pool_t``：簇证据时间（查询 argmax
        + 场景扩池帧）；``q_best_t``：查询帧 argmax 时间（时间戳诊断用,纯扩池簇为空）。
        纯扩池簇（查询帧 argmax 全部落在别处）退用查询均值 ``qf`` 代表。

        ``span_mode``：``union``（默认）= span = 簇证据范围 ∪ finloc run（帧级/场景单元,
        保住子镜头完整区域）；``run``（事件单元精修）= span = 仅 finloc 精确 run, 不 ∪
        事件窗全范围——事件身份命中后的事件窗可能跨数百秒, ∪ 全窗产生粗跨度假命中
        （2026-09-05 回归诚实边界）, 只输出帧级精修 run 才够精确; 无 run 则 span=None。
        """
        qidx = np.asarray(qidx, dtype=np.int64)
        q_best_t = np.asarray(q_best_t, dtype=np.float32)
        if qidx.size:
            qc = q[qidx]
            tq_c = tq[qidx]
        elif qf is not None:
            qc = qf[None, :]
            tq_c = np.asarray([], dtype=np.float32)
        else:
            qc = q[:0]
            tq_c = np.asarray([], dtype=np.float32)
        sel = (bundle.times >= low) & (bundle.times <= high)
        r_idx = np.where(sel)[0]
        if tq_c.size:
            et0 = round(float(tq_c.min()), 2)
            et1 = round(float(tq_c.max()), 2)
        else:
            et0, et1 = round(float(tq.min()), 2), round(float(tq.max()), 2)
        edf = [round(float(t), 2) for t in tq_c]
        if r_idx.size == 0 or qc.shape[0] == 0:
            return EvidenceSpan((et0, et1), edf, None, 0.0, None,
                                int(cluster_pool_t.size), query_frames=int(qidx.size))
        rfeats = bundle.features[r_idx[0]:r_idx[-1] + 1]
        rtimes = bundle.times[r_idx[0]:r_idx[-1] + 1]
        cand = Candidate(start=float(rtimes[0]), end=float(rtimes[-1]),
                         width=float(rtimes[-1] - rtimes[0]), peak_sim=0.0, mean_sim=0.0,
                         consistency=0.0, hit_count=0, n_reps=0, qcov=0.0, sim_std=0.0,
                         rank_score=0.0, best_cover=0.0, scene_div=0)
        loc = finloc_window(cand, qc, rfeats, rtimes, max_span_s=self.max_span_s,
                            stable_s=self.finloc_stable_s)
        # 子 span 用「簇最佳匹配范围 ∪ finloc run」保住子镜头完整区域（GT recall）；不收紧到 tight_span。
        # span_mode="run"（事件单元精修）: 只用 finloc 精确 run, 不 ∪ 事件窗全范围——
        # 事件身份命中后的窗可能跨数百秒, ∪ 全窗会产生粗跨度假命中（回归诚实边界）。
        c_min, c_max = float(cluster_pool_t.min()), float(cluster_pool_t.max())
        if loc.span is not None:
            if span_mode == "run":
                span = (round(float(loc.span[0]), 2), round(float(loc.span[1]), 2))
            else:
                span = (round(min(c_min, float(loc.span[0])), 2),
                        round(max(c_max, float(loc.span[1])), 2))
        else:
            span = None if span_mode == "run" else (round(c_min, 2), round(c_max, 2))
        bsim = round(float(loc.mean_sim), 3) if loc.mean_sim is not None else None
        both_low = (loc.best_cover < self.weak_cover and (bsim is None or bsim < self.weak_sim))
        moments = []
        if self.seq_align is not None and qc.shape[0] >= 2:
            moments = self._align_global_moments(qc, tq_c, c_min, c_max, bundle, dense_query)
        return EvidenceSpan(
            (et0, et1), edf, span, round(float(loc.best_cover), 3), bsim,
            int(cluster_pool_t.size), both_low, query_frames=int(qidx.size),
            finloc=loc,
            peak_sim=round(float(loc.peak_sim), 3) if loc.peak_sim is not None else None,
            span_stability=round(loc.span_stability, 4),
            timestamp_mean=float(q_best_t.mean()) if q_best_t.size
            else (float(cluster_pool_t.mean()) if cluster_pool_t.size else None),
            timestamp_std=float(q_best_t.std()) if q_best_t.size > 1 else 0.0,
            moments=moments)

    def _align_global_moments(self, qc, tq_c, c_min, c_max, bundle, dense_query):
        """全局对齐找 moment：候选窗 = evidence span ± seq_pad_s（钳 window_max_s），
        编辑用 dense_query（密帧）或 cluster 帧，align → 连续段 → moment 收窄 ±1s → 双门控。"""
        lo = max(0.0, c_min - self.seq_pad_s)
        hi = c_max + self.seq_pad_s
        if (hi - lo) > self.seq_window_max_s:
            cc = (lo + hi) / 2.0
            lo = cc - self.seq_window_max_s / 2.0
            hi = cc + self.seq_window_max_s / 2.0
        ssel = (bundle.times >= lo) & (bundle.times <= hi)
        s_idx = np.where(ssel)[0]
        if not s_idx.size:
            return []
        if dense_query is not None:
            dnq, dnt = dense_query
            et0, et1 = float(tq_c.min()), float(tq_c.max())
            eps = 0.5
            dsel = (dnt >= et0 - eps) & (dnt <= et1 + eps)
            qq, qt = dnq[dsel], dnt[dsel]
        else:
            qq, qt = qc, tq_c
        if len(qq) < 2:
            return []
        if len(qq) > self.seq_max_query_frames:
            idx = np.linspace(0, len(qq) - 1, self.seq_max_query_frames).astype(int)
            qq, qt = qq[idx], qt[idx]
        order = np.argsort(qt)
        raw = self.seq_align(
            qq[order], qt[order], bundle.features[s_idx[0]:s_idx[-1] + 1],
            bundle.times[s_idx[0]:s_idx[-1] + 1],
            moment_half_s=self.seq_moment_half_s).segments
        return self._filter_moments(raw, (c_min, c_max))

    def _filter_moments(self, moments, scene):
        """双门控：in-scope(与 evidence scene 相交) 用 seq_mean_sim_min(0.40) 收紧保现网；
        out-of-scope 用 seq_global_mean_sim_min(0.20) 放行 scene 偏差外正确 moment + 强制标 low。"""
        out = []
        for m in moments:
            in_scope = m.original_span[1] >= scene[0] and m.original_span[0] <= scene[1]
            if in_scope:
                if m.mean_sim >= self.seq_mean_sim_min:
                    out.append(m)
            else:
                if m.mean_sim >= self.seq_global_mean_sim_min:
                    out.append(MomentSpan(m.edited_interval, m.original_span, m.mean_sim,
                                          m.peak_sim, m.n_frames, "low"))
        return out
