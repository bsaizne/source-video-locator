"""研究原型 — 蒙太奇多段定位（query-axis clustering + gating + per-cluster finloc）。

机制（对齐已证实的查询轴簇结构实验）：
  1. 对每个查询单元，逐查询帧取全索引最佳匹配原片时间 + 相似度。
  2. 按时间间隔切簇，滤出"显著"簇（>=MIN_FRAMES 帧 且 簇均值 best_sim >= MIN_SIM）。
  3. 门控：>=2 个显著簇 -> 蒙太奇 -> 对每簇用该簇的查询帧在 [簇min-pad, 簇max+pad] 窗内
     跑 finloc -> 子 span（多段输出）；否则 -> 单段（保持现状单 span）。
  4. 输出：每段 (mode, 子span列表〔edited 子区间 + original 子span + cover + best_sim〕)。

只做**观测/原型**，不接入 runtime；验证 mvp/benchmark/user_case 的 12 段。
运行（venv python）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_montage_localize.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app import SourceLocatorService
from domain import Candidate
from engine.common import cosine_similarity
from engine.localization.finloc import finloc_window
from media.ffmpeg import FFmpegIO

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
EDIT = Path("D:/video/1.mp4")
ORIG = Path("D:/video/2.mkv")
APP_INDEX_ROOT = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
APP_MODEL = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                 "dinov2_cls_384/dinov2_cls_384.onnx")
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "montage_research"

CLUSTER_GAP_S = 30.0
MIN_FRAMES = 3
MIN_SIM = 0.45
PAD_S = 15.0
# 弱簇丢弃：cover < WEAK_COVER 且 best_sim < WEAK_SIM（双低=明确噪声）；单低保留（真实部分子镜头）
WEAK_COVER = 0.35
WEAK_SIM = 0.55


def cluster_times(times, gap):
    if len(times) == 0:
        return []
    order = np.argsort(times)
    st = times[order]
    breaks = np.where(np.diff(st) > gap)[0]
    clusters, start = [], 0
    for b in breaks:
        seg = st[start:b + 1]
        clusters.append((float(seg.min()), float(seg.max()), int(seg.size)))
        start = b + 1
    seg = st[start:]
    clusters.append((float(seg.min()), float(seg.max()), int(seg.size)))
    return clusters


def robust_span(times, lo_pct=5.0, hi_pct=95.0):
    """簇内最佳匹配时间的稳健范围 [p5, p95]（鲁棒于 1-2 帧离群）。"""
    if len(times) == 0:
        return None
    return (round(float(np.percentile(times, lo_pct)), 2),
            round(float(np.percentile(times, hi_pct)), 2))


def finloc_cluster(cluster_idx, cluster_best_t, q, tq, bundle, lo, hi):
    """子 span = 簇最佳匹配范围[min,max] ∪ finloc run 的凸包（既有对齐又有宽度）。"""
    qc = q[cluster_idx]
    sel = (bundle.times >= lo) & (bundle.times <= hi)
    r_idx = np.where(sel)[0]
    rfeats = bundle.features[r_idx[0]:r_idx[-1] + 1]
    rtimes = bundle.times[r_idx[0]:r_idx[-1] + 1]
    cand = Candidate(start=float(rtimes[0]), end=float(rtimes[-1]),
                     width=float(rtimes[-1] - rtimes[0]), peak_sim=0.0, mean_sim=0.0,
                     consistency=0.0, hit_count=0, n_reps=0, qcov=0.0, sim_std=0.0,
                     rank_score=0.0, best_cover=0.0, scene_div=0)
    loc = finloc_window(cand, qc, rfeats, rtimes)
    c_min, c_max = float(cluster_best_t.min()), float(cluster_best_t.max())
    if loc.span is not None:
        span = (round(min(c_min, loc.span[0]), 2), round(max(c_max, loc.span[1]), 2))
    else:
        span = robust_span(cluster_best_t)
    ed_times = sorted(float(t) for t in tq[cluster_idx])
    ed_lo, ed_hi = ed_times[0], ed_times[-1]
    return (span, loc.best_cover, loc.mean_sim, int(len(cluster_idx)),
            (round(ed_lo, 2), round(ed_hi, 2)), [round(t, 2) for t in ed_times])


def main() -> int:
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    svc = SourceLocatorService(ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                               index_root=APP_INDEX_ROOT, export_root=OUT)
    bundle = svc.build_original_index(ORIG)
    shots = svc.analyze_edited_video(EDIT)
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, shot in enumerate(shots):
        q, tq = shot.feats, shot.times
        sim = cosine_similarity(q, bundle.features)
        best = np.argmax(sim, axis=1)
        best_t = bundle.times[best]
        best_s = sim[np.arange(q.shape[0]), best]
        clusters = cluster_times(best_t, CLUSTER_GAP_S)
        sig = []
        for (c0, c1, cnt) in clusters:
            mask = (best_t >= c0) & (best_t <= c1)
            cidx = np.where(mask)[0]
            if cnt >= MIN_FRAMES and float(best_s[cidx].mean()) >= MIN_SIM:
                sig.append((c0, c1, cnt, cidx))
        if len(sig) >= 2:
            mode = "montage"
            subs = []
            for (c0, c1, cnt, cidx) in sig:
                lo, hi = max(0.0, c0 - PAD_S), c1 + PAD_S
                span, cover, bsim, nq, edsub, edframes = finloc_cluster(
                    cidx, best_t[cidx], q, tq, bundle, lo, hi)
                subs.append({"cluster": [round(c0, 1), round(c1, 1)], "cluster_frames": cnt,
                             "edited_sub": edsub, "edited_frames": edframes,
                             "span": list(span) if span else None,
                             "cover": round(cover, 3),
                             "best_sim": round(bsim, 3) if bsim is not None else None})
        else:
            mode = "clean"
            (c0, c1, cnt, cidx) = max(sig, key=lambda s: s[2]) if sig else None
            if cidx is not None:
                lo, hi = max(0.0, c0 - PAD_S), c1 + PAD_S
                span, cover, bsim, nq, edsub, edframes = finloc_cluster(
                    cidx, best_t[cidx], q, tq, bundle, lo, hi)
                subs = [{"cluster": [round(c0, 1), round(c1, 1)], "cluster_frames": cnt,
                         "edited_sub": edsub, "edited_frames": edframes,
                         "span": list(span) if span else None,
                         "cover": round(cover, 3),
                         "best_sim": round(bsim, 3) if bsim is not None else None}]
            else:
                subs = []
        # 弱簇过滤：丢弃「cover < WEAK_COVER 且 best_sim < WEAK_SIM」的双低子 span（明确噪声）；
        # 单低保留（真实但部分命中的子镜头，如 [0] 峡谷 .33/.68）。
        kept, dropped = [], 0
        for s in subs:
            both_low = (s["cover"] < WEAK_COVER and s["best_sim"] is not None
                        and s["best_sim"] < WEAK_SIM)
            if both_low:
                dropped += 1
                s["dropped_weak"] = True
            else:
                s["dropped_weak"] = False
                kept.append(s)
        subs = kept
        row_dropped = dropped
        rows.append({"idx": idx, "edited": [round(shot.span.start, 2), round(shot.span.end, 2)],
                     "nq": int(q.shape[0]), "mode": mode, "n_clusters": len(sig),
                     "dropped_weak": row_dropped, "sub_spans": subs})

    with open(OUT / "montage_localize.json", "w", encoding="utf-8") as f:
        json.dump({"segments": rows}, f, ensure_ascii=False, indent=2)

    print("\n=== 蒙太奇多段定位原型 ===")
    for r in rows:
        print(f"[{r['idx']:2}] edited={r['edited']} mode={r['mode']:8} "
              f"sig_clusters={r['n_clusters']} kept={len(r['sub_spans'])} "
              f"dropped_weak={r['dropped_weak']} nq={r['nq']}")
        for s in r["sub_spans"]:
            print(f"      edited_sub={s['edited_sub']} -> span={s['span']} "
                  f"cover={s['cover']} betsim={s['best_sim']} (cluster {s['cluster']}, "
                  f"{s['cluster_frames']}f)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
