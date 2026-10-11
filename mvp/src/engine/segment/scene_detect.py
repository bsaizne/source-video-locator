"""engine.segment.scene_detect — 原片侧**场景表边界检测**（A2：像素通道 + CLS 融合）。

为什么新增这一层（依据 2026-10-11 边界尺子实测，见
``mvp/docs/FINDINGS_SHOT_DETECTION_A1_20261011.md``）：

- 旧路径（``detect_shots`` 直接切场景）在 44 窗 / 125 条**画面确认**的边界尺子上
  召回只有 **0.232** —— 即 ``scenes.npy`` 把约 3/4 的真镜头切换漏掉，合成 30~50s 的假大镜头
  （下游「完整镜头」扩宽与边界吸附都吃这个表，是成片"重合"的根因）。
- 漏切的主因**不是模型看不见**：真边界邻域内 CLS 相邻帧距离中位 0.70~0.88（信号在），
  但 ① ``z_thresh`` 的局部 z-score 在「整段都在切」的快切材料上系统性把真切换否掉
  （现役参数下 79~94% 真边界邻域 z<1.5），② 1fps 网格上快切段**没有可分离的局部极大**
  （test2 有 44% 真边界连峰都不存在 ⇒ 任何阈值救不了）。
- 像素/颜色通道在同一把尺子上单独 P 0.69 / R 0.86；与 CLS 证据融合（NMS 0.5s）后
  **P 0.70 / R 0.92 / F1 0.796**（旧 0.349），且相邻边界间隔中位 1.8s、<0.5s 占 0%（不碎片化）。

设计约束（与既有纪律一致）：
- **不改 CLS embedding、不 bump 特征语义版本**：本层只替换「场景表怎么派生」，
  ``scenes.npy`` / ``scene_feats.npy`` 的 schema 与「连续覆盖全部帧」的不变式不变；
  派生版本位 ``scn1 -> scn2`` 走 ``FeatureStore.refresh_derived``（只重算派生表，不重抽特征）。
- 像素判据是**流式**的（``PixelStream.push`` 每次只留上一帧 + 直方图），内存 O(帧数) 个浮点，
  不缓存任何图像。
- 编辑侧查询单元切分仍用 ``detect_shots`` / ``detect_shots_two_level``，本模块**只服务原片侧**。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# 灰度权重（ITU-R BT.601 整数近似）与直方图桶数 —— 与调参期（work/shot_gt）逐字一致，
# 改了它们等于换判据，必须重新过一遍边界尺子。
_LUMA_R, _LUMA_G, _LUMA_B = 77, 151, 28
_HIST_BINS = 32
_EPS = 1e-8


@dataclass(frozen=True)
class SceneDetectConfig:
    """场景表检测参数。默认值 = 2026-10-11 在边界尺子上选定并经留出窗复验的那一档。"""

    pixel_enabled: bool = True
    pixel_fps: float = 10.0          # 像素通道采样密度（解码成本与 1fps 几乎相同，见 FINDINGS §5）
    pixel_width: int = 160           # 低分辨率即可：判据是全局直方图/均值差
    pixel_height: int = 90
    pixel_hist_weight: float = 0.5   # mix = w*直方图L1 + (1-w)*灰度均值差
    pixel_thr: float = 0.12          # 绝对门（主阈值；配 A-B-A 门后可低于无门时的 0.15）
    pixel_abs_floor: float = 0.08    # 相对判据的地板（防安静段里微小抖动成峰）
    pixel_rel_mult: float = 3.0      # 须 ≥ mult × 邻域中位数（自适应：明暗呼吸/甩镜不再算切换）
    pixel_rel_win: int = 8           # 邻域半宽（帧）
    cls_cut_abs: float = 0.30        # CLS 证据腿的距离门（尺子扫参值；不再用局部 z-score）
    cls_weight: float = 0.6          # 融合时 CLS 候选的强度系数（像素证据优先）
    min_gap_s: float = 0.5           # 融合后 NMS 间隔
    min_shot_s: float = 1.0          # 最短场景（秒）
    # --- 持续性门（两腿共用）-------------------------------------------------------
    # 「闪一下又回到同一画面」不是镜头切换：闪电/爆白/灯管/甩镜都会造瞬时尖峰。
    # 读图确证（2026-10-11）：2mkv 4853-4864 是**同一个暗场景**里的闪电，无门时那里被切了 7 刀。
    # 第一版只要求「后块 ≠ 前块」，在真数据上几乎无效（闪电彼此也不同）；
    # 有效的判据是**后块内部要落定**：新状态自己得稳，还在抖就说明没切完/只是闪。
    # 同尺实测：无门 P/R/F1 0.701/0.920/0.796 -> 本门 0.845/0.907/0.875（留出半窗）。
    block_gate: bool = True
    block_pre: int = 4               # 前块帧数（0.4s @10fps）
    block_post: int = 4              # 后块帧数
    block_skip: int = 2              # 后块跳过的前导帧数（给转场/运动模糊留余量）
    block_dist_thr: float = 0.10     # 前后块直方图距离下限（真的换了画面）
    block_dev_thr: float = 0.30      # 后块内任一帧到块均值的 L1 距离上限（新状态要稳）


def to_gray(frame_bgr: np.ndarray) -> np.ndarray:
    """BGR uint8 -> 灰度 uint8（整数 BT.601）。

    ⚠️ 必须先在 **int32** 上加权：uint8 直接乘会溢出，而 int16 也放不下
    ``255*151=38505``（>32767）——那样白帧会绕回负数被 clip 成 0，
    「黑帧 vs 白帧」的差变成 0，整条判据静默失效（2026-10-11 调参期就是这么翻车的，
    修好后必须重选阈值）。
    """
    f = np.asarray(frame_bgr, dtype=np.int32)
    return (((f[:, :, 2] * _LUMA_R + f[:, :, 1] * _LUMA_G + f[:, :, 0] * _LUMA_B)
             >> 8).clip(0, 255)).astype(np.uint8)


def gray_hist(gray: np.ndarray) -> np.ndarray:
    """32 桶归一化灰度直方图。"""
    h = np.bincount(np.asarray(gray).reshape(-1) >> 3, minlength=_HIST_BINS).astype(np.float64)
    return h / max(h.sum(), _EPS)


class PixelStream:
    """流式累加相邻帧像素差。``push(t, frame)`` 只保留上一帧的灰度与直方图。

    产出序列的索引 i 对应「进入第 i+1 帧的那次变化」：``times[i]`` 就是**新镜头首帧时间**
    （与 ``detect_pixel_boundaries`` 的返回值同一条时间轴，直接可当场景起点）。
    """

    def __init__(self, hist_weight: float = 0.5) -> None:
        self.w = float(hist_weight)
        self._prev_gray: np.ndarray | None = None
        self._prev_hist: np.ndarray | None = None
        self.times: list[float] = []
        self.scores: list[float] = []
        self.hist_l1: list[float] = []      # 两条分量各自留一份：调参/排障时要能分开看
        self.mean_abs: list[float] = []
        self.hist_rows: list[np.ndarray] = []   # 每帧直方图：A-B-A 持续性判据要用「块对块」比较

    def push(self, t: float, frame_bgr: np.ndarray) -> None:
        gray = to_gray(frame_bgr)
        hist = gray_hist(gray)
        if self._prev_hist is not None:
            hl = float(np.abs(hist - self._prev_hist).sum())
            mad = float(np.abs(gray.astype(np.int32)
                               - self._prev_gray.astype(np.int32)).mean()) / 255.0
            self.times.append(float(t))
            self.hist_l1.append(hl)
            self.mean_abs.append(mad)
            self.scores.append(self.w * hl + (1.0 - self.w) * mad)
        self.hist_rows.append(hist.astype(np.float32))
        self._prev_gray = gray
        self._prev_hist = hist

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        return (np.asarray(self.times, dtype=np.float64),
                np.asarray(self.scores, dtype=np.float64))

    def hist_matrix(self) -> np.ndarray:
        """[n,32] float32 每帧直方图（与 ``times`` 同起点：第 i 行 = 第 i 帧）。"""
        if not self.hist_rows:
            return np.zeros((0, _HIST_BINS), dtype=np.float32)
        return np.vstack(self.hist_rows)


def local_peaks(x: np.ndarray) -> np.ndarray:
    """内部（非首尾）局部极大布尔掩码；用 >= 以便平顶也能响应。"""
    n = len(x)
    c = np.zeros(n, dtype=bool)
    if n >= 3:
        c[1:-1] = (x[1:-1] >= x[:-2]) & (x[1:-1] >= x[2:])
    return c


def detect_pixel_boundaries(times: np.ndarray, score: np.ndarray, *,
                            thr: float, abs_floor: float, rel_mult: float,
                            rel_win: int) -> list[float]:
    """像素通道判据：局部极大 + 绝对门 + **相对邻域中位数**（自适应）。

    ``rel_mult`` 这一腿是精度的来源：明暗呼吸、甩镜、快速运动这类「瞬时尖」在安静材料里
    比值很高（该要），在本来就一直在抖的材料里比值≈1（不该要）—— 单一绝对阈值做不到。
    """
    times = np.asarray(times, dtype=np.float64)
    score = np.asarray(score, dtype=np.float64)
    n = score.size
    if n < 3:
        return []
    pk = local_peaks(score)
    out: list[float] = []
    for k in np.flatnonzero(pk & (score >= max(abs_floor, thr))):
        k = int(k)
        lo, hi = max(0, k - rel_win), min(n, k + rel_win + 1)
        med = float(np.median(score[lo:hi]))
        if score[k] >= max(abs_floor, rel_mult * med, thr):
            out.append(float(times[k]))
    return out


def nms_by_strength(items: list[tuple[float, float]], gap_s: float) -> list[tuple[float, float]]:
    """按强度非极大抑制：``items = [(时间, 强度)]`` -> 保留强者，弱者被抑制（按时间升序）。"""
    out: list[tuple[float, float]] = []
    for t, st in sorted(items, key=lambda x: -x[1]):
        if all(abs(t - u) >= gap_s for u, _ in out):
            out.append((t, st))
    return sorted(out)


_nms_by_strength = nms_by_strength   # 旧私有名保留别名：调参期探针还在引用


def _merge_short(bounds: list[int], n: int, min_gap: int,
                 strength: dict[int, float]) -> list[int]:
    """把过短场景并入相邻场景：删掉该场景两侧边界中**较弱**的一条。

    与 ``segment._merge_short`` 同思想（碎片化比留短段更伤下游吸附），但作用在
    「帧索引边界集」上而不是 ``ShotSegment`` 列表上——本层的产出就是边界集。
    """
    cuts = list(bounds)
    while cuts:
        edges = [0] + cuts + [n]
        lens = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
        short = next((i for i, v in enumerate(lens) if v < min_gap), None)
        if short is None:
            break
        opts = []
        if short > 0:
            opts.append(cuts[short - 1])
        if short < len(cuts):
            opts.append(cuts[short])
        if not opts:
            break
        cuts.remove(min(opts, key=lambda b: strength.get(b, 0.0)))
    return cuts


def block_stats(hist: np.ndarray, k: int, pre: int, post: int,
                skip: int) -> tuple[float, float]:
    """候选帧 k（新镜头首帧）的持续性读数：``(前后块直方图距离, 后块内部最大偏离)``。

    - 距离小 = 闪一下又回原画面（A-B-A）；
    - 后块内部偏离大 = 那一秒里画面还在剧烈跳（闪电连闪/甩镜），没落定成新镜头。
    """
    n = int(hist.shape[0])
    a0, a1 = max(0, k - pre), max(1, k)
    b0, b1 = min(max(n - 1, 1), k + skip), min(n, k + skip + post)
    if a1 <= a0 or b1 <= b0 + 1:
        return 0.0, 9.9
    before = hist[a0:a1].mean(axis=0)
    after = hist[b0:b1]
    cen = after.mean(axis=0)
    return (float(np.abs(before - cen).sum()),
            float(np.abs(after - cen).sum(axis=1).max()))


def block_gate_ok(hist: np.ndarray, k: int, cfg: SceneDetectConfig) -> bool:
    """持续性门（生产与尺子**共用这一个入口**，避免两处判据漂移）。"""
    if not cfg.block_gate or hist is None or hist.shape[0] < 3:
        return True
    dist, dev = block_stats(hist, k, cfg.block_pre, cfg.block_post, cfg.block_skip)
    return dist >= cfg.block_dist_thr and dev <= cfg.block_dev_thr


def _snap_index(times: np.ndarray, t: float) -> int:
    """把任意时刻**就近**吸附到 ``times`` 网格的帧索引（不是向上取整）。

    ⚠️ 这里不能用 ``searchsorted(..., side="left")``：那是「第一个不早于它的帧」= 永远往后
    取整，会把每条边界系统性推晚最多一个网格步长。边界尺子实测（2026-10-11，44 窗内区口径）：
    同样一批像素候选，落到 1fps 网格后**有符号位移中位 +0.215s、绝对中位 0.28s**，
    而在像素时间轴上打分的探针臂绝对中位只有 0.05s —— 差的 0.067 个 F1 全是这个取整偏置
    在 ±1.0s 容差下把 1.2~1.7s 的近失判成 FP 造成的。网格粒度（1s）省不掉，**无偏**省得掉。
    """
    i = int(np.searchsorted(times, t, side="left"))
    if i <= 0:
        return 0
    if i >= len(times):
        return len(times) - 1
    return i - 1 if (t - times[i - 1]) <= (times[i] - t) else i


def detect_scene_bounds(n_frames: int, times: np.ndarray, s_cls: np.ndarray | None,
                        pixel: tuple[np.ndarray, np.ndarray, np.ndarray] | None,
                        cfg: SceneDetectConfig, fps: float) -> list[int]:
    """CLS 证据 + 像素证据融合 -> **新场景首帧的索引列表**（升序，落在 ``[1, n_frames-1]``）。

    - CLS 腿：``s_cls``（= 相邻帧 CLS 余弦距离，长度 n-1）上的局部极大且 ``>= cls_cut_abs``；
      距离索引 k 对应「帧 k+1 是新场景首帧」。
    - 像素腿：``detect_pixel_boundaries`` 的时间戳，**就近**映射到 CLS 网格帧（见 ``_snap_index``）。
    - **持续性门**（两腿共用）：候选前后块要「真的换了画面且新状态已落定」，否则是瞬时闪动。
    - 融合：两腿候选都带强度，NMS 按 ``min_gap_s`` 保强；然后 ``min_shot_s`` 兜底防碎片。
    """
    times = np.asarray(times, dtype=np.float64)
    items: list[tuple[float, float]] = []
    pix_t = pix_s = pix_h = None
    if pixel is not None and cfg.pixel_enabled:
        pix_t, pix_s, pix_h = (np.asarray(pixel[0], dtype=np.float64),
                               np.asarray(pixel[1], dtype=np.float64),
                               np.asarray(pixel[2], dtype=np.float32))
    n_hist = int(pix_h.shape[0]) if pix_h is not None else 0

    def gate(t: float) -> bool:
        """把边界时间换算到 hist 行号后过持续性门；无 hist 时放行（CLS-only 降级）。"""
        if not cfg.block_gate or n_hist < 3:
            return True
        k = int(np.clip(np.searchsorted(pix_t, t, side="left") + 1, 1, n_hist - 1))
        return block_gate_ok(pix_h, k, cfg)

    if s_cls is not None and len(s_cls):
        arr = np.asarray(s_cls, dtype=np.float64)
        for k in np.flatnonzero(local_peaks(arr) & (arr >= cfg.cls_cut_abs)):
            k = int(k)
            if k + 1 < n_frames:
                t = float(times[k + 1])
                if gate(t):
                    items.append((t, cfg.cls_weight * float(arr[k])))
    if pix_t is not None and pix_s is not None and len(pix_t) >= 3:
        for t in detect_pixel_boundaries(pix_t, pix_s, thr=cfg.pixel_thr,
                                         abs_floor=cfg.pixel_abs_floor,
                                         rel_mult=cfg.pixel_rel_mult,
                                         rel_win=cfg.pixel_rel_win):
            j = _snap_index(times, t)
            if 1 <= j < n_frames and gate(t):
                items.append((float(times[j]), 1.0))
    if not items:
        return []
    # NMS 间隔不强制抬到 1/fps：两条真边界可以只差 0.75s（快切蒙太奇），
    # 它们在 1fps 网格上落到相邻两帧、都该保留；同帧重复由下面的索引去重解决。
    strength: dict[int, float] = {}
    for t, st in nms_by_strength(items, cfg.min_gap_s):
        j = _snap_index(times, t)
        if 1 <= j < n_frames:
            strength[j] = max(strength.get(j, 0.0), st)
    bounds = sorted(strength)
    return _merge_short(bounds, n_frames, max(1, int(round(cfg.min_shot_s * fps))), strength)


def build_scene_table(feats: np.ndarray, times: np.ndarray,
                      pixel: tuple[np.ndarray, np.ndarray, np.ndarray] | None,
                      cfg: SceneDetectConfig, fps: float
                      ) -> tuple[np.ndarray, np.ndarray]:
    """特征 + 像素序列 -> ``(scenes[S,2], scene_feats[S,384])``，语义与旧实现一致。

    ``pixel`` = ``(新镜头首帧时间[], 像素差分数[], 每帧直方图[n,32])``，可为 ``None``
    （像素预扫失败时降级为「只有 CLS 证据」）。
    连续覆盖全部帧（不变式由边界集构造保证），场景指纹 = 场景内帧均值再 L2。
    """
    feats = np.asarray(feats, dtype=np.float32)
    times = np.asarray(times, dtype=np.float64)
    n = int(feats.shape[0])
    if n == 0:
        return (np.zeros((0, 2), dtype=np.float32),
                np.zeros((0, feats.shape[1] if feats.ndim > 1 else 0), dtype=np.float32))
    from .segment import adjacent_distances          # 复用冻结距离语义，避免两份实现漂移
    s_cls = adjacent_distances(feats)
    bounds = detect_scene_bounds(n, times, s_cls, pixel, cfg, fps)
    edges = [0] + bounds + [n]
    edges = [e for i, e in enumerate(edges) if i == 0 or e > edges[i - 1]]
    scenes = np.zeros((len(edges) - 1, 2), dtype=np.float32)
    rows = []
    for k in range(len(edges) - 1):
        a, b = edges[k], edges[k + 1]
        scenes[k, 0] = float(times[a])
        scenes[k, 1] = float(times[b - 1]) + 1.0 / float(fps)
        rows.append(feats[a:b].mean(axis=0))
    fp = np.vstack(rows).astype(np.float32)
    fp = fp / np.maximum(np.linalg.norm(fp, axis=1, keepdims=True), _EPS)
    return scenes, fp
