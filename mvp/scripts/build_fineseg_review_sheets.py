"""test 域细切分候选(t2r02b/t2r03a) 多模态复审对照图生成（2026-09-04）。

ED 帧 vs 命中窗 vs whole_primary 对照, 供 VLM 判定内容匹配。
输出: work/fineseg_review/{id}_candidates.jpg
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
EDIT_VID = r"D:/ProjectXIXI/test2/tset2-ed.mp4"
ORIG_VID = r"D:/ProjectXIXI/test2/test2-om.mp4"
OUT_DIR = BENCH / "work" / "fineseg_review"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CASES = [
    ("t2r02b", (17.2, 23.5), (2931.0, 2931.37), [2921.0, 2934.0], [3301.0, 3315.0]),
    ("t2r03a", (24.0, 27.8), (3406.0, 3406.97), [3406.0, 3407.0], [3407.0, 3424.0]),
]


def grab(video, t, out):
    subprocess.run(
        [str(FFMPEG), "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
         "-frames:v", "1", "-vf", "scale=360:-1", str(out)], check=True)


def row_frames(video, mid, n=3, step=1.0):
    imgs = []
    for i in range(n):
        p = OUT_DIR / f"_tmp_{len(list(OUT_DIR.glob('*.jpg')))}_{i}.jpg"
        grab(video, mid + (i - n // 2) * step, p)
        imgs.append(Image.open(p))
    return imgs


def main() -> int:
    for cid, (e0, e1), (g0, g1), hit_span, whole_span in CASES:
        # ED 行(编辑段中点 3 帧)
        emid = (e0 + e1) / 2
        ed = row_frames(EDIT_VID, emid)
        w = max(f.width for f in ed); h = max(f.height for f in ed)
        ed = [f.resize((w, h)) for f in ed]
        # 命中窗行
        hmid = (hit_span[0] + hit_span[1]) / 2
        hit = [f.resize((w, h)) for f in row_frames(ORIG_VID, hmid)]
        # whole_primary 行
        wmid = (whole_span[0] + whole_span[1]) / 2
        whole = [f.resize((w, h)) for f in row_frames(ORIG_VID, wmid)]

        pad = 6; label_w = 170
        W_tot = label_w + 3 * w + 4 * pad
        H_tot = pad + 3 * (h + pad) + 30
        canvas = Image.new("RGB", (W_tot, H_tot), (240, 240, 240))
        draw = ImageDraw.Draw(canvas)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
        except Exception:
            font = ImageFont.load_default()
        x0 = label_w + pad; y = pad
        draw.text((8, y + h // 2 - 8), f"ED {cid} ed{e0}-{e1}", font=font, fill=(0, 0, 0))
        for i, f in enumerate(ed): canvas.paste(f, (x0 + i * (w + pad), y))
        y += h + pad
        draw.text((8, y + h // 2 - 8), f"W_HIT {hit_span}", font=font, fill=(0, 0, 0))
        for i, f in enumerate(hit): canvas.paste(f, (x0 + i * (w + pad), y))
        y += h + pad
        draw.text((8, y + h // 2 - 8), f"W_WHOLE {whole_span}", font=font, fill=(0, 0, 0))
        for i, f in enumerate(whole): canvas.paste(f, (x0 + i * (w + pad), y))
        out = OUT_DIR / f"{cid}_candidates.jpg"
        canvas.save(out, quality=92)
        print("saved", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())