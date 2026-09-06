"""白闪检测模块——四层方案实现（2026-09-05 用户方案）。

方案:
  1. 特征前置过滤(优先): is_flash_frame 灰度直方图判据; flash 帧不参与镜头边界计算/
     相似度比对/不生成候选切点。
  2. 切点后处理(兜底): 段内含连续白闪帧 → 切点合并回退; 白闪类候选切点动态抬阈(1.0-1.2s)。
  3. 相似度衰减: 帧间差异区分「真实镜头切换」vs「瞬时亮度爆增」(纯亮度拉满不判切变)。
  4. 业务兜底: 输出后校验, 片段全部/大部分由白闪帧构成 → 合并相邻镜头。

判据校准(1.mp4 实测): 白闪帧 ed 18.35-18.46 (mean 219-251, >=200 占比 ~0.99, >=250 0.23-0.98);
正常帧 mean <= 155。用「灰度均值 >= FLASH_MEAN_TH 且 亮像素(>=200)占比 >= FLASH_FRAC_TH」双判据。

本模块供 rerun_twopass.py 等研究脚本复用。零 runtime 改动。
"""
from __future__ import annotations

import numpy as np

FLASH_MEAN_TH = 200.0    # 灰度均值门槛(白闪核心帧 mean 219-251; 过渡帧 155-195 不判)
FLASH_FRAC_TH = 0.5      # 亮像素(>=200)占比门槛(白闪 >=0.65; 正常 <=0.4)
FLASH_DYN_MIN_SHOT_S = 1.0   # 白闪邻域动态最短镜头阈值(用户建议 1.0-1.2s)
FLASH_SEG_MERGE_FRAC = 0.5   # 段内白闪占比 >= 此值 → 业务兜底合并

# --- 亮度尖峰检测(用户方案3: 区分真实镜头切换 vs 瞬时亮度爆增) ---
BRIGHT_SPIKE_MEAN_DELTA = 80.0   # 相邻粗帧 mean 亮度差 >= 此值 → 亮度突变区
BRIGHT_SPIKE_PEAK_TH = 180.0     # 突变峰值 mean >= 此值 → 判「向过曝级突亮」= 白闪型


def frame_mean_brightness(frame) -> float:
    """帧灰度均值(0-255)。"""
    return float(frame.astype(np.float32).mean(axis=2).mean())


def brightness_spike_regions(means, times, delta=BRIGHT_SPIKE_MEAN_DELTA,
                             peak_th=BRIGHT_SPIKE_PEAK_TH):
    """白闪型亮度尖峰检测: 返回「突变边界时间」列表。

    区分(方案3): 白闪转场 = 暗→**过曝级突亮**(峰值 mean >= peak_th)后回落——
    纯亮度拉满不判镜头切变; 真实镜头切换 = 单向变亮/变暗(如 139→21 暗场切换,
    峰值 < peak_th) → **不判**白闪。实测: 18.21 白闪 26.6→188.2(d=161.6, peak=188)
    判白闪; 20.07 真实切换 139.4→21.1(d=118.3, peak=139) 不判。
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


def drop_brightness_spike_cuts(cut_times, spike_times, margin_s=0.25):
    """切点落在亮度突变边界邻域(±margin) → 丢弃(白闪转场非真实切点)。"""
    if not spike_times:
        return cut_times
    st = np.asarray(spike_times, dtype=np.float64)
    kept = []
    for t in cut_times:
        if np.any(np.abs(st - t) <= margin_s):
            continue
        kept.append(t)
    return kept


def is_flash_frame(frame, mean_th=FLASH_MEAN_TH, frac_th=FLASH_FRAC_TH):
    """灰度直方图判据: 均值高 且 亮像素占比高 → 白闪/过曝帧。返回 (bool, mean, frac)。"""
    gray = frame.astype(np.float32).mean(axis=2)
    mean = float(gray.mean())
    frac = float(np.mean(gray >= 200))
    return (mean >= mean_th and frac >= frac_th), round(mean, 1), round(frac, 3)


def flash_flags_for_frames(frames):
    """对帧列表逐帧判白闪, 返回 np.ndarray[bool]。"""
    return np.array([is_flash_frame(f)[0] for f in frames], dtype=bool)


def drop_flash_cuts(cut_times, flash_times, flash_margin_s=0.2):
    """切点后处理: 切点邻域(±margin)内有白闪帧 → 该切点删除(合并回退)。"""
    if not flash_times:
        return cut_times
    ft = np.asarray(flash_times, dtype=np.float64)
    kept = []
    for t in cut_times:
        if np.any(np.abs(ft - t) <= flash_margin_s):
            continue   # 白闪邻域切点 → 不生成(合并)
        kept.append(t)
    return kept


def dynamic_min_shot(seg_bounds, flash_times, min_shot_s=0.5,
                     dyn_s=FLASH_DYN_MIN_SHOT_S, flash_margin_s=0.2):
    """动态最短镜头阈值: 段内含白闪帧(或其邻域跨段) → 该段最短时长抬到 dyn_s。
    返回过滤后的段边界(不满足动态阈值的段被合并到相邻段——此处由调用方用 pts 合并逻辑处理,
    本函数仅返回每段的生效阈值)。"""
    if not flash_times:
        return [min_shot_s] * max(0, len(seg_bounds))
    ft = np.asarray(flash_times, dtype=np.float64)
    ths = []
    for (a, b) in seg_bounds:
        has_flash = bool(np.any((ft >= a - flash_margin_s) & (ft <= b + flash_margin_s)))
        ths.append(dyn_s if has_flash else min_shot_s)
    return ths


def merge_flash_segments(seg_bounds, flash_times, merge_frac=FLASH_SEG_MERGE_FRAC):
    """业务兜底: 段内白闪帧占比 >= merge_frac → 该段与相邻段合并(删边界)。
    白闪是特效转场不是真实镜头。"""
    if not flash_times:
        return seg_bounds
    ft = np.asarray(flash_times, dtype=np.float64)
    drop_idx = set()
    for i, (a, b) in enumerate(seg_bounds):
        n_in = int(np.sum((ft >= a) & (ft <= b)))
        # 白闪帧总数少(粗网格), 用「段宽 vs 白闪帧跨度」近似占比
        if n_in == 0:
            continue
        flash_span = float(ft[(ft >= a) & (ft <= b)].max()) - float(ft[(ft >= a) & (ft <= b)].min())             if n_in >= 2 else 0.05
        frac = min(1.0, flash_span / max(1e-6, b - a))
        if frac >= merge_frac:
            # 合并: 删右边界(并入后一段); 最后一段则删左边界
            drop_idx.add(i + 1 if i + 1 < len(seg_bounds) else i)
    if drop_idx:
        out = [s for j, s in enumerate(seg_bounds) if j not in drop_idx]
        return out
    return seg_bounds
