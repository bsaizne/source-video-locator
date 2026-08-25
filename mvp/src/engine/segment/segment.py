"""engine.segment — 无 GT 编辑侧 shot 切分（Stage 1 第 6 项）。

产品运行时没有 GT（benchmark 用 GT 窗口 ±0.5s/pad±4s 定义查询段），必须自己定义查询单元
（MVP_ARCHITECTURE §5）。本模块对 edited 特征序列做**轻量 shot 切分**：用同一 DINOv2 CLS 的
相邻帧余弦距离做编辑侧边界检测，输出一批 ``ShotSegment``（每段即一个独立定位的查询单元）。

研究护栏：本层是**产品胶水**，不改变任何冻结算法（相似度/检索/聚类/排序/定位/置信）；
不把 Phase19 原片侧 cut-aware 逻辑引入；不做参数 sweep。切分阈值是**产品化参数**（非冻结
finloc 阈值），标为 placeholder，待 Stage 1 用真实 edited 视频标定。

产品约束（用户指定）：
- 目标不是精确还原每个摄影机 shot，而是生成**适合独立定位的 Edited 查询单元**。
- 过长 segment 可接受；过短/碎片化 segment 更危险 → 整体**偏向下切分**（NMS + merge 保底）。

为什么不是"裸绝对阈值"：研究（Phase18/19）证明 0.5fps 下相邻帧距离 d=1-cos 几乎处处高
（0.6~0.94），绝对阈值 0.5/0.65 区分不了"真 cut"与"段内 content break"。因此这里用
**局部 z-score**（某点相对自身邻域均值的统计异常）作主判别，``cut_abs`` 仅作下限安全垫：
- 平滑 d（smooth 窗，默认 1=不平滑，保留单帧 cut 的锐利尖峰）；
- ``z = (s - 局部均值) / max(局部σ, SEG_SD_FLOOR)``；
- 边界 = 平滑 d 的**内部局部极大** 且 ``z >= z_thresh`` 且 ``s >= cut_abs``；
- NMS（间隔 >= min_gap）+ merge（过短段并入更弱边界一侧）防碎片化；
- 无边界/单帧/空 -> 整条回退为 1 个查询单元（等于"整段查询"现状行为）。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain import TimeSpan

# --- 产品化切分参数（placeholder，待真实 edited 视频标定；禁 sweep）---
SEG_CUT_ABS = 0.30    # 距离下限（安全垫，非判别器）：大得足以挡掉近零σ静态段的微尖峰
SEG_Z_THRESH = 2.0    # 局部 z-score 门限：s 须为自身邻域的统计异常才判边界
SEG_SMOOTH = 1        # d 平滑窗（偶数自动 +1 成奇数；默认 1=不平滑，保留单帧 cut 的锐利尖峰）
SEG_MIN_SHOT_S = 1.0  # 最短查询单元时长（秒）；过短段并入弱边界一侧
SEG_SD_FLOOR = 1e-4   # 局部σ下限（防近零σ时 z 爆炸产生微切）
SEG_EPS = 1e-8


@dataclass
class ShotSegment:
    """一个 edited 查询单元（一个 shot 的边界 + 其特征/时间切片）。

    携带 ``feats``/``times`` 切片（numpy 读视图，不 copy），可直接喂给
    ``produce_candidates`` / ``localize_segment``（第 7 项 app service 逐段调用）。
    属 engine 层（可含 numpy），与 ``Hits``/``LocalizationResult`` 同级；domain 禁 numpy。
    """

    span: TimeSpan     # [首帧时间, 末帧时间]（绝对秒）
    feats: np.ndarray  # [nq,384] L2 归一化
    times: np.ndarray  # [nq] float，升序绝对时间，与 feats 行对齐

    @property
    def nq(self) -> int:
        return int(self.feats.shape[0])


def adjacent_distances(ed_feats: np.ndarray) -> np.ndarray:
    """相邻帧余弦距离 ``d = 1 - cos(f[i], f[i+1])``，长度 n-1。

    复用冻结语义（``cosine_similarity`` 会再 L2 归一化，double-normalize 无害），
    O(N) 点积实现，数值上与冻结路径一致。
    """
    q = ed_feats[:-1]
    r = ed_feats[1:]
    qn = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), SEG_EPS)
    rn = r / np.maximum(np.linalg.norm(r, axis=1, keepdims=True), SEG_EPS)
    return 1.0 - np.sum(qn * rn, axis=1)


def detect_shots(ed_feats: np.ndarray, ed_times: np.ndarray, *,
                 cut_abs: float = SEG_CUT_ABS,
                 z_thresh: float = SEG_Z_THRESH,
                 smooth: int = SEG_SMOOTH,
                 min_shot_s: float = SEG_MIN_SHOT_S,
                 fps: float | None = None,
                 context_window: int | None = None) -> list[ShotSegment]:
    """``<edited 特征, edited 时间轴>`` -> ``list[ShotSegment]``（升序，覆盖整段）。

    - ``cut_abs``：距离下限（安全垫，非判别器）。
    - ``z_thresh``：局部 z-score 门限（主判别：s 须为自身邻域的统计异常）。
    - ``smooth``：d 平滑窗（默认 1=不平滑，保留单帧 cut 锐利尖峰）。
    - ``min_shot_s``：最短段时长；过短段并入更弱边界一侧（防碎片化）。
    - ``fps``：缺省时从 ``ed_times`` 中值自举（``1/median(diff)``）。
    - ``context_window``：局部均值/σ 窗口，缺省由 ``smooth`` 派生。
    无边界/单帧/空 -> 回退为 1 个查询单元（整段查询）。
    """
    ed_feats = np.asarray(ed_feats, dtype=np.float32)
    ed_times = np.asarray(ed_times, dtype=np.float32)
    n = int(ed_feats.shape[0])
    if n == 0:
        return []
    if n == 1:
        return [_make_shot(0, 1, ed_times, ed_feats)]

    if fps is None:
        dts = np.diff(ed_times)
        med = float(np.median(dts)) if dts.size else 0.0
        fps = float(1.0 / med) if med > 0 else 1.0

    smooth = max(int(smooth) | 1, 1)          # 强制奇数
    win = context_window or _context_window(smooth)

    d = adjacent_distances(ed_feats)          # [n-1]
    s = _moving_average(d, smooth)            # [n-1]
    mu, sd = _local_stats(s, win)             # [n-1]
    z = (s - mu) / np.maximum(sd, SEG_SD_FLOOR)
    peak = _local_peaks(s)                    # [n-1]

    cands = np.flatnonzero(peak & (s >= cut_abs) & (z >= z_thresh)).tolist()
    min_gap = max(1, int(round(min_shot_s * fps)))   # 帧数；NMS 与 merge 共用
    kept = _nms(cands, s, min_gap)
    return _merge_short(kept, s, min_gap, ed_times, ed_feats)


# --------------------------------------------------------------------------- #
# 帮助函数
# --------------------------------------------------------------------------- #
def _context_window(smooth: int) -> int:
    """局部均值/σ 窗口（奇数）：从平滑窗派生，不额外增加 config 参数。"""
    smooth = max(int(smooth), 1)
    return max(2 * smooth + 1, 7)


def _moving_average(x: np.ndarray, smooth: int) -> np.ndarray:
    """长度保持的均值平滑（edge-pad）。``smooth<=1`` 时原样返回。"""
    x = np.asarray(x, dtype=np.float64)
    if smooth <= 1:
        return x
    k = int(smooth) | 1
    half = k // 2
    kernel = np.ones(k) / k
    xp = np.pad(x, (half, half), mode="edge")
    return np.convolve(xp, kernel, mode="valid")


def _local_stats(s: np.ndarray, window: int) -> tuple[np.ndarray, np.ndarray]:
    """逐点局部均值/标准差（edge-pad，含中心点），长度与 s 相同。"""
    half = window // 2
    ker = np.ones(window) / window
    mu = np.convolve(np.pad(s, (half, half), mode="edge"), ker, mode="valid")
    mu2 = np.convolve(np.pad(s * s, (half, half), mode="edge"), ker, mode="valid")
    sd = np.sqrt(np.maximum(mu2 - mu * mu, 0.0))
    return mu, sd


def _local_peaks(x: np.ndarray) -> np.ndarray:
    """内部（非边界）局部极大布尔掩码。用 >= 以便平顶也能响应，仅取非首尾位置。"""
    n = len(x)
    c = np.zeros(n, dtype=bool)
    if n >= 3:
        c[1:-1] = (x[1:-1] >= x[:-2]) & (x[1:-1] >= x[2:])
    return c


def _nms(cands, strength, min_gap):
    """按强度保留、间隔 >= min_gap 的非极大抑制。返回升序保留索引。"""
    if not cands:
        return []
    cands = np.asarray(cands, dtype=np.int64)
    order = np.argsort(-strength[cands].astype(np.float64), kind="stable")
    kept: list[int] = []
    for pos in cands[order]:
        pos = int(pos)
        if all(abs(pos - k) >= min_gap for k in kept):
            kept.append(pos)
    kept.sort()
    return kept


def _make_shot(a: int, b: int, ed_times: np.ndarray, ed_feats: np.ndarray) -> ShotSegment:
    times = np.asarray(ed_times[a:b], dtype=np.float32)
    feats = ed_feats[a:b]
    if times.size:
        span = TimeSpan(float(times[0]), float(times[-1]))
    else:
        span = TimeSpan(0.0, 0.0)
    return ShotSegment(span=span, feats=feats, times=times)


def _merge_short(dcuts, s, min_gap, ed_times, ed_feats):
    """把过短段并入更弱边界一侧，直到所有段 >= min_gap 帧。（dcuts 为 d 空间 cut 索引）"""
    n = int(ed_feats.shape[0])
    dcuts = list(dcuts)

    def bounds():
        return [0] + [int(c) + 1 for c in dcuts] + [n]

    b = bounds()
    while len(b) - 1 > 1:
        lens = [b[i + 1] - b[i] for i in range(len(b) - 1)]
        short = [i for i, l in enumerate(lens) if l < min_gap]
        if not short:
            break
        i = short[0]
        choices = []
        if i > 0:                                # 左边界 dcuts[i-1]
            choices.append((i - 1, float(s[dcuts[i - 1]])))
        if i < len(dcuts):                       # 右边界 dcuts[i]
            choices.append((i, float(s[dcuts[i]])))
        if not choices:
            break
        drop_j = min(choices, key=lambda t: (t[1], t[0]))[0]   # 更弱（s 更小）；平手取左
        del dcuts[drop_j]
        b = bounds()

    return [_make_shot(b[i], b[i + 1], ed_times, ed_feats) for i in range(len(b) - 1)]
