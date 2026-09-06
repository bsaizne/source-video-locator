"""verify_moment_recall.py — 局对齐 scene 校正 + moment ±1s 终核。

对 corrected GT 每段：product shot(@2fps) + dense(@8fps) -> EvidenceLocalizer(全局对齐)
-> scene original_span + moment ±1s。判定 scene 校正(moment 中心在 GT ±tol 内) 与
moment 收窄(宽度≤2s)。多模态 contact sheet（编辑帧 vs moment 原片帧并排）。

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/verify_moment_recall.py
"""
from __future__ import annotations

import json
import sys
from functools import partial
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

import verify_greedy_top1 as G  # noqa: E402
from engine.localization.evidence_localize import EvidenceLocalizer  # noqa: E402
from engine.localization.seq_align import align_moments  # noqa: E402

io = G.FFmpegIO(G.FFMPEG, G.FFPROBE)
backend = G.resolve_backend("auto")
store = G.FeatureStore(io, "C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index",
                       sampling_fps=1.0)
bundle = store.load_index("D:/video/2.mkv")
EDIT = BENCH / "datasets" / "real" / "edited" / "1.mp4"
GT = BENCH / "datasets" / "real" / "ground_truth_corrected.json"
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "verify_moment"
OUT.mkdir(parents=True, exist_ok=True)
TOL = 2.0

align = partial(align_moments, mean_sim_min=0.20, min_hits=2, min_moment_s=1.0)
loc = EvidenceLocalizer(seq_align=align, seq_pad_s=15, seq_window_max_s=45,
                        seq_global_mean_sim_min=0.20, seq_max_query_frames=64,
                        seq_moment_half_s=1.0, seq_mean_sim_min=0.40)


def center(span):
    return None if span is None else (span[0] + span[1]) / 2


def main() -> int:
    rows = []
    data = json.loads(GT.read_text(encoding="utf-8"))
    for i, seg in enumerate(data["segments"]):
        es, ee = float(seg["edited_start"]), float(seg["edited_end"])
        gs, ge = float(seg["original_start"]), float(seg["original_end"])
        # product shot @2fps + dense @8fps（app 层重采样）
        s2, t2 = G.embed_range(io, backend, EDIT, 2.0, es, ee)
        d8, t8 = G.embed_range(io, backend, EDIT, 8.0, es, ee)
        if s2 is None:
            continue
        ev = loc.localize(s2, t2, bundle, dense_query=(d8, t8))
        p = ev.primary
        scene = p.original_span if (p and p.original_span) else None
        m0 = p.moments[0].original_span if (p and p.moments) else None
        sc = center(scene)
        m = center(m0)
        in_gt = bool(m is not None and gs - TOL <= m <= ge + TOL)
        width = (m0[1] - m0[0]) if m0 else 0.0
        rows.append({"seg": i, "gt": [gs, ge], "scene": scene, "m0": m0,
                     "n_moments": len(p.moments) if p else 0,
                     "scene_center": sc, "moment_center": m, "moment_in_gt": in_gt,
                     "moment_width": round(width, 2)})
        print(f"  seg{i} gt[{gs:7.1f},{ge:7.1f}] scene={scene} moments={len(p.moments) if p else 0} "
              f"m0={m0} moment_in_gt={in_gt} width={width:.1f}")
        if m0:
            G.pair_image(io, str(EDIT), (es + ee) / 2, "D:/video/2.mkv", m,
                         OUT / f"seg{i}_moment.jpg", f"seg{i}")
    n_in = sum(1 for r in rows if r["moment_in_gt"])
    n_w = sum(1 for r in rows if 0 < r["moment_width"] <= 2.0 + 1e-6)
    print(f"\n== moment 中心 in GT: {n_in}/{len(rows)}; moment 宽度≤2s: {n_w}/{len(rows)} ==")
    json.dump(rows, open(OUT / "moment_recall.json", "w"), indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
