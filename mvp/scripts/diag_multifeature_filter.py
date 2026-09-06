# -*- coding: utf-8 -*-
"""三特征后处理过滤分析: 对两级切分切点做像素显著性判定(1fps 窗口峰值)。

问题: 两级切分(语义)给出的切点里, 有没有"像素可识别的假阳性"?
      三特征过滤(≥2 特征超阈值)会误伤真实切点吗?
方法: 对每个切点, 1fps 抽 ±0.25s 窗口, 算相邻对三特征峰值与"≥2 超阈"判定;
      被判定"像素不显著"的切点 = 潜在被过滤对象;
      对照 GT: 切点是否落在 GT positives 编辑边界 ±0.3s 内(真实边界候选)。
输出: 每片统计 + 被过滤切点列表。
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

# 判据阈值(与 iframecut 探针一致)
HIST_TH, EDGE_TH, SSD_TH = 0.22, 0.18, 0.16

CASES = [
    ("2mkv",  r"D:\video\1.mp4", r"D:\claudework\benchmark\work\rerun_2mkv_twopass_flash.results.json",
     r"D:\claudework\benchmark\datasets\real\ground_truth_v4.json", 29.0),
    ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\claudework\benchmark\work\rerun_test1_twopass.results.json",
     r"D:\claudework\benchmark\datasets\real\ground_truth_test1.json", 29.0),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\claudework\benchmark\work\rerun_test2_twopass.results.json",
     r"D:\claudework\benchmark\datasets\real\ground_truth_test2.json", 29.0),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\claudework\benchmark\work\rerun_test3_twopass.results.json",
     r"D:\claudework\benchmark\datasets\real\ground_truth_test3.json", 29.0),
]

# 白闪守卫已覆盖的(2mkv flash 结果已删除 18.345), 这里测的是"白闪守卫之外"的增量
for name, edit, resp, gtp, vfps in CASES:
    io = FFmpegIO()
    res = json.loads(open(resp, encoding="utf-8").read())["results"]
    gt = json.loads(open(gtp, encoding="utf-8").read())
    # 切点 = 段边界(去重, 去两端)
    bounds = set()
    for r in res:
        bounds.add(float(r["edited_segment"]["start"])); bounds.add(float(r["edited_segment"]["end"]))
    cuts = sorted(t for t in bounds if t > 0.1)
    # GT 编辑边界候选(真实切点参照): positives 编辑区间端点
    gt_bounds = set()
    for p in gt["positives"]:
        gt_bounds.add(p["edited"][0]); gt_bounds.add(p["edited"][1])
    for n in gt["negatives"]:
        gt_bounds.add(n["edited"][0]); gt_bounds.add(n["edited"][1])
    gt_bounds = sorted(gt_bounds)

    filtered = []   # 像素不显著(≥2 特征未超阈)的切点
    near_gt = 0     # 被过滤切点中落在 GT 边界 ±0.3s 的
    for c in cuts:
        t0 = max(0.0, c - 0.25); t1 = c + 0.25
        try:
            fr = list(io.iter_frames(edit, vfps, start=t0, end=t1))
        except Exception:
            continue
        if len(fr) < 3:
            continue
        best = None
        for j in range(1, len(fr)):
            ta, fa = fr[j-1]; tb, fb = fr[j]
            h, e, s = chist(fa,fb), ehist(fa,fb), ssd(fa,fb)
            n_over = int(h>=HIST_TH) + int(e>=EDGE_TH) + int(s>=SSD_TH)
            score = h/HIST_TH + e/EDGE_TH + s/SSD_TH
            if best is None or score > best[0]:
                best = (score, n_over, h, e, s)
        if best and best[1] < 2:
            ng = any(abs(c - g) <= 0.3 for g in gt_bounds)
            filtered.append((round(c,2), round(best[2],3), round(best[3],3), round(best[4],3), ng))
            if ng: near_gt += 1
    print(f"\n===== {name}: 切点={len(cuts)} 像素不显著={len(filtered)} "
          f"(其中贴近GT边界={near_gt}, 独立假切点候选={len(filtered)-near_gt}) =====")
    for row in filtered[:20]:
        tag = "贴近GT" if row[4] else "独立"
        print(f"  t={row[0]:6.2f} hist={row[1]:.3f} edge={row[2]:.3f} ssd={row[3]:.3f} {tag}")
    if len(filtered) > 20:
        print(f"  ... 共 {len(filtered)} 个")
print("\nDONE")
