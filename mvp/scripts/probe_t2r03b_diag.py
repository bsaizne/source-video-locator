# -*- coding: utf-8 -*-
"""t2r03b no_evidence 根因诊断（单段，研究侧，零 runtime）。

t2r03b：edited 27.8-28.7（0.9s 短段）/ GT original 3570.43-3571。现役批 failure_reason=no_evidence。
要区分两种根因：
  (a) 检索池外：GT 区在 top-20 余弦命中里 rank 太靠后 / sim 太低（召回缺口）；
  (b) 门控：检索有命中但聚类/显著簇门控（min_frames/min_sim）或 dense retry sim 门把它滤掉。
输出：2fps 与 dense(8fps) 两路查询的 GT 区 rank/sim + localize 的簇/门控明细 + dense_retry 门值。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", r"D:\claudework\benchmark\tools\ffmpeg.exe")
os.environ.setdefault("MEDIA_FFPROBE", r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
os.environ.setdefault("SVL_DML_MODEL", r"C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np  # noqa: E402

ED = r"D:\ProjectXIXI\test2\tset2-ed.mp4"
OG = r"D:\ProjectXIXI\test2\test2-om.mp4"
E0, E1 = 27.8, 28.7
O0, O1 = 3570.43, 3571.0


def main() -> int:
    from app.locator_service import SourceLocatorService
    from device.directml_backend import DirectMLBackend
    from infrastructure.config import load_config
    from engine.retrieval.retrieval import retrieve_hits

    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), type(srv.backend).__name__
    print("BACKEND_SELECTED type=%s" % type(srv.backend).__name__, flush=True)
    bundle = srv.store.load_index(Path(OG))
    feats, times = bundle.features, np.asarray(bundle.times, dtype=np.float64)
    print("index frames=%d span=%.1f-%.1f" % (len(times), times[0], times[-1]), flush=True)
    gt_mask = (times >= O0 - 2.0) & (times <= O1 + 2.0)
    print("GT-area index frames:", int(gt_mask.sum()), flush=True)

    def qset(fps):
        n = max(2, int(round((E1 - E0) * fps)))
        ts = [round(E0 + (i + 0.5) * (E1 - E0) / n, 3) for i in range(n)]
        fr = [srv.ffmpeg.grab_frame(ED, t) for t in ts]
        return srv.backend.embed_frames(fr), np.asarray(ts, dtype=np.float64), fr

    q2, t2, _ = qset(2.0)
    q8, t8, _ = qset(8.0)
    print("query frames: 2fps=%d 8fps=%d" % (len(t2), len(t8)), flush=True)

    for tag, q, tq in (("2fps", q2, t2), ("8fps", q8, t8)):
        sims = q @ feats.T
        print("-- %s query: per-frame GT-area best sim / global top1 sim --" % tag, flush=True)
        for i in range(len(tq)):
            gmax = float(sims[i][gt_mask].max()) if gt_mask.any() else float("nan")
            order = np.argsort(-sims[i])
            grank = np.where(gt_mask[order])[0]
            gr = int(grank[0]) + 1 if len(grank) else -1
            print("   t=%.2f  sim@GT=%.4f  GT_rank_in_top=%s  top1_sim=%.4f"
                  % (tq[i], gmax, gr if gr > 0 else "NOT_IN_ALL", float(sims[i][order[0]])), flush=True)
        h = retrieve_hits(q, tq, feats, times)
        ing = int(gt_mask[np.searchsorted(times, h.orig_t)].sum()) if len(h.orig_t) else 0
        print("   top20 hits landing in GT-area: %d / %d" % (ing, len(h.orig_t)), flush=True)

    ev2 = srv._evidence_localizer.localize(q2, t2, bundle, dense_query=(q8, t8))
    print("localize(2fps): mode=%s n_clusters=%d n_strong=%d n_dropped=%d"
          % (ev2.mode, ev2.n_clusters, ev2.n_strong_clusters, ev2.n_dropped_weak), flush=True)
    for s in ev2.all_spans:
        print("   span=%s best_sim=%s cover=%.3f cluster_frames=%d q=%d"
              % (s.original_span, s.best_sim, s.cover or 0.0, s.cluster_frames, s.query_frames), flush=True)
    ev8 = srv._evidence_localizer.localize(q8, t8, bundle, dense_query=(q8, t8))
    print("localize(8fps dense): mode=%s n_clusters=%d n_strong=%d"
          % (ev8.mode, ev8.n_clusters, ev8.n_strong_clusters), flush=True)
    for s in ev8.all_spans:
        print("   span=%s best_sim=%s cover=%.3f cluster_frames=%d"
              % (s.original_span, s.best_sim, s.cover or 0.0, s.cluster_frames), flush=True)
    print("gate cfg: min_frames=%s min_sim=%s dense_retry_min_sim=%s subshot_retry_min_sim=%s"
          % (srv._evidence_localizer.min_frames, srv._evidence_localizer.min_sim,
             getattr(cfg.pipeline, "dense_retry_min_sim", None),
             getattr(cfg.pipeline, "subshot_retry_min_sim", None)), flush=True)
    for tag, ev in (("2fps", ev2), ("8fps", ev8)):
        print("%s kept spans: %s" % (tag, [(s.original_span, s.best_sim, s.cover, s.cluster_frames)
                                           for s in ev.spans]), flush=True)
        print("%s primary: %s best_sim=%s" % (tag,
              ev.primary.original_span if ev.primary else None,
              ev.primary.best_sim if ev.primary else None), flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
