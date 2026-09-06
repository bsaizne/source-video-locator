# -*- coding: utf-8 -*-
"""多模态复审抽帧: 把结案证据链关键判点抽帧拼成带标签对照图(纯本地 ffmpeg+PIL, 无 VLM)。

每个判点一张 sheet: 上排 = 编辑段帧(ed t), 下排 = 原片候选区帧(og t), 标签注明角色与 sim。
输出 work/subshot_review/<case>_sheet.jpg
"""
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FFMPEG = r"D:\claudework\benchmark\tools\ffmpeg.exe"
OUT = Path(r"D:\claudework\benchmark\work\subshot_review")
OUT.mkdir(parents=True, exist_ok=True)

TEST2_ED = r"D:\ProjectXIXI\test2\tset2-ed.mp4"
TEST2_OM = r"D:\ProjectXIXI\test2\test2-om.mp4"
MKV_ED = r"D:\video\1.mp4"
MKV_OM = r"D:\video\2.mkv"
TEST3_ED = r"D:\ProjectXIXI\test3\test3-ed.mp4"
TEST3_OM = r"D:\ProjectXIXI\test3\test3-om.mp4"

CASES = {
    # 判点1: t2r02b oracle 证伪 —— 正确子镜头(Jacob)是否= GT 2931 区, 其他高 sim 子镜头是否别处
    "t2r02b": {
        "ed": (TEST2_ED, [(17.4, "ed17.4 子镜头A(Jacob?) sim.625->2934"),
                          (19.0, "ed19.0 子镜头B sim.770->3302"),
                          (20.2, "ed20.2 子镜头C sim.853->3303"),
                          (22.7, "ed22.7 子镜头E sim.805->3315")]),
        "og": (TEST2_OM, [(2931.2, "og2931 GT(正确答案)"),
                          (3303.0, "og3303 max-sim子镜头命中(洒水器?)"),
                          (3313.0, "og3313 子镜头D命中"),
                          (3406.0, "og3406 子镜头F命中 sim.809")]),
    },
    # 判点2: p10 漂移真实 + 已被 pool sub span 命中(GT 1300-1302, 主定位 1144.5-1146.5)
    "p10": {
        "ed": (MKV_ED, [(17.0, "ed17.0"), (18.5, "ed18.5"), (20.0, "ed20.0")]),
        "og": (MKV_OM, [(1145.5, "og1145 主定位(漂移, LOW)"),
                        (1301.0, "og1301 GT/pool span(1294-1308)")]),
    },
    # 判点3: t2r05a 唯一严格可动段 —— GT 4344.8-4346.8, 主定位 3954, max-sim 子镜头 3629/3995
    "t2r05a": {
        "ed": (TEST2_ED, [(41.2, "ed41.2 子镜头A"), (42.0, "ed42.0 子镜头B"), (42.4, "ed42.4 子镜头C")]),
        "og": (TEST2_OM, [(4345.5, "og4345 GT(答案)"),
                          (3954.0, "og3954 主定位(漂移)"),
                          (3631.0, "og3631 max-sim子镜头命中"),
                          (3998.0, "og3998 次高sim子镜头命中")]),
    },
    # 判点4: t3r04a 采纳未变区 —— GT 402, 主定位 412(采纳前后同区, HIT)
    "t3r04a": {
        "ed": (TEST3_ED, [(25.5, "ed25.5"), (27.0, "ed27.0")]),
        "og": (TEST3_OM, [(402.0, "og402 GT(答案)"), (412.5, "og412 主定位(HIT)")]),
    },
}

TW, TH, PAD, LBL = 320, 180, 8, 22


def grab(vid, t, p):
    subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", vid,
                    "-frames:v", "1", "-update", "1", "-y", "-q:v", "2", str(p)],
                   check=True, timeout=120)


def sheet(case, spec):
    ed_vid, ed_frames = spec["ed"]
    og_vid, og_frames = spec["og"]
    cols = max(len(ed_frames), len(og_frames))
    W = cols * (TW + PAD) + PAD
    rows = 2
    H = rows * (TH + LBL + PAD) + PAD + LBL
    img = Image.new("RGB", (W, H), (24, 24, 24))
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 13)
    except Exception:
        font = ImageFont.load_default()
    d.text((PAD, 4), f"{case}  上排=编辑段  下排=原片候选", fill=(255, 220, 120), font=font)
    for r, (vid, frames) in enumerate([(ed_vid, ed_frames), (og_vid, og_frames)]):
        y = PAD + LBL + r * (TH + LBL + PAD)
        for c, (t, label) in enumerate(frames):
            x = PAD + c * (TW + PAD)
            p = OUT / f"_{case}_{r}{c}.png"
            grab(vid, t, p)
            im = Image.open(p).resize((TW, TH))
            img.paste(im, (x, y))
            d.text((x, y + TH + 2), label, fill=(200, 230, 255) if r == 0 else (255, 200, 200),
                   font=font)
    outp = OUT / f"{case}_sheet.jpg"
    img.save(outp, quality=88)
    for f in OUT.glob(f"_{case}_*.png"):
        f.unlink()
    print("saved", outp)


for case, spec in CASES.items():
    sheet(case, spec)
print(json.dumps({"out": str(OUT)}, ensure_ascii=False))
