# -*- coding: utf-8 -*-
"""门控案例多模态复审: 查询段 / patch top1 / 当前主定位 / GT 中点 画面对照。"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FFMPEG = r"D:\claudework\benchmark\tools\ffmpeg.exe"
OUT = Path(r"D:\claudework\benchmark\work\patch_gate_review")
OUT.mkdir(parents=True, exist_ok=True)

TEST3_ED = r"D:\ProjectXIXI\test3\test3-ed.mp4"
TEST3_OM = r"D:\ProjectXIXI\test3\test3-om.mp4"
MKV_ED = r"D:\video\1.mp4"
MKV_OM = r"D:\video\2.mkv"
TEST1_ED = r"D:\ProjectXIXI\test1\test1-ed.mp4"
TEST1_OM = r"D:\ProjectXIXI\test1\test1-om.mkv"

# (case, ed_vid, om_vid, q1, q2, top1, main, gt)
CASES = [
    ("p26", MKV_ED, MKV_OM, 76.5, 77.5, 1769.0, 1778.0, 1769.1),
    ("p14", MKV_ED, MKV_OM, 31.4, 32.0, 1381.0, 1394.0, 1381.0),
    ("t3r26", TEST3_ED, TEST3_OM, 126.5, 128.0, 2882.0, 2892.0, 2890.7),
    ("p10", MKV_ED, MKV_OM, 17.5, 19.5, 1210.0, 1145.5, 1301.0),
    ("t1r02", TEST1_ED, TEST1_OM, 6.0, 8.0, 2175.0, 2181.0, 2183.5),
]
TW, TH, PAD, LBL = 300, 169, 8, 20


def grab(vid, t, p):
    subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", vid,
                    "-frames:v", "1", "-update", "1", "-y", "-q:v", "2", str(p)],
                   check=True, timeout=120)


def sheet(case, ed, om, q1, q2, top1, main, gt):
    W = 3 * (TW + PAD) + PAD
    H = 2 * (TH + LBL + PAD) + PAD + LBL
    img = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)
    except Exception:
        font = ImageFont.load_default()
    d.text((PAD, 4), f"{case}  左=查询段  右上=patch top1  右下=当前主定位/GT", fill=(255, 220, 120), font=font)
    cells = [
        (0, 0, ed, q1, "查询段帧1", (200, 230, 255)),
        (1, 0, ed, q2, "查询段帧2", (200, 230, 255)),
        (2, 0, om, top1, f"patch top1 {top1:.0f}s", (255, 230, 140)),
        (0, 1, om, gt, f"GT 中点 {gt:.0f}s", (140, 240, 160)),
        (1, 1, om, main, f"当前主定位 {main:.0f}s", (255, 160, 160)),
        (2, 1, om, main + 3.0, f"主定位+3s {main+3:.0f}s", (255, 160, 160)),
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


for row in CASES:
    sheet(*row)
