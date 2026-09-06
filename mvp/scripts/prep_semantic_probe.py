# -*- coding: utf-8 -*-
"""语义可分性验证 - 数据准备 v2: ffmpeg 单帧 png 抓取。

4 个负例的「编辑段 3 帧 + 误配源片区 3 帧」→ work/semantic_probe/*.png + manifest.json。
"""
import json
import os
import subprocess
from pathlib import Path

FFMPEG = r"D:\claudework\benchmark\tools\ffmpeg.exe"
OUT = Path(r"D:\claudework\benchmark\work\semantic_probe")
OUT.mkdir(parents=True, exist_ok=True)

CASES = [
    ("n01", r"D:\video\1.mp4", (56.0, 59.5), r"D:\video\2.mkv", (1692.0, 1694.0)),
    ("n02", r"D:\video\1.mp4", (62.5, 66.1), r"D:\video\2.mkv", (1746.0, 1748.0)),
    ("n03", r"D:\video\1.mp4", (66.1, 67.0), r"D:\video\2.mkv", (116.0, 118.0)),
    ("t3r15", r"D:\ProjectXIXI\test3\test3-ed.mp4", (77.5, 79.5),
     r"D:\ProjectXIXI\test3\test3-om.mp4", (436.0, 438.0)),
]

def grab_png(vid, t, out_p):
    subprocess.run([FFMPEG, "-v", "error", "-ss", f"{t:.3f}", "-i", vid,
                    "-frames:v", "1", "-update", "1", "-y", "-q:v", "2", str(out_p)],
                   check=True, timeout=120)

manifest = []
for nid, ed_vid, (e0, e1), og_vid, (o0, o1) in CASES:
    for k in range(3):
        t = e0 + (e1 - e0) * (k + 1) / 4
        p = OUT / f"{nid}_ed{k}.png"
        grab_png(ed_vid, t, p)
        manifest.append({"id": nid, "side": "edited", "frame": k,
                         "video": Path(ed_vid).name, "time": round(t, 2), "path": str(p)})
    for k in range(3):
        t = o0 + (o1 - o0) * (k + 1) / 4
        p = OUT / f"{nid}_og{k}.png"
        grab_png(og_vid, t, p)
        manifest.append({"id": nid, "side": "original_mismatch", "frame": k,
                         "video": Path(og_vid).name, "time": round(t, 2), "path": str(p)})

(OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
print("entries:", len(manifest))
for m in manifest:
    sz = Path(m["path"]).stat().st_size if Path(m["path"]).exists() else -1
    print(f"  {m['id']} {m['side']}{m['frame']} {m['video']} @{m['time']} {sz}B")
