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
# 续54 补：当前阶段名（后处理三段是同步串行 ⇒ 用于把抓帧/嵌入账单按阶段归因）
STAGE = {"name": "other"}
# 续54 补：逐次抓帧目标清单（离线复算「并集合并 / 去重」能省多少 spawn 与解码秒数）
WINDOWS_LOG: list = []


def _count_clusters(uniq: list) -> int:
    """与 FFmpegIO.grab_frames 同口径的聚簇数（max_gap 4s / max_span 40s）。"""
    if not uniq:
        return 0
    n, c0, prev = 1, uniq[0], uniq[0]
    for t in uniq[1:]:
        if t - prev <= 4.0 and t - c0 <= 40.0:
            prev = t
        else:
            n += 1
            c0 = prev = t
    return n


def _span_s(uniq) -> float:
    u = sorted(float(t) for t in uniq)
    return round(u[-1] - u[0], 3) if len(u) > 1 else 0.0


def _add(key: str, dt: float, n: int = 0) -> None:
    cur = ACC.setdefault(key, {"s": 0.0, "n": 0})
    cur["s"] += dt
    cur["n"] += n


def _add_stage(base: str, dt: float, **counts) -> None:
    """按「阶段 × 计量项」记账（key = base@stage），counts 逐项累加到 .n/<字段>。"""
    key = "%s@%s" % (base, STAGE["name"])
    cur = ACC.setdefault(key, {"s": 0.0, "n": 0})
    cur["s"] += dt
    cur["n"] += 1
    for k, v in counts.items():
        cur[k] = cur.get(k, 0) + v


def _wrap(mod, name: str, key: str, count_arg=None, stage_name=None):
    """把模块级函数包成计时版（不改行为；异常原样抛出）。

    ``stage_name`` 非空时进入该阶段期间把 STAGE 切过去（抓帧/嵌入账单据此归因），
    嵌套调用时恢复外层值。
    """
    orig = getattr(mod, name)

    def _timed(*a, **kw):
        t0 = time.monotonic()
        prev = STAGE["name"]
        if stage_name:
            STAGE["name"] = stage_name
        try:
            return orig(*a, **kw)
        finally:
            STAGE["name"] = prev
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
    _wrap(LS, "apply_shot_split", "stage.shot_split", stage_name="shot_split")
    _wrap(LS, "apply_patch_refine", "stage.patch_refine", stage_name="patch_refine")
    _wrap(LS, "apply_isc_refine", "stage.isc_refine", stage_name="isc_refine")
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
    # --- 窗 spawn 级记账（续54）：grab_frames/_decode_window 次数·目标数·墙钟 ---
    import media.ffmpeg as _mf
    _orig_gf = _mf.FFmpegIO.grab_frames
    _orig_dw = _mf.FFmpegIO._decode_window

    def _gf_timed(self, path, times, **kw):
        t0 = time.monotonic()
        try:
            return _orig_gf(self, path, times, **kw)
        finally:
            uniq = sorted({round(float(t), 6) for t in times})
            WINDOWS_LOG.append({"stage": STAGE["name"], "file": Path(str(path)).name,
                                "targets": uniq})
            _add_stage("grab.frames_calls", time.monotonic() - t0,
                       targets=len(uniq), clusters=_count_clusters(uniq))

    def _dw_timed(self, path, ts_sorted, **kw):
        t0 = time.monotonic()
        try:
            return _orig_dw(self, path, ts_sorted, **kw)
        finally:
            _add_stage("grab.window_spawns", time.monotonic() - t0,
                       targets=len(ts_sorted),
                       span_s=_span_s(ts_sorted))

    _mf.FFmpegIO.grab_frames = _gf_timed
    _mf.FFmpegIO._decode_window = _dw_timed
    # 抓帧：源片 vs 编辑片（⚠️ orig 变量已被上方 _wrap 循环占用 ⇒ 从 CASES 重取）
    orig_cached = srv._grab_frame_cached
    src_key = str(Path(CASES[args.case][1]).resolve())

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

    # --- 逐帧嵌入记账（续54 补）：按帧对象 id 去重 ⇒ 重复嵌入比例（合并/缓存的收益上界）---
    from engine.localization.isc_refine import IscScorer as _ISC      # noqa: E402
    from engine.localization.patch_rerank import PatchReranker as _PR  # noqa: E402
    EMBED_SEEN: dict = {}

    def _wrap_embed(cls, meth, key):
        orig_m = getattr(cls, meth)

        def _t(self, frame, *a, **kw):
            t0 = time.monotonic()
            try:
                return orig_m(self, frame, *a, **kw)
            finally:
                k = "%s@%s" % (key, STAGE["name"])
                cur = ACC.setdefault(k, {"s": 0.0, "n": 0})
                cur["s"] += time.monotonic() - t0
                cur["n"] += 1
                seen = EMBED_SEEN.setdefault(k, set())
                if id(frame) in seen:
                    cur["dup"] = cur.get("dup", 0) + 1
                else:
                    seen.add(id(frame))
                    cur["distinct"] = cur.get("distinct", 0) + 1

        setattr(cls, meth, _t)

    _wrap_embed(_PR, "frame_dual", "embed.patch_dual")
    _wrap_embed(_ISC, "embed", "embed.isc")

    t_all = time.monotonic()
    batch = srv.locate(edited, CASES[args.case][1])
    total = time.monotonic() - t_all
    ACC["TOTAL"] = {"s": total, "n": len(batch.results)}
    # ISC embed 计数（由 isc_refine 内部调用）
    if getattr(srv, "_isc_scorer", None) is not None:
        ACC["isc_refine_device"] = {"s": 0.0, "n": 0, "device": srv._isc_scorer.device}

    OUT.mkdir(parents=True, exist_ok=True)
    rep = {"case": args.case, "grid": args.grid, "total_s": round(total, 1),
           "segments": len(batch.results),
           "acc": {k: {kk: (round(vv, 1) if isinstance(vv, float) else vv)
                       for kk, vv in v.items()} for k, v in ACC.items()}}
    print("\n=== 阶段账单（%.1fs / %d 段）===" % (total, len(batch.results)))
    for k, v in sorted(rep["acc"].items(), key=lambda kv: -kv[1]["s"]):
        print("  %-24s %8.1fs  %5.1f%%  n=%d" % (k, v["s"], 100.0 * v["s"] / max(1e-9, total), v["n"]))
    out = Path(args.out) if args.out else (OUT / ("timing_%s_grid%s.json" % (args.case, args.grid)))
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    wout = out.with_name(out.stem.replace("timing_", "windows_") + ".jsonl")
    with wout.open("w", encoding="utf-8") as fh:
        for rec in WINDOWS_LOG:
            fh.write(json.dumps(rec) + "\n")
    print("saved %s (+ %s, %d 次抓帧调用)" % (out, wout.name, len(WINDOWS_LOG)))
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
