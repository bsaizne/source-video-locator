# -*- coding: utf-8 -*-
"""为 44 张盲判图补一条客观旁证: 每个候选时刻的「跨点帧差 vs 同侧基线帧差」。

判据(仅作旁证, 不代替读图): 真切换处 |f(t-0.07)-f(t+0.07)| 应显著大于同侧 |f(t-0.20)-f(t-0.07)|。
输出 work/proxy_blind_disputes/frame_diff_sidechannel.json
"""
from __future__ import annotations
import json, os, sys
from pathlib import Path
import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
D = BENCH / "work" / "proxy_blind_disputes"
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
from media.ffmpeg import FFmpegIO  # noqa
import cv2

VIDEO = {"2mkv": r"D:\video\1.mp4", "test1": r"D:\ProjectXIXI\test1\test1-ed.mp4",
         "test2": r"D:\ProjectXIXI\test2\tset2-ed.mp4", "test3": r"D:\ProjectXIXI\test3\test3-ed.mp4"}


def gray(ff, path, t):
    img = np.asarray(ff.grab_frame(Path(path), max(0.0, t)))
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return cv2.resize(g, (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32)


def main():
    key = json.load(open(D / "blind_key.json", encoding="utf-8"))["sheets"]
    ff = FFmpegIO()
    out = []
    for i, s in enumerate(key, 1):
        case = s["case"]
        v = VIDEO[case]
        rec = {"sheet": s["sheet"], "case": case, "kind": s["kind"], "A": s["A"], "B": s["B"]}
        for side in ("A", "B"):
            t = s["ours_s"] if s[side] == "ours" else s["theirs_s"]
            a = gray(ff, v, t - 0.20)
            b = gray(ff, v, t - 0.07)
            c = gray(ff, v, t + 0.07)
            d = gray(ff, v, t + 0.20)
            across = float(np.abs(b - c).mean())
            ctrl_lo = float(np.abs(a - b).mean())
            ctrl_hi = float(np.abs(c - d).mean())
            ctrl = max(ctrl_lo, ctrl_hi, 0.25)
            rec[side] = {"t": round(t, 3), "side": s[side], "across": round(across, 2),
                         "ctrl": round(ctrl, 2), "ratio": round(across / ctrl, 2),
                         "ctrl_lo": round(ctrl_lo, 2), "ctrl_hi": round(ctrl_hi, 2)}
        out.append(rec)
        print("%2d/%d %-22s A(%-6s t=%.2f) across=%.1f ctrl=%.1f r=%.2f | B(%-6s t=%.2f) across=%.1f ctrl=%.1f r=%.2f" % (
            i, len(key), s["sheet"], s["A"], rec["A"]["t"], rec["A"]["across"], rec["A"]["ctrl"], rec["A"]["ratio"],
            s["B"], rec["B"]["t"], rec["B"]["across"], rec["B"]["ctrl"], rec["B"]["ratio"]), flush=True)
    (D / "frame_diff_sidechannel.json").write_text(json.dumps(
        {"note": "across = |f(t-0.07)-f(t+0.07)| 均值(96x54 灰度); ctrl = max(|f(t-0.20)-f(t-0.07)|, |f(t+0.07)-f(t+0.20)|, 0.25); ratio = across/ctrl",
         "rows": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved frame_diff_sidechannel.json")


if __name__ == "__main__":
    main()