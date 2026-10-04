# -*- coding: utf-8 -*-
"""ISC 源片索引构建（2026-10-03 续52，L2 的第一步：把「每次定位重复扫 + 重复解 180s 窗」换成
「每部母片一次顺序解码 + 一张 1s 网格 ISC 表」）。

为什么这么建：
  - 顺序解码（iter_frames，整片一次流式）远比「每段随机 seek 180s 窗」便宜（实测顺序 26~27× 实时，
    随机窗 21× 实时，且窗之间大量重叠 ⇒ 生产里同一秒被重复解码多次）。
  - 网格抓帧安全网（续51）保证 1s 网格帧与冻结契约一致；这里直接用 iter_frames（顺序流式）更省。
  - ⚠️ 续52-C 实测：iter_frames 的合成标签（timestamp = start + i/fps）比帧的真实 pts 晚 ~0.5s
    （fps 滤镜语义），切点处索引帧与扫描帧是两幅画面 ⇒ truepts 模式改用 L1 grab_grid（select 抽取，
    真实 pts + first_ge，与扫描侧 grab_frame 逐字节同帧）。L2 接线以 truepts 索引为准。

产物：npz（times / feats / meta），meta 记源片 sha256、ISC onnx 路径、fps、维度、device。

用法（venv 绝对路径 python，repo 根）:
  python mvp/scripts/build_isc_index.py --source test1 [--fps 1.0] [--limit-s 0]
"""
from __future__ import annotations

import argparse
import hashlib
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
sys.path.insert(0, str(BENCH / "mvp"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np                                              # noqa: E402

from media.ffmpeg import FFmpegIO                                # noqa: E402
from engine.localization.isc_refine import IscScorer, resolve_isc_onnx   # noqa: E402
from engine.localization.isc_l2_index import build_tp_index              # noqa: E402

OUT = BENCH / "work" / "isc_source_index"
SOURCES = {
    "2mkv": r"D:\video\2.mkv",
    "test1": r"D:\ProjectXIXI\test1\test1-om.mkv",
    "test2": r"D:\ProjectXIXI\test2\test2-om.mp4",
    "test3": r"D:\ProjectXIXI\test3\test3-om.mp4",
}


def _sha256(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True, choices=sorted(SOURCES))
    ap.add_argument("--fps", type=float, default=1.0)
    ap.add_argument("--limit-s", type=float, default=0.0, help="只建前 N 秒（调试用）")
    ap.add_argument("--sampling", choices=["seq", "truepts"], default="seq",
                    help="seq = iter_frames 合成标签（首版，标签比真实 pts 晚 ~0.5s，续52-C 实测）；"
                         "truepts = grab_grid select 抽取（真实 pts + first_ge，与扫描侧同一取帧契约）")
    args = ap.parse_args()
    src = Path(SOURCES[args.source])
    io = FFmpegIO()
    scorer = IscScorer()
    if not scorer.ensure():
        print("ISC 资产缺失", flush=True)
        return 2
    print("[build] source=%s fps=%g isc_device=%s sampling=%s"
          % (src.name, args.fps, scorer.device, args.sampling), flush=True)

    times: list = []
    feats: list = []
    t0 = time.monotonic()
    meta: dict = {}
    if args.sampling == "truepts":
        # 真实 pts 取帧：目标网格 = k/fps，L1 网格抽取（select 只吐网格帧，管道 ÷~30；
        # first_ge 冻结契约 ⇒ 帧内容与扫描侧 grab_frame(t) 逐字节一致，续52-C 对齐双时间系统）。
        # 2026-10-05 起委托 engine.localization.isc_l2_index.build_tp_index（与 runtime 自动
        # 建表同一实现：逐簇流式嵌入 + 目标网格按最后一个视频帧 pts 截断——test1-om 尾部
        # 音频比最后一帧视频晚 8.4s，旧「整表逐目标重试」每目标全片重复解码 ⇒ 2.57 帧/s）。
        def _on_frame(done: int, total: int) -> None:
            el = time.monotonic() - t0
            print("  %d/%d 帧  %.0fs  (%.1f 帧/s)" % (done, total, el, done / max(1e-9, el)),
                  flush=True)

        T, F, meta = build_tp_index(src, ffmpeg=io, scorer=scorer, fps=args.fps,
                                    limit_s=args.limit_s, on_frame=_on_frame)
        times = T.tolist()
        feats = F
        wall = time.monotonic() - t0
    else:
        end = args.limit_s if args.limit_s > 0 else None
        for t, frame in io.iter_frames(src, args.fps, end=end):
            times.append(round(float(t), 6))
            feats.append(np.asarray(scorer.embed(frame), dtype=np.float32))
            if len(times) % 500 == 0:
                el = time.monotonic() - t0
                print("  %d 帧  %.0fs  (%.1f 帧/s)" % (len(times), el, len(times) / max(1e-9, el)),
                      flush=True)
        wall = time.monotonic() - t0
    F = np.asarray(feats, dtype=np.float32)
    T = np.asarray(times, dtype=np.float64)
    assert F.shape[0] == T.shape[0] and F.shape[0] > 0
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "" if args.sampling == "seq" else ".tp"
    out = OUT / ("%s@%.3ffps%s.isci.npz" % (src.stem, args.fps, tag))
    if not meta:
        meta = {"source": str(src), "source_sha256": _sha256(src), "fps": args.fps,
                "sampling": args.sampling, "device": scorer.device,
                "isc_onnx": resolve_isc_onnx(), "limit_s": args.limit_s,
                "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    else:
        meta["isc_onnx"] = resolve_isc_onnx()
    meta["wall_s"] = round(wall, 1)
    meta["build_fps"] = round(F.shape[0] / max(1e-9, wall), 2)
    meta["frames"] = int(F.shape[0])
    meta["dim"] = int(F.shape[1])
    np.savez_compressed(out, times=T, feats=F, meta=json.dumps(meta, ensure_ascii=False))
    print("[build] %d 帧 / %.1fs (%.1f 帧/s) → %s (%.1f MB)"
          % (F.shape[0], wall, F.shape[0] / max(1e-9, wall), out.name,
             out.stat().st_size / 1e6), flush=True)
    print("META " + json.dumps(meta, ensure_ascii=False))
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
