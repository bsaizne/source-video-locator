# -*- coding: utf-8 -*-
"""多模态复审: 同场景偏移案例的 查询段/正确位置/错误位置 画面对照（纯本地 ffmpeg+PIL）。"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FFMPEG = r"D:\claudework\benchmark\tools\ffmpeg.exe"
OUT = Path(r"D:\claudework\benchmark\work\context_review")
OUT.mkdir(parents=True, exist_ok=True)

TEST3_ED = r"D:\ProjectXIXI\test3\test3-ed.mp4"
TEST3_OM = r"D:\ProjectXIXI\test3\test3-om.mp4"
MKV_ED = r"D:\video\1.mp4"
MKV_OM = r"D:\video\2.mkv"

CASES = [
    ("t3r03a", TEST3_ED, TEST3_OM, 16.0, 17.0, 347.15, 353.5),
    ("t3r04b", TEST3_ED, TEST3_OM, 38.0, 39.0, 396.1, 407.0),
    ("t3r06b", TEST3_ED, TEST3_OM, 44.0, 44.4, 429.35, 435.0),
    ("t3r25", TEST3_ED, TEST3_OM, 124.6, 124.9, 2879.5, 2892.0),
    ("t3r29", TEST3_ED, TEST3_OM, 140.5, 141.0, 504.0, 501.0),
    ("p35", MKV_ED, MKV_OM, 121.5, 122.0, 2102.1, 2092.0),
]
TW, TH, PAD, LBL = 300, 169, 8, 20


def grab(vid, t, p):
    subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", vid,
                    "-frames:v", "1", "-update", "1", "-y", "-q:v", "2", str(p)],
                   check=True, timeout=120)


def sheet(case, ed, om, e_mid, right, wrong):
    cols = 2
    W = 3 * (TW + PAD) + PAD
    H = 2 * (TH + LBL + PAD) + PAD + LBL
    img = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)
    except Exception:
        font = ImageFont.load_default()
    d.text((PAD, 4), f"{case}  左=查询段  右上=正确位置  右下=当前错误位置", fill=(255, 220, 120), font=font)
    cells = [
        (0, 0, ed, e_mid, "查询段帧1", (200, 230, 255)),
        (1, 0, ed, e_mid + 0.6, "查询段帧2", (200, 230, 255)),
        (2, 0, om, right, f"正确位置 {right:.0f}s", (140, 240, 160)),
        (0, 1, om, right - 3.0, f"正确-3s {right-3:.0f}s", (140, 240, 160)),
        (1, 1, om, wrong, f"错误位置 {wrong:.0f}s", (255, 160, 160)),
        (2, 1, om, wrong + 3.0, f"错误+3s {wrong+3:.0f}s", (255, 160, 160)),
    ]
    for c, r, vid, t, label, color in cells:
        x = PAD + c * (TW + PAD)
        y = PAD + LBL + r * (TH + LBL + PAD)
        p = OUT / f"_{case}_{r}{c}.png"
        grab(vid, t, p)
        img.paste(Image.open(p).resize((TW, TH)), (x, y))
        d.text((x, y + TH + 2), label, fill=color, font=font)
        p.unlink()
    outp = OUT / f"{case}_sheet.jpg"
    img.save(outp, quality=88)
    print("saved", outp)


for case, ed, om, e0, e1, right, wrong in CASES:
    sheet(case, ed, om, (e0 + e1) / 2, right, wrong)
