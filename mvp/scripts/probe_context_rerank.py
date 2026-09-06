# -*- coding: utf-8 -*-
"""P0 提案判决探针: Context-aware Sequence Re-ranking（研究侧, 零 runtime）。

用户假设: 查询窗口 Q[t-2:t+2] 与源候选窗口 S[s-2:s+2] 的序列相似度重排,
能修复当前管线的同场景相邻镜头偏移(±3~13s)与兄弟机位错位。

判据: 对每个已知失败案例, 分别计算 正确位置 vs 当前错误位置 的窗口序列相似度
  S(pos) = mean_{q∈Q} max_{s∈S(pos)} cos(q, s)   (query→source 覆盖方向)
  S_sym  = 两个方向的平均
若 S(正确) 稳定 > S(错误) 且 margin 显著 → 重排可行; 若 margin≈0 或反向 → 证伪。
"""
import json
import os
import sys
from pathlib import Path

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

import numpy as np  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

TEST3_ED = r"D:\ProjectXIXI\test3\test3-ed.mp4"
TEST3_OM = r"D:\ProjectXIXI\test3\test3-om.mp4"

# (id, edited video, original video, ed0, ed1, right_mid, wrong_mid, note)
CASES = [
    ("t3r03a", TEST3_ED, TEST3_OM, 12.5, 21.0, 347.15, 353.5, "同场景偏移6.3s"),
    ("t3r04b", TEST3_ED, TEST3_OM, 35.8, 41.5, 396.1, 407.0, "同场景偏移10.9s"),
    ("t3r06b", TEST3_ED, TEST3_OM, 43.8, 44.5, 429.35, 435.0, "同场景偏移5.7s"),
    ("t3r25", TEST3_ED, TEST3_OM, 124.5, 125.0, 2879.5, 2892.0, "同场景偏移12.5s"),
    ("t3r29", TEST3_ED, TEST3_OM, 140.0, 141.5, 504.0, 501.0, "同场景偏移3.0s"),
    ("p35", r"D:\video\1.mp4", r"D:\video\2.mkv", 121.0, 122.5, 2102.1, 2092.0, "同场景偏移10.2s"),
    ("p30", r"D:\video\1.mp4", r"D:\video\2.mkv", 92.5, 93.8, 2003.5, 1800.5, "大偏移203s(对照)"),
]


def embed_at(srv, video, t0, t1, fps):
    frames, times = [], []
    for t, f in srv.ffmpeg.iter_frames(video, fps, start=t0, end=t1):
        frames.append(f)
        times.append(t)
    if not frames:
        return None, None
    feats = srv.backend.embed_frames(frames)
    q = feats / np.maximum(np.linalg.norm(feats, axis=1, keepdims=True), 1e-8)
    return q, np.array(times)


def seq_sim(Q, S):
    """S = mean_q max_s cos; 对称版再算反向。"""
    m = Q @ S.T
    fwd = float(m.max(axis=1).mean())
    bwd = float(m.max(axis=0).mean())
    return fwd, (fwd + bwd) / 2.0


def main():
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    print(f"BACKEND type={type(srv.backend).__name__}", flush=True)
    CTX = 2.0      # 查询上下文窗口 ±2s（提案口径）
    SW = 15.0      # 源候选窗口 ±15s
    print(f"窗口: 查询 ±{CTX}s@4fps, 源 ±{SW}s@1fps", flush=True)
    print(f"{'id':8s}{'note':16s}{'S_right':>9}{'S_wrong':>9}{'margin':>9}   "
          f"{'sym_right':>9}{'sym_wrong':>9}{'sym_margin':>10}  判定", flush=True)
    wins = 0
    n = 0
    for cid, ed, og, e0, e1, right, wrong, note in CASES:
        Q, _ = embed_at(srv, ed, max(0.0, e0 - CTX), e1 + CTX, 4.0)
        if Q is None:
            print(f"{cid:8s} 查询抽帧失败", flush=True)
            continue
        Sr, Srr = None, None
        res = {}
        for tag, mid in (("right", right), ("wrong", wrong)):
            S, _ = embed_at(srv, og, max(0.0, mid - SW), mid + SW, 1.0)
            fwd, sym = seq_sim(Q, S)
            res[tag] = (fwd, sym)
        m_f = res["right"][0] - res["wrong"][0]
        m_s = res["right"][1] - res["wrong"][1]
        verdict = "✅ 可修复" if m_f > 0.01 else ("⚠️ 微弱" if m_f > -0.005 else "❌ 无判别/反向")
        if m_f > 0.01:
            wins += 1
        n += 1
        print(f"{cid:8s}{note:16s}{res['right'][0]:>9.4f}{res['wrong'][0]:>9.4f}{m_f:>+9.4f}   "
              f"{res['right'][1]:>9.4f}{res['wrong'][1]:>9.4f}{m_s:>+10.4f}  {verdict}", flush=True)
    print(f"\n总计: {wins}/{n} 案例 margin>0.01（重排可修复）", flush=True)


if __name__ == "__main__":
    main()
