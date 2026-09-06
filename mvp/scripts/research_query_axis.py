"""研究实验（原型）— 查询轴簇结构：多镜头蒙太奇段 vs 干净单镜头段在查询轴上是否可分。

问题：冻结定位对蒙太奇段只返回单条最长连续 runs，丢子镜头。假设：若查询轴有判别力，
则蒙太奇段的逐查询帧最佳匹配（per-query argmax over 全原片）会聚成多个原片时间簇
（每个子镜头一个簇），干净单镜头段聚成一个簇。「查询簇数」即可作为蒙太奇门控信号。

本脚本只做**观测**（不改变任何 runtime 算法）：对 12 段计算 per-query best-match 时间的
簇结构（多个 gap 阈值），输出每段的簇数/簇 span/每簇查询帧数，供判断该信号是否可分。

运行（venv python）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_query_axis.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app import SourceLocatorService
from engine.common import cosine_similarity
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

GAPS = [10.0, 20.0, 30.0, 60.0]
MIN_FRAMES = 2  # 一个"显著"查询簇至少几帧


def cluster_times(times, gap):
    """按相邻间隔切簇：返回 [(start,end,count), ...]（按时间排序）。"""
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


def main() -> int:
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    svc = SourceLocatorService(ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                               index_root=APP_INDEX_ROOT, export_root=OUT)
    bundle = svc.build_original_index(ORIG)
    shots = svc.analyze_edited_video(EDIT)
    print(f"orig_frames={bundle.num_frames} segments={len(shots)}")
    OUT.mkdir(parents=True, exist_ok=True)
    all_rows = []
    for idx, shot in enumerate(shots):
        q = shot.feats
        tq = shot.times
        sim = cosine_similarity(q, bundle.features)      # [nq, T]
        best = np.argmax(sim, axis=1)                    # per-query best orig index
        best_t = bundle.times[best]                      # [nq] orig time
        row = {"idx": idx,
               "edited": [round(shot.span.start, 2), round(shot.span.end, 2)],
               "nq": int(q.shape[0]),
               "best_times": [round(float(t), 1) for t in best_t],
               "best_sim": [round(float(s), 3) for s in sim[np.arange(q.shape[0]), best]],
               "clusters": {}}
        for g in GAPS:
            cl = cluster_times(best_t, g)
            row["clusters"][g] = [(round(a, 1), round(b, 1), c) for a, b, c in cl]
        all_rows.append(row)

    with open(OUT / "query_axis.json", "w", encoding="utf-8") as f:
        json.dump({"segments": all_rows}, f, ensure_ascii=False, indent=2)

    print("\n=== 查询轴簇结构（gap=30s）===")
    for r in all_rows:
        cl = r["clusters"][30.0]
        sig = [c for c in cl if c[2] >= MIN_FRAMES]
        print(f"[{r['idx']:2}] edited={r['edited']} nq={r['nq']:3} "
              f"clusters={len(cl)} significant={len(sig)}")
        for c in cl:
            mark = " *" if c[2] >= MIN_FRAMES else ""
            print(f"       {c[0]:8.1f}..{c[1]:8.1f}  frames={c[2]:3}{mark}")

    # 用 cluster-spread 归纳：max cluster span + n_clusters 是否区分蒙太奇/干净
    print("\n=== 归纳（gap=30s, 仅显著簇）===")
    for r in all_rows:
        sig = [c for c in r["clusters"][30.0] if c[2] >= MIN_FRAMES]
        spans = [c[1] - c[0] for c in sig]
        print(f"[{r['idx']:2}] n_sig_clusters={len(sig)} "
              f"spans={[round(s,1) for s in spans]} "
              f"span_range={round(max(spans, default=0),1)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
