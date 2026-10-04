# -*- coding: utf-8 -*-
"""locate 阶段级计时探针（2026-10-03 续51，回答「性能还能推进吗」）。

零 runtime 改动：monkey-patch 生产链路的阶段函数与两个 embed 入口，只加计时/计数，
不改任何语义（不替换实现，只包一层）。输出「每一层花了多少秒」的账单，用于决定下一刀砍哪里。

计量项：
  - analyze_edited_video（切分/取帧/编辑侧嵌入）
  - _embed_dense_query（编辑侧稠密帧）
  - shot_split 模块（两旋钮之一）
  - patch_refine 模块（两旋钮之二）
  - isc_refine 模块（宽扫，逐段累计，另记 embed 次数）
  - evidence/检索等其余（总量 - 以上）
  - 抓帧总时间与次数（按「源片 / 编辑片」分开），DINOv2 embed 与 ISC embed 的耗时与帧数

用法（venv 绝对路径 python，repo 根）:
  python mvp/scripts/probe_locate_stage_timing.py --case test1 [--grid on|off]
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
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np                                              # noqa: E402

from app import locator_service as LS                           # noqa: E402
from app.locator_service import SourceLocatorService            # noqa: E402
from device.directml_backend import DirectMLBackend             # noqa: E402
from infrastructure.config import load_config                   # noqa: E402

OUT = BENCH / "work" / "locate_timing"
CASES = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
ACC: dict = {}


def _add(key: str, dt: float, n: int = 0) -> None:
    cur = ACC.setdefault(key, {"s": 0.0, "n": 0})
    cur["s"] += dt
    cur["n"] += n


def _wrap(mod, name: str, key: str, count_arg=None):
    """把模块级函数包成计时版（不改行为；异常原样抛出）。"""
    orig = getattr(mod, name)

    def _timed(*a, **kw):
        t0 = time.monotonic()
        try:
            return orig(*a, **kw)
        finally:
            n = 0
            if count_arg is not None and len(a) > count_arg:
                try:
                    n = len(a[count_arg])
                except TypeError:
                    n = 0
            _add(key, time.monotonic() - t0, n)

    setattr(mod, name, _timed)
    return orig


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="test1", choices=sorted(CASES))
    ap.add_argument("--grid", default="on", choices=["on", "off"])
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    edited, orig = CASES[args.case]
    cfg = load_config()
    cfg.pipeline.grab_grid_decode = (args.grid == "on")
    srv = SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    print("BACKEND=%s grab_grid_decode=%s radius=%s"
          % (type(srv.backend).__name__, cfg.pipeline.grab_grid_decode,
             cfg.pipeline.isc_refine_scan_radius_s), flush=True)

    # --- 模块级阶段 ---
    _wrap(LS, "split_results", "stage.shot_split")
    _wrap(LS, "apply_patch_refine", "stage.patch_refine")
    _wrap(LS, "apply_isc_refine", "stage.isc_refine")
    # --- 服务方法级阶段 ---
    for meth, key in (("analyze_edited_video", "stage.analyze_edited"),
                      ("_embed_dense_query", "stage.embed_dense_query")):
        orig = getattr(SourceLocatorService, meth)

        def _mk(orig_fn, key_name):
            def _timed(self, *a, **kw):
                t0 = time.monotonic()
                try:
                    return orig_fn(self, *a, **kw)
                finally:
                    _add(key_name, time.monotonic() - t0)
            return _timed

        setattr(SourceLocatorService, meth, _mk(orig, key))
    # --- embed 入口 ---
    orig_embed = srv.backend.embed_frames

    def _embed_frames(frames, *a, **kw):
        t0 = time.monotonic()
        try:
            return orig_embed(frames, *a, **kw)
        finally:
            _add("embed.dinov2", time.monotonic() - t0, len(frames))

    srv.backend.embed_frames = _embed_frames
    # 抓帧：源片 vs 编辑片
    orig_cached = srv._grab_frame_cached
    src_key = str(Path(orig).resolve())

    def _grab(path, t):
        t0 = time.monotonic()
        try:
            return orig_cached(path, t)
        finally:
            k = "grab.source" if str(Path(path).resolve()) == src_key else "grab.edited"
            _add(k, time.monotonic() - t0, 1)

    srv._grab_frame_cached = _grab
    orig_batch = srv._grab_frames_parallel

    def _grab_batch(path, times):
        t0 = time.monotonic()
        try:
            return orig_batch(path, times)
        finally:
            k = "grab.source" if str(Path(path).resolve()) == src_key else "grab.edited"
            _add(k, time.monotonic() - t0, len(list(times)))

    srv._grab_frames_parallel = _grab_batch
    orig_grid = srv._grab_grid_batch

    def _grab_grid(path, times):
        t0 = time.monotonic()
        try:
            return orig_grid(path, times)
        finally:
            k = "grab.source_grid" if str(Path(path).resolve()) == src_key else "grab.edited_grid"
            _add(k, time.monotonic() - t0, len(list(times)))

    srv._grab_grid_batch = _grab_grid

    t_all = time.monotonic()
    batch = srv.locate(edited, orig)
    total = time.monotonic() - t_all
    ACC["TOTAL"] = {"s": total, "n": len(batch.results)}
    # ISC embed 计数（由 isc_refine 内部调用）
    if getattr(srv, "_isc_scorer", None) is not None:
        ACC["isc_refine_device"] = {"s": 0.0, "n": 0, "device": srv._isc_scorer.device}

    OUT.mkdir(parents=True, exist_ok=True)
    rep = {"case": args.case, "grid": args.grid, "total_s": round(total, 1),
           "segments": len(batch.results), "acc": {k: {"s": round(v["s"], 1), "n": v["n"]}
                                                  for k, v in ACC.items()}}
    print("\n=== 阶段账单（%.1fs / %d 段）===" % (total, len(batch.results)))
    for k, v in sorted(rep["acc"].items(), key=lambda kv: -kv[1]["s"]):
        print("  %-24s %8.1fs  %5.1f%%  n=%d" % (k, v["s"], 100.0 * v["s"] / max(1e-9, total), v["n"]))
    out = Path(args.out) if args.out else (OUT / ("timing_%s_grid%s.json" % (args.case, args.grid)))
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved %s" % out)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
