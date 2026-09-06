"""诊断 Phase C — dump 每段全部 Candidate/LocalizationResult/置信 信号（标定原始依据）。

mirror App 生产路径（DirectML + 复用 App 索引 + edited fps=2.0），对 12 段逐一
produce_candidates + finloc_window + ConfidenceEngine.assess，dump 全部信号供标定。

运行（venv python）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/diag_user_signals.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app import SourceLocatorService
from engine import confidence
from engine.candidates import produce_candidates
from engine.confidence import ConfidenceEngine
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
OUT = BENCH / "mvp" / "benchmark" / "user_case"


def cand_dict(c) -> dict:
    return {
        "start": round(float(c.start), 2), "end": round(float(c.end), 2),
        "width": round(float(c.width), 2), "peak_sim": round(float(c.peak_sim), 4),
        "mean_sim": round(float(c.mean_sim), 4), "consistency": round(float(c.consistency), 4),
        "hit_count": int(c.hit_count), "n_reps": int(c.n_reps), "qcov": round(float(c.qcov), 4),
        "sim_std": round(float(c.sim_std), 4), "rank_score": round(float(c.rank_score), 4),
        "best_cover": round(float(c.best_cover), 4), "scene_div": int(c.scene_div),
    }


def loc_dict(loc) -> dict:
    return {
        "span": list(loc.span) if loc.span else None,
        "best_cover": round(float(loc.best_cover), 4),
        "run_len_s": round(float(loc.run_len_s), 2),
        "run_len_frames": int(loc.run_len_frames),
        "num_runs": int(loc.num_runs), "significant_runs": int(loc.significant_runs),
        "largest_gap_s": round(float(loc.largest_gap_s), 2),
        "span_coverage": round(float(loc.span_coverage), 4),
        "coverage_quality": round(float(loc.coverage_quality), 4),
        "span_stability": round(float(loc.span_stability), 4),
        "multi_island": bool(loc.multi_island),
        "window_width": round(float(loc.window_width), 2),
        "mean_sim": round(float(loc.mean_sim), 4) if loc.mean_sim is not None else None,
        "peak_sim": round(float(loc.peak_sim), 4) if loc.peak_sim is not None else None,
        "n_query": int(loc.n_query),
    }


def main() -> int:
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    svc = SourceLocatorService(ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                               index_root=APP_INDEX_ROOT, export_root=OUT)
    print("device:", svc.device_settings()["actual_device_name"])
    bundle = svc.build_original_index(ORIG)
    shots = svc.analyze_edited_video(EDIT)
    cfg = svc.config.pipeline
    n = len(shots)
    print(f"segments={n} bundle_frames={bundle.num_frames}")
    rows = []
    for idx, shot in enumerate(shots):
        cands = produce_candidates(shot.feats, shot.times, bundle, cfg=cfg)
        if not cands:
            rows.append({"idx": idx, "edited": [shot.span.start, shot.span.end],
                         "no_candidates": True})
            continue
        best = cands[0]
        loc = finloc_window(best, shot.feats, bundle.features, bundle.times)
        best.best_cover = loc.best_cover
        assess = ConfidenceEngine(cfg.confidence).assess(cands, loc, best=best)
        rows.append({
            "idx": idx,
            "edited": [round(shot.span.start, 3), round(shot.span.end, 3)],
            "n_candidates": len(cands),
            "best_candidate": cand_dict(best),
            "loc": loc_dict(loc),
            "confidence": {
                "level": assess.confidence.level.value,
                "score": round(float(assess.confidence.score), 4),
                "reasons": list(assess.confidence.reasons),
                "montage_flag": bool(assess.montage_flag),
                "hard_flags": list(assess.hard_flags),
            },
        })
    with open(OUT / "signals.json", "w", encoding="utf-8") as f:
        json.dump({"segments": rows}, f, ensure_ascii=False, indent=2)
    # quick human-readable table
    print("\n=== signals ===")
    for r in rows:
        if r.get("no_candidates"):
            print(f"[{r['idx']:2}] NO_CANDIDATES edited={r['edited']}")
            continue
        c = r["best_candidate"]; l = r["loc"]; cf = r["confidence"]
        print(f"[{r['idx']:2}] edited={r['edited']} {cf['level']} score={cf['score']} "
              f"mont={cf['montage_flag']} flags={cf['hard_flags']}")
        print(f"      cand[sim={c['mean_sim']} cons={c['consistency']} nreps={c['n_reps']} "
              f"qcov={c['qcov']} simstd={c['sim_std']} scendiv={c['scene_div']} "
              f"width={c['width']} best_cover={c['best_cover']}]")
        print(f"      loc [span={l['span']} cover={l['best_cover']} run={l['run_len_s']}s/"
              f"{l['run_len_frames']}f runs={l['num_runs']} significant={l['significant_runs']} "
              f"multi={l['multi_island']} span_stab={l['span_stability']} "
              f"span_cov={l['span_coverage']} covq={l['coverage_quality']} "
              f"best_sim={l['mean_sim']} nq={l['n_query']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
