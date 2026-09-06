import os, sys, json
import numpy as np
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
sys.path.insert(0, r"D:\claudework\benchmark\mvp\src")
from media.ffmpeg import FFmpegIO
from device import resolve_backend
ED = r"D:\ProjectXIXI\test2\tset2-ed.mp4"
OG_IDX = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data\index\test2-om__35b9a58f.idx"
ffmpeg = FFmpegIO(ffmpeg=r"D:\claudework\benchmark\tools\ffmpeg.exe", ffprobe=r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
backend = resolve_backend("auto")
print("BACKEND_SELECTED type=%s device=%s dtype=%s" % (type(backend).__name__, backend.device_name(), backend.device_type()))
og_f = np.load(OG_IDX + "/features.npy").astype(np.float32)
og_t = np.load(OG_IDX + "/times.npy")
# 蒙太奇段: t2r02b (ed17.2-23.5), 用4fps密采样 embed 帧级特征
def embed_dense(t0, t1, fps=4.0):
    frames = list(ffmpeg.iter_frames(ED, fps))
    feats, times = [], []
    for t, f in frames:
        if t0 - 0.1 <= t <= t1 + 0.1:
            feats.append(backend.embed_frames([f])[0]); times.append(t)
    if not feats:
        return None, None
    return np.vstack(feats).astype(np.float32), np.array(times, dtype=np.float32)
# 相邻帧距离(余弦距离 1-cos), 找突变点 = 子镜头边界
def subshot_cuts(feats, times, thresh):
    if len(feats) < 2:
        return []
    q = feats[:-1] / np.maximum(np.linalg.norm(feats[:-1], axis=1, keepdims=True), 1e-8)
    r = feats[1:] / np.maximum(np.linalg.norm(feats[1:], axis=1, keepdims=True), 1e-8)
    d = 1.0 - np.sum(q * r, axis=1)
    cuts = [int(i + 1) for i in range(len(d)) if d[i] > thresh]
    # 合并相邻(间隔<2帧)
    merged = []
    for c in cuts:
        if not merged or c - merged[-1] > 2:
            merged.append(c)
    return merged, d
# 检索: 子镜头特征均值 vs 原片索引, 返回最佳命中
def retrieve(q):
    q = q / np.linalg.norm(q)
    sims = og_f @ q
    best = int(np.argmax(sims))
    return float(og_t[best]), float(sims[best]), [round(float(og_t[i]),1) for i in np.argsort(-sims)[:5]]
# 测试 t2r02b
ed_t0, ed_t1 = 17.2, 23.5
feats, times = embed_dense(ed_t0, ed_t1)
print(f"\nt2r02b 密集采样: {len(feats)} 帧 @ {times[0]:.1f}-{times[-1]:.1f}s")
# 整段均值查询
q_all = feats.mean(axis=0)
best_all, sim_all, top_all = retrieve(q_all)
print(f"整段均值: 最佳 {best_all:.1f} (sim {sim_all:.3f}) top5 {top_all}")
# 帧级距离突变识别子镜头
cuts, d = subshot_cuts(feats, times, 0.25)
print(f"帧级距离突变点(阈值0.25): {[(round(float(times[c]),1)) for c in cuts]}")
# 按突变分段, 每段独立查询
segments = []
prev = 0
for c in cuts:
    segments.append((prev, c)); prev = c
segments.append((prev, len(feats)))
print(f"\n逐子镜头查询 ({len(segments)} 个子镜头):")
for si, (a, b) in enumerate(segments):
    if b - a < 1:
        continue
    q = feats[a:b].mean(axis=0)
    b_t, b_s, top = retrieve(q)
    print(f"  子镜头{si} [{times[a]:.1f}-{times[b-1]:.1f}] ({b-a}帧) -> 最佳 {b_t:.1f} (sim {b_s:.3f}) top5 {top}")