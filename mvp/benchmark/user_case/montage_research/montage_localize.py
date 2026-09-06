"""montage_localize — 蒙太奇多段定位（研究模块，不接 runtime / domain 契约）。

把「一个可能含多个子镜头的 edited 查询单元」定位成「多个子镜头原片区」：
  1. 逐查询帧取全索引最佳匹配原片时间（query-axis）。
  2. 按时间簇（cluster_gap_s）切分，滤出显著簇（>=min_frames 帧 且 簇均值 best_sim>=min_sim）。
  3. 门控：>=2 显著簇 = montage -> 每簇单独定位（子 span = 簇最佳匹配范围 ∪ finloc run 凸包）；
     否则单显著簇 = clean -> 单 span。
  4. 弱簇过滤：丢弃「cover<weak_cover 且 best_sim<weak_sim」的双低子 span（单低保留=真实部分子镜头）。

核心 ``localize()``：无 IO、确定性、只依赖冻结的 ``cosine_similarity`` / ``finloc_window`` /
``domain.Candidate`` / ``IndexBundle``（不改它们）。研究护栏：不进 mvp/src / 不改相似度·检索·
排序·定位·置信语义；多段输出为研究原型，生产多 span 契约待后续。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from domain import Candidate
from engine.common import cosine_similarity
from engine.feature_store import IndexBundle
from engine.localization.finloc import finloc_window


@dataclass
class MontageSpan:
    """一个子镜头定位结果。"""

    edited_interval: tuple[float, float]      # 该子镜头在编辑片的时间区间（簇帧 min/max）
    edited_frames: list[float]                # 簇内查询帧的编辑时间（集合）
    original_span: tuple[float, float] | None  # 子镜头对应原片区（簇范围 ∪ finloc run）
    cover: float                              # finloc best_cover（质量信号）
    best_sim: float | None                    # finloc run 内平滑覆盖率均值（质量信号）
    cluster_frames: int                       # 簇内查询帧数
    dropped_weak: bool = False                # 是否被弱簇过滤丢弃

    def to_dict(self) -> dict:
        return {
            "edited_interval": [round(self.edited_interval[0], 2), round(self.edited_interval[1], 2)],
            "edited_frames": [round(t, 2) for t in self.edited_frames],
            "original_span": list(self.original_span) if self.original_span else None,
            "cover": round(self.cover, 3),
            "best_sim": round(self.best_sim, 3) if self.best_sim is not None else None,
            "cluster_frames": self.cluster_frames,
            "dropped_weak": self.dropped_weak,
        }


@dataclass
class MontageLocalizationResult:
    """一个 edited 查询单元的蒙太奇多段定位结果。"""

    mode: str                     # "montage" | "clean" | "empty"
    spans: list[MontageSpan] = field(default_factory=list)
    n_clusters: int = 0
    n_strong_clusters: int = 0
    n_dropped_weak: int = 0

    def to_dict(self) -> dict:
        return {"mode": self.mode, "n_clusters": self.n_clusters,
                "n_strong_clusters": self.n_strong_clusters,
                "n_dropped_weak": self.n_dropped_weak,
                "spans": [s.to_dict() for s in self.spans]}


def cluster_by_gap(times: np.ndarray, gap: float) -> list[tuple[float, float, int]]:
    """把一维时间数组按相邻间隔>gap 切成簇。返回 [(min,max,count), ...]（按时间排序）。"""
    if len(times) == 0:
        return []
    order = np.argsort(times)
    st = times[order]
    breaks = np.where(np.diff(st) > gap)[0]
    clusters, start = [], 0
    for b in breaks:
        seg = st[start:b + 1]
        clusters.append((float(seg.min()), float(seg.max()), int(seg.size)))
        start = b + 1
    seg = st[start:]
    clusters.append((float(seg.min()), float(seg.max()), int(seg.size)))
    return clusters


class MontageLocalizer:
    """蒙太奇多段定位（query-axis clustering + 门控 + 每簇 merged span + 弱簇过滤）。"""

    def __init__(self, *, cluster_gap_s: float = 30.0, min_frames: int = 3,
                 min_sim: float = 0.45, pad_s: float = 15.0,
                 weak_cover: float = 0.35, weak_sim: float = 0.55):
        self.cluster_gap_s = cluster_gap_s
        self.min_frames = min_frames
        self.min_sim = min_sim
        self.pad_s = pad_s
        self.weak_cover = weak_cover
        self.weak_sim = weak_sim

    # ------------------------------------------------------------------ #
    def localize(self, ed_feats: np.ndarray, ed_times: np.ndarray,
                 bundle: IndexBundle) -> MontageLocalizationResult:
        """对单个 edited 查询单元做蒙太奇多段定位。无 IO、确定性。"""
        q = np.asarray(ed_feats, dtype=np.float32)
        tq = np.asarray(ed_times, dtype=np.float32)
        if q.shape[0] == 0 or bundle.features.shape[0] == 0:
            return MontageLocalizationResult(mode="empty")

        sim = cosine_similarity(q, bundle.features)
        best = np.argmax(sim, axis=1)
        best_t = bundle.times[best]
        best_s = sim[np.arange(q.shape[0]), best]

        clusters = cluster_by_gap(best_t, self.cluster_gap_s)
        sig = []
        for (c0, c1, cnt) in clusters:
            cidx = np.where((best_t >= c0) & (best_t <= c1))[0]
            if cnt >= self.min_frames and float(best_s[cidx].mean()) >= self.min_sim:
                sig.append((c0, c1, cnt, cidx))

        if len(sig) >= 2:
            mode = "montage"
        elif len(sig) == 1:
            mode = "clean"
        else:
            return MontageLocalizationResult(mode="empty", n_clusters=len(clusters))

        # 每簇定位（montage 全簇；clean 只主簇）
        if mode == "clean":
            sig = [max(sig, key=lambda s: s[2])]
        built, dropped = [], 0
        for (c0, c1, cnt, cidx) in sig:
            low, high = max(0.0, c0 - self.pad_s), c1 + self.pad_s
            span, cover, bsim, edsub, edframes = self._locate_cluster(
                cidx, best_t[cidx], q, tq, bundle, low, high)
            both_low = (cover < self.weak_cover
                        and (bsim is None or bsim < self.weak_sim))   # None=无置信 span 视为低
            ms = MontageSpan(edited_interval=edsub, edited_frames=edframes,
                             original_span=span, cover=cover, best_sim=bsim,
                             cluster_frames=cnt, dropped_weak=both_low)
            if both_low:
                dropped += 1
            built.append(ms)
        spans = [s for s in built if not s.dropped_weak]      # 弱簇丢弃
        # clean 段若无 span 残留，退回 empty（不输出空）
        return MontageLocalizationResult(
            mode=mode if spans else "empty", spans=spans,
            n_clusters=len(clusters), n_strong_clusters=len(sig),
            n_dropped_weak=dropped)

    # ------------------------------------------------------------------ #
    def _locate_cluster(self, cidx, cluster_best_t, q, tq, bundle, low, high):
        """簇['span'] = 簇最佳匹配范围[min,max] ∪ finloc run; finloc 作质量信号。"""
        qc = q[cidx]
        sel = (bundle.times >= low) & (bundle.times <= high)
        r_idx = np.where(sel)[0]
        if r_idx.size == 0:
            return (None, 0.0, None,
                    (round(float(tq[cidx].min()), 2), round(float(tq[cidx].max()), 2)),
                    [round(float(t), 2) for t in tq[cidx]])
        rfeats = bundle.features[r_idx[0]:r_idx[-1] + 1]
        rtimes = bundle.times[r_idx[0]:r_idx[-1] + 1]
        cand = Candidate(start=float(rtimes[0]), end=float(rtimes[-1]),
                         width=float(rtimes[-1] - rtimes[0]), peak_sim=0.0, mean_sim=0.0,
                         consistency=0.0, hit_count=0, n_reps=0, qcov=0.0, sim_std=0.0,
                         rank_score=0.0, best_cover=0.0, scene_div=0)
        loc = finloc_window(cand, qc, rfeats, rtimes)
        c_min, c_max = float(cluster_best_t.min()), float(cluster_best_t.max())
        if loc.span is not None:
            span = (round(min(c_min, float(loc.span[0])), 2),
                    round(max(c_max, float(loc.span[1])), 2))
        else:
            span = (round(c_min, 2), round(c_max, 2))
        ed_times = sorted(float(t) for t in tq[cidx])
        return (span, round(float(loc.best_cover), 3),
                round(float(loc.mean_sim), 3) if loc.mean_sim is not None else None,
                (round(ed_times[0], 2), round(ed_times[-1], 2)),
                [round(t, 2) for t in ed_times])
