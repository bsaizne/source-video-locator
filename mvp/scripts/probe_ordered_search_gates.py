# -*- coding: utf-8 -*-
"""ordered_search 门限诊断（2026-09-29 续27）：逐段打印 top-1 候选的
coarse/support/refined/margin 与 GT 正确起点侧的同三项分值，判断竞品 0.55/0.35/0.62
门限在我方分值分布上的可达性。纯 numpy 秒级探针（CPU 允许，无推理）。"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
for p in ("mvp/src", "mvp", "mvp/scripts"):
    sys.path.insert(0, str(BENCH / p))

import numpy as np  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from rerun_fast_global import CASES  # noqa: E402

name = sys.argv[1] if len(sys.argv) > 1 else "test1"
n_show = int(sys.argv[2]) if len(sys.argv) > 2 else 12
srv = SourceLocatorService(config=load_config())
paths = CASES[name]
b = srv.store.load_index(paths["original"])
shots = srv.analyze_edited_video(paths["edited"])
st = np.asarray(b.times, float)
gs = 1.0 / float(st[1] - st[0])
step = max(1, int(round(srv.config.pipeline.seq_align.edit_fps / 3.0)))
rows, meta = [], []
for sh in sorted(shots, key=lambda x: x.span.start):
    d = srv._embed_dense_query(sh, Path(paths["edited"]))
    if d is None:
        continue
    f = np.asarray(d[0])[::step]
    if f.shape[0] == 0:
        continue
    rows.append(f)
    meta.append(sh)
ED = np.vstack(rows)
S = np.maximum(ED @ b.features.T, 0.0)
gt = json.loads((BENCH / f"datasets/real/ground_truth_{name}.json").read_text(encoding="utf-8")) \
    if name != "2mkv" else json.loads((BENCH / "datasets/real/ground_truth_v4.json").read_text(encoding="utf-8"))
pos_by_ed = {round(p["edited"][0], 1): p["original"] for p in gt["positives"]}

cur = 0
out = []
for k, (sh, f) in enumerate(zip(meta, rows)):
    r = S[cur:cur + f.shape[0]]
    cur += f.shape[0]
    dur = sh.span.end - sh.span.start
    sc = max(1, int(round(dur * gs)))
    N = r.shape[1]
    if sc >= N:
        out.append(f"{k:2d} dur={dur:5.2f} SKIP(seg longer than index)")
        continue
    coarse_a, sup_a, ref_a = [], [], []
    for c in range(0, N - sc):
        sub = r[:, c:c + sc]
        bv = sub.max(axis=1)
        am = sub.argmax(axis=1)
        med = int(np.median(am))
        lo, hi = max(0, med - 1), min(sc, med + 2)
        coarse_a.append(bv.mean()); sup_a.append((bv >= 0.55).mean())
        ref_a.append(r[:, c + lo:c + hi].max(axis=1).mean())
    coarse_a = np.array(coarse_a); sup_a = np.array(sup_a); ref_a = np.array(ref_a)
    order = np.argsort(-coarse_a)[:3]
    margin = float(coarse_a[order[0]] - coarse_a[order[1]]) if order.size > 1 else 1.0
    line = (f"{k:2d} dur={dur:5.2f} top1 coarse={coarse_a[order[0]]:.3f} "
            f"sup={sup_a[order[0]]:.3f} ref={ref_a[order[0]]:.3f} mg={margin:.3f} "
            f"@{order[0] / gs:6.1f}s")
    key = round(sh.span.start, 1)
    o0 = pos_by_ed.get(key)
    if o0 is not None:
        gi = int(round(o0[0] * gs))
        gi = max(0, min(gi, N - sc - 1))
        line += f" || GT@{o0[0]:6.1f}s coarse={coarse_a[gi]:.3f} sup={sup_a[gi]:.3f} ref={ref_a[gi]:.3f}"
    out.append(line)
    if k + 1 >= n_show:
        break
print("\n".join(out))
