# -*- coding: utf-8 -*-
"""跨切点对精确分析: 对每个生产切点, 找真正跨过它的粗对(ta<=c<=tb),
统计该对三特征 vs 全片非跨切点对分布。回答: 粗采样(2.9fps)下像素特征对硬切
是否有判别力? (修正之前 mid<0.35s 标签污染: 未跨切点的对差异当然小。)

结论(FINDINGS_IFRAME_CUT.md 二章): 跨切点对 AUC 0.58-0.80, ≥2 特征命中率
最好仅 13-26%(2mkv/test2) —— 粗采样运动噪声淹没切点信号, 像素粗筛不可行。
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
    base = list(io.iter_frames(edit, vfps / 10.0))
    times = np.array([t for t, _ in base], dtype=np.float64)
    straddle = []
    for c in cuts:
        j = int(np.searchsorted(times, c)) - 1
        if j < 0 or j >= len(times) - 1:
            continue
        fa, fb = base[j][1], base[j+1][1]
        straddle.append((chist(fa,fb), ehist(fa,fb), ssd(fa,fb)))
    allpairs = []
    for j in range(len(times)-1):
        allpairs.append((chist(base[j][1],base[j+1][1]), ehist(base[j][1],base[j+1][1]), ssd(base[j][1],base[j+1][1])))
    strad_set = set()
    for c in cuts:
        j = int(np.searchsorted(times, c)) - 1
        if 0 <= j < len(times)-1:
            strad_set.add(j)
    nonpairs = [p for i,p in enumerate(allpairs) if i not in strad_set]
    print(f"\n===== {name}: 切点={len(cuts)} 粗对={len(allpairs)} 跨切点对={len(straddle)} =====")
    for nm, idx in [("hist",0),("edge",1),("ssd",2)]:
        sv = sorted(p[idx] for p in straddle)
        nv = sorted(p[idx] for p in nonpairs)
        def pct(v,q): return v[min(len(v)-1,int(len(v)*q))]
        print(f"  {nm}: 跨切点对 p25={pct(sv,0.25):.3f} p50={pct(sv,0.5):.3f} p75={pct(sv,0.75):.3f} | 非跨 p90={pct(nv,0.9):.3f} p99={pct(nv,0.99):.3f}")
    for th_h, th_e, th_s in [(0.22,0.18,0.16),(0.15,0.12,0.10),(0.10,0.08,0.08),(0.08,0.06,0.06)]:
        hit = sum(1 for p in straddle if sum([p[0]>=th_h, p[1]>=th_e, p[2]>=th_s]) >= 2)
        fp = sum(1 for p in nonpairs if sum([p[0]>=th_h, p[1]>=th_e, p[2]>=th_s]) >= 2)
        print(f"  ≥2特征 H{th_h}/E{th_e}/S{th_s}: 跨切点命中 {hit}/{len(straddle)} ({100*hit/len(straddle):.0f}%) 非跨误报 {fp}/{len(nonpairs)}")
    for nm, idx in [("hist",0),("edge",1),("ssd",2)]:
        sv = [p[idx] for p in straddle]; nv = [p[idx] for p in nonpairs]
        npos = len(sv); nneg = len(nv)
        auc = 0.0
        for s in sv:
            auc += sum(1 for n in nv if n < s) / nneg
        auc /= npos
        print(f"  {nm} AUC≈{auc:.3f}")
print("\nDONE")
