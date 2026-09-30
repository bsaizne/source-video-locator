# -*- coding: utf-8 -*-
"""fast_global 翻转裁决出图（通用版, 2026-09-28 M1）。

用法: python mvp/scripts/visual_fastglobal_flip.py --case test1 --ridx 7
  ridx = 两臂 zip 后该结果行下标(diff_four_batches 翻转清单会给 result_id, 用 --rid 代替)。
  出图 = 该行编辑窗 3 帧 + GT(与其重叠最大的正例)原片窗 3 帧 + OFF span 3 帧 + ON span 3 帧,
  2x2 中帧拼图 + 12 帧全帧图, 供逐张读图裁决。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

EDS = {
    "2mkv": r"D:\video\1.mp4",
    "test1": r"D:\ProjectXIXI\test1\test1-ed.mp4",
    "test2": r"D:\ProjectXIXI\test2\tset2-ed.mp4",
    "test3": r"D:\ProjectXIXI\test3\test3-ed.mp4",
}
OMS = {
    "2mkv": r"D:\video\2.mkv",
    "test1": r"D:\ProjectXIXI\test1\test1-om.mkv",
    "test2": r"D:\ProjectXIXI\test2\test2-om.mp4",
    "test3": r"D:\ProjectXIXI\test3\test3-om.mp4",
}
GTS = {
    "2mkv": "datasets/real/ground_truth_v4.json",
    "test1": "datasets/real/ground_truth_test1.json",
    "test2": "datasets/real/ground_truth_test2.json",
    "test3": "datasets/real/ground_truth_test3.json",
}
FFMPEG = str(BENCH / "tools" / "ffmpeg.exe")


def grab(src, t, out_png):
    subprocess.run([FFMPEG, "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(max(t, 0)), "-i", src, "-frames:v", "1",
                    "-vf", "scale=320:-2", str(out_png)], check=True)


def tile(frames, out_png, cols=3):
    """多输入拼版: 本 ffmpeg 构建的 tile 只收单流, 用 hstack/vstack 链替代。"""
    scale = "".join(
        f"[{i}:v]scale=320:200:force_original_aspect_ratio=decrease,"
        f"pad=320:200:(ow-iw)/2:(oh-ih)/2:color=gray[a{i}];" for i in range(len(frames)))
    rows = []
    parts = []
    for r in range((len(frames) + cols - 1) // cols):
        grp = frames[r * cols:(r + 1) * cols]
        labels = [f"a{r * cols + k}" for k in range(len(grp))]
        out = f"row{r}"
        if len(labels) == 1:
            parts.append(f"[{labels[0]}]null[{out}]")
        else:
            parts.append("".join(f"[{l}]" for l in labels) +
                         f"hstack=inputs={len(labels)}[{out}]")
        rows.append(out)
    filt = scale + ";".join(parts) + ";" + \
        "".join(f"[{r}]" for r in rows) + f"vstack=inputs={len(rows)}[out]"
    cmd = ([FFMPEG, "-y", "-hide_banner", "-loglevel", "error"]
           + sum([["-i", str(f)] for f in frames], [])
           + ["-filter_complex", filt, "-map", "[out]", "-frames:v", "1",
              "-update", "1", str(out_png)])
    subprocess.run(cmd, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--ridx", type=int, default=None)
    ap.add_argument("--rid", default=None, help="OFF 臂 result_id 前缀")
    ap.add_argument("--a", default="off", help="左臂产物 tag (默认 off)")
    ap.add_argument("--b", default="on", help="右臂产物 tag (默认 on)")
    args = ap.parse_args()

    off = json.loads((BENCH / f"work/fastglobal_{args.a}_{args.case}.results.json").read_text(encoding="utf-8"))
    on = json.loads((BENCH / f"work/fastglobal_{args.b}_{args.case}.results.json").read_text(encoding="utf-8"))
    gt = json.loads((BENCH / GTS[args.case]).read_text(encoding="utf-8"))

    if args.rid:
        idx = next(i for i, r in enumerate(off["results"]) if r["result_id"].startswith(args.rid))
    else:
        idx = args.ridx
    a, b = off["results"][idx], on["results"][idx]
    ed = a["edited_segment"]
    print("row", idx, "ed", ed, "OFF", a["original"], "ON", b["original"],
          "conf", a["confidence"], "->", b["confidence"])

    # 与该编辑窗重叠最大的 GT 正例
    best, bo = None, 0.0
    for g in gt["positives"]:
        ov = min(g["edited"][1], ed["end"]) - max(g["edited"][0], ed["start"])
        if ov > bo:
            best, bo = g, ov
    if best is None:
        print("no overlapping GT positive for row", idx)
        return 1
    print("GT:", best["id"], "edited", best["edited"], "original", best["original"],
          "overlap=%.2f" % bo)

    out = BENCH / "work" / "fastglobal_visual"
    out.mkdir(exist_ok=True)
    frames = []
    for tag, src, rng in (
            ("ed", EDS[args.case], (ed["start"], ed["end"])),
            ("gt", OMS[args.case], (best["original"][0], best["original"][1])),
            ("off", OMS[args.case], (a["original"]["candidate_start"], a["original"]["candidate_end"])),
            ("on", OMS[args.case], (b["original"]["candidate_start"], b["original"]["candidate_end"]))):
        ts = [rng[0] + 0.3, (rng[0] + rng[1]) / 2, rng[1] - 0.3]
        for i, t in enumerate(ts):
            p = out / f"{args.case}_{idx}_{tag}_{i}.png"
            grab(src, t, p)
            frames.append(p)
    tile(frames, out / f"{args.case}_{idx}_sheet12.png")
    tile([frames[1], frames[4], frames[7], frames[10]], out / f"{args.case}_{idx}_mid2x2.png", cols=2)
    print("SHEETS:", out / f"{args.case}_{idx}_sheet12.png", out / f"{args.case}_{idx}_mid2x2.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
