"""engine.localization.finloc — Fine Localization（REUSE Phase 13A/14C，冻结基线 #7/#8）。

输入一个候选窗（``domain.Candidate``）+ Edited 查询特征 + Original 索引特征/时间轴；
输出该候选窗内的**精确 Original TimeSpan**（longest_run）以及定位质量信号。

冻结语义（逐字对齐 research ``fine_localization.narrow`` / ``query_density_14c.localize``）：
  1. 取候选窗 [candidate.start, candidate.end] 在 Original 时间轴上的帧区间 R。
     —— 用 ``orig_times`` 时间轴定位（``searchsorted``），不硬编码 fps。
  2. ``sim = cosine_similarity(edited_query, R)``            -> [nq, nr]
  3. ``cover = sim.max(axis=0)``                             -> per-original max-over-query coverage
  4. ``cs = convolve(cover, ones(3)/3, mode=same)``          -> 3 帧平滑
  5. ``mask = cs >= thresh``（FINLOC_THRESH=0.4，冻结）
  6. longest_run(mask)  ->  精确 span [tr0, tr1]

montage 处理：**只做检测与标记**（``multi_island``），不自动解 montage 边界。
检测 = 同一 mask 上数出所有 run 与 gap，≥2 个显著 run 且其间 gap 超过 ``MONTAGE_GAP_S``
即为多岛（Phase15/16B.1 的 s4 型 [1376,1382]+[1390,1396] 形态）。

研究护栏（MVP_ARCHITECTURE §8 / TODO 护栏）：禁 per-query argmax、禁 voting、禁
cut-aware segmentation、禁 temporal alignment、禁改 similarity/ranking。本层只做
"候选窗内 coverage + run 结构 + 精 span"。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain import Candidate
from engine.common import cosine_similarity

# --- 冻结 finloc 参数（研究基线，禁调） ---
FINLOC_THRESH = 0.4        # coverage "high sim" 阈值（research FINLOC_THRESH）
MIN_RUN_FRAMES = 2         # 一个"显著"run 至少 2 个原片帧（1 帧=退化点）
MONTAGE_GAP_S = 5.0        # 两个显著 run 间隔超过此值 -> 多岛（占位，待 H1 标定）
FINLOC_STABLE_S = 4.0      # span 稳定性归一化锚点（秒，占位，待标定）


@dataclass
class LocalizationResult:
    """一个候选窗的精定位结果（纯计算，无 IO）。

    ``span`` 是精确 Original 时间区间（longest_run）；``None`` 表示候选窗内没有
    超过阈值的连续高匹配段（此时不应输出伪精确边界）。
    """

    span: tuple[float, float] | None
    best_cover: float          # mask 覆盖的原片帧比例（=per-orig 覆盖质量，回填 Candidate.best_cover）
    run_len_s: float           # 最长 run 时长（秒）
    run_len_frames: int        # 最长 run 帧数
    num_runs: int              # 所有 run 数
    significant_runs: int      # >= MIN_RUN_FRAMES 的 run 数
    largest_gap_s: float       # 相邻 run 间最大 gap（秒）
    span_coverage: float       # span 宽度 / 候选窗宽度（0~1）
    coverage_quality: float    # 单峰集中度：最长 run 帧数 / 全部 run 帧数（1.0 单峰，~0.5 两岛）
    span_stability: float      # span 稳健性 0~1：run 时长归一 +（多岛/退化点）惩罚
    multi_island: bool         # >=2 显著 run 且其间 gap > MONTAGE_GAP_S（montage_flag 结构信号）
    window_width: float        # 候选窗宽度（秒）
    mean_sim: float | None     # 最长 run 内平滑 coverage 均值
    peak_sim: float | None     # 最长 run 内 raw cover 峰值
    n_query: int               # 参与的 edited 查询帧数

    @property
    def has_span(self) -> bool:
        return self.span is not None


def _runs(mask: np.ndarray) -> list[tuple[int, int]]:
    """所有连续 True run，返回 [(start, end_exclusive), ...]。"""
    if not mask.any():
        return []
    padded = np.concatenate(([0], mask.view(np.int8), [0]))
    starts = np.where(np.diff(padded) == 1)[0]
    ends = np.where(np.diff(padded) == -1)[0]
    return list(zip(starts.tolist(), ends.tolist()))


def longest_run(mask: np.ndarray) -> tuple[int, int, int]:
    """最长连续 run：返回 (len, start, end_exclusive)。无 run -> (0, -1, -1)。"""
    runs = _runs(mask)
    if not runs:
        return 0, -1, -1
    lens = [e - s for s, e in runs]
    i = int(np.argmax(lens))
    s, e = runs[i]
    return int(lens[i]), s, e


def _window_indices(orig_times: np.ndarray, w0: float, w1: float) -> tuple[int, int]:
    """把候选窗 [w0,w1]（秒）映射到 orig_times 的帧索引区间 [r_lo, r_hi]（含两端）。"""
    n = int(len(orig_times))
    if n == 0:
        return 0, -1
    r_lo = max(0, int(np.searchsorted(orig_times, w0, side="left")))
    r_hi = min(n - 1, int(np.searchsorted(orig_times, w1, side="right")) - 1)
    return r_lo, r_hi


def finloc_window(candidate: Candidate, ed_feats: np.ndarray,
                  orig_feats: np.ndarray, orig_times: np.ndarray,
                  *,
                  thresh: float = FINLOC_THRESH,
                  min_run_frames: int = MIN_RUN_FRAMES,
                  montage_gap_s: float = MONTAGE_GAP_S,
                  stable_s: float = FINLOC_STABLE_S) -> LocalizationResult:
    """在一个候选窗上做 per-orig max-over-query coverage + longest_run。

    ``ed_feats`` [nq,384]（Edited 查询特征，L2 归一化），``orig_feats`` [T,384]，
    ``orig_times`` [T]（与 orig_feats 行对齐的绝对时间秒）。``candidate`` 给出窗区间。
    返回 ``LocalizationResult``（含精确 span 与定位质量信号）。
    """
    w0, w1 = float(candidate.start), float(candidate.end)
    width = max(w1 - w0, 0.0)
    n_query = int(ed_feats.shape[0]) if ed_feats.ndim else 0

    r_lo, r_hi = _window_indices(orig_times, w0, w1)
    if r_hi < r_lo or n_query == 0:
        return LocalizationResult(
            span=None, best_cover=0.0, run_len_s=0.0, run_len_frames=0,
            num_runs=0, significant_runs=0, largest_gap_s=0.0, span_coverage=0.0,
            coverage_quality=0.0, span_stability=0.0, multi_island=False,
            window_width=round(width, 2), mean_sim=None, peak_sim=None, n_query=n_query)

    R = orig_feats[r_lo:r_hi + 1]
    sim = cosine_similarity(ed_feats, R)                 # [nq, nr]
    cover = sim.max(axis=0)                              # [nr]  per-orig max-over-query
    cs = np.convolve(cover, np.ones(3) / 3.0, mode="same")
    mask = cs >= thresh
    nr = int(mask.shape[0])
    best_cover = float(mask.sum()) / float(nr) if nr else 0.0

    runs = _runs(mask)
    num_runs = len(runs)
    run_times = [(float(orig_times[r_lo + s]), float(orig_times[r_lo + e - 1]))
                 for s, e in runs]
    gaps = [b[0] - a[1] for a, b in zip(run_times[:-1], run_times[1:])]
    largest_gap = float(max(gaps)) if gaps else 0.0

    sig_runs = [(s, e) for s, e in runs if (e - s) >= min_run_frames]
    significant = len(sig_runs)
    sig_times = [(float(orig_times[r_lo + s]), float(orig_times[r_lo + e - 1]))
                 for s, e in sig_runs]
    sig_gaps = [sig_times[i + 1][0] - sig_times[i][1] for i in range(len(sig_times) - 1)]
    multi = significant >= 2 and bool(sig_gaps and max(sig_gaps) >= montage_gap_s)

    run_len, run_s, run_e = longest_run(mask)
    total_run_frames = int(sum(e - s for s, e in runs))
    coverage_quality = float(run_len / total_run_frames) if total_run_frames else 0.0

    if run_len == 0:
        return LocalizationResult(
            span=None, best_cover=best_cover, run_len_s=0.0, run_len_frames=0,
            num_runs=num_runs, significant_runs=significant, largest_gap_s=round(largest_gap, 2),
            span_coverage=0.0, coverage_quality=coverage_quality, span_stability=0.0,
            multi_island=multi, window_width=round(width, 2),
            mean_sim=None, peak_sim=None, n_query=n_query)

    tr0 = float(orig_times[r_lo + run_s])
    tr1 = float(orig_times[r_lo + run_e - 1])
    span_coverage = (tr1 - tr0) / width if width > 0 else 0.0
    run_len_s = float(orig_times[r_lo + run_e - 1] - orig_times[r_lo + run_s])

    stability = min(run_len_s / stable_s, 1.0)
    if multi:
        stability *= 0.25
    elif run_len <= 1:
        stability *= 0.25
    span_stability = float(np.clip(stability, 0.0, 1.0))

    return LocalizationResult(
        span=(round(tr0, 2), round(tr1, 2)), best_cover=best_cover,
        run_len_s=round(run_len_s, 2), run_len_frames=int(run_len),
        num_runs=num_runs, significant_runs=significant,
        largest_gap_s=round(largest_gap, 2), span_coverage=round(span_coverage, 4),
        coverage_quality=round(coverage_quality, 4), span_stability=round(span_stability, 4),
        multi_island=multi, window_width=round(width, 2),
        mean_sim=round(float(cs[run_s:run_e].mean()), 4),
        peak_sim=round(float(cover[run_s:run_e].max()), 4),
        n_query=n_query)
