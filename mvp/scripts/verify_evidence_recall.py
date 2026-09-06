"""verify_evidence_recall.py — multi-evidence 定位器在 corrected GT 上的召回验证。

对 ground_truth_corrected.json 每段：抽 edited 区间帧 -> embed -> EvidenceLocalizer.localize
-> 检查 primary/各 span 是否命中 corrected original 区间。对比"循规 finloc 单段"的基线。

Run (venv python):
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/verify_evidence_recall.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from device import resolve_backend
from engine.feature_store import FeatureStore
from engine.localization import EvidenceLocalizer, finloc_window
from media.ffmpeg import FFmpegIO

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
EDIT = BENCH / "datasets" / "real" / "edited" / "1.mp4"
ORIG = Path("D:/video/2.mkv")
INDEX_ROOT = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
GT = BENCH / "datasets" / "real" / "ground_truth_corrected.json"
EDIT_FPS = 8.0
TOL = 2.0          # 命中容差（原片 1fps 采样）
OVERLAP = 0.30     # span 与 GT 区间重叠 / GT 宽度 >= 此值算命中


def overlap(span, gs, ge):
    if span is None:
        return 0.0
    lo, hi = max(span[0], gs - TOL), min(span[1], ge + TOL)
    return max(0.0, hi - lo) / max(ge - gs, 1e-6)


def main() -> int:
    io = FFmpegIO(FFMPEG, FFPROBE)
    backend = resolve_backend("auto")
    store = FeatureStore(io, INDEX_ROOT, sampling_fps=1.0)
    bundle = store.load_index(ORIG)
    loc = EvidenceLocalizer(cluster_gap_s=15.0, min_frames=2, min_sim=0.40,
                            weak_cover=0.30, weak_sim=0.45, max_span_s=15.0)
    print(f"[lib] {bundle.num_frames} frames backend={backend.device_name()}")

    data = json.loads(GT.read_text(encoding="utf-8"))
    n_hit = 0
    rows = []
    for i, seg in enumerate(data["segments"]):
        es, ee = float(seg["edited_start"]), float(seg["edited_end"])
        gs, ge = float(seg["original_start"]), float(seg["original_end"])
        feats, times = [], []
        for t, f in io.iter_frames(EDIT, EDIT_FPS, start=es, end=ee):
            feats.append(f)
            times.append(t)
        if not feats:
            continue
        emb = backend.embed_frames(feats)
        tq = np.array(times, dtype=np.float32)
        ev = loc.localize(emb, tq, bundle)
        # 命中 = 任一保留 span 覆盖 GT 区间足够比例
        ovs = [overlap(s.original_span, gs, ge) for s in ev.spans if s.original_span]
        hit = max(ovs) >= OVERLAP if ovs else False
        n_hit += int(hit)
        rows.append({
            "seg": i, "edited": [es, ee], "gt_orig": [gs, ge], "mode": ev.mode,
            "n_spans": len(ev.spans), "ovs": [round(o, 2) for o in ovs], "hit": hit})
        details = " ".join(f"[{s.original_span[0]:.0f},{s.original_span[1]:.0f}]c{s.cover:.2f}"
                           for s in ev.spans if s.original_span)
        print(f"  seg{i} edit[{es:6.1f},{ee:6.1f}] gt[{gs:7.1f},{ge:7.1f}] mode={ev.mode:>7} "
              f"n_spans={len(ev.spans)} spans={details} hit={hit}")
    print(f"\n== multi-evidence recall (overlap>={OVERLAP}): {n_hit}/{len(rows)} ==")
    json.dump(rows, open("mvp/benchmark/user_case/verify_evidence_recall.json", "w"),
              indent=2, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
