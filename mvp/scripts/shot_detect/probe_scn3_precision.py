# -*- coding: utf-8 -*-
"""scn3 精度探针（只读）：边界**表**的时间精度，不改 runtime、不建索引。

问题：现役 scenes.npy 的边界时刻被吸到 1fps 索引网格，而像素通道本身跑在 10fps。
本探针量化「若边界表保留 10fps 时刻」在同尺上的收益，并做两条独立交叉验证。

口径（与评测 harness 同一把尺子，判据**全部从生产模块导入**，不另写一份）：
  A 现役表    = 索引里的 scenes.npy 边界（1fps 网格）
  B 像素10fps = detect_pixel_boundaries 的原始时刻（10fps，不 snap）
  C 融合      = B（10fps）+ CLS 腿（1fps 网格）按 nms_by_strength 融合 —— 即 scn3 形态

交叉验证样本（独立于尺子）：
  cut13 = work/cap15_film_20261018/edge_offsets_v2.json 里逐帧自算的真剪点 13 条

用法：
  python mvp/scripts/shot_detect/probe_scn3_precision.py             # 尺子口径
  python mvp/scripts/shot_detect/probe_scn3_precision.py --cuts      # 导出侧真剪点
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BENCH = HERE.parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(HERE))

import eval_shot_detector as E                      # noqa: E402
from engine.segment.scene_detect import (           # noqa: E402
    PixelStream, SceneDetectConfig, block_gate_ok, detect_pixel_boundaries,
    local_peaks, nms_by_strength, _snap_index)
from infrastructure import paths                    # noqa: E402

OUT = BENCH / "work" / "scn3_precision_20261018"
TOL_SNAP_FAIR = 0.5      # 1fps 网格自身下限 ±0.5s，用它做“公平容差”对照


def signed(preds, gts, tol):
    """一一配对（与 eval.match 同贪心），返回 pred-gt 有符号差。"""
    preds, gts = sorted(preds), sorted(gts)
    used, out = set(), []
    for g in gts:
        bi, bd = None, tol + 1e-9
        for i, p in enumerate(preds):
            if i in used:
                continue
            if abs(p - g) < bd:
                bi, bd = i, abs(p - g)
        if bi is not None:
            used.add(bi)
            out.append(preds[bi] - g)
    return out


def stat(d):
    a = np.abs(np.asarray(d)) if len(d) else np.array([])
    if not len(a):
        return {}
    return dict(n=int(len(a)), med=round(float(np.median(a)), 3),
                p90=round(float(np.percentile(a, 90)), 3), max=round(float(a.max()), 3),
                le012=int((a <= 0.12).sum()), le025=int((a <= 0.25).sum()),
                le050=int((a <= 0.50).sum()),
                signed_med=round(float(np.median(d)), 3))


def pixel_series_on(dt, case, t0, t1):
    st = PixelStream(hist_weight=E.scene_cfg().pixel_hist_weight)
    for t, f in dt.io.iter_frames(dt.video[case], E.PIX_FPS, start=t0, end=t1, scale=E.PIX_SCALE):
        st.push(float(t), f)
    tt, mix = st.arrays()
    return tt, mix, st.hist_matrix()


def legs_for_window(dt, case, t0, t1):
    """窗内三档边界：A 现役表 / B 像素 10fps / C 融合。"""
    cfg = E.scene_cfg()
    tt, mix, hist = pixel_series_on(dt, case, t0, t1)
    def gate(x):
        if not cfg.block_gate or hist.shape[0] < 3:
            return True
        k = int(np.clip(np.searchsorted(tt, x, side="left") + 1, 1, hist.shape[0] - 1))
        return block_gate_ok(hist, k, cfg)

    raw = [float(t) for t in detect_pixel_boundaries(tt, mix, thr=cfg.pixel_thr,
            abs_floor=cfg.pixel_abs_floor, rel_mult=cfg.pixel_rel_mult,
            rel_win=cfg.pixel_rel_win) if gate(t)]
    d = dt.cls[case]
    times = np.asarray(d["times"], dtype=float)
    fps = float(d["fps"])
    snap = sorted({float(times[_snap_index(times, t)]) for t in raw})
    # CLS 腿（1fps 网格，与 runtime 同判据）
    cls_items = []
    s = d["s"]
    for k in np.flatnonzero(local_peaks(s) & (s >= cfg.cls_cut_abs)):
        x = float(d["times"][int(k)] + 1.0 / fps)
        if t0 <= x <= t1 and gate(x):
            cls_items.append((x, cfg.cls_weight * float(s[int(k)])))
    fused = [x for x, _ in nms_by_strength(list(cls_items) + [(t, 1.0) for t in raw], cfg.min_gap_s)
             if t0 <= x <= t1]
    A = [p for p in dt.scenes_now(case) if t0 - 1e-6 <= p <= t1 + 1e-6]
    B = [t for t in raw if t0 <= t <= t1]
    return A, B, sorted(fused)


def mode_gt():
    gt = E.load_gt(high_only=True)
    dt = E.Data()
    acc = {"A_scn2_1fps": [], "B_pixel_10fps": [], "C_fused_scn3": []}
    counts = {"A": 0, "B": 0, "C": 0}
    for c in E.CASES:
        for w in [x for x in gt if x["case"] == c]:
            A, B, C = legs_for_window(dt, c, float(w["t0"]), float(w["t1"]))
            counts["A"] += len(A); counts["B"] += len(B); counts["C"] += len(C)
            acc["A_scn2_1fps"] += signed(A, w["gt_times"], TOL_SNAP_FAIR)
            acc["B_pixel_10fps"] += signed(B, w["gt_times"], TOL_SNAP_FAIR)
            acc["C_fused_scn3"] += signed(C, w["gt_times"], TOL_SNAP_FAIR)
    print(f"[尺子 boundary_gt_v1] 44 窗，GT conf=high，配对容差 ±{TOL_SNAP_FAIR}s")
    print(f"  窗内边界条数：A={counts['A']} B={counts['B']} C={counts['C']}")
    out = {}
    for k, v in acc.items():
        s = stat(v); out[k] = s
        print(f"  {k:16s} n={s['n']:3d} |d|med={s['med']:.3f} p90={s['p90']:.3f} "
              f"le0.12={s['le012']:3d} le0.25={s['le025']:3d} le0.50={s['le050']:3d} "
              f"signed_med={s['signed_med']:+.3f}")
    return out


def mode_cuts():
    src = BENCH / "work" / "cap15_film_20261018" / "edge_offsets_v2.json"
    d = json.loads(src.read_text(encoding="utf-8"))
    rows = d["rows"]
    print(f"[导出侧独立样本] edge_offsets_v2 的 {len(rows)} 条逐帧自算真剪点")
    dt = E.Data()
    # edge_offsets_v2 只覆盖 2mkv（edge 1304 等），按 case 绑定
    case = "2mkv"
    out_rows = []
    for r in rows:
        if r.get("true_cut") is None:
            print(f"  skip row i={r.get('i')} side={r.get('side')} (窗口内无显著剪点)")
            continue
        cut = float(r["true_cut"])
        A, B, C = legs_for_window(dt, case, cut - 3.0, cut + 3.0)
        def nearest(v):
            return min(v, key=lambda x: abs(x - cut)) if v else None
        na, nb, nc = nearest(A), nearest(B), nearest(C)
        out_rows.append(dict(true_cut=cut, side=r.get("side"),
                             A=na, dA=None if na is None else round(na - cut, 3),
                             B=nb, dB=None if nb is None else round(nb - cut, 3),
                             C=nc, dC=None if nc is None else round(nc - cut, 3)))
        print(f"  cut={cut:9.3f} ({r.get('side')})  A={na} d={out_rows[-1]['dA']}   "
              f"B={nb} d={out_rows[-1]['dB']}   C={nc} d={out_rows[-1]['dC']}")
    for k, key in (("A_scn2_1fps", "dA"), ("B_pixel_10fps", "dB"), ("C_fused_scn3", "dC")):
        vals = [x[key] for x in out_rows if x[key] is not None]
        s = stat(vals)
        print(f"  {k:16s} {s}")
    return out_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuts", action="store_true")
    ap.add_argument("--save", action="store_true")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    res = mode_cuts() if a.cuts else mode_gt()
    if a.save:
        tag = "cuts" if a.cuts else "gt"
        p = OUT / f"probe_scn3_{tag}.json"
        p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print("saved", p)


if __name__ == "__main__":
    main()
