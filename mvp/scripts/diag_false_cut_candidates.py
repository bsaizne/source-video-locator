# -*- coding: utf-8 -*-
"""假切点候选定向检查: 两级切分切点中, 找「像素单特征显著」的切点。

问题: 多特征抑制(≥2 特征才判切)并入白闪守卫是否有增量价值?
结论(FINDINGS_IFRAME_CUT.md 八章): 单特征型切点 72 个(31%)中 36 个贴近 GT 边界
= 误伤率 50% → 不建议实施(有据)。数据: work/diag_false_cut_candidates_full.txt。
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

def edge_density(a, b, th=60):
    def dens(f):
        g = gray_small(f, 128).astype(np.float32)
        gx = np.abs(np.diff(g, axis=1)); gy = np.abs(np.diff(g, axis=0))
        mag = gx[:-1,:] + gy[:,:-1]
        return float(np.mean(mag > th))
    return abs(dens(a) - dens(b))

def ssd(a, b):
    ga, gb = gray_small(a), gray_small(b)
    return float(np.mean(np.abs(ga-gb))/255.0)

def features(a, b):
    return np.array([chist(a,b), edge_density(a,b), ssd(a,b)], dtype=np.float64)

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
REL_TH = 3.0
ABS_H, ABS_E, ABS_S = 0.10, 0.05, 0.05

for name, edit, resp, gtp, vfps in CASES:
    io = FFmpegIO()
    res = json.loads(open(resp, encoding="utf-8").read())["results"]
    gt = json.loads(open(gtp, encoding="utf-8").read())
    bounds = set()
    for r in res:
        bounds.add(float(r["edited_segment"]["start"])); bounds.add(float(r["edited_segment"]["end"]))
    cuts = sorted(t for t in bounds if t > 0.1)
    gt_bounds = set()
    for p in gt["positives"]:
        gt_bounds.add(p["edited"][0]); gt_bounds.add(p["edited"][1])
    for n in gt["negatives"]:
        gt_bounds.add(n["edited"][0]); gt_bounds.add(n["edited"][1])
    strong = single = weak = 0
    single_near_gt = 0
    single_list = []
    for c in cuts:
        try:
            fr = list(io.iter_frames(edit, vfps, start=max(0,c-0.25), end=c+0.25))
        except Exception:
            continue
        if len(fr) < 3:
            continue
        vals = np.array([features(fr[j-1][1], fr[j][1]) for j in range(1, len(fr))])
        med = np.median(vals, axis=0)
        pk_idx = int(np.argmax(vals.sum(axis=1)))
        peak = vals[pk_idx]
        sig = []
        for i in range(3):
            rel = peak[i] / max(med[i], 1e-9)
            sig.append(bool(rel >= REL_TH and peak[i] >= [ABS_H, ABS_E, ABS_S][i]))
        n_sig = sum(sig)
        if n_sig >= 2:
            strong += 1
        elif n_sig == 1:
            single += 1
            near = any(abs(c - g) <= 0.3 for g in gt_bounds)
            if near: single_near_gt += 1
            single_list.append((round(c,2), [round(peak[i],3) for i in range(3)],
                                [round(med[i],3) for i in range(3)], sig, near))
        else:
            weak += 1
    print(f"\n===== {name}: 切点={len(cuts)} 强(≥2特征)={strong} 单特征={single} 弱(0特征)={weak} =====")
    print(f"  单特征型中贴近GT(真实边界,误伤风险)={single_near_gt} / 独立(假切点候选)={single-single_near_gt}")
    for row in single_list[:25]:
        tag = "贴近GT" if row[4] else "独立"
        print(f"  t={row[0]:6.2f} peak={row[1]} med={row[2]} sig={row[3]} {tag}")
    if len(single_list) > 25:
        print(f"  ... 共 {len(single_list)} 个单特征型")
print("\nDONE")
