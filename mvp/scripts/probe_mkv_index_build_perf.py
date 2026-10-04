# -*- coding: utf-8 -*-
"""mkv 建表性能归因探针（2026-10-05）：为什么 select 网格抽取在 mkv 上 ~3 帧/s 而 mp4 11~16 帧/s？
只读不改零 runtime。三组对照：
  A 解码地板：-ss 后 -t 60 纯解码（null muxer）
  B select 网格抽取 60 帧：FFmpegIO.grab_grid（生产建表同路径）
  C iter_frames 顺序解码 60 帧（seq 快路径基线）
"""
import os
import subprocess
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from media.ffmpeg import FFmpegIO  # noqa: E402

SOURCES = {
    "test1(mkv)": r"D:\ProjectXIXI\test1\test1-om.mkv",
    "2mkv": r"D:\video\2.mkv",
    "test2(mp4)": r"D:\ProjectXIXI\test2\test2-om.mp4",
}
AT = 3600.0
N = 60

io = FFmpegIO()
ff = str(io.ffmpeg)

for name, src in SOURCES.items():
    print(f"== {name}", flush=True)
    # A 解码地板（输入 seek 后 60s 纯解码）
    t0 = time.monotonic()
    subprocess.run([ff, "-v", "error", "-ss", str(AT), "-i", src, "-t", "60",
                    "-map", "0:v:0", "-f", "null", "-"],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    dtA = time.monotonic() - t0
    # B select 网格抽取（生产建表路径，600s 簇形态 = max_span 600）
    t0 = time.monotonic()
    try:
        g = io.grab_grid(src, AT, 1.0, N, max_span_s=600.0)
        dtB = time.monotonic() - t0
        okB = len(g)
    except Exception as exc:
        dtB, okB = float("nan"), f"FAIL {exc}"
    # C 顺序解码 60 帧网格（seq 快路径）
    t0 = time.monotonic()
    cnt = 0
    for _t, _f in io.iter_frames(src, 1.0, start=AT):
        cnt += 1
        if cnt >= N:
            break
    dtC = time.monotonic() - t0
    print("  A 解码地板60s   %.2fs (%.1fx 实时)" % (dtA, 60 / max(dtA, 1e-9)))
    print("  B grab_grid60帧 %.2fs (%.1f 帧/s) got=%s" % (dtB, N / max(dtB, 1e-9), okB))
    print("  C iter_frames60帧 %.2fs (%.1f 帧/s) got=%d" % (dtC, cnt / max(dtC, 1e-9), cnt), flush=True)
print("PROBE_DONE")
