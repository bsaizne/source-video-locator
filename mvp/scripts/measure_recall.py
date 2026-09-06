"""测量 — 召回参数优化（蒙太奇/切分/聚类，独立于索引密度）对真实数据的召回提升。

用 config 覆盖 index_sampling_fps=0.5（复用 App 缓存索引，快）+ 新的召回向蒙太奇/切分参数，
跑真实 1.mp4→2.mkv，统计 段数 / 总子 span 数 / LOW 数 / failure_reason，与基线
（12 段 / 18 子 span / 9 LOW / 0 failure）对比。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/measure_recall.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app import SourceLocatorService
from infrastructure.config import load_config
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
OUT = BENCH / "mvp" / "benchmark" / "user_case"

INDEX_FPS = float(os.environ.get("MEASURE_INDEX_FPS", "0.5"))   # 0.5=复用 App 索引测参数效果


def _env_f(v, default):
    return float(os.environ.get(v, default)) if v in os.environ else default


def main() -> int:
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    cfg = load_config()
    cfg.pipeline.index_sampling_fps = INDEX_FPS    # 复用 App 0.5 索引（快）；1.0 则重建（慢）
    for attr, env in [("seg_z_thresh", "Z"), ("seg_cut_abs", "CUT"), ("seg_min_shot_s", "MINSHOT"),
                      ("montage_min_frames", "MMIN_FR"), ("montage_min_sim", "MMIN_SIM"),
                      ("montage_cluster_gap_s", "MGAP"), ("retrieval_top_k", "TOP_K"),
                      ("seg_max_shot_s", "SEG_MAX"), ("seg_fine_cut_factor", "FINE_CUT"),
                      ("seg_fine_z_factor", "FINE_Z"), ("seg_fine_min_shot_s", "FINE_MIN"),
                      ("max_orig_span_s", "MAX_SPAN"), ("span_width_factor", "WFAC")]:
        if env in os.environ:
            setattr(cfg.pipeline, attr, type(getattr(cfg.pipeline, attr))(_env_f(env, 0)))
    svc = SourceLocatorService(config=cfg, ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                               index_root=APP_INDEX_ROOT, export_root=OUT)
    print(f"config: index_fps={cfg.pipeline.index_sampling_fps} "
          f"montage(min_frames={cfg.pipeline.montage_min_frames} "
          f"min_sim={cfg.pipeline.montage_min_sim} gap={cfg.pipeline.montage_cluster_gap_s}) "
          f"seg(z={cfg.pipeline.seg_z_thresh} cut={cfg.pipeline.seg_cut_abs}) "
          f"top_k={cfg.pipeline.retrieval_top_k}")
    batch = svc.locate(EDIT, ORIG)
    svc.export_results(batch, out_dir=OUT, filename="user_results.json")   # 供 GT 校检/contact sheet
    res = batch.results
    from collections import Counter
    conf = Counter(r.confidence.level.value for r in res)
    n_sub = sum(len(r.original_segments) for r in res)
    n_mont = sum(1 for r in res if r.montage_flag)
    n_fail = sum(1 for r in res if r.failure_reason)
    segs_w_sub = sum(1 for r in res if r.original_segments)
    print(f"\n=== recall 测量 ===\nsegments={len(res)} conf={dict(conf)} "
          f"sub_spans_total={n_sub} segs_with_sub={segs_w_sub} "
          f"montage_flag={n_mont} failure_reason={n_fail}")
    print("各段子 span 数:", [len(r.original_segments) for r in res])
    print("各段 confidence:", [r.confidence.level.value for r in res])
    print("\n各段宽度（主 original）:")
    for r in res:
        es = r.edited; o = r.original
        print(f"  ed({es.start:6.1f}-{es.end:6.1f} w{es.width:5.1f}) -> "
              f"orig({o.start:7.1f}-{o.end:7.1f} w{o.width:5.1f}) {r.confidence.level.value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
