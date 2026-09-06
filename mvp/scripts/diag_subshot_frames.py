# -*- coding: utf-8 -*-
"""诊断: 漂移型 montage 段在 dense 采样下的帧数/子镜头数——验证 _subshot_relocalize 门槛阻断。"""
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

SEGS = [
    ("2mkv s55(p32)", r"D:\video\1.mp4", 100.6, 102.6),
    ("2mkv s61",      r"D:\video\1.mp4", 111.9, 113.2),
    ("test1 s30(t1r18)", r"D:\ProjectXIXI\test1\test1-ed.mp4", 73.9, 78.2),
    ("test2 s32",     r"D:\ProjectXIXI\test2\tset2-ed.mp4", 36.1, 38.5),
    ("test2 s35(t2r05a)", r"D:\ProjectXIXI\test2\tset2-ed.mp4", 40.9, 42.5),
    ("test3 s15",     r"D:\ProjectXIXI\test3\test3-ed.mp4", 37.4, 39.2),
    ("test3 s49",     r"D:\ProjectXIXI\test3\test3-ed.mp4", 112.0, 113.6),
]

cfg = load_config()
srv = SourceLocatorService(config=cfg)
b = srv.backend
print(f"BACKEND_SELECTED type={type(b).__name__}", flush=True)
efps = cfg.pipeline.seq_align.edit_fps
print("seq_align edit_fps =", efps, flush=True)

for name, edited, a, z in SEGS:
    frames, times = [], []
    for t, f in srv.ffmpeg.iter_frames(edited, efps, start=a, end=z):
        frames.append(f)
        times.append(t)
    if len(frames) < 2:
        print(f"{name}: {len(frames)} 帧(<2) -> 不可拆", flush=True)
        continue
    feats = b.embed_frames(frames)
    q = feats[:-1] / np.maximum(np.linalg.norm(feats[:-1], axis=1, keepdims=True), 1e-8)
    r = feats[1:] / np.maximum(np.linalg.norm(feats[1:], axis=1, keepdims=True), 1e-8)
    d = 1.0 - np.sum(q * r, axis=1)
    cuts = [i + 1 for i in range(len(d)) if d[i] > 0.5]
    merged = []
    for c in cuts:
        if not merged or c - merged[-1] > 1:
            merged.append(c)
    nsub = len(merged) + 1
    print(f"{name}: {len(frames)}帧@{efps}fps 距离max={d.max():.3f} "
          f"cuts>{0.5}={len(cuts)} merged={merged} 子镜头={nsub} "
          f"{'-> PASS 门槛' if len(frames) >= 6 and nsub >= 3 else '-> 被门槛挡(帧<6 或 子镜头<3)'}",
          flush=True)
print("DONE", flush=True)
