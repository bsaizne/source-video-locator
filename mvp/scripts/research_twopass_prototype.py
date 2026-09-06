"""两级分层切分原型验证——粗采样找候选切点 + 局部密帧精修边界（2026-09-05）。

用户方案(编辑侧切分架构修正):
  1. 全局粗采样: 较大间隔(5-8帧)跑完整视频, 初步标记候选镜头切变点;
  2. 局部稠密回扫: 疑似切点前后±20帧, 小间隔(1-2帧)精细复核, 修正真实时间戳;
  约束: ① 最短镜头保护 0.5s(过滤 <0.5s 候选切分点, 减少误报);
       ② FPS 对齐: 帧间隔按 fps 换算(60fps 视频同等时间粒度帧间隔翻倍)。

本原型: 对编辑视频实现两级切分, 输出 ShotSegment 列表;
在 p36(2.mkv, ed 110-111.5) 上验证「水瓶女子」子镜头是否成为独立查询单元并命中 GT;
对照 2fps 现状(整段查询失败) 与 8fps(成功但过度切分)。
零 runtime 改动。输出: work/twopass_prototype.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "poc" / "amdgpu_onnx"))
from common import MODEL_PATH, preprocess_np, l2norm  # noqa: E402
import onnxruntime as ort  # noqa: E402
from domain import IndexMeta, TimeSpan  # noqa: E402
from engine.feature_store import IndexBundle  # noqa: E402
from engine.localization.evidence_localize import EvidenceLocalizer  # noqa: E402
from engine.segment.segment import ShotSegment, adjacent_distances  # noqa: E402

IDX = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
EDIT_VID = r"D:/video/1.mp4"
GT = (2042.0, 2043.4)
EDIT_FPS = 29.0

# 用户方案参数
COARSE_INTERVAL_FRAMES = 6    # 粗采样: 每 6 帧取 1 帧 (~4.8fps @29)
FINE_WINDOW_FRAMES = 20       # 局部精修窗: 切点前后 ±20 帧
FINE_INTERVAL_FRAMES = 2      # 精修采样: 每 2 帧取 1 帧 (~14.5fps @29)
MIN_SHOT_S = 0.5              # 最短镜头保护(秒)

# EvidenceLocalizer 生产参数
LOC = dict(min_frames=2, min_sim=0.40, cluster_gap_s=15.0,
           weak_cover=0.30, weak_sim=0.45, max_span_s=15.0,
           subspan_min_cover=0.45, subspan_min_sim=0.50,
           subspan_iou_merge=0.60, subspan_max_keep=4,
           scene_recall_enabled=True, scene_top_k=5, scene_max_expand_frames=120)

W = H = 518


def grab_frames_range(t0_s, t1_s, step_frames):
    """按帧步长抽帧(时间->帧换算, fps 对齐): 返回 (frames[N,H,W,3], times[N])。"""
    f0 = int(round(t0_s * EDIT_FPS))
    f1 = int(round(t1_s * EDIT_FPS))
    frames_idx = list(range(f0, f1, step_frames))
    if not frames_idx:
        return np.zeros((0, H, W, 3), np.uint8), np.zeros((0,), np.float64)
    n = len(frames_idx)
    # ffmpeg: 用 fps=EDIT_FPS/step 等价(先抽全帧再挑) 简化为 fps 换算
    eff_fps = EDIT_FPS / step_frames
    proc = subprocess.run(
        [str(FFMPEG), "-y", "-v", "error", "-ss", f"{t0_s:.3f}", "-t", f"{t1_s - t0_s:.3f}",
         "-i", EDIT_VID, "-vf", f"fps={eff_fps:.4f},scale={W}:{H}", "-f", "rawvideo",
         "-pix_fmt", "bgr24", "-frames:v", str(n), "-"], capture_output=True)
    raw = proc.stdout
    n_ok = min(len(raw) // (H * W * 3), n)
    if n_ok <= 0:
        return np.zeros((0, H, W, 3), np.uint8), np.zeros((0,), np.float64)
    buf = np.frombuffer(raw[:n_ok * H * W * 3], dtype=np.uint8).reshape(n_ok, H, W, 3)
    # 时间对齐: 首帧时间 = t0_s + 首帧偏移
    times = np.array([t0_s + i * step_frames / EDIT_FPS for i in range(n_ok)])
    return buf, times


def embed(sess, buf):
    if len(buf) == 0:
        return np.zeros((0, 384), np.float32)
    outs = []
    for i in range(len(buf)):
        inp = preprocess_np([buf[i]])
        outs.append(sess.run(["embedding"], {"input": np.ascontiguousarray(inp)})[0])
    return l2norm(np.concatenate(outs, axis=0))


def detect_cuts_coarse(feats, times, cut_abs=0.30, z_thresh=1.5, min_shot_frames=2):
    """粗检测候选切点: 相邻距离 + 局部z-score(复用 segment 语义)。返回切点时间列表。"""
    d = adjacent_distances(feats)                       # [n-1]
    win = max(7, 2 * 1 + 1)
    mu = np.convolve(np.pad(d, (win // 2, win // 2), mode="edge"),
                     np.ones(win) / win, mode="valid")
    mu2 = np.convolve(np.pad(d * d, (win // 2, win // 2), mode="edge"),
                      np.ones(win) / win, mode="valid")
    sd = np.sqrt(np.maximum(mu2 - mu * mu, 1e-4))
    z = (d - mu) / sd
    peak = np.zeros(len(d), dtype=bool)
    if len(d) >= 3:
        peak[1:-1] = (d[1:-1] >= d[:-2]) & (d[1:-1] >= d[2:])
    cands = np.flatnonzero(peak & (d >= cut_abs) & (z >= z_thresh))
    # NMS: 最小镜头保护(min_shot_s) -> 间隔须 >= min_shot_frames 个粗帧
    kept = []
    for c in cands:
        if all(abs(c - k) >= min_shot_frames for k in kept):
            kept.append(int(c))
    kept.sort()
    cuts_t = [float(times[c + 1]) for c in kept]   # 切点在 c 与 c+1 之间
    return kept, cuts_t


def refine_cut(sess, cut_t):
    """局部密帧精修: 切点 ±20帧 窗内每 2 帧抽帧, 找相邻距离峰 → 精确切点时间。"""
    f = cut_t * EDIT_FPS
    t0 = max(0.0, (f - FINE_WINDOW_FRAMES) / EDIT_FPS)
    t1 = min(EDIT_VID_DURATION, (f + FINE_WINDOW_FRAMES) / EDIT_FPS)
    buf, ts = grab_frames_range(t0, t1, FINE_INTERVAL_FRAMES)
    if len(buf) < 3:
        return cut_t
    q = embed(sess, buf)
    d = adjacent_distances(q)
    i = int(np.argmax(d))
    return float(ts[i + 1])


EDIT_VID_DURATION = 126.793


def main() -> int:
    bundle = IndexBundle(
        IndexMeta.from_dict(json.loads((IDX / "index.json").read_text(encoding="utf-8"))),
        np.load(IDX / "features.npy").astype(np.float32),
        np.load(IDX / "times.npy").astype(np.float64),
        np.load(IDX / "scenes.npy").astype(np.float64),
        np.load(IDX / "scene_feats.npy").astype(np.float32),
    )
    sess = ort.InferenceSession(str(MODEL_PATH),
                                providers=[("DmlExecutionProvider", {"device_id": 0}),
                                           "CPUExecutionProvider"])

    # --- 1) 粗采样全片(步长 6 帧) ---
    buf, ts = grab_frames_range(0.0, EDIT_VID_DURATION, COARSE_INTERVAL_FRAMES)
    print(f"coarse: {len(buf)} 帧 ({len(ts)} 时间), 步长 {COARSE_INTERVAL_FRAMES} 帧", flush=True)
    q = embed(sess, buf)
    kept, cuts_t = detect_cuts_coarse(q, ts, min_shot_frames=max(1, int(round(MIN_SHOT_S * EDIT_FPS / COARSE_INTERVAL_FRAMES))))
    print(f"粗切点 {len(cuts_t)} 个: {[round(t,2) for t in cuts_t[:20]]}...", flush=True)

    # --- 2) 局部密帧精修每个切点 ---
    refined = [refine_cut(sess, t) for t in cuts_t]
    refined = sorted(set(round(t, 3) for t in refined))

    # --- 3) 最短镜头保护: 相邻切点间隔 < 0.5s 的合并(删较弱: 间距小的一侧) ---
    pts = [0.0] + refined + [EDIT_VID_DURATION]
    changed = True
    while changed:
        changed = False
        i = 1
        while i < len(pts) - 1:
            gap_l = pts[i] - pts[i - 1]
            gap_r = pts[i + 1] - pts[i]
            if gap_l < MIN_SHOT_S or gap_r < MIN_SHOT_S:
                drop = i if gap_l <= gap_r else i + 1
                del pts[drop]
                changed = True
            else:
                i += 1
    segs = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1) if pts[j + 1] - pts[j] >= MIN_SHOT_S]

    # --- 4) p36 查询单元检查: ed 110-111.5 附近被切出的段 ---
    p36_related = [s for s in segs if s[1] >= 110.0 and s[0] <= 111.5]
    print(f"最终段数 {len(segs)} (最短镜头保护 {MIN_SHOT_S}s)", flush=True)
    print(f"p36 区(110-111.5)相关段: {[tuple(round(x,2) for x in s) for s in p36_related]}", flush=True)

    # --- 5) 对 p36 区每段跑 EvidenceLocalizer ---
    report = {"edited": EDIT_VID, "fps": EDIT_FPS, "params": {
        "coarse_interval_frames": COARSE_INTERVAL_FRAMES,
        "fine_window_frames": FINE_WINDOW_FRAMES, "fine_interval_frames": FINE_INTERVAL_FRAMES,
        "min_shot_s": MIN_SHOT_S}, "n_cuts_coarse": len(cuts_t), "n_segments": len(segs),
        "p36_region_segments": [tuple(round(x, 2) for x in s) for s in p36_related], "cases": {}}
    for (a, b) in p36_related:
        buf2, ts2 = grab_frames_range(a, b, COARSE_INTERVAL_FRAMES)
        if len(buf2) == 0:
            continue
        q2 = embed(sess, buf2)
        r = EvidenceLocalizer(**LOC).localize(q2, ts2.astype(np.float32), bundle)
        hit = bool(r.primary and r.primary.original_span
                   and r.primary.original_span[0] <= GT[1] and r.primary.original_span[1] >= GT[0])
        report["cases"][f"{a:.2f}-{b:.2f}"] = {
            "n_query": len(q2), "mode": r.mode,
            "primary": list(r.primary.original_span) if r.primary else None,
            "cover": round(r.primary.cover or 0, 3) if r.primary else None,
            "gt_hit": hit}
        print(f"  seg {a:.2f}-{b:.2f}: nq={len(q2)} mode={r.mode} "
              f"primary={list(r.primary.original_span) if r.primary else None} hit={hit}", flush=True)
    out = BENCH / "work" / "twopass_prototype.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
