# -*- coding: utf-8 -*-
"""L2 对照探针：ISC「源片索引 matmul」 vs 现役「每段 ±90s 窗扫」（2026-10-03 续52）。

目的：L2 把宽扫从「每段抓 91 点 + 91 次 ISC 推理」换成「一次 matmul」，前提是**峰值不丢**。
本探针在同一批段上把两种扫法的**最优峰位置/分数**对齐比较，给出 |Δt| 分布与不一致清单。
两边查询特征完全相同（同 3 帧 ED ISC 均值），差异只来自「源侧候选怎么取」。

用法:
  python mvp/scripts/probe_l2_index_replay.py --case test1 --sample 20
"""
from __future__ import annotations

import argparse
import json
import os
import sys
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
from engine.localization.isc_refine import (                      # noqa: E402
    IscScorer, N_QUERY, ISC_STEP, WIDE_COARSE_STEP, WIDE_TOPK, WIDE_REFINE_S)

CASES = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv", "v2_2mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv", "v2_test1"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4", "v2_test2"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4", "v2_test3"),
}
OUT = BENCH / "work" / "isc_source_index"


def _mean_q(scorer, io, edited, ets):
    frames = io.grab_frames(Path(edited), list(ets))
    vs = [np.asarray(scorer.embed(frames[round(float(t), 6)]), dtype=np.float64) for t in ets]
    v = np.mean(vs, axis=0)
    return v / max(1e-9, float(np.linalg.norm(v)))


def scan_window(scorer, io, src, main_mid, radius, q):
    """复刻 isc_refine v2 宽扫：粗步长 WIDE_COARSE_STEP + top-k 峰 ±WIDE_REFINE_S @1s 细化。"""
    lo, hi = max(0.0, main_mid - radius), main_mid + radius
    n_c = max(2, int(np.ceil((hi - lo) / WIDE_COARSE_STEP)) + 1)
    coarse = sorted({round(lo + (hi - lo) * i / (n_c - 1), 3) for i in range(n_c)})
    fr = io.grab_frames(Path(src), coarse)
    cache = {t: np.asarray(scorer.embed(fr[t]), dtype=np.float64)
             for t in coarse if t in fr}

    def sc(t):
        return float(cache[t] @ q)

    best_t, best_s = None, -1.0
    for t0 in sorted(cache, key=sc, reverse=True)[:WIDE_TOPK]:
        rlo, rhi = max(0.0, t0 - WIDE_REFINE_S), t0 + WIDE_REFINE_S
        n_f = max(2, int(np.ceil((rhi - rlo) / ISC_STEP)))
        fine = sorted({round(rlo + (rhi - rlo) * (i + 0.5) / n_f, 3) for i in range(n_f)})
        miss = [t for t in fine if t not in cache]
        if miss:
            fr2 = io.grab_frames(Path(src), miss)
            for t in miss:
                if t in fr2:
                    cache[t] = np.asarray(scorer.embed(fr2[t]), dtype=np.float64)
        for t in fine:
            if t in cache and sc(t) > best_s:
                best_s, best_t = sc(t), t
    return best_t, best_s, len(cache)


def scan_index(times, feats, main_mid, radius, q):
    if radius > 0:
        m = np.abs(times - main_mid) <= radius
    else:
        m = np.ones_like(times, dtype=bool)
    tt, ff = times[m], feats[m]
    if tt.size == 0:
        return None, -1.0, 0
    s = ff @ q
    i = int(np.argmax(s))
    return float(tt[i]), float(s[i]), int(tt.size)


def scan_l2(scorer, io, src, times, feats, main_mid, radius, q,
            topk=None, refine_s=None):
    """L2 接线形态：索引 matmul 粗扫 → top-K 峰 ±refine_s 局部精扫（真帧）。
    缺省镜像生产 v2 `_refine_topk`（WIDE_TOPK / WIDE_REFINE_S / ISC_STEP）。"""
    topk = WIDE_TOPK if topk is None else topk
    refine_s = WIDE_REFINE_S if refine_s is None else refine_s
    if radius > 0:
        m = np.abs(times - main_mid) <= radius
    else:
        m = np.ones_like(times, dtype=bool)
    tt, ff = times[m], feats[m]
    if tt.size == 0:
        return None, -1.0, 0
    s = ff @ q
    order = np.argsort(-s)[:topk]
    best_t, best_s = None, -1.0
    cache = {}
    for k in order:
        p = float(tt[k])
        rlo, rhi = max(0.0, p - refine_s), p + refine_s
        n_f = max(2, int(np.ceil((rhi - rlo) / ISC_STEP)))
        fine = sorted({round(rlo + (rhi - rlo) * (i + 0.5) / n_f, 3) for i in range(n_f)})
        miss = [t for t in fine if t not in cache]
        if miss:
            fr = io.grab_frames(Path(src), miss)
            for t in miss:
                if t in fr:
                    cache[t] = float(np.asarray(scorer.embed(fr[t]), dtype=np.float64) @ q)
        for t in fine:
            if t in cache and cache[t] > best_s:
                best_s, best_t = cache[t], t
    if best_t is None:
        best_t, best_s = float(tt[int(np.argmax(s))]), float(np.max(s))
    return best_t, best_s, int(tt.size)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", default="test1", choices=sorted(CASES))
    ap.add_argument("--index", default=None)
    ap.add_argument("--sample", type=int, default=20)
    ap.add_argument("--radius", type=float, default=90.0)
    ap.add_argument("--l2-topk", type=int, default=None)
    ap.add_argument("--l2-refine-s", type=float, default=None)
    ap.add_argument("--mode", choices=["window", "l2"], default="window",
                    help="window = 索引 matmul vs 现役窗扫复刻；l2 = 接线形态"
                         "（索引粗扫 top-K → 局部精扫真帧）vs 现役窗扫复刻")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    edited, src, arm = CASES[args.case]
    idx_p = Path(args.index) if args.index else (OUT / ("%s@1.000fps.isci.npz" % Path(src).stem))
    if not idx_p.exists():
        print("索引不存在：%s（先跑 build_isc_index.py）" % idx_p, flush=True)
        return 2
    z = np.load(idx_p, allow_pickle=True)
    times = np.asarray(z["times"], dtype=np.float64)
    feats = np.asarray(z["feats"], dtype=np.float64)
    print("[replay] index=%s frames=%d dim=%d"
          % (idx_p.name, times.size, feats.shape[1]), flush=True)
    io = FFmpegIO()
    scorer = IscScorer()
    if not scorer.ensure():
        return 2
    res = json.loads((BENCH / "work" / "isc_refine_arms" / (arm + ".results.json"))
                     .read_text(encoding="utf-8"))["results"]
    rows = [r for r in res
            if (r["original"]["candidate_end"] - r["original"]["candidate_start"]) > 0.01
            and not r.get("not_in_source") and not r.get("excluded")
            and not r.get("manual_override")]
    step = max(1, len(rows) // max(1, args.sample))
    pick = [(i, r) for i, r in enumerate(rows)][::step][:args.sample]
    out_rows = []
    for i, r in pick:
        e0, e1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        w = e1 - e0
        ets = [e0 + w * (k + 0.5) / N_QUERY for k in range(N_QUERY)]
        q = _mean_q(scorer, io, edited, ets)
        main_mid = (r["original"]["candidate_start"] + r["original"]["candidate_end"]) / 2
        if args.mode == "l2":
            t_i, s_i, n_i = scan_l2(scorer, io, src, times, feats, main_mid, args.radius, q,
                                    topk=args.l2_topk, refine_s=args.l2_refine_s)
            t_w, s_w, n_w = t_i, s_i, n_i      # l2 模式不再复跑窗扫（对照列 = 生产 main）
        else:
            t_i, s_i, n_i = scan_index(times, feats, main_mid, args.radius, q)
            t_w, s_w, n_w = scan_window(scorer, io, src, main_mid, args.radius, q)
        dt = None if (t_i is None or t_w is None) else round(t_i - t_w, 3)
        out_rows.append({"seg": i, "main_mid": round(main_mid, 2), "index_t": t_i,
                         "window_t": t_w, "index_score": round(s_i, 4),
                         "window_score": round(s_w, 4), "dt": dt,
                         "index_pts": n_i, "window_pts": n_w})
        print("  seg=%-3d main=%-9.2f index=%-9.2f(%.4f) window=%-9.2f(%.4f) dt=%s"
              % (i, main_mid, t_i, s_i, t_w, s_w, dt), flush=True)
    dts = np.asarray([abs(x["dt"]) for x in out_rows if x["dt"] is not None])
    rep = {"case": args.case, "index": str(idx_p), "radius": args.radius, "rows": out_rows,
           "summary": {"n": len(out_rows),
                       "dt_abs_median": float(np.median(dts)) if dts.size else None,
                       "dt_abs_max": float(dts.max()) if dts.size else None,
                       "n_dt_gt_2": int((dts > 2.0).sum()) if dts.size else 0,
                       "window_pts_median": int(np.median([x["window_pts"] for x in out_rows]))}}
    print("\n[summary] " + json.dumps(rep["summary"], ensure_ascii=False))
    op = Path(args.out) if args.out else (OUT / ("replay_%s.json" % args.case))
    op.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved %s" % op)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
