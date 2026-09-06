"""verify_greedy_top1.py — 最小暴力 top1 检索，验证「特征能否找到答案」。

跳过整个 pipeline（clustering/ranking/finloc/confidence/montage），只用：
  单视频/区间 → 逐帧 DINO embedding → 暴力 cosine → top1 原片时间。

判定逻辑：
  - 若 top1 命中正确原片区间 → 复杂 pipeline 反害，需简化/修正 pipeline
  - 若 top1 就错（如命中暗色错原片）→ 证实特征层上限（CLS 全局语义混淆，Phase 15 C）

诊断脚本，不进产品 runtime，不改任何产品算法语义；放 mvp/scripts/。

Run (venv python per AGENTS.md):
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/verify_greedy_top1.py \
      --original "D:/video/2.mkv" \
      --edited   "datasets/real/edited/1.mp4" \
      --gt       "datasets/real/ground_truth.json" \
      --index-root "C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index"
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from device import resolve_backend
from domain import IndexValidationStatus
from engine.common import cosine_similarity
from engine.feature_store import FeatureStore
from media.ffmpeg import FFmpegIO

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")


def load_library(store, backend, original):
    """复用已建索引（VALID 则秒级读回），否则现场 create_index。"""
    val = store.validate_index(original)
    if val.status == IndexValidationStatus.VALID:
        meta = store.get_metadata(original)
        print(f"[lib] REUSE {store.index_dir(original).name} ({meta.num_frames} frames "
              f"@{meta.sampling_fps:g}fps) backend={meta.backend}")
        return store.load_index(original)
    print(f"[lib] BUILD index ({getattr(val, 'reason', None) or val.status}) {original.name} ...")
    store.create_index(original, backend)
    return store.load_index(original)


def greedy_top1(feats, lib):
    """逐编辑帧 → 暴力 cosine → top1 原片 time/sim。核心 3 行。"""
    sim = cosine_similarity(feats, lib.features)                  # [Nq, T]
    best = np.argmax(sim, axis=1)
    return lib.times[best], sim[np.arange(feats.shape[0]), best]


def embed_range(io, backend, path, fps, start, end):
    frames, ts = [], []
    for t, f in io.iter_frames(path, fps, start=start, end=end):
        frames.append(f)
        ts.append(t)
    if not frames:
        return None, None
    return backend.embed_frames(frames), np.array(ts, dtype=np.float32)


def span_of(best_t, best_s):
    """该查询 top1 时间的聚集区间（min..max）+ 平均 top1 相似度。"""
    if best_t.size == 0:
        return None, 0.0
    return [round(float(best_t.min()), 1), round(float(best_t.max()), 1)], float(best_s.mean())


def pair_image(io, edited, e_t, original, o_t, out_path, label):
    """编辑帧(top1相似度最高) | top1 原片帧 并排，供多模态复核。"""
    try:
        ef = io.grab_frame(edited, e_t)
        of = io.grab_frame(original, o_t)
    except Exception as exc:  # noqa: BLE001
        print(f"    [warn] grab_frame {label}: {exc}")
        return
    h = 360
    rs = lambda im: cv2.resize(im, (int(im.shape[1] * h / im.shape[0]), h))
    ef, of = rs(ef), rs(of)
    row = np.hstack([ef, np.full((h, 8, 3), 255, np.uint8), of])
    cv2.putText(row, label, (6, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    cv2.imwrite(str(out_path), row)


def main() -> int:
    ap = argparse.ArgumentParser(description="暴力 top1 检索：验证特征能否找到答案")
    ap.add_argument("--original", required=True, help="原片路径（复用索引须与建索引路径一致）")
    ap.add_argument("--edited", required=True, help="编辑片路径")
    ap.add_argument("--gt", default=None, help="ground_truth.json（逐段算命中率）")
    ap.add_argument("--index-root", default=None, help="FeatureStore index_root")
    ap.add_argument("--orig-fps", type=float, default=1.0)
    ap.add_argument("--segment-fps", type=float, default=8.0, help="抽 GT edited 区间查询密度")
    ap.add_argument("--edit-fps", type=float, default=2.0, help="无 GT 时全片查询密度")
    ap.add_argument("--backend", default="auto", choices=["auto", "cpu", "directml"])
    ap.add_argument("--tol", type=float, default=2.0, help="命中容差 ±s（原片 1fps 采样）")
    ap.add_argument("--dump", default=None, help="导出 top 相似帧对目录")
    ap.add_argument("--out", default=None, help="汇总 json 输出路径")
    args = ap.parse_args()

    io = FFmpegIO(FFMPEG, FFPROBE)
    backend = resolve_backend(args.backend)
    store = FeatureStore(io, args.index_root, sampling_fps=args.orig_fps)
    lib = load_library(store, backend, args.original)
    print(f"[lib] original features {lib.features.shape}, times {lib.times.shape} "
          f"[{lib.times[0]:.1f}..{lib.times[-1]:.1f}]s")

    summary = {"backend": backend.device_name(), "original": str(Path(args.original).resolve()),
               "edited": str(Path(args.edited).resolve()), "segments": []}

    if args.gt:
        data = json.loads(Path(args.gt).read_text(encoding="utf-8"))
        segs = data["segments"]
        for i, seg in enumerate(segs):
            es, ee = float(seg["edited_start"]), float(seg["edited_end"])
            gs, ge = float(seg["original_start"]), float(seg["original_end"])
            feats, ts = embed_range(io, backend, args.edited, args.segment_fps, es, ee)
            if feats is None:
                continue
            best_t, best_s = greedy_top1(feats, lib)
            in_gt = (best_t >= gs - args.tol) & (best_t <= ge + args.tol)
            hit = float(in_gt.mean()) if best_t.size else 0.0
            span, mean_s = span_of(best_t, best_s)
            j = int(np.argmax(best_s))
            rec = {"seg": seg.get("test", i), "edited": [es, ee], "gt_original": [gs, ge],
                   "n_query": int(feats.shape[0]), "hit_rate": round(hit, 3),
                   "top1_span": span, "mean_top1_sim": round(mean_s, 3),
                   "top1_median": round(float(np.median(best_t)), 1)}
            summary["segments"].append(rec)
            print(f"  seg {rec['seg']:>3} edit[{es:6.1f},{ee:6.1f}] -> gt[{gs:7.1f},{ge:7.1f}] "
                  f"hit={hit:5.1%} top1_span={span} sim={mean_s:.3f} n={rec['n_query']}")
            if args.dump:
                Path(args.dump).mkdir(parents=True, exist_ok=True)
                pair_image(io, args.edited, float(ts[j]), args.original, float(best_t[j]),
                           Path(args.dump) / f"seg{i:02d}_pair.jpg",
                           f"seg{i:02d}")
        n_over = sum(1 for s in summary["segments"] if s["hit_rate"] >= 0.5)
        summary["segments_ge_0p5"] = n_over
        summary["segments_total"] = len(summary["segments"])
        print(f"\n== 命中率>=0.5 的段: {n_over}/{len(summary['segments'])} ==")
    else:
        feats, ts = embed_range(io, backend, args.edited, args.edit_fps, None, None)
        best_t, best_s = greedy_top1(feats, lib)
        span, mean_s = span_of(best_t, best_s)
        summary["segments"].append({"n_query": int(feats.shape[0]), "top1_span": span,
                                    "mean_top1_sim": round(mean_s, 3),
                                    "top1_median": round(float(np.median(best_t)), 1)})
        print(f"  n_query={feats.shape[0]} top1_span={span} mean_sim={mean_s:.3f}")

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
        print(f"\n[out] {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
