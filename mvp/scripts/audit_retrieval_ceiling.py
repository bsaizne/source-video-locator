"""检索天花板 vs 运行期定位 —— 审计"非 HIT 案例到底卡在哪一层" (2026-09-26).

背景: HANDOFF_CUTMATCH_AND_METRIC_AUDIT §3 提出"三指标口径伪影"假设
(用 GT 编辑段中点代表整段 → 17/22 非 HIT 案例的真值窗内其实有 rank<=3 的帧)。
本脚本把该假设**做对并做全**: 对四片全部正例(不只是非 HIT), 在编辑段内多点查询,
用**带 ±TOL 容差**(默认 0.5s, 1fps 索引粒度)的真值窗算「窗内最佳帧的全片检索 rank」,
再与运行期结果(perfopt 批)的命中标记对照, 得到三层分类:

  R1_RETRIEVAL_TOP3  运行期未命中 但 窗内有 rank<=3 帧   -> 定位/候选池层问题(非特征层)
  R2_RETRIEVAL_TOP20 运行期未命中 但 窗内有 rank<=20 帧  -> 检索池边缘
  R3_REAL_FAIL       运行期未命中 且 窗内最佳 rank > 20   -> 特征层失败

零 runtime 改动(只读索引 + 跑前向, 不碰 mvp/src).

用法:
  python mvp/scripts/audit_retrieval_ceiling.py [--tol 0.5] [--points 6] [--out work/loc_retrieval_audit.json]
"""
from __future__ import annotations

import argparse
import io
import contextlib
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from media.ffmpeg import FFmpegIO                       # noqa: E402
from engine.feature_store import FeatureStore           # noqa: E402
from infrastructure import paths                        # noqa: E402
from infrastructure.config import load_config           # noqa: E402
from device import resolve_backend                      # noqa: E402
from measure_shot_recall import evaluate                # noqa: E402

CASES = [
    ("2mkv", r"D:\video\1.mp4", r"D:\video\2.mkv", "datasets/real/ground_truth_v4.json",
     "work/rerun_2mkv_perfopt.results.json"),
    ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv",
     "datasets/real/ground_truth_test1.json", "work/rerun_test1_perfopt.results.json"),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4",
     "datasets/real/ground_truth_test2.json", "work/rerun_test2_perfopt.results.json"),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4",
     "datasets/real/ground_truth_test3.json", "work/rerun_test3_perfopt.results.json"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tol", type=float, default=0.5, help="真值窗 ±容差(秒), 默认 0.5 (1fps 粒度)")
    ap.add_argument("--points", type=int, default=6, help="编辑段内查询点数, 默认 6")
    ap.add_argument("--out", default=str(BENCH / "work" / "loc_retrieval_audit.json"))
    ap.add_argument("--coarse-stride", default="",
                    help="逗号分隔的抽帧步长(模拟更低 fps 的粗索引; 例如 \"2,10\" = 0.5fps/0.1fps)")
    ap.add_argument("--coarse-k", type=int, default=100, help="粗筛候选池大小(竞品 global_top_k=100)")
    args = ap.parse_args()
    strides = [int(x) for x in args.coarse_stride.split(",") if x.strip()] if args.coarse_stride else []

    cfg = load_config()
    backend = resolve_backend(cfg.device.preferred, config=cfg)
    print("BACKEND_SELECTED type=%s device=%s dtype=%s" % (
        getattr(backend, "name", type(backend).__name__), cfg.device.preferred, getattr(backend, "dtype", "-")),
        flush=True)
    ff = FFmpegIO()
    store = FeatureStore(ff, paths.index_root(), sampling_fps=float(cfg.pipeline.index_sampling_fps))

    out = {"tol": args.tol, "points": args.points, "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
           "cases": {}, "summary": {}}
    tally = {"R1_RETRIEVAL_TOP3": [], "R2_RETRIEVAL_TOP20": [], "R3_REAL_FAIL": [], "HIT": []}
    t0 = time.time()
    for case, edit, orig, gt_rel, res_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        res = json.loads((BENCH / res_rel).read_text(encoding="utf-8"))["results"]
        with contextlib.redirect_stdout(io.StringIO()):
            rep = evaluate(gt, res, label=case)
        marks = {p["id"]: p["mark"] for p in rep["per_pos"]}
        bundle = store.load_index(orig)
        times = np.asarray(bundle.times, dtype=np.float64)
        feats = np.asarray(bundle.features, dtype=np.float32)
        meta = getattr(bundle, "meta", None)
        print("\n=== %s: index frames=%d fv=%s ===" % (
            case, len(times), getattr(meta, "feature_version", "?")), flush=True)
        rows = []
        for p in gt["positives"]:
            pid = p["id"]
            e0, e1 = [float(x) for x in p["edited"]]
            o0, o1 = [float(x) for x in p["original"]]
            qs = [round(e0 + (e1 - e0) * k / max(args.points - 1, 1), 3) for k in range(args.points)]
            mask = (times >= o0 - args.tol) & (times <= o1 + args.tol)
            # 粗索引(抽帧)统计: 1) 窗±半步长内最佳粗帧的"粗池内 rank"; 2) 是否 <= coarse_k
            coarse = {s: {"stride": s, "n_frames": int(np.ceil(len(times) / s))} for s in strides}
            best_rank, best_row = 10 ** 9, None
            for qt in qs:
                frame = ff.grab_frame(Path(edit), min(max(qt, 0.0), max(e1, 0.0) + 1e-3))
                q = np.asarray(backend.embed_frames([frame]), dtype=np.float32)[0]
                q = q / max(float(np.linalg.norm(q)), 1e-8)
                sim = feats @ q
                i = int(np.argmax(np.where(mask, sim, -1.0)))
                r = int(np.sum(sim > sim[i])) + 1
                if r < best_rank:
                    best_rank, best_row = r, dict(qt=qt, t_best=float(times[i]), sim=float(sim[i]))
                for s in strides:
                    idx = np.arange(0, len(times), s)
                    sim_c = sim[idx]
                    half = s / 2.0 + args.tol
                    mask_c = (times[idx] >= o0 - half) & (times[idx] <= o1 + half)
                    if not mask_c.any():
                        coarse[s].setdefault("no_near_frame", 0)
                        coarse[s]["no_near_frame"] += 1
                        continue
                    ic = int(np.argmax(np.where(mask_c, sim_c, -1.0)))
                    rc = int(np.sum(sim_c > sim_c[ic])) + 1
                    cur = coarse[s].get("min_rank")
                    if cur is None or rc < cur:
                        coarse[s]["min_rank"] = rc
                        coarse[s]["t_best"] = float(times[idx[ic]])
                        coarse[s]["sim"] = float(sim_c[ic])
            mark = marks.get(pid, "?")
            label = ("HIT" if mark == "HIT" else
                     ("R1_RETRIEVAL_TOP3" if best_rank <= 3 else
                      ("R2_RETRIEVAL_TOP20" if best_rank <= 20 else "R3_REAL_FAIL")))
            tally[label].append("%s/%s" % (case, pid))
            rows.append(dict(id=pid, mark=mark, retrieval_rank=int(best_rank),
                             t_best=best_row["t_best"], sim=best_row["sim"],
                             original=[o0, o1], label=label,
                             coarse=({str(s): {k: v for k, v in coarse[s].items() if k != "stride"}
                                      for s in strides} or None)))
            print("  %-8s %-5s rank=%5d (%.1fs sim %.3f) -> %s" % (
                pid, mark, best_rank, best_row["t_best"], best_row["sim"], label), flush=True)
        out["cases"][case] = {"gt": gt_rel, "results": res_rel,
                              "feature_version": getattr(meta, "feature_version", None),
                              "rows": rows}
    print("\n" + "=" * 78)
    for k in ("HIT", "R1_RETRIEVAL_TOP3", "R2_RETRIEVAL_TOP20", "R3_REAL_FAIL"):
        print("%-20s %3d  %s" % (k, len(tally[k]), " ".join(tally[k][:14]) + (" ..." if len(tally[k]) > 14 else "")))
    if strides:
        print("\n" + "=" * 78)
        print("两级采样对照 (粗索引抽帧; K=%d): 窗±(stride/2+tol) 内最佳粗帧的粗池 rank" % args.coarse_k)
        all_rows = [r for c in out["cases"].values() for r in c["rows"]]
        for s in strides:
            ranks = [r["coarse"][str(s)].get("min_rank") for r in all_rows]
            near = [r for r in all_rows if r["coarse"][str(s)].get("min_rank") is not None]
            hit = [r for r in near if r["coarse"][str(s)]["min_rank"] <= args.coarse_k]
            noframe = sum(1 for r in all_rows if r["coarse"][str(s)].get("no_near_frame"))
            fps = float(cfg.pipeline.index_sampling_fps) / s
            print("  stride=%-3d (%.3f fps): 可判 %d/%d, 粗池 rank<=%d 命中 %d (%.1f%%), 邻近无粗帧 %d"
                  % (s, fps, len(near), len(all_rows),
                     args.coarse_k, len(hit), 100.0 * len(hit) / max(1, len(near)), noframe))
            pct = np.percentile([x for x in ranks if x is not None], [50, 90, 99]) if near else []
            if len(pct):
                print("       rank 分位 p50=%.1f p90=%.1f p99=%.1f" % tuple(pct))
    print("elapsed %.0fs" % (time.time() - t0))
    out["summary"] = {k: v for k, v in tally.items()}
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
