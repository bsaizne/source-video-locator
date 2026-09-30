# -*- coding: utf-8 -*-
"""索引密度探针 v2（2026-09-29 续28, 用户批准）。

⚠️ 前提更正（v1→v2）：v1 假设「生产=0.5fps/2s 网格」——实测**错**：
``config.pipeline.index_sampling_fps`` 出厂默认 = **1.0**，生产 2.mkv 索引 7668 行/1s 间距
（0.5fps 是 2026-08 H2 时代历史口径，已升代）。v1 的 phase C 两档实为同一网格、
phase B 增益 0 也是同配置重跑（副产品=确定性复跑零翻转回归确认，有效但非密度结论）。
v2 改为：以生产 1fps 为基线，测**更密网格 2fps** 的红利（SVL_PROBE_FPS 可调）；
≥+3 ID ⇒ 索引密度工程立项候选；<+3 ⇒ 关闭（竞品同为 1fps，我方已不欠网格）。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

PROBE_FPS = float(os.environ.get("SVL_PROBE_FPS", "2.0"))

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
for p in (BENCH / "mvp" / "src", BENCH / "mvp", BENCH / "mvp" / "scripts"):
    sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

import sandbox_ordered_search_replay as osr  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402
from engine.feature_store import FeatureStore  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from measure_mainspan_caliber import truncate_main  # noqa: E402
from measure_shot_recall import evaluate  # noqa: E402

ORIG = r"D:\video\2.mkv"
EDITED = r"D:\video\1.mp4"
GT = BENCH / "datasets/real/ground_truth_v4.json"
BASE_RESULTS = BENCH / "work/fastglobal_default_2mkv.results.json"
BASE_FPS = 1.0  # 生产出厂默认（v1 误标 0.5 已更正）
IDX = BENCH / "work" / f"index{PROBE_FPS:g}fps"


def marks_of(r):
    return {row["id"]: row["mark"] for row in r["per_pos"]}


def flip_list(m_base, m_new):
    return {k: [m_base.get(k), v] for k, v in m_new.items() if m_base.get(k) != v}


def main() -> int:
    report: dict = {}
    srv = SourceLocatorService(config=load_config())
    assert isinstance(srv.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(srv.backend).__name__}"
    print("BACKEND_SELECTED type=%s" % type(srv.backend).__name__, flush=True)

    # ---------------- A: PROBE_FPS 索引（隔离根） ---------------- #
    store1 = FeatureStore(srv.ffmpeg, IDX, sampling_fps=PROBE_FPS)
    from domain import IndexValidationStatus  # noqa: E402
    t0 = time.monotonic()
    if store1.validate_index(ORIG).status is not IndexValidationStatus.VALID:
        def _cb(ev):
            done = getattr(ev, "done", None)
            if done and done % 1500 == 0:
                print(f"  index{PROBE_FPS:g}fps embedding {done}/{getattr(ev, 'total', '?')}", flush=True)
        store1.create_index(ORIG, srv.backend, progress=_cb)
    print(f"[A] {PROBE_FPS:g}fps index ready {time.monotonic()-t0:.1f}s", flush=True)

    # ---------------- B: 生产全链 @1fps ---------------- #
    srv._store = store1  # 只换源索引域；编辑侧缓存键含 store.feature_version ⇒ 会重建 ED 缓存(预期)
    t0 = time.monotonic()
    batch = srv.locate(EDITED, ORIG)
    out = BENCH / "work" / f"fpsprod_{PROBE_FPS:g}.results.json"
    out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[B] prod locate @{PROBE_FPS:g}fps {time.monotonic()-t0:.1f}s ({len(batch.results)} segs)", flush=True)

    gt = json.loads(GT.read_text(encoding="utf-8"))
    base = json.loads(BASE_RESULTS.read_text(encoding="utf-8"))
    new = batch.to_dict()
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        b_full = evaluate(gt, base["results"], label="base_full")
        n_full = evaluate(gt, new["results"], label="new_full")
        b_tr = evaluate(gt, truncate_main(base)["results"], label="base_trunc")
        n_tr = evaluate(gt, truncate_main(new)["results"], label="new_trunc")
    report["prod"] = {
        "base": {"strict": b_full["strict_hit"], "scene": b_full["scene_hit"], "fp": b_full["fp"],
                 "trunc": b_tr["strict_hit"], "n": b_full["n_pos"]},
        "new": {"strict": n_full["strict_hit"], "scene": n_full["scene_hit"], "fp": n_full["fp"],
                "trunc": n_tr["strict_hit"], "n": n_full["n_pos"]},
        "trunc_gain": n_tr["strict_hit"] - b_tr["strict_hit"],
        "full_strict_gain": n_full["strict_hit"] - b_full["strict_hit"],
        "flips_full": flip_list(marks_of(b_full), marks_of(n_full)),
        "flips_trunc": flip_list(marks_of(b_tr), marks_of(n_tr)),
    }
    print("[B] prod:", json.dumps(report["prod"]["base"], ensure_ascii=False), "→",
          json.dumps(report["prod"]["new"], ensure_ascii=False),
          f"trunc_gain={report['prod']['trunc_gain']}", flush=True)

    # ---------------- C: ordered 沙盒三臂 × 两档网格 ---------------- #
    bundle1 = store1.load_index(ORIG)
    store05 = FeatureStore(srv.ffmpeg, srv.index_root, sampling_fps=BASE_FPS)
    bundle05 = store05.load_index(ORIG)
    shots = srv.analyze_edited_video(EDITED)
    step = max(1, int(round(srv.config.pipeline.seq_align.edit_fps / 3.0)))
    rows, meta = [], []
    for sh in sorted(shots, key=lambda x: x.span.start):
        d = srv._embed_dense_query(sh, Path(EDITED))
        if d is None:
            continue
        f = np.asarray(d[0])[::step]
        if f.shape[0]:
            rows.append(f)
            meta.append(sh)
    ED = np.vstack(rows)
    segs, cur = [], 0
    for sh, f in zip(meta, rows):
        segs.append((cur, cur + f.shape[0], sh.span.end - sh.span.start,
                     sh.span.start, sh.span.end))
        cur += f.shape[0]
    report["sandbox"] = {}
    for tag, bundle in ((f"grid{BASE_FPS:g}", bundle05), (f"grid{PROBE_FPS:g}", bundle1)):
        st = np.asarray(bundle.times, dtype=np.float64)
        S = np.maximum(ED @ bundle.features.T, 0.0)
        row = {}
        with contextlib.redirect_stdout(buf):
            for arm in ("raw", "argmax_g", "rrnop"):
                pls, _ = osr.ordered_search(S, st, segs, arm=arm)
                res = osr.build_results(pls, segs, st)
                r = evaluate(gt, res["results"], label=f"{tag}_{arm}")
                row[arm] = {"strict": r["strict_hit"],
                            "placed": sum(p is not None for p in pls)}
        report["sandbox"][tag] = row
        print(f"[C] {tag}:", json.dumps(row), flush=True)

    gate = report["prod"]["trunc_gain"]
    report["verdict"] = ("GAIN_CONFIRMED(≥+3): 量化红利坐实→可申请工程化+门限复标"
                         if gate >= 3 else
                         "GAIN_NEGATIVE(<+3): 关闭, 竞品网格叙事不构成我方欠账")
    (BENCH / "work" / f"fps_probe_report_{PROBE_FPS:g}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("VERDICT:", report["verdict"], flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
