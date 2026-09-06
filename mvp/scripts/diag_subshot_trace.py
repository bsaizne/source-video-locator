# -*- coding: utf-8 -*-
"""离线单段重放: montage 漂移触发判据 + _subshot_relocalize 内部值逐步打印(研究侧诊断)。"""
import os
import sys
from pathlib import Path

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

import numpy as np  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

CASES = [
    ("2mkv s55(p32)", r"D:\video\1.mp4", r"D:\video\2.mkv", 100.6, 102.6),
    ("test2 s32", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4", 36.1, 38.5),
    ("test2 s35(t2r05a)", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4", 40.9, 42.5),
    ("test3 s15", r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4", 37.4, 39.2),
    ("test3 s49", r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4", 112.0, 113.6),
]

cfg = load_config()
srv = SourceLocatorService(config=cfg)
efps = cfg.pipeline.seq_align.edit_fps
bundle_cache = {}

for name, edited, original, a, z in CASES:
    if original not in bundle_cache:
        bundle_cache[original] = srv.store.load_index(original)
    bundle = bundle_cache[original]
    frames, times = [], []
    for t, f in srv.ffmpeg.iter_frames(edited, efps, start=a, end=z):
        frames.append(f)
        times.append(t)
    feats = srv.backend.embed_frames(frames)
    dense = (feats, np.array(times, dtype=np.float32))
    # 生产口径: 查询 = 2fps shot.feats, dense 仅作 dense_query 传入
    qframes, qtimes = [], []
    ifps = cfg.pipeline.index_sampling_fps
    for t, f in srv.ffmpeg.iter_frames(edited, ifps, start=a, end=z):
        qframes.append(f)
        qtimes.append(t)
    qfeats = srv.backend.embed_frames(qframes)
    ev = srv._evidence_localizer.localize(qfeats, np.array(qtimes, dtype=np.float32),
                                          bundle, dense_query=dense)
    print(f"\n===== {name} ed{a}-{z} mode={ev.mode} n_query={ev.n_query}", flush=True)
    prim = ev.primary
    if prim is None or prim.original_span is None:
        print("  primary None -> 触发前提不成立", flush=True)
        continue
    psim = prim.best_sim or 0.0
    pmid = (prim.original_span[0] + prim.original_span[1]) / 2.0
    print(f"  primary {prim.original_span[0]:.1f}-{prim.original_span[1]:.1f} sim={psim:.3f} cover={prim.cover:.3f}", flush=True)
    ext = [x for x in (ev.all_spans or []) if x is not prim] \
        + list(ev.scene_spans or []) + list(ev.event_spans or [])
    best_ext_mid, best_ext_sim = None, -1.0
    for s in ext:
        if s.original_span is None or s.best_sim is None:
            continue
        if s.best_sim > best_ext_sim:
            best_ext_sim = s.best_sim
            best_ext_mid = (s.original_span[0] + s.original_span[1]) / 2.0
    gap = abs(best_ext_mid - pmid) if best_ext_mid is not None else float("nan")
    drift = best_ext_mid is not None and gap > cfg.pipeline.subshot_drift_gap_s \
        and psim < cfg.pipeline.subshot_retry_min_sim
    print(f"  best_ext mid={best_ext_mid} sim={best_ext_sim:.3f} gap={gap:.1f} "
          f"drift={drift} (gap>{cfg.pipeline.subshot_drift_gap_s} & psim<{cfg.pipeline.subshot_retry_min_sim})", flush=True)
    if not drift:
        continue
    sub_ev, sub_sim = srv._subshot_relocalize(
        type("S", (), {"feats": qfeats, "times": np.array(qtimes, dtype=np.float32),
                       "span": type("SP", (), {"start": a, "end": z, "width": z - a})()})(),
        bundle, dense, cfg.pipeline)
    if sub_ev is None:
        print("  sub_ev None -> 不可拆/无证据", flush=True)
        continue
    print(f"  sub_sim={sub_sim:.3f} sub primary={sub_ev.primary.original_span} "
          f"sim={(sub_ev.primary.best_sim or 0):.3f}", flush=True)
    for s in sub_ev.spans:
        print(f"    sub span {s.original_span[0]:.1f}-{s.original_span[1]:.1f} "
              f"sim={(s.best_sim or 0):.3f} cover={s.cover:.3f} frames={s.query_frames}", flush=True)
    promo = max(sub_ev.spans, key=lambda s: (s.best_sim or 0.0))
    print(f"  采纳判据 promo.sim={(promo.best_sim or 0):.3f} > psim={psim:.3f} "
          f"-> {((promo.best_sim or 0) > psim)}", flush=True)
print("\nDONE", flush=True)
