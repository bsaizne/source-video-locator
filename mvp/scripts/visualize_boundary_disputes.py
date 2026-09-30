"""为「边界精修判据分歧点」出对照图 —— 供视觉/多模态复审 (2026-09-26).

每张图两行: 上=我方边界位置, 下=CM(H-CM1 假设)位置; 每行 4 帧 (t-0.20/-0.07/+0.07/+0.20 s)。
判读要点: 真切换的那一行应在中间两帧之间"内容全变", 而两侧各自稳定。
数据(帧差)只为定位分歧点, 结论以画面为准.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import cv2

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
from media.ffmpeg import FFmpegIO  # noqa: E402

VIDEO = {"2mkv": r"D:\video\1.mp4", "test1": r"D:\ProjectXIXI\test1\test1-ed.mp4",
         "test2": r"D:\ProjectXIXI\test2\tset2-ed.mp4", "test3": r"D:\ProjectXIXI\test3\test3-ed.mp4"}
OFF = (-0.20, -0.07, 0.07, 0.20)
H = 200


def strip(ff, path, t, label, color):
    tiles = []
    for o in OFF:
        img = np.asarray(ff.grab_frame(Path(path), max(0.0, t + o)))
        hh, ww = img.shape[:2]
        im = cv2.resize(img, (max(1, int(round(ww * H / hh))), H), interpolation=cv2.INTER_AREA)
        bar = np.full((26, im.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, "%+.2fs" % o, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        tiles.append(np.vstack([bar, im]))
    gap = np.full((tiles[0].shape[0], 6, 3), 255, np.uint8)
    row = tiles[0]
    for c in tiles[1:]:
        row = np.hstack([row, gap, c])
    lab = np.full((row.shape[0], 150, 3), 255, np.uint8)
    cv2.putText(lab, label, (8, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return np.hstack([lab, row])


def main() -> int:
    probe = json.loads((BENCH / "work" / "boundary_refiner_probe.json").read_text(encoding="utf-8"))
    rows = probe["disputed"]
    min_shift = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    out = BENCH / "work" / "boundary_disputes"
    out.mkdir(parents=True, exist_ok=True)
    ff = FFmpegIO()
    made = []
    for r in rows:
        if abs(r["shift_frames"]) < min_shift:
            continue
        case = r["case"]
        vfps = probe["cases"][case]["vfps"]
        t_ours = r["boundary_s"]
        t_cm = t_ours + r["shift_s"]
        top = strip(ff, VIDEO[case], t_ours, "OURS %.2f" % t_ours, (0, 0, 200))
        bot = strip(ff, VIDEO[case], t_cm, "CM-H1 %.2f" % t_cm, (200, 0, 0))
        head = np.full((30, top.shape[1], 3), 255, np.uint8)
        cv2.putText(head, "%s  boundary=%.2fs  shift=%+d frames (%+.2fs)  diff@ours=%.1f diff@cm=%.1f  |  vfps=%.2f"
                    % (case, t_ours, r["shift_frames"], r["shift_s"], r["diff_at_ours"],
                       r["diff_at_cm"] or -1, vfps), (6, 21),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
        fn = out / ("%s_%.2fs_%+dfr.png" % (case, t_ours, r["shift_frames"]))
        cv2.imwrite(str(fn), np.vstack([head, top, np.full((6, top.shape[1], 3), 200, np.uint8), bot]))
        made.append(str(fn))
        print("saved %s" % fn)
    print("total %d sheets (min_shift=%d)" % (len(made), min_shift))
    return 0


if __name__ == "__main__":
    sys.exit(main())
