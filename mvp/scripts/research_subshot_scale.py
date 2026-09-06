import os, sys, json
import numpy as np
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
sys.path.insert(0, r"D:\claudework\benchmark\mvp\src")
from pathlib import Path
from media.ffmpeg import FFmpegIO
from device import resolve_backend
import time

ffmpeg = FFmpegIO(ffmpeg=r"D:\claudework\benchmark\tools\ffmpeg.exe", ffprobe=r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
backend = resolve_backend("auto")
print("BACKEND_SELECTED type=%s device=%s dtype=%s" % (type(backend).__name__, backend.device_name(), backend.device_type()), flush=True)

# 四片: (label, edit_video, orig_index_dir)
PIECES = [
  ("2mkv", r"D:\video\1.mp4", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data\index\2__4c6d4ab2.idx", "ground_truth_v4.json"),
  ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data\index\test1-om__5d4fdc2b.idx", "ground_truth_test1.json"),
  ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data\index\test2-om__35b9a58f.idx", "ground_truth_test2.json"),
  ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data\index\test3-om__074e2dcc.idx", "ground_truth_test3.json"),
]

def load_orig(idx_dir):
    return (np.load(idx_dir + "/features.npy").astype(np.float32), np.load(idx_dir + "/times.npy"))

def embed_dense_into(ed, t0, t1, fps=4.0):
    feats, times = [], []
    for t, f in ffmpeg.iter_frames(ed, fps):
        if t0 - 0.1 <= t <= t1 + 0.1:
            feats.append(backend.embed_frames([f])[0]); times.append(t)
    if not feats: return None, None
    return np.vstack(feats).astype(np.float32), np.array(times, dtype=np.float32)

def subshot_bounds(feats, times, thresh=0.5):
    if len(feats) < 2: return []
    q = feats[:-1]/np.maximum(np.linalg.norm(feats[:-1],axis=1,keepdims=True),1e-8)
    r = feats[1:]/np.maximum(np.linalg.norm(feats[1:],axis=1,keepdims=True),1e-8)
    d = 1.0-np.sum(q*r,axis=1)
    cuts = [int(i+1) for i in range(len(d)) if d[i] > thresh]
    merged = []
    for c in cuts:
        if not merged or c - merged[-1] > 1: merged.append(c)
    return merged

def retrieve(og_f, og_t, q):
    q = q/np.linalg.norm(q)
    sims = og_f @ q
    best = int(np.argmax(sims))
    return float(og_t[best]), float(sims[best])

results = []
for label, ed, og_idx, gt_name in PIECES:
    og_f, og_t = load_orig(og_idx)
    gt = json.loads((Path(r"D:\claudework\benchmark\datasets\real") / gt_name).read_text(encoding="utf-8"))
    print(f"\n===== {label}: 正例段子镜头规模 + 逐子查询 vs 整段均值 =====", flush=True)
    n_montage = 0; n_improve = 0; n_regress = 0; n_total = 0
    for p in gt["positives"]:
        e0, e1 = p["edited"]; o0, o1 = p["original"]; gmid = (o0+o1)/2
        feats, times = embed_dense_into(ed, e0, e1)
        if feats is None or len(feats) < 4: continue
        n_total += 1
        # 整段均值
        q_all = feats.mean(axis=0)
        b_all, s_all = retrieve(og_f, og_t, q_all)
        gap_all = abs(b_all - gmid)
        # 子镜头数
        cuts = subshot_bounds(feats, times)
        n_sub = len(cuts) + 1
        # 逐子镜头查询, 取最佳命中
        best_gap_sub = None
        bounds = [0] + cuts + [len(feats)]
        for si in range(len(bounds)-1):
            a, b = bounds[si], bounds[si+1]
            if b - a < 1: continue
            q = feats[a:b].mean(axis=0)
            b_t, s = retrieve(og_f, og_t, q)
            gap = abs(b_t - gmid)
            if best_gap_sub is None or gap < best_gap_sub: best_gap_sub = gap
        if n_sub >= 3 and (gap_all > 15):
            n_montage += 1
            if best_gap_sub is not None and best_gap_sub < gap_all - 2: n_improve += 1
            if best_gap_sub is not None and best_gap_sub > gap_all + 2: n_regress += 1
            print(f"  {p["id"]:7s} ed{e0:.1f}-{e1:.1f} GTog{o0:.0f}-{o1:.0f} | 子镜头{n_sub} | 整段gap {gap_all:.1f} 逐子最佳gap {best_gap_sub if best_gap_sub is not None else -1:.1f} ", flush=True)
    print(f"  {label}: 有效段 {n_total}, 多镜头(>=3)且整段gap>15 {n_montage}, 逐子改善 {n_improve}, 逐子回退 {n_regress}", flush=True)
    results.append((label, n_total, n_montage, n_improve, n_regress))

print("\n=== 汇总 ===", flush=True)
tot_m = tot_i = tot_r = 0
for label, n_total, n_montage, n_improve, n_regress in results:
    print(f"  {label}: 多镜头蒙太奇段 {n_montage}, 逐子查询改善 {n_improve}, 回退 {n_regress}", flush=True)
    tot_m += n_montage; tot_i += n_improve; tot_r += n_regress
print(f"  合计: 多镜头蒙太奇 {tot_m}, 逐子改善 {tot_i}, 回退 {tot_r}", flush=True)