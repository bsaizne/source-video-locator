# -*- coding: utf-8 -*-
"""偏移投票起点先验（2026-09-27 续10m/续11, 竞品 coarse_retrieval 语义重建, 立项=用户拍板）。

对每个已定位段, 用段内采样帧逐帧独立检索全片源索引（跨查询全局共识, 与 P0 密集复核的
局部窗复核本质不同——P0 只在 span ±margin 窗内重找, 本模块提供「整部原片哪里最可信」的全局先验）:
  - 每个采样帧对源索引全库做余弦检索, 取 top-1 源帧;
  - 命中投影回段起点（proj = t*_i - (q_t_i - q_t_0)）后按 0.05s 分桶加权投票;
  - 共识簇(共识桶 ±half_bucket)内加权质心 = 种子起点; support_ratio = 簇内票数占比。
采纳门（生产安全, 比沙盒形态多一道位移上限）:
  ① support_ratio >= min_support（竞品 coarse 可靠性形态; 沙盒同值 0.2）;
  ② |seed - span_start| <= max_shift（防多实例场景的种子偏置; 沙盒 2mkv 回退 1 例即此型）。

沙盒四片实测（FINDINGS_FAST_GLOBAL_REPRO.md）: 截等长严格 89 -> 100/139（test1 +10 零退化）。
纯函数无 IO; 源索引特征由调用方注入（locator_service 用 IndexBundle.features/times, 零解码开销）。
"""
from __future__ import annotations

import numpy as np

__all__ = ["offset_vote_seed", "global_offset_anchor", "frame_quality_stats"]


def frame_quality_stats(frame) -> tuple[float, float, float]:
    """单帧质量三元组 (亮度, 对比, 清晰度) —— 沙盒复现链 F1 形态（推断级, 竞品形状未确证）。

    灰度 160x90: 亮度 = mean/255; 对比 = std/128; 清晰度 = min(Laplacian 方差/2000, 1.5)。
    接受 BGR 或 RGB ndarray（灰度统计与通道序无关）。
    """
    import cv2
    g = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY).astype(np.float32)
    bright = float(g.mean()) / 255.0
    contrast = float(g.std()) / 128.0
    sharp = min(float(cv2.Laplacian(g, cv2.CV_32F).var()) / 2000.0, 1.5)
    return bright, contrast, sharp


def offset_vote_seed(q_feats: np.ndarray, q_times: np.ndarray,
                     lib_feats: np.ndarray, lib_times: np.ndarray, *,
                     bucket_s: float = 0.05,
                     cluster_half_buckets: int = 1,
                     min_support: float = 0.2,
                     max_shift_s: float = 4.0,
                     span_start: float | None = None,
                     source_duration_s: float | None = None,
                     ) -> tuple[float | None, dict]:
    """逐样本偏移投票, 返回 (seed_start | None, info)。

    q_feats/lib_feats 须为 L2 归一化 CLS [n,384]; q_times 为编辑侧秒, lib_times 为源侧秒。
    返回 None 表示不采纳（info 含 support/seed/门控诊断）。
    """
    info: dict = {"applied": False}
    n_q = q_feats.shape[0]
    if n_q < 2 or lib_feats.shape[0] < 2:
        info["reason"] = "insufficient_frames"
        return None, info
    q = q_feats.astype(np.float32)
    L = lib_feats.astype(np.float32)
    sims = q @ L.T                                    # [n, N] 余弦
    top_j = np.argmax(sims, axis=1)
    top_s = sims[np.arange(n_q), top_j].astype(np.float64)
    q_t = np.asarray(q_times, dtype=np.float64)
    proj = lib_times[top_j].astype(np.float64) - (q_t - q_t[0])   # 投影回段起点
    bucket = np.round(proj / bucket_s).astype(np.int64)
    ub, inv = np.unique(bucket, return_inverse=True)
    bw = np.zeros(len(ub), np.float64)
    np.add.at(bw, inv, top_s)
    c_b = int(ub[int(np.argmax(bw))])
    cluster = np.abs(bucket - c_b) <= cluster_half_buckets
    if not cluster.any():
        info["reason"] = "no_cluster"
        return None, info
    cw = top_s[cluster]
    seed = float((proj[cluster] * cw).sum() / cw.sum())
    support = float(cluster.sum() / n_q)
    info.update({"seed": round(seed, 3), "support": round(support, 3),
                 "votes": int(n_q), "cluster_votes": int(cluster.sum()),
                 "dispersion_s": round(float(np.sqrt(float(((proj[cluster] - seed) ** 2 * cw).sum() / cw.sum()))), 3)})
    if support < min_support:
        info["reason"] = "support_below_threshold"
        return None, info
    if span_start is not None:
        move = abs(seed - float(span_start))
        info["move_s"] = round(move, 3)
        if move > max_shift_s:
            info["reason"] = "move_exceeds_max_shift"
            return None, info
    if source_duration_s is not None and not (0.0 <= seed <= float(source_duration_s)):
        info["reason"] = "seed_out_of_range"
        return None, info
    info["applied"] = True
    if span_start is not None:
        info["before_start"] = round(float(span_start), 3)
    return round(seed, 3), info


def _offset_votes(q_feats: np.ndarray, q_times: np.ndarray,
                  lib_feats: np.ndarray, lib_times: np.ndarray,
                  bucket_s: float, *,
                  vote_top_k: int = 1,
                  min_samples: int = 2,
                  quality_w: np.ndarray | None = None) -> "tuple[np.ndarray, np.ndarray] | None":
    """逐样本 top-k 检索 + 投影回段起点。返回 (proj, vote_w); None=帧数不足。

    vote_top_k=1 为 M1 生产形态(逐样本仅 top-1 一票); >1 时每样本贡献 top-k 票
    (权重=相似度), M2 消融腿 a(竞品 coarse_retrieval 原始形态, k 值未确证)。
    quality_w = 每样本质量权(腿 c, None=均匀); 投票权 = 相似度 × 质量权(沙盒 F2 同款)。
    """
    n_q = q_feats.shape[0]
    if n_q < min_samples or lib_feats.shape[0] < 2:
        return None
    q = q_feats.astype(np.float32)
    L = lib_feats.astype(np.float32)
    sims = q @ L.T
    q_t = np.asarray(q_times, dtype=np.float64)
    k = int(vote_top_k)
    if k <= 1:
        top_j = np.argmax(sims, axis=1)
        vote_w = sims[np.arange(n_q), top_j].astype(np.float64)
        proj = lib_times[top_j].astype(np.float64) - (q_t - q_t[0])
    else:
        k = min(k, L.shape[0])
        part = np.argpartition(-sims, k - 1, axis=1)[:, :k]
        order = np.take_along_axis(sims, part, axis=1).argsort(axis=1)[:, ::-1]
        top_j = np.take_along_axis(part, order, axis=1).ravel()
        vote_w = sims[np.repeat(np.arange(n_q), k), top_j].astype(np.float64)
        proj = lib_times[top_j].astype(np.float64) - (np.repeat(q_t, k) - q_t[0])
    if quality_w is not None:
        qw = np.asarray(quality_w, dtype=np.float64)
        vote_w = vote_w * (np.repeat(qw, k) if k > 1 else qw)
    return proj, vote_w


def global_offset_anchor(q_feats: np.ndarray, q_times: np.ndarray,
                         lib_feats: np.ndarray, lib_times: np.ndarray, *,
                         bucket_s: float = 0.05,
                         cluster_half_buckets: int = 1,
                         min_support: float = 0.1,
                         min_cluster_votes: int = 1,
                         wide_win_s: float = 1.5,
                         min_wide_support: float = 0.5,
                         vote_top_k: int = 1,
                         wide_std_max_s: float = 0.0,
                         min_valid_samples: int = 2,
                         quality_w: np.ndarray | None = None,
                         span_start: float | None = None,
                         source_duration_s: float | None = None,
                         ) -> tuple[float | None, dict]:
    """快速全局锚定（PROJECT_FAST_GLOBAL_ANCHOR, 2026-09-28 立项"立"）。

    与 ``offset_vote_seed`` 同一投票内核（簇质心种子 + support 门），差在**无位移帽**——
    主病灶"同场景内选错时刻"是 18~21s 级偏移, 4s 帽结构上挡死它。无帽的安全门 =
    **宽窗共识支持度**：全体票落在种子 ±wide_win_s 内的比例 >= min_wide_support
    （多实例/蒙太奇场景的票散在几十秒尺度 → 宽窗支持度低被拒；真切合同因 1fps 库网格 +
    分数偏移天然聚在种子 ±0.5s 内。窗/阈 = 工程先验, **禁 GT 反标**）。
    注：±0.05s 簇的簇内 std 数学上 ≤0.05s，不能充当无帽安全门——dispersion_s 仅作诊断记录。

    M2 消融腿（PROJECT_FAST_GLOBAL_ANCHOR §6/§7, 2026-09-28; 默认值=M1 生产形态, 行为零变化）:
      a) ``vote_top_k``: 逐样本 top-k 汇总投票(竞品 coarse 原始形态, k 未确证; 1=M1 top-1)。
         support/wide_support 分母随之变为总票数(n_q*k)。
      b) ``wide_std_max_s``: 宽窗内票集 std ≤ 该值(竞品 dispersion≤0.35s 门的宽窗重建; 0=关)。
      d) ``min_valid_samples``: 参与投票样本数下限(竞品 min_valid_samples 2/3; 2=M1 现状)。
      c) ``quality_w``: 每样本质量权(腿 c; None=均匀)。投票权 = 相似度 × 质量权(沙盒 F2 同款);
         support/wide_support 仍按**票数**计(计数语义不变), 权重只影响桶加权/质心/簇内 std。
    """
    info: dict = {"applied": False}
    votes = _offset_votes(q_feats, q_times, lib_feats, lib_times, bucket_s,
                          vote_top_k=vote_top_k, min_samples=min_valid_samples,
                          quality_w=quality_w)
    if votes is None:
        info["reason"] = "insufficient_frames"
        return None, info
    proj, top_s = votes
    n_q = proj.shape[0]
    bucket = np.round(proj / bucket_s).astype(np.int64)
    ub, inv = np.unique(bucket, return_inverse=True)
    bw = np.zeros(len(ub), np.float64)
    np.add.at(bw, inv, top_s)
    c_b = int(ub[int(np.argmax(bw))])
    cluster = np.abs(bucket - c_b) <= cluster_half_buckets
    if not cluster.any():
        info["reason"] = "no_cluster"
        return None, info
    cw = top_s[cluster]
    seed = float((proj[cluster] * cw).sum() / cw.sum())
    support = float(cluster.sum() / n_q)
    wide = float(np.mean(np.abs(proj - seed) <= wide_win_s))
    info.update({"seed": round(seed, 3), "support": round(support, 3),
                 "votes": int(n_q), "cluster_votes": int(cluster.sum()),
                 "wide_support": round(wide, 3),
                 "dispersion_s": round(float(np.sqrt(float(
                     ((proj[cluster] - seed) ** 2 * cw).sum() / cw.sum()))), 3)})
    if support < min_support:
        info["reason"] = "support_below_threshold"
        return None, info
    if int(cluster.sum()) < int(min_cluster_votes):
        # 票数下界门。注: M1 双臂实测(2026-09-28)证伪"窄簇票数>=2"作为假共识判别——
        # 真匹配在 1s 库网格量化下 proj 天然是单票窄桶(宽窗才聚拢), 该门会饿死整个机制。
        # 生产值由 config.fast_global_min_cluster_votes 持有(现=1, 即门关闭);
        # 参数保留仅作诊断/消融用途, row4 型邻镜滑移需另找判别(见 M1 裁决已知缺陷)。
        info["reason"] = "cluster_votes_below_min"
        return None, info
    if wide < min_wide_support:
        info["reason"] = "wide_support_below_threshold"
        return None, info
    if wide_std_max_s and wide_std_max_s > 0.0:
        # M2 消融腿 b: 宽窗内票集 std(竞品 dispersion≤0.35s 门的宽窗重建)。
        in_win = np.abs(proj - seed) <= wide_win_s
        if int(in_win.sum()) < 2:
            info["reason"] = "wide_std_insufficient_votes"
            return None, info
        w_std = float(np.std(proj[in_win]))
        info["wide_std_s"] = round(w_std, 3)
        if w_std > float(wide_std_max_s):
            info["reason"] = "wide_std_above_threshold"
            return None, info
    if span_start is not None:
        info["move_s"] = round(abs(seed - float(span_start)), 3)
    if source_duration_s is not None and not (0.0 <= seed <= float(source_duration_s)):
        info["reason"] = "seed_out_of_range"
        return None, info
    info["applied"] = True
    if span_start is not None:
        info["before_start"] = round(float(span_start), 3)
    return round(seed, 3), info
