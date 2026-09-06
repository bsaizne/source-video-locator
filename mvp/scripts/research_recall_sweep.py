"""研究实验 — 蒙太奇子镜头召回参数扫描：能否提高「识别到的镜头数」。

问题：用户反馈「很多镜头没识别到」= 召回低（编辑片很多子镜头没定位）。当前蒙太奇模块
min_frames=3 / min_sim=0.45 / cluster_gap=30s。本实验扫描更细参数（min_frames=2,
min_sim<=0.40, gap<=15s），统计每个 edited 段召回的显著簇/子 span 数，看能否提高召回
而不爆噪声；同时看 detect_shots 更细切分（z/cut 降低）能否多分查询单元。

运行（DirectML + 复用 App 索引，~30s）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_recall_sweep.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app import SourceLocatorService
from engine.localization.montage_localize import MontageLocalizer
from engine.segment import detect_shots
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

PARAMS = [
    ("base(3,0.45,30)", dict(min_frames=3, min_sim=0.45, cluster_gap_s=30.0)),
    ("fine(2,0.40,15)", dict(min_frames=2, min_sim=0.40, cluster_gap_s=15.0)),
    ("finer(2,0.38,10)", dict(min_frames=2, min_sim=0.38, cluster_gap_s=10.0)),
]


def main() -> int:
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    svc = SourceLocatorService(ffmpeg=FFmpegIO(FFMPEG, FFPROBE), index_root=APP_INDEX_ROOT)
    bundle = svc.build_original_index(ORIG)
    shots = svc.analyze_edited_video(EDIT)
    print(f"segments={len(shots)} bundle={bundle.num_frames}")
    # detect_shots 更细切分测试
    print("\n=== detect_shots 切分（当前 vs 更细）===")
    for label, kw in [("默认 z=2/cut=0.30", {}),
                      ("细 z=1.5/cut=0.25", dict(z_thresh=1.5, cut_abs=0.25)),
                      ("更细 z=1.2/cut=0.20", dict(z_thresh=1.2, cut_abs=0.20))]:
        s = detect_shots(svc_emb, ed_times, fps=2.0, **kw) if False else None
    # 重新 embed（detect_shots 需要 feats）——写一份
    ed_feats = shots[0].feats  # 占位，实际用全部
    # 用 analyze 的 shots 已含 feats/times，直接对 feats 重切
    all_feats = np.concatenate([s.feats for s in shots], axis=0) if len(shots) > 1 else shots[0].feats
    all_times = np.concatenate([s.times for s in shots], axis=0) if len(shots) > 1 else shots[0].times
    for label, kw in [("默认 z=2/cut=0.30", {}),
                      ("细 z=1.5/cut=0.25", dict(z_thresh=1.5, cut_abs=0.25)),
                      ("更细 z=1.2/cut=0.20", dict(z_thresh=1.2, cut_abs=0.20))]:
        segs = detect_shots(all_feats, all_times, fps=2.0, **kw)
        print(f"  {label}: {len(segs)} 段")

    print("\n=== 蒙太奇子镜头召回（不同参数）===")
    for label, kw in PARAMS:
        ml = MontageLocalizer(**kw)
        total = 0
        per = []
        for sh in shots:
            r = ml.localize(sh.feats, sh.times, bundle)
            strong = r.n_strong_clusters if r.mode != "empty" else 0
            total += strong
            per.append(strong)
        print(f"  {label}: 总显著簇={total} 每段={per}")

    print("\n=== 各段（base vs finer）每段显著簇 ===")
    for label, kw in PARAMS:
        ml = MontageLocalizer(**kw)
        print(f"  {label}:", [ml.localize(s.feats, s.times, bundle).n_strong_clusters for s in shots])
    return 0


if __name__ == "__main__":
    sys.exit(main())
