"""engine.segment.flash_guard — 白闪/亮度突变守卫（纯 numpy，零依赖）。

来源: C 项验证（2026-09-05）从研究脚本 mvp/scripts/flash_guard.py 提取入库，
判据校准见 FINDINGS_C_ITEM_8FPS.md 七章。供 app 层两级切分（twopass+flash）复用：
  - is_flash_frame: 灰度均值 + 亮像素占比双判据（真实白闪 mean 219-251, >=200 占比 ~0.99）;
  - brightness_spike_regions: 相邻帧 mean 亮度剧变且峰值过曝级 -> 白闪型转场;
  - drop_flash_cuts / drop_brightness_spike_cuts: 切点落在白闪/尖峰邻域 -> 删除(合并回退);
  - dynamic_min_shot: 白闪邻域段动态抬升最短镜头阈值(1.0-1.2s, 不全局抬升);
  - merge_flash_segments: 段内白闪占比高 -> 合并相邻镜头(业务兜底)。

参数默认值 = 研究校准值；app 层从 PipelineConfig.flash_* 传入（JSON 可覆盖）。
"""
from __future__ import annotations

import numpy as np

# --- 判据默认值（研究校准，见 FINDINGS_C_ITEM_8FPS 七章）---
FLASH_MEAN_TH = 200.0      # 灰度均值门槛（白闪核心帧 mean 219-251; 过渡帧 155-195 不判）
FLASH_FRAC_TH = 0.5        # 亮像素(>=200)占比门槛（白闪 >=0.65; 正常 <=0.4）
FLASH_DYN_MIN_SHOT_S = 1.0 # 白闪邻域动态最短镜头阈值（用户建议 1.0-1.2s）
FLASH_SEG_MERGE_FRAC = 0.5 # 段内白闪占比 >= 此值 -> 业务兜底合并
BRIGHT_SPIKE_MEAN_DELTA = 80.0  # 相邻粗帧 mean 亮度差 >= 此值 -> 亮度突变区
BRIGHT_SPIKE_PEAK_TH = 180.0    # 突变峰值 mean >= 此值 -> 判「向过曝级突亮」= 白闪型


def frame_mean_brightness(frame) -> float:
    """帧灰度均值(0-255)。"""
    return float(frame.astype(np.float32).mean(axis=2).mean())


def is_flash_frame(frame, mean_th: float = FLASH_MEAN_TH,
                   frac_th: float = FLASH_FRAC_TH):
    """灰度直方图判据: 均值高 且 亮像素占比高 -> 白闪/过曝帧。返回 (bool, mean, frac)。"""
    gray = frame.astype(np.float32).mean(axis=2)
    mean = float(gray.mean())
    frac = float(np.mean(gray >= 200))
    return (mean >= mean_th and frac >= frac_th), round(mean, 1), round(frac, 3)


def flash_flags_for_frames(frames) -> np.ndarray:
    """对帧列表逐帧判白闪, 返回 np.ndarray[bool]。"""
    return np.array([is_flash_frame(f)[0] for f in frames], dtype=bool)


def brightness_spike_regions(means, times, delta: float = BRIGHT_SPIKE_MEAN_DELTA,
                             peak_th: float = BRIGHT_SPIKE_PEAK_TH):
    """白闪型亮度尖峰检测: 返回「突变边界时间」列表。

    区分(方案3): 白闪转场 = 暗→**过曝级突亮**(峰值 mean >= peak_th)后回落——
    纯亮度拉满不判镜头切变; 真实镜头切换 = 单向变亮/变暗(峰值 < peak_th) -> 不判。
    实测: 18.21 白闪 26.6→188.2(d=161.6, peak=188) 判白闪; 20.07 真实切换
    139.4→21.1(d=118.3, peak=139) 不判。
    """
    means = np.asarray(means, dtype=np.float64)
    if len(means) < 2:
        return []
    d = np.abs(np.diff(means))
    out = []
    for i in np.flatnonzero(d >= delta):
        peak = max(means[i], means[i + 1])
        if peak >= peak_th:
            out.append(float(times[i + 1]))
    return out


def drop_brightness_spike_cuts(cut_times, spike_times, margin_s: float = 0.25):
    """切点落在亮度突变边界邻域(±margin) -> 丢弃(白闪转场非真实切点)。"""
    if not spike_times:
        return cut_times
    st = np.asarray(spike_times, dtype=np.float64)
    kept = []
    for t in cut_times:
        if np.any(np.abs(st - t) <= margin_s):
            continue
        kept.append(t)
    return kept


def drop_flash_cuts(cut_times, flash_times, flash_margin_s: float = 0.2):
    """切点后处理: 切点邻域(±margin)内有白闪帧 -> 该切点删除(合并回退)。"""
    if not flash_times:
        return cut_times
    ft = np.asarray(flash_times, dtype=np.float64)
    kept = []
    for t in cut_times:
        if np.any(np.abs(ft - t) <= flash_margin_s):
            continue   # 白闪邻域切点 -> 不生成(合并)
        kept.append(t)
    return kept


def dynamic_min_shot(seg_bounds, flash_times, min_shot_s: float = 0.5,
                     dyn_s: float = FLASH_DYN_MIN_SHOT_S,
                     flash_margin_s: float = 0.2):
    """动态最短镜头阈值: 段内含白闪帧(或其邻域跨段) -> 该段最短时长抬到 dyn_s。
    返回每段生效阈值列表(调用方用它做合并决策)。"""
    if not flash_times:
        return [min_shot_s] * max(0, len(seg_bounds))
    ft = np.asarray(flash_times, dtype=np.float64)
    ths = []
    for (a, b) in seg_bounds:
        has_flash = bool(np.any((ft >= a - flash_margin_s) & (ft <= b + flash_margin_s)))
        ths.append(dyn_s if has_flash else min_shot_s)
    return ths


def merge_flash_segments(seg_bounds, flash_times, merge_frac: float = FLASH_SEG_MERGE_FRAC):
    """业务兜底: 段内白闪帧占比 >= merge_frac -> 该段与相邻段合并(删边界)。
    白闪是特效转场不是真实镜头。"""
    if not flash_times:
        return seg_bounds
    ft = np.asarray(flash_times, dtype=np.float64)
    drop_idx = set()
    for i, (a, b) in enumerate(seg_bounds):
        m = (ft >= a) & (ft <= b)
        n_in = int(np.sum(m))
        if n_in == 0:
            continue
        flash_span = (float(ft[m].max()) - float(ft[m].min())) if n_in >= 2 else 0.05
        frac = min(1.0, flash_span / max(1e-6, b - a))
        if frac >= merge_frac:
            drop_idx.add(i + 1 if i + 1 < len(seg_bounds) else i)
    if drop_idx:
        return [s for j, s in enumerate(seg_bounds) if j not in drop_idx]
    return seg_bounds
