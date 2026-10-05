# -*- coding: utf-8 -*-
"""patch_refine 窗形状 micro A/B（2026-10-05 续54 补二）：现役窗解码 vs 网格抽取。

形状取自真实账单 `work/locate_timing/windows_*.jsonl` 的 patch_refine 条目
（134 次调用 / 跨度中位 9.00s / 步长恰为 1.0 ⇒ 整数秒网格，续50 已证该类网格逐字节同帧）；
或 `--mode synth` = 在任意源片上合成同形状窗（跨片/跨编码验证相位契约是否仍成立）。

判据：① 逐点帧**逐字节相等**（不等 = 该形状不可零语义接线）② 墙钟比。
用法: python mvp/scripts/probe_patch_grid_shape.py [--case test1] [--n 12] [--mode real|synth]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np                                                # noqa: E402

from media.ffmpeg import FFmpegIO                                 # noqa: E402

SRC = {
    "test1": r"D:\ProjectXIXI\test1\test1-om.mkv",
    "2mkv": r"D:\video\2.mkv",
    "test2": r"D:\ProjectXIXI\test2\test2-om.mp4",
    "test3": r"D:\ProjectXIXI\test3\test3-om.mp4",
}
OUT = BENCH / "work" / "patch_grid_shape"


def _synth_windows(io, src, n, seed):
    """合成与生产同形状的窗：起点带三位小数相位、步长恰 1.0s、10 点（= patch_refine 形态）。"""
    import random

    info = io.metadata(src)
    rng = random.Random(seed)
    wins = []
    while len(wins) < n:
        t0 = round(rng.uniform(1.0, max(11.0, info.duration - 15.0)), 3)
        wins.append([round(t0 + 0.5 + i * 1.0, 3) for i in range(10)])
    return wins


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="test1", choices=sorted(SRC))
    ap.add_argument("--jsonl", default=str(BENCH / "work" / "locate_timing"
                                           / "windows_test1_post54.jsonl"))
    ap.add_argument("--n", type=int, default=12)
    ap.add_argument("--mode", default="real", choices=["real", "synth"])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    io = FFmpegIO()
    src = SRC[args.case]
    if args.mode == "synth":
        wins = _synth_windows(io, src, args.n, args.seed)
    else:
        recs = [json.loads(l) for l in Path(args.jsonl).read_text(encoding="utf-8")
                .splitlines() if l.strip()]
        wins = [r["targets"] for r in recs if r["stage"] == "patch_refine"
                and len(r["targets"]) >= 8][-args.n:]
    OUT.mkdir(parents=True, exist_ok=True)
    tot = {"base": 0.0, "grid": 0.0}
    mism = 0
    rows = []
    for ts in wins:
        t0 = time.monotonic()
        base = io.grab_frames(src, ts)
        tb = time.monotonic() - t0
        t0 = time.monotonic()
        grid = io.grab_grid_times(src, ts)
        tg = time.monotonic() - t0
        bad = [t for t in base if not np.array_equal(base[t], grid.get(t, np.array([])))]
        mism += len(bad)
        tot["base"] += tb
        tot["grid"] += tg
        rows.append({"t0": ts[0], "n": len(ts), "base_s": round(tb, 3),
                     "grid_s": round(tg, 3), "n_mismatch": len(bad)})
        print("win %8.3f n=%d base %.3fs grid %.3fs  不同帧 %d" %
              (ts[0], len(ts), tb, tg, len(bad)), flush=True)
    rep = {"case": args.case, "mode": args.mode, "windows": len(wins),
           "points": sum(len(w) for w in wins),
           "totals_s": {k: round(v, 2) for k, v in tot.items()},
           "speedup": round(tot["base"] / max(tot["grid"], 1e-9), 3),
           "n_frame_mismatch": mism, "rows": rows}
    (OUT / ("shape_%s_%s.json" % (args.case, args.mode))).write_text(
        json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("case", "mode", "windows", "points", "totals_s",
                                          "speedup", "n_frame_mismatch")}, ensure_ascii=False))
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
