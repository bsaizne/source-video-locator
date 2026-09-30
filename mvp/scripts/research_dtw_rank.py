# -*- coding: utf-8 -*-
"""A2 — 对齐链(单调 DP / DTW)用作「候选排序信号」的价值探针(研究侧, 零 runtime 改动).

竞品对标依据(D:/claudework/cutmatch-analysis, 137 模块图):
  matching.alignment.{dtw,timeline,geometry,continuity,offset_refiner} +
  fast_timeline.{dense_alignment,ordered_search,path_selection,local_refiner}。

我方现状(重要, 避免重复造轮子):
  * engine/localization/seq_align.py = 单调 DP 对齐(REUSE research src/experiments/ta.py),
    **已接入 runtime**, 但只用于「候选窗内 moment 精修」(_align_global_moments);
  * 它**不参与**「哪个候选/哪个实例」的排序决策 —— 竞品 dtw 可能多的正是这一步。
  本探针测的就是这个位置: 对齐得分用于跨候选排序, 能否分离正确实例与近同干扰实例。

口径(每案例):
  ① 编辑段 [ed0,ed1] @8fps(=config.edit_fps) 抽帧 -> DINOv2 CLS 384d(DML);
  ② 原片索引(1fps, 生产 data/index/) features/times;
  ③ 候选锚点 = 编辑段逐帧 best-match 帧时间(1s 去重) ∪ 真值窗中心;
  ④ 每个锚点 t -> 原片窗 W = times∈[t-half, t+half], half = 段时长/2 + 1s;
     baseline = cos(mean(E), mean(W))                  ← 现行检索分口径
     dtw_mean = 单调 DP 路径上的 sim 均值
     dtw_norm = Σpath_sim / |E|
     dtw_cov  = |path| / (|E|+|W|)
  ⑤ 输出: 真值锚点在各打分下的 rank + 真值/最强干扰的 margin。

用法:
  python mvp/scripts/research_dtw_rank.py            # 固定 5 个探针案例(逐条明细)
  python mvp/scripts/research_dtw_rank.py all        # 四片全部 GT 正例 + 汇总统计
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from device import resolve_backend                        # noqa: E402
from engine.common import cosine_similarity               # noqa: E402
from engine.feature_store import FeatureStore             # noqa: E402
from engine.localization.seq_align import _dp_path        # noqa: E402  (研究侧复用 runtime DP)
from infrastructure import paths                          # noqa: E402
from infrastructure.config import load_config             # noqa: E402
from media.ffmpeg import FFmpegIO                         # noqa: E402

EDIT_FPS = 8.0
PAD_S = 1.0
DP_KW = dict(sim_thresh=0.40, diag_penalty=0.5, step_penalty=1.0)

CASES = [
    ("2mkv", r"D:\video\1.mp4", r"D:\video\2.mkv",
     "datasets/real/ground_truth_v4.json", ["p08", "p09", "p26", "p01"]),
    ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv",
     "datasets/real/ground_truth_test1.json", ["t1r00"]),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4",
     "datasets/real/ground_truth_test2.json", ["t2r02b"]),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4",
     "datasets/real/ground_truth_test3.json", ["t3r12"]),
]


def embed_segment(backend, ff, edited, t0, t1, fps=EDIT_FPS):
    frames = [f for _, f in ff.iter_frames(edited, fps, start=t0, end=t1)]
    if not frames:
        return None, None
    feats = np.asarray(backend.embed_frames(frames), dtype=np.float32)
    times = np.arange(feats.shape[0], dtype=np.float32) / np.float32(fps) + np.float32(t0)
    return feats, times


def score_pair(E, W):
    qm = E.mean(axis=0)
    qm = qm / max(float(np.linalg.norm(qm)), 1e-8)
    wm = W.mean(axis=0)
    wm = wm / max(float(np.linalg.norm(wm)), 1e-8)
    base = float(qm @ wm)
    sim = cosine_similarity(E, W)
    path = _dp_path(sim, **DP_KW)
    if len(path) == 0:
        return base, 0.0, 0.0, 0.0
    psim = sim[path[:, 0], path[:, 1]].astype(np.float64)
    return (base, float(psim.mean()), float(psim.sum() / max(E.shape[0], 1)),
            float(len(path) / (E.shape[0] + W.shape[0])))


def run_case(backend, ff, store, case, edited, original, gt_rel, ids):
    gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
    pos = {it["id"]: it for it in gt["positives"]}
    if ids is None:
        ids = list(pos.keys())
    bundle = store.load_index(original)
    print("\n=== %s | index frames=%d | edited=%s | cases=%d ===" % (
        case, bundle.features.shape[0], Path(edited).name, len(ids)), flush=True)
    rows_out = {}
    for pid in ids:
        it = pos.get(pid)
        if it is None or "original" not in it:
            continue
        ed0, ed1 = [float(x) for x in it["edited"]]
        og0, og1 = [float(x) for x in it["original"]]
        og_mid = (og0 + og1) / 2.0
        E, _tE = embed_segment(backend, ff, Path(edited), ed0, ed1)
        if E is None or E.shape[0] < 2:
            continue
        half = (ed1 - ed0) / 2.0 + PAD_S
        sim_all = E @ bundle.features.T
        cand_t = sorted({float(bundle.times[i]) for i in sim_all.argmax(axis=1)})
        dedup = []
        for t in cand_t:
            if not dedup or t - dedup[-1] > 1.0:
                dedup.append(t)
        truth_t = float(bundle.times[int(np.argmin(np.abs(bundle.times - og_mid)))])
        if all(abs(truth_t - t) > 1.0 for t in dedup):
            dedup.append(truth_t)
        rows = []
        for t in dedup:
            wi = np.where((bundle.times >= t - half) & (bundle.times <= t + half))[0]
            if wi.size < 2:
                continue
            base, dtw_mean, dtw_norm, cov = score_pair(E, bundle.features[wi])
            rows.append({"t": round(t, 2), "base": round(base, 4), "dtw_mean": round(dtw_mean, 4),
                         "dtw_norm": round(dtw_norm, 4), "cov": round(cov, 4),
                         "is_truth": abs(t - truth_t) <= 1.0})
        if not rows:
            continue
        ranking = {}
        for key in ("base", "dtw_mean", "dtw_norm", "cov"):
            order = sorted(rows, key=lambda r: -r[key])
            ranking[key] = next((i + 1 for i, r in enumerate(order) if r["is_truth"]), None)
        truth_row = next((r for r in rows if r["is_truth"]), None)
        if truth_row is None:
            continue
        others = [r for r in rows if not r["is_truth"]]
        top_other = max(others, key=lambda r: r["base"]) if others else None
        rec = {"case": case, "id": pid, "nq": int(E.shape[0]), "n_cand": len(rows),
               "ranks": ranking, "truth": truth_row, "top_other": top_other}
        if top_other:
            rec["margin"] = {k: round(truth_row[k] - top_other[k], 4)
                             for k in ("base", "dtw_mean", "dtw_norm", "cov")}
        rows_out[pid] = rec
        print("  %-8s nq=%-3d cand=%-2d rank base=%s dtw_mean=%s | margin base=%+.4f dtw_mean=%+.4f" % (
            pid, E.shape[0], len(rows), ranking["base"], ranking["dtw_mean"],
            rec.get("margin", {}).get("base", 0.0), rec.get("margin", {}).get("dtw_mean", 0.0)), flush=True)
    return rows_out


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "cases"
    cfg = load_config()
    backend = resolve_backend(cfg.device.preferred, config=cfg)
    print("BACKEND_SELECTED type=%s device=%s mode=%s" % (
        type(backend).__name__, getattr(backend, "device_name", lambda: "?")(), mode), flush=True)
    ff = FFmpegIO()
    store = FeatureStore(ff, paths.index_root(), sampling_fps=float(cfg.pipeline.index_sampling_fps))

    out = {}
    t0 = time.monotonic()
    for case, edited, original, gt_rel, ids in CASES:
        out.update(run_case(backend, ff, store, case, edited, original, gt_rel,
                            None if mode == "all" else ids))
    (BENCH / "work" / ("dtw_rank_results%s.json" % ("_all" if mode == "all" else ""))).write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    if mode == "all":
        tot = len(out)
        rb = [r["ranks"]["base"] for r in out.values() if r["ranks"]["base"]]
        rd = [r["ranks"]["dtw_mean"] for r in out.values() if r["ranks"]["dtw_mean"]]
        better = sum(1 for r in out.values()
                     if r["ranks"]["dtw_mean"] and r["ranks"]["base"]
                     and r["ranks"]["dtw_mean"] < r["ranks"]["base"])
        worse = sum(1 for r in out.values()
                    if r["ranks"]["dtw_mean"] and r["ranks"]["base"]
                    and r["ranks"]["dtw_mean"] > r["ranks"]["base"])
        neg = [r for r in out.values() if r.get("margin", {}).get("base", 1.0) < 0]
        neg_fixed = [r for r in neg if r["margin"]["dtw_mean"] > 0]
        marg_b = [r["margin"]["base"] for r in out.values() if "margin" in r]
        marg_d = [r["margin"]["dtw_mean"] for r in out.values() if "margin" in r]
        print("\n================ SUMMARY (all) ================", flush=True)
        print("cases=%d  rank_base mean=%.2f  rank_dtw_mean=%.2f  rank 改善=%d 恶化=%d 持平=%d" % (
            tot, float(np.mean(rb)) if rb else -1, float(np.mean(rd)) if rd else -1,
            better, worse, tot - better - worse), flush=True)
        print("base margin<0 的错配案例=%d 其中 dtw margin>0(纠正)=%d" % (len(neg), len(neg_fixed)), flush=True)
        print("margin mean: base=%.4f dtw_mean=%.4f  (n=%d)" % (
            float(np.mean(marg_b)) if marg_b else 0, float(np.mean(marg_d)) if marg_d else 0, len(marg_b)), flush=True)
        print("elapsed=%.1fs" % (time.monotonic() - t0), flush=True)
    else:
        print("\nsaved work/dtw_rank_results.json (%d cases) elapsed=%.1fs" % (
            len(out), time.monotonic() - t0), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
