# -*- coding: utf-8 -*-
"""代理复现切分 × 我方切点 —— 分歧边界**盲判**对照图 (判卷侧 §4.2).

读 work/proxy_geom_summary.json(由 geom_proxy_vs_ours.py 产出), 对每片取
  · 仅我方切点 (全部)
  · 仅代理切点 (按"四阈值稳定出现次数"降序)
在 (我方时刻, 代理时刻) 配对上各出一行 4 帧 (t-0.20/-0.07/+0.07/+0.20 s),
行标签只写 **A / B**(随机、可复现), 不暴露归属 —— 盲判要求。
答案键: work/proxy_blind_disputes/blind_key.csv/.json

判读要点: 真切换那一行的中间两帧之间应"内容全变"且两侧各自稳定;
另一行应是无切换的连续内容(或过渡/黑场/字卡)。结论以画面为准。
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from pathlib import Path

import numpy as np
import cv2

BENCH = Path(r"D:\claudework\benchmark")
WORK = BENCH / "work"
OUT = WORK / "proxy_blind_disputes"
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
from media.ffmpeg import FFmpegIO  # noqa: E402

VIDEO = {"2mkv": r"D:\video\1.mp4", "test1": r"D:\ProjectXIXI\test1\test1-ed.mp4",
         "test2": r"D:\ProjectXIXI\test2\tset2-ed.mp4", "test3": r"D:\ProjectXIXI\test3\test3-ed.mp4"}
OFF = (-0.20, -0.07, 0.07, 0.20)
H = 190


def strip(ff, path, t, label, color):
    tiles = []
    for o in OFF:
        img = np.asarray(ff.grab_frame(Path(path), max(0.0, t + o)))
        hh, ww = img.shape[:2]
        im = cv2.resize(img, (max(1, int(round(ww * H / hh))), H), interpolation=cv2.INTER_AREA)
        bar = np.full((24, im.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, "%+.2fs" % o, (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        tiles.append(np.vstack([bar, im]))
    gap = np.full((tiles[0].shape[0], 6, 3), 255, np.uint8)
    row = tiles[0]
    for c in tiles[1:]:
        row = np.hstack([row, gap, c])
    lab = np.full((row.shape[0], 120, 3), 255, np.uint8)
    cv2.putText(lab, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2, cv2.LINE_AA)
    return np.hstack([lab, row])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary", default=str(WORK / "proxy_geom_summary.json"))
    ap.add_argument("--batch", default="runtime", choices=["runtime", "tn"])
    ap.add_argument("--threshold", default="040")
    ap.add_argument("--max-per-case", type=int, default=12)
    ap.add_argument("--cases", default="2mkv,test1,test2,test3")
    ap.add_argument("--seed", type=int, default=20260926)
    args = ap.parse_args()

    s = json.loads(Path(args.summary).read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    ff = FFmpegIO()
    key, made = [], []
    for case in args.cases.split(","):
        e = s["cases"][case]["batches"][args.batch]["thresholds"][args.threshold]
        ours_only = list(e["ours_only_list"])
        theirs_only = sorted(e["theirs_only_list"],
                             key=lambda x: -x.get("stable_in_n_thresholds", 0))
        picks = [("ours_only", x) for x in ours_only]
        room = max(0, args.max_per_case - len(picks))
        picks += [("theirs_only", x) for x in theirs_only[:room]]
        for i, (kind, x) in enumerate(picks):
            if kind == "ours_only":
                t_ours, t_theirs = x["time"], x["nearest_theirs"]
                ref = x
            else:
                t_theirs, t_ours = x["time"], x["nearest_ours"]
                ref = x
            flip = rng.random() < 0.5
            tA, tB = (t_ours, t_theirs) if not flip else (t_theirs, t_ours)
            sideA = "ours" if not flip else "theirs"
            rowA = strip(ff, VIDEO[case], tA, "A", (0, 0, 0))
            rowB = strip(ff, VIDEO[case], tB, "B", (0, 0, 0))
            head = np.full((30, rowA.shape[1], 3), 255, np.uint8)
            cv2.putText(head, "%s   blind sheet #%02d   A=%.2fs   B=%.2fs   (无归属标注)" % (
                case, i, tA, tB), (6, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
            fn = OUT / ("blind_%s_%02d.png" % (case, i))
            cv2.imwrite(str(fn), np.vstack([head, rowA,
                                            np.full((6, rowA.shape[1], 3), 190, np.uint8), rowB]))
            made.append(str(fn))
            key.append({"sheet": fn.name, "case": case, "kind": kind,
                        "A": "ours" if sideA == "ours" else "theirs",
                        "B": "theirs" if sideA == "ours" else "ours",
                        "ours_s": round(t_ours, 3), "theirs_s": round(t_theirs, 3),
                        "dist_s": ref.get("dist_s"),
                        "stable_in_n_thresholds": ref.get("stable_in_n_thresholds")})
            print("saved %s  A=%s B=%s  ours=%.3f theirs=%.3f" % (
                fn.name, key[-1]["A"], key[-1]["B"], t_ours, t_theirs))

    (OUT / "blind_key.json").write_text(json.dumps(
        {"batch": args.batch, "threshold": "0." + args.threshold[1:], "seed": args.seed,
         "note": "盲判图归属键 —— 先看图再查此文件", "sheets": key},
        ensure_ascii=False, indent=1), encoding="utf-8")
    with (OUT / "blind_key.csv").open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh)
        w.writerow(["sheet", "case", "kind", "A", "B", "ours_s", "theirs_s", "dist_s", "stable_in_n_thresholds"])
        for k in key:
            w.writerow([k["sheet"], k["case"], k["kind"], k["A"], k["B"],
                        k["ours_s"], k["theirs_s"], k["dist_s"], k["stable_in_n_thresholds"]])
    print("total %d sheets -> %s" % (len(made), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
