"""verify_frame_precision.py — 帧级精确"定向验证"：序列对齐 (a) vs patch 空间匹配 (b)。

目标：判定哪个方法能把 seg1 编辑"直升机 moment"(19-20s) 从 CLS 误配的"士兵 moment"
定位到原片"直升机 moment"(约 1317-1322)。基准（多模态钉出）：
  h（直升机帧）≈ 1317-1322s；s（士兵帧）≈ 1294-1298s / 1304（士兵吊索）。

(a) 序列对齐：编辑 CLS 序列 vs 原片候选区 CLS 序列，ta._dp_path 单调 DP -> 编辑帧映射原片时刻。
(b) patch 空间匹配：编辑帧 patch token vs 候选区逐帧 patch token，逐位置空间匹配。

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/verify_frame_precision.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))          # -> mvp/src
sys.path.insert(0, str(BENCH / "src" / "experiments"))  # -> research experiments (ta / patch_features)

import ta  # noqa: E402  (src/experiments/ta.py)

import verify_greedy_top1 as G  # noqa: E402  (mvp/scripts/verify_greedy_top1.py; 复用 FFMPEG/FFPROBE/embed)

# 复用 verify_greedy_top1 的 io/backend
io = G.FFmpegIO(G.FFMPEG, G.FFPROBE)
backend = G.resolve_backend("auto")
store = G.FeatureStore(io, "C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index",
                       sampling_fps=1.0)
bundle = store.load_index("D:/video/2.mkv")

EDIT_PATH = BENCH / "datasets" / "real" / "edited" / "1.mp4"
EDIT_LO, EDIT_HI = 18.5, 20.5          # 编辑"直升机 moment"（渐近）区间
ORIG_LO, ORIG_HI = 1280, 1331          # 原片候选区（含 h=1317-1322, s=1294-98/1304）
EDIT_FPS = 8.0
H_LO, H_HI = 1317, 1322                # 多头模态标注：原片"直升机 moment"
S_LO, S_HI = 1294, 1298                # 原片"士兵 moment"（当前 CLS 误配侧）


def run_seq_align() -> None:
    """(a) 序列对齐：编辑 CLS 序列 vs 原片候选区 CLS 序列 -> 编辑帧映射原片时刻。"""
    q_feats, q_times = G.embed_range(io, backend, EDIT_PATH, EDIT_FPS, EDIT_LO, EDIT_HI)
    r_feats = bundle.features[ORIG_LO:ORIG_HI]
    r_times = bundle.times[ORIG_LO:ORIG_HI]
    print(f"[a] n_edit={len(q_times)} ({q_times[0]:.2f}..{q_times[-1]:.2f}s) "
          f"n_orig={len(r_times)} ({r_times[0]:.0f}..{r_times[-1]:.0f}s)")

    sim = ta.cosine_similarity(q_feats, r_feats)
    path = ta._dp_path(sim, sim_thresh=0.4)   # 放宽阈值拿 raw path
    print(f"[a] dp_path len={len(path)}（raw，含所有匹配）")
    # 每个编辑帧 -> 它的原片映射时刻（取 path 中该编辑帧对应的 r_idx；若编辑帧有多个映射取均值）
    edit_to_r = {}
    for qi, ri in path:
        edit_to_r.setdefault(qi, []).append(float(r_times[ri]))
    hit_h = hit_s = 0
    for qi in sorted(edit_to_r):
        et = float(q_times[qi])
        rt_list = edit_to_r[qi]
        rt = float(np.mean(rt_list))
        in_h = H_LO <= rt <= H_HI
        in_s = S_LO <= rt <= S_HI
        if in_h:
            hit_h += 1
        if in_s:
            hit_s += 1
        print(f"   edit {et:6.2f}s -> orig {rt:7.1f}s  {'H' if in_h else 'S' if in_s else ''}")
    print(f"[a] 直升机帧命中H({H_LO}-{H_HI})={hit_h}, 士兵帧命中S({S_LO}-{S_HI})={hit_s}")

    segs = ta.temporal_align(q_feats, r_feats, sim_thresh=0.4, min_hits=2)
    print(f"[a] temporal_align segments={segs}")


def run_patch_match() -> None:
    """(b) patch 空间匹配：编辑"直升机帧"patch token vs 候选区逐帧 patch token。

    竖屏裁剪致位置不对齐，故同时测两种：逐位置余弦 + 内容 max-match(每编辑 patch 找最近
    原片 patch)。看 argmax 帧是否落在 h(1317-1322)。
    """
    import cv2  # noqa: F401
    import torch
    from dinov2_features import _get_model, _imagenet_preprocess
    from patch_features import _patch_tokens

    model = _get_model()
    model.eval()
    with torch.no_grad():
        e_t = _patch_tokens(model, _imagenet_preprocess(io.grab_frame(EDIT_PATH, 19.0))
                            ).cpu().numpy()[0]                     # [1369,384]
        e_t = e_t / np.maximum(np.linalg.norm(e_t, axis=1, keepdims=True), 1e-8)
        rows = []
        for t in range(ORIG_LO, ORIG_HI):
            o_t = _patch_tokens(model, _imagenet_preprocess(io.grab_frame(str(ORIG), float(t)))
                                ).cpu().numpy()[0]
            o_t = o_t / np.maximum(np.linalg.norm(o_t, axis=1, keepdims=True), 1e-8)
            pos = float(np.mean(np.sum(e_t * o_t, axis=1)))         # 逐位置（裁剪敏感）
            sim = e_t @ o_t.T
            maxmatch = float(np.mean(sim.max(axis=1)))              # 内容 patch max-match
            rows.append((t, pos, maxmatch))
    best_pos = max(rows, key=lambda r: r[1])
    best_mm = max(rows, key=lambda r: r[2])
    print("[b] 逐位置余弦 best:", best_pos, " | 内容 max-match best:", best_mm)
    print(f"[b]    目标 h 区(1317-1322): 逐位置argmax帧={best_pos[0]} inH={H_LO<=best_pos[0]<=H_HI}, "
          f"max-match argmax帧={best_mm[0]} inH={H_LO<=best_mm[0]<=H_HI}")
    for t, pos, mm in rows:
        tag = "  <-H" if H_LO <= t <= H_HI else ("  <-S" if S_LO <= t <= S_HI else "")
        if pos > 0.4 or mm > 0.4 or tag:
            print(f"   orig {t:5.0f}s pos={pos:.3f} maxmatch={mm:.3f}{tag}")


ORIG = "D:/video/2.mkv"


if __name__ == "__main__":
    run_seq_align()
    run_patch_match()
