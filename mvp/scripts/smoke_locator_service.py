"""Standalone end-to-end smoke for mvp.app.SourceLocatorService (无 GT).

首选项：真实素材 2.mkv(Original) + 1.mp4(Edited)，跑通完整后台链路并报告 §十 统计。
``--dataset synthetic`` 切到小合成对 (source.mp4 + a1.mp4) 用作快路径。

只断言结构不变式（index/segments/candidates/ranking/finloc/confidence/Results/
progress/cancellation/失败隔离），**不断言 GT 正确性**；真实素材结果仅作工程观察，
不据此调算法。

运行（venv python）：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/smoke_locator_service.py [--dataset real|synthetic]
"""
from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from unittest.mock import patch

import numpy as np

from app import CancellationToken, SourceLocatorService
from domain import ConfidenceLevel, IndexMeta, ResultBatch, TimeSpan
from engine.candidates import produce_candidates as _real_produce_candidates
from engine.feature_store import IndexBundle
from engine.localization.pipeline import localize_segment as _real_localize_segment
from engine.segment import ShotSegment
from media.ffmpeg import FFmpegIO

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
REAL_ORIG = BENCH / "datasets" / "real" / "originals" / "2.mkv"
REAL_EDITED = BENCH / "datasets" / "real" / "edited" / "1.mp4"
SYN_ORIG = BENCH / "datasets" / "synthetic" / "originals" / "source.mp4"
SYN_EDITED = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"


def _peak_ram_mb():
    try:
        import psutil
        return psutil.Process().memory_info().rss / 1048576.0
    except Exception:
        return None


def _progress(evt):
    msg = f"    [{evt.stage.value}] {evt.current}/{evt.total} {evt.message}".rstrip()
    print(msg)


def main() -> int:
    dataset = "real"
    if "--dataset" in sys.argv:
        i = sys.argv.index("--dataset")
        dataset = sys.argv[i + 1]
    orig = REAL_ORIG if dataset == "real" else SYN_ORIG
    edited = REAL_EDITED if dataset == "real" else SYN_EDITED
    print(f"=== smoke_locator_service: dataset={dataset} ===")
    print(f"    original: {orig.name} ({orig.stat().st_size / 1e6:.1f} MB)")
    print(f"    edited  : {edited.name} ({edited.stat().st_size / 1e6:.1f} MB)")

    t_start = time.perf_counter()
    with tempfile.TemporaryDirectory() as td:
        svc = SourceLocatorService(ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                                   index_root=td, export_root=td)
        cfg = svc.config.pipeline

        # 1) Original index build / load
        print("\n=== 1. build_original_index ===")
        t0 = time.perf_counter()
        bundle = svc.build_original_index(orig, on_progress=_progress)
        t_idx = time.perf_counter() - t0
        print(f"    frames={bundle.num_frames} dim={bundle.features.shape[1]} "
              f"time={t_idx:.1f}s")
        assert bundle.num_frames > 0

        # 2) Edited feature extraction + segment detection
        print("\n=== 2. analyze_edited_video ===")
        t0 = time.perf_counter()
        shots = svc.analyze_edited_video(edited, on_progress=_progress)
        t_edit = time.perf_counter() - t0
        print(f"    segments={len(shots)} time={t_edit:.1f}s")
        assert len(shots) >= 1

        # 3) per-segment retrieval + ranking + finloc + confidence (timed)
        print("\n=== 3. per-segment pipeline (retrieval/ranking/finloc/confidence) ===")
        stats = {"candidates": 0, "retrieve_s": 0.0, "localize_s": 0.0}

        def counting_pc(ed_feats, ed_times, index_bundle, *, cfg=None):
            t = time.perf_counter()
            c = _real_produce_candidates(ed_feats, ed_times, index_bundle, cfg=cfg)
            stats["retrieve_s"] += time.perf_counter() - t
            stats["candidates"] += len(c)
            return c

        def counting_ls(candidates, ed_feats, index_bundle, *, cfg=None):
            t = time.perf_counter()
            r = _real_localize_segment(candidates, ed_feats, index_bundle, cfg=cfg)
            stats["localize_s"] += time.perf_counter() - t
            return r

        with patch("app.locator_service.produce_candidates", side_effect=counting_pc), \
                patch("app.locator_service.localize_segment", side_effect=counting_ls):
            t0 = time.perf_counter()
            results = svc._locate_features(shots, bundle, cfg=cfg, on_progress=_progress)
            t_lat = time.perf_counter() - t0
        print(f"    results={len(results)} time={t_lat:.1f}s")
        assert len(results) == len(shots)

        # 4) export + reload round-trip
        print("\n=== 4. export_results + load_results ===")
        batch = ResultBatch(schema_version=1, original_video=str(orig.resolve()),
                            edited_video=str(edited.resolve()), results=results)
        path = svc.export_results(batch, on_progress=_progress)
        reloaded = svc.load_results(path)
        assert reloaded.to_dict() == batch.to_dict(), "persistence round-trip"
        print(f"    exported: {path.name}")

        # 5) cancellation path (fast, pre-cancelled token -> ApplicationError)
        print("\n=== 5. cancellation path ===")
        tok = CancellationToken()
        tok.cancel()
        try:
            svc.build_original_index(orig, cancel_token=tok)
            raise SystemExit("FAIL: expected cancellation to abort")
        except Exception as exc:
            assert type(exc).__name__ == "ApplicationError", type(exc).__name__
            print("    [ok] pre-cancelled token raises ApplicationError")

        # 6) single-segment failure isolation (synthetic mini-bundle, quick)
        print("\n=== 6. single-segment failure isolation (synthetic) ===")
        rng = np.random.RandomState(0)
        _o = rng.randn(60, 384).astype(np.float32)
        _o = _o / np.maximum(np.linalg.norm(_o, axis=1, keepdims=True), 1e-8)
        _t = (np.arange(60) * 2.0).astype(np.float32)
        mini = IndexBundle(IndexMeta("mini", 0, 118.0, "h"), _o, _t)
        src = _o[20:30]
        q = src + 1e-3 * rng.randn(10, 384).astype(np.float32)
        q = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-8)
        s1 = ShotSegment(TimeSpan(0.0, 4.5), q, (np.arange(10) * 0.5).astype(np.float32))

        def raiser(ed_feats, ed_times, index_bundle, *, cfg=None):
            raise RuntimeError("boom")

        with patch("app.locator_service.produce_candidates", side_effect=raiser):
            iso = svc._locate_features([s1], mini, cfg=cfg)
        assert len(iso) == 1 and iso[0].confidence.level == ConfidenceLevel.LOW
        assert iso[0].failure_reason.startswith("segment_error")
        print("    [ok] failing segment -> unresolved LOW, continues")

    t_total = time.perf_counter() - t_start
    ram = _peak_ram_mb()

    # ---- §十 report（仅观察，不调算法）----
    counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for r in results:
        counts[r.confidence.level.value] += 1
    report = {
        "dataset": dataset,
        "segment_count": len(shots),
        "result_count": len(results),
        "HIGH": counts["HIGH"], "MEDIUM": counts["MEDIUM"], "LOW": counts["LOW"],
        "unresolved_count": sum(1 for r in results if r.failure_reason is not None),
        "candidate_count": stats["candidates"],
        "index_build_time_s": round(t_idx, 1),
        "edited_feature_extraction_time_s": round(t_edit, 1),
        "retrieval_time_s": round(stats["retrieve_s"], 1),
        "localization_time_s": round(stats["localize_s"], 1),
        "total_time_s": round(t_total, 1),
        "peak_ram_mb": ram,
    }
    print("\n=== report (engineering observation, not tuning) ===")
    for k, v in report.items():
        print(f"    {k}: {v}")

    print(f"\nALL SMOKE CHECKS PASSED (dataset={dataset})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
