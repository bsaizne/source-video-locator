"""p36 多模态复审对照图生成（2026-09-04）——ED 帧 vs 各候选窗。

为 p36(ed 110-111.5) 生成 VLM 复审对照图: 顶行=ED 三帧, 下面=候选窗各三帧。
候选窗: W0=2040-2044(细切分命中正确区), W1=2060-2065(runtime 当前主定位),
        W2=2829-2834(另一 argmax), W3=1855-1858(另一 argmax)。
输出: work/p36_review/p36_candidates.jpg
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
EDIT_VID = r"D:/video/1.mp4"
ORIG_VID = r"D:/video/2.mkv"
OUT_DIR = BENCH / "work" / "p36_review"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ED_TIMES = [110.0, 110.75, 111.5]   # 2fps 查询帧
WINDOWS = [
    ("W0", 2040, 2044, "correct-region (fine-seg hit)"),
    ("W1", 2060, 2065, "runtime main (current)"),
    ("W2", 2829, 2834, "argmax-other"),
    ("W3", 1855, 1858, "argmax-other"),
]


def grab(video, t, out):
    subprocess.run(
        [str(FFMPEG), "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
         "-frames:v", "1", "-vf", "scale=360:-1", str(out)], check=True)


def main() -> int:
    # 顶行: ED 三帧
    ed_frames = []
    for i, t in enumerate(ED_TIMES):
        p = OUT_DIR / f"ed_{i}.jpg"
        grab(EDIT_VID, t, p)
        ed_frames.append(Image.open(p))
    w = max(f.width for f in ed_frames); h = max(f.height for f in ed_frames)
    ed_frames = [f.resize((w, h)) for f in ed_frames]

    # 每个候选窗三帧(中点±1s)
    win_frames = []
    for name, a, b, note in WINDOWS:
        mid = (a + b) / 2
        row = []
        for i, dt in enumerate((-1.0, 0.0, 1.0)):
            p = OUT_DIR / f"{name}_{i}.jpg"
            grab(ORIG_VID, mid + dt, p)
            row.append(Image.open(p).resize((w, h)))
        win_frames.append((name, note, row))

    # 拼图: 顶行 ED, 每候选窗一行(行首标签) 3 帧
    pad = 6; label_w = 150; rows_total = 1 + len(win_frames)
    W_tot = label_w + 3 * w + 4 * pad
    H_tot = pad + rows_total * (h + pad) + 30
    canvas = Image.new("RGB", (W_tot, H_tot), (240, 240, 240))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 16)
    except Exception:
        font = ImageFont.load_default()
    x0 = label_w + pad
    y = pad
    draw.text((8, y + h // 2 - 8), "ED (edited 110-111.5)", font=font, fill=(0, 0, 0))
    for i, f in enumerate(ed_frames):
        canvas.paste(f, (x0 + i * (w + pad), y))
    y += h + pad
    for name, note, row in win_frames:
        draw.text((8, y + h // 2 - 8), f"{name} {note}", font=font, fill=(0, 0, 0))
        for i, f in enumerate(row):
            canvas.paste(f, (x0 + i * (w + pad), y))
        y += h + pad
    out = OUT_DIR / "p36_candidates.jpg"
    canvas.save(out, quality=92)
    print("saved", out, out.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())