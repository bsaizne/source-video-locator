# -*- coding: utf-8 -*-
"""低信息帧数据摸底: 4 片编辑视频全片 2fps 帧的 模糊度/对比度/边缘密度 分布,
对照 4 个负例区段(n01/n02/n03/t3r15)的帧指标, 判断「低信息帧降权」对负例是否有信号。

纯 numpy 像素指标(下采样 64x64 灰度):
  - blur: Laplacian 方差(二阶差分方差) —— 模糊帧偏低
  - contrast: 灰度 std —— 纯色/低对比偏低
  - edge: Sobel 幅值>th 占比 —— 无纹理偏低
综合 low = (blur, contrast, edge) 三者的相对位置。
"""
import json, os, sys
import numpy as np
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
sys.path.insert(0, r"D:\claudework\benchmark\mvp\src")
sys.path.insert(0, r"D:\claudework\benchmark\mvp")
from media.ffmpeg import FFmpegIO

def gray_small(frame, side=64):
    h, w = frame.shape[:2]
    ys = np.linspace(0, h-1, side).astype(int); xs = np.linspace(0, w-1, side).astype(int)
    return frame[np.ix_(ys, xs, [0])][..., 0].astype(np.float32)

def frame_metrics(f):
    g = gray_small(f, 96)
    blur = float(np.var(np.diff(np.diff(g, axis=0), axis=0)))       # Laplacian 方差(近似)
    contrast = float(np.std(g))
    gx = np.abs(np.diff(g, axis=1)); gy = np.abs(np.diff(g, axis=0))
    mag = gx[:-1,:] + gy[:,:-1]
    edge = float(np.mean(mag > 60))
    return blur, contrast, edge

CASES = [
    ("2mkv",  r"D:\video\1.mp4", {"n01": (56.0, 59.5), "n02": (62.5, 66.1), "n03": (66.1, 67.0)}),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", {"t3r15": (77.5, 79.5)}),
]

for name, edit, neg_ranges in CASES:
    io = FFmpegIO()
    print(f"\n===== {name} =====")
    # 全片 2fps
    frames = list(io.iter_frames(edit, 2.0))
    all_m = np.array([frame_metrics(f) for _, f in frames])
    print(f"全片帧数={len(frames)}")
    for i, mname in enumerate(["blur", "contrast", "edge"]):
        v = all_m[:, i]
        print(f"  {mname}: p05={np.percentile(v,5):.3f} p10={np.percentile(v,10):.3f} "
              f"p25={np.percentile(v,25):.3f} p50={np.percentile(v,50):.3f} "
              f"p75={np.percentile(v,75):.3f} p90={np.percentile(v,90):.3f}")
    # 负例区段帧指标 vs 全片分位
    for nid, (a, b) in neg_ranges.items():
        seg = [(t, f) for t, f in frames if a <= t <= b]
        if not seg:
            print(f"  {nid} (ed {a}-{b}): 无帧"); continue
        sm = np.array([frame_metrics(f) for _, f in seg])
        print(f"  {nid} (ed {a}-{b}): {len(seg)} 帧")
        for i, mname in enumerate(["blur", "contrast", "edge"]):
            v_all = all_m[:, i]
            vs = sm[:, i]
            print(f"    {mname}: 中位={np.median(vs):.3f} 全片分位位置="
                  f"{np.mean(v_all < np.median(vs)):.0%}")
        # 每帧的"低信息判据": blur<全片p25 且 edge<全片p25
        low_frac = 0.0
        for m in sm:
            low = (m[0] < np.percentile(all_m[:,0],25)) and (m[2] < np.percentile(all_m[:,2],25))
            low_frac += low
        print(f"    低信息帧占比(blur<全片p25 且 edge<全片p25): {low_frac/len(sm):.0%}")
print("\nSCAN DONE")
