# -*- coding: utf-8 -*-
"""抓帧管道模式 A/B 探针（2026-10-03 续50，L1 验收）。

对照生产形状：**180s 窗、2s 网格（91 点）= ISC 宽扫粗扫的真实调用形态**。
四模式同窗口同目标跑一遍，逐点比帧（像素差）+ 比 ISC 余弦 + 比墙钟：

  base        = grab_frames（现役窗解码：读全部解码帧的原始 BGR）
  grid        = grab_grid（select 抽取：只吐网格帧，原始分辨率）
  grid512     = grab_grid + scale=512:512（消费者侧预缩放）
  grid512fps  = grab_grid 的 fps 变体（仅作对照：已知 fps 会重定时间轴，不应采用）

用法:
  python mvp/scripts/probe_grab_pipe_modes.py --source test1 --t0 1382.5 --span 180 --step 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402

from media.ffmpeg import FFmpegIO                                  # noqa: E402
from engine.localization.isc_refine import IscScorer               # noqa: E402

OUT = BENCH / "work" / "grab_pipe_ab"
SOURCES = {
    "2mkv": r"D:\video\2.mkv",
    "test1": r"D:\ProjectXIXI\test1\test1-om.mkv",
    "test2": r"D:\ProjectXIXI\test2\test2-om.mp4",
    "test3": r"D:\ProjectXIXI\test3\test3-om.mp4",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="test1", choices=sorted(SOURCES))
    ap.add_argument("--file", default=None, help="直接指定输入文件（覆盖 --source）")
    ap.add_argument("--t0", type=float, default=1382.5, help="窗起点（实测用任意相位）")
    ap.add_argument("--span", type=float, default=180.0)
    ap.add_argument("--step", type=float, default=2.0)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    src = args.file or SOURCES[args.source]
    n = int(args.span / args.step) + 1
    times = [round(args.t0 + i * args.step, 6) for i in range(n)]
    ff = FFmpegIO()
    OUT.mkdir(parents=True, exist_ok=True)
    rep = {"source": src, "t0": args.t0, "span": args.span, "step": args.step,
           "points": n, "modes": {}, "caliber": (
               "同一窗/同一目标；base=现役窗解码；grid=select 抽取；grid512=+scale=512:512；"
               "gridfps=fps 变体（对照，已知重定时间轴）")}

    t = time.time()
    base = ff.grab_frames(Path(src), times)
    rep["modes"]["base"] = {"wall_s": round(time.time() - t, 2), "n": len(base)}
    print("[base] %.1fs n=%d" % (rep["modes"]["base"]["wall_s"], len(base)), flush=True)

    modes = [
        ("grid", dict(filters=None, size=None)),
        ("grid512", dict(filters=None, size=(512, 512))),
        ("gridfps", dict(filters="fps=%g" % (1.0 / args.step), size=None)),
    ]
    frames = {"base": base}
    for name, kw in modes:
        t = time.time()
        got = ff.grab_grid(Path(src), args.t0, args.step, n, **kw)
        wall = time.time() - t
        frames[name] = got
        rep["modes"][name] = {"wall_s": round(wall, 2), "n": len(got),
                              "speedup_vs_base": round(rep["modes"]["base"]["wall_s"] / max(1e-6, wall), 2)}
        print("[%s] %.1fs n=%d speedup=%.2fx" % (name, wall, len(got),
              rep["modes"][name]["speedup_vs_base"]), flush=True)

    # ---- 逐点像素差（同 t 对 base） ----
    for name, kw in modes:
        diffs, cover = [], 0
        for tt in times:
            a, b = base.get(tt), frames[name].get(tt)
            if a is None or b is None:
                continue
            cover += 1
            if b.shape != a.shape:
                diffs.append(255)
            else:
                diffs.append(float(np.abs(a.astype(np.int16) - b.astype(np.int16)).max()))
        d = np.asarray(diffs, dtype=np.float64) if diffs else np.zeros(1)
        rep["modes"][name].update({
            "compared": cover,
            "max_pixel_diff": float(d.max()),
            "mean_max_diff": round(float(d.mean()), 2),
            "n_exact_like": int((d < 40).sum()),
            "n_identical": int((d == 0).sum())})
        print("  %-8s 逐点 max|Δ|: 最大 %3.0f 均值 %5.2f  完全同帧 %d/%d  (<40 视作同帧)"
              % (name, d.max(), d.mean(), int((d == 0).sum()), cover), flush=True)

    # ---- ISC 余弦（同 t 对 base） ----
    sc = IscScorer()
    if sc.ensure():
        for name, kw in modes[:2] + [modes[2]]:
            cs = []
            for tt in times:
                a, b = base.get(tt), frames[name].get(tt)
                if a is None or b is None:
                    continue
                va = np.asarray(sc.embed(a), dtype=np.float64)
                vb = np.asarray(sc.embed(b), dtype=np.float64)
                cs.append(float(np.dot(va, vb) / max(1e-9, np.linalg.norm(va) * np.linalg.norm(vb))))
            c = np.asarray(cs) if cs else np.zeros(1)
            rep["modes"][name]["isc_cos_min"] = round(float(c.min()), 6)
            rep["modes"][name]["isc_cos_mean"] = round(float(c.mean()), 6)
            print("  %-8s ISC cos: min %.6f mean %.6f (n=%d)" % (name, c.min(), c.mean(), len(cs)),
                  flush=True)
    else:
        rep["isc"] = "asset missing"

    out = Path(args.out) if args.out else (OUT / ("ab_%s_%s_s%g.json"
                                                  % (args.source, str(args.t0).replace(".", "p"), args.step)))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved %s" % out)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
