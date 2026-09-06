"""白闪帧检测原型验证——n03(ed 66.1-67 过曝白闪)识别 + 四层方案接入点（2026-09-05）。

用户方案:
  1. 特征前置过滤: 全画面灰度直方图, 绝大多数像素接近最大亮度 → flash_frame;
     该帧不参与镜头边界计算/相似度比对/不生成候选切点。
  2. 切点后处理(兜底): 片段内含连续白闪帧 → 切点合并回退; 白闪类候选切点动态抬阈(1.0-1.2s)。
  3. 相似度衰减: 帧间差异区分「真实镜头切换」vs「瞬时亮度爆增」(纯亮度拉满不判切变)。
  4. 业务兜底: 输出后校验, 片段全部/大部分由白闪帧构成 → 合并相邻镜头。
  注意: 不全局调大最短镜头阈值(会误杀真实短镜头), 只对白闪场景局部抬阈;
        白闪 1-3 帧但前后采样帧亮度差巨大, 粗采样易误报切点, 稠密回扫也要带白闪检测。

本原型: ① 实现 is_flash_frame(灰度直方图判据); ② 在 1.mp4 全片粗网格(step=6)上扫描白闪帧,
统计命中/分布; ③ 验证 n03 区(66-67s)白闪帧被正确标记; ④ 检查其它真实镜头区不误伤。
零 runtime 改动。输出: work/flash_detect_prototype.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
EDIT_VID = r"D:/video/1.mp4"
EDIT_FPS = 29.0
EDIT_DUR = 126.79
W = H = 518
COARSE_STEP = 6   # 粗采样步长(帧)

# 白闪判据参数（用户: 绝大多数像素接近最大亮度）
FLASH_BRIGHT_THRESH = 250   # 像素值 >= 250 视为"接近最大亮度"
FLASH_MIN_FRAC = 0.85       # 亮像素占比 >= 0.85 判白闪


def grab_range(t0, t1, step):
    f0 = int(round(t0 * EDIT_FPS)); f1 = int(round(t1 * EDIT_FPS))
    n = max(0, (f1 - f0) // step)
    if n == 0:
        return np.zeros((0, H, W, 3), np.uint8), np.zeros((0,), np.float64)
    eff = EDIT_FPS / step
    proc = subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1-t0:.3f}",
        "-i", EDIT_VID, "-vf", f"fps={eff:.4f},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-frames:v", str(n), "-"], capture_output=True)
    raw = proc.stdout
    n_ok = min(len(raw) // (H * W * 3), n)
    if n_ok <= 0:
        return np.zeros((0, H, W, 3), np.uint8), np.zeros((0,), np.float64)
    buf = np.frombuffer(raw[:n_ok * H * W * 3], dtype=np.uint8).reshape(n_ok, H, W, 3)
    times = np.array([t0 + i * step / EDIT_FPS for i in range(n_ok)])
    return buf, times


def is_flash_frame(frame, bright_thresh=FLASH_BRIGHT_THRESH, min_frac=FLASH_MIN_FRAC):
    """灰度直方图判据: 绝大多数像素接近最大亮度 → 白闪/过曝帧。"""
    gray = frame.astype(np.float32).mean(axis=2)   # [H,W]
    frac = float(np.mean(gray >= bright_thresh))
    return frac >= min_frac, round(frac, 4)


def main() -> int:
    buf, ts = grab_range(0.0, EDIT_DUR, COARSE_STEP)
    print(f"coarse frames={len(buf)}", flush=True)
    flags = []
    n_flash = 0
    for i in range(len(buf)):
        is_f, frac = is_flash_frame(buf[i])
        flags.append({"t": round(float(ts[i]), 2), "flash": bool(is_f), "bright_frac": frac})
        if is_f:
            n_flash += 1
    print(f"白闪帧总数: {n_flash}/{len(buf)}", flush=True)

    # n03 区 (66.1-67) 与周边
    n03 = [f for f in flags if 65.0 <= f["t"] <= 68.0]
    print("\nn03 区(65-68s)粗网格帧:", flush=True)
    for f in n03:
        print(f"  t={f['t']:6.2f} flash={f['flash']} bright_frac={f['bright_frac']}", flush=True)

    # 全部白闪帧时间分布(粗网格)
    flashes = [f["t"] for f in flags if f["flash"]]
    print(f"\n全片白闪帧时间: {flashes}", flush=True)

    out = BENCH / "work" / "flash_detect_prototype.json"
    out.write_text(json.dumps({"params": {"bright_thresh": FLASH_BRIGHT_THRESH,
                                          "min_frac": FLASH_MIN_FRAC, "coarse_step": COARSE_STEP},
                               "n_flash": n_flash, "n_total": len(buf), "flashes": flashes,
                               "n03_region": n03}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
