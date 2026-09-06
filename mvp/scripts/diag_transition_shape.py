# -*- coding: utf-8 -*-
"""转场形态诊断: 生产切点处 1fps 窗口内三特征峰值 vs 非切点差异 (2mkv vs test2)。

回答: 像素三特征对真实切点是否有判别力? 切点是硬切还是渐隐?
产物数据: FINDINGS_IFRAME_CUT.md 二章（1fps 下 2mkv 63/69、test2 53/54 硬切显著）。
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

def chist(a, b, bins=16):
    d = 0.0
    for c in range(3):
        ha,_ = np.histogram(a[...,c].ravel(), bins=bins, range=(0,256))
        hb,_ = np.histogram(b[...,c].ravel(), bins=bins, range=(0,256))
        ha=ha/max(1e-6,ha.sum()); hb=hb/max(1e-6,hb.sum())
        d += 1.0 - np.sum(np.sqrt(ha*hb))
    return d/3.0

def ehist(a, b, bins=16):
    def sobel(f):
        g = gray_small(f, 128)
        gx = np.abs(np.diff(g, axis=1)); gy = np.abs(np.diff(g, axis=0))
        mag = gx[:-1,:]+gy[:,:-1]
        h,_ = np.histogram(mag.ravel(), bins=bins, range=(0,510))
        return h/max(1e-6,h.sum())
    ha,hb = sobel(a), sobel(b)
    return 1.0 - np.sum(np.sqrt(ha*hb))

def ssd(a, b):
    ga, gb = gray_small(a), gray_small(b)
    return float(np.mean(np.abs(ga-gb))/255.0)

def three(a, b):
    return [chist(a,b), ehist(a,b), ssd(a,b)]

CASES = [
    ("2mkv",  r"D:\video\1.mp4", r"D:\claudework\benchmark\work\rerun_2mkv_twopass_flash.results.json", 29.0),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\claudework\benchmark\work\rerun_test2_twopass.results.json", 29.0),
]

for name, edit, resp, vfps in CASES:
    io = FFmpegIO()
    res = json.loads(open(resp, encoding="utf-8").read())["results"]
    bounds = set()
    for r in res:
        bounds.add(float(r["edited_segment"]["start"])); bounds.add(float(r["edited_segment"]["end"]))
    cuts = sorted(t for t in bounds if t > 0.1 and t < 300)
    print(f"\n===== {name}: 切点数={len(cuts)} =====")
    n_hard = 0; n_soft = 0
    peak_offsets = []
    in_win_med = []
    for c in cuts:
        try:
            fr = list(io.iter_frames(edit, vfps, start=max(0,c-0.35), end=c+0.35))
        except Exception:
            continue
        if len(fr) < 3:
            continue
        vals = []
        for j in range(1, len(fr)):
            ta, fa = fr[j-1]; tb, fb = fr[j]
            h, e, s = three(fa, fb)
            vals.append((h+e+s, abs((ta+tb)/2 - c), ta, tb, h, e, s))
        if not vals:
            continue
        peak = max(vals, key=lambda v: v[0])
        peak_offsets.append(peak[1])
        med = sorted(v[0] for v in vals)[len(vals)//2]
        in_win_med.append(med)
        if peak[1] < 0.12 and peak[0] > 1.2 * med + 1e-6:
            n_hard += 1
        else:
            n_soft += 1
    peak_offsets = np.array(peak_offsets)
    in_win_med = np.array(in_win_med)
    print(f"  切点窗口统计: 硬切(峰值贴切点&显著)={n_hard} 软切/渐隐/未突出={n_soft}")
    print(f"  峰值距切点偏移: p25={np.percentile(peak_offsets,25):.2f}s p50={np.percentile(peak_offsets,50):.2f}s p75={np.percentile(peak_offsets,75):.2f}s")
    print(f"  窗口内中位差异: p10={np.percentile(in_win_med,10):.2f} p50={np.percentile(in_win_med,50):.2f} p90={np.percentile(in_win_med,90):.2f}")
print("\nDIAG DONE")
