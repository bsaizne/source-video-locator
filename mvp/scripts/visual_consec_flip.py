# -*- coding: utf-8 -*-
"""E1 翻转裁决出图: t2r01b（consec OFF/ON 双臂主 span + GT 窗 + 相邻段对照）。"""
import json
import subprocess
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
OUT = BENCH / "work" / "consec_flip_visual"
OUT.mkdir(exist_ok=True)
FFMPEG = str(BENCH / "tools" / "ffmpeg.exe")
ED = r"D:\ProjectXIXI\test2\tset2-ed.mp4"
OM = r"D:\ProjectXIXI\test2\test2-om.mp4"

gt = json.loads((BENCH / "datasets/real/ground_truth_test2.json"
                 ).read_text(encoding="utf-8"))
entry = next(g for g in gt["positives"] if g["id"] == "t2r01b")
print("GT:", entry)

off = json.loads((BENCH / "work/consec_off_test2.results.json").read_text(encoding="utf-8"))
on = json.loads((BENCH / "work/consec_on_test2.results.json").read_text(encoding="utf-8"))


def find(batch, rid):
    return next(r for r in batch["results"] if r["result_id"] == rid)


# 找到被平移的段（两臂 original 不同者; result_id 每批新生成, 只能按位置配对）
flips = [(i, a, b) for i, (a, b) in enumerate(zip(off["results"], on["results"]))
         if a["original"] != b["original"]]
for i, a, b in flips:
    print("shifted idx", i, a["result_id"][:8],
          a["original"], "->", b["original"], "conf", a["confidence"], b["confidence"],
          "ed", a["edited_segment"])


def grab(tag, src, t, out_png):
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(t), "-i", src, "-frames:v", "1",
                    "-vf", "scale=320:-2", str(out_png)], check=True)
    print("wrote", out_png.name)


ed_s = entry["edited"][0]
og = entry["original"]
_, a_off, b_on = flips[0]
frames = []
for i, t in enumerate([ed_s + 0.5, (entry["edited"][0] + entry["edited"][1]) / 2, entry["edited"][1] - 0.5]):
    p = OUT / f"ed_{i}.png"
    grab(f"ed{i}", ED, t, p)
    frames.append(p)
for label, rng in (("gt", og), ("off", [a_off["original"]["candidate_start"], a_off["original"]["candidate_end"]]),
                   ("on", [b_on["original"]["candidate_start"], b_on["original"]["candidate_end"]])):
    for i, t in enumerate([rng[0] + 0.3, (rng[0] + rng[1]) / 2, rng[1] - 0.3]):
        p = OUT / f"{label}_{i}.png"
        grab(label, OM, t, p)
        frames.append(p)
# 拼 3x3 网格（ed 行 / gt+off+on 各取中帧 + 全帧两列）
inputs = "".join(f"[{i}:v]" for i in range(len(frames)))
filt = "".join(f"[{i}:v]scale=320:200:force_original_aspect_ratio=decrease,"
               f"pad=320:200:(ow-iw)/2:(oh-ih)/2:color=gray[a{i}];" for i in range(len(frames)))
cols = 3
rows = (len(frames) + cols - 1) // cols
tile = "".join(f"[a{i}]" for i in range(len(frames))) + \
    f"tile={cols}x{rows}:inputs={len(frames)}:margin=4:padding=4:color=black"
cmd = [FFMPEG, "-y", "-hide_banner", "-loglevel", "error"] + \
      sum([["-i", str(f)] for f in frames], []) + \
      ["-filter_complex", filt + tile, "-frames:v", "1",
       str(OUT / "t2r01b_sheet.png")]
subprocess.run(cmd, check=True)
print("SHEET:", OUT / "t2r01b_sheet.png")
