# -*- coding: utf-8 -*-
"""原片镜头边界检测的**常设评测 harness**（尺子 = boundary_gt_v1.json）。

尺子怎么来的：4 片分层抽 44 个 12s 窗（+test2 已知漏切区定向 4 窗），4fps 接触表逐格目检，
每条边界都经过画面确认（详见 mvp/docs/FINDINGS_SHOT_DETECTION_A1_20261011.md §2）。

口径（改动前请先读）：
- 现役索引 CLS 采样 **1fps** ⇒ 检测器边界粒度 1s，所以**主容差 ±1.0s**；±0.5s 只对像素通道公平。
- 主判据只用 conf=high 的边界（conf=low 是正反打/手持漂移歧义，另档报数）。
- 只读：不改 runtime、不重建索引。

用法：
  PYTHONPATH=mvp/src;mvp python mvp/scripts/shot_detect/eval_shot_detector.py --mode ablation
  ... --mode arms | holdout | ceiling | region
"""
from __future__ import annotations
import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
BENCH = HERE.parents[2]
GT_PATH = HERE / "boundary_gt_v1.json"
SCRATCH = BENCH / "work" / "shot_gt"
CASES = ("2mkv", "test1", "test2", "test3")
TOL_MAIN = 1.0
TOL_SEC = 0.5
PIX_FPS = 10.0
PIX_SCALE = (160, 90)
_SCENE_CFG = None


def scene_cfg():
    """生产判据默认值（懒导入：本模块的 sys.path 装配在 _bootstrap 里）。"""
    global _SCENE_CFG
    if _SCENE_CFG is None:
        _bootstrap()
        from engine.segment.scene_detect import SceneDetectConfig
        _SCENE_CFG = SceneDetectConfig()
    return _SCENE_CFG

# 现役生产参数（feature_store 的场景表旋钮）
CUR = dict(cut_abs=0.15, z_thresh=1.5, smooth=1, min_shot_s=3.0, context_window=7)


def _bootstrap() -> None:
    sys.path.insert(0, str(BENCH / "mvp" / "src"))
    sys.path.insert(0, str(BENCH / "mvp"))
    import os
    os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
    os.environ.setdefault("MEDIA_FFPROBE", str(
        Path(r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
             r"\static_ffmpeg\bin\win32\ffprobe.exe")))


def load_gt(high_only: bool = True) -> list[dict]:
    gt = json.loads(GT_PATH.read_text(encoding="utf-8"))["windows"]
    out = []
    for w in gt:
        bs = [b for b in w["boundaries"] if (not high_only or b["conf"] == "high")]
        out.append({**w, "gt_times": [float(b["t"]) for b in bs]})
    return out


def match(preds, gts, tol):
    preds, gts = sorted(preds), sorted(gts)
    used, pairs = set(), []
    for g in gts:
        best, bd = None, tol + 1e-9
        for i, p in enumerate(preds):
            if i in used:
                continue
            if abs(p - g) < bd:
                best, bd = i, abs(p - g)
        if best is not None:
            used.add(best)
            pairs.append(bd)
    return len(pairs), len(preds) - len(pairs), len(gts) - len(pairs), pairs


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return round(p, 3), round(r, 3), round(2 * p * r / (p + r), 3) if p + r else 0.0


def score(preds_by_case, gt, tol=TOL_MAIN):
    tot, per, disp = [0, 0, 0], {}, []
    for c in CASES:
        ct = [0, 0, 0]
        for w in [x for x in gt if x["case"] == c]:
            pw = [p for p in preds_by_case[c] if w["t0"] - 1e-6 <= p <= w["t1"] + 1e-6]
            tp, fp, fn, dd = match(pw, w["gt_times"], tol)
            ct = [ct[i] + v for i, v in enumerate((tp, fp, fn))]
            disp += dd
        per[c] = list(prf(*ct)) + [round(float(np.median(dd)), 2) if dd else None]
        tot = [tot[i] + ct[i] for i in range(3)]
    return per, list(prf(*tot)) + [round(float(np.median(disp)), 3) if disp else None]


class Data:
    """索引特征 + 像素通道的解码缓存（缓存落在 work/shot_gt，删了会自动重解码）。"""

    def __init__(self):
        _bootstrap()
        from engine.segment import segment as seg
        from engine.feature_store import FeatureStore
        from infrastructure import paths
        from infrastructure.config import load_config
        from infrastructure.results_repo import load_results
        from media.ffmpeg import FFmpegIO
        self.seg = seg
        cfg = load_config()
        self.io = FFmpegIO()
        store = FeatureStore(self.io, paths.index_root(),
                             sampling_fps=float(cfg.pipeline.index_sampling_fps))
        self.video = {}
        self.cls = {}
        for c in CASES:
            b = load_results(BENCH / "work" / f"fastglobal_default_{c}.results.json")
            v = Path(b.original_video)
            self.video[c] = v
            d = store.index_dir(v)
            feats = np.load(d / "features.npy")
            times = np.load(d / "times.npy")
            dd = self.seg.adjacent_distances(feats)
            s = self.seg._moving_average(dd, CUR["smooth"])
            mu, sd = self.seg._local_stats(s, CUR["context_window"])
            self.cls[c] = dict(feats=feats, times=times, fps=float(np.median(np.diff(times))),
                               s=s, z=(s - mu) / np.maximum(sd, self.seg.SEG_SD_FLOOR),
                               scenes=np.load(d / "scenes.npy"))

    # ---- CLS 通道臂 ----
    def cls_arm(self, c, **over):
        p = dict(CUR); p.update(over)
        d = self.cls[c]
        shots = self.seg.detect_shots(d["feats"], d["times"], fps=d["fps"], **p)
        return [float(sh.span.start) for sh in shots[1:]]

    def scenes_now(self, c) -> list[float]:
        return [float(x[0]) for x in self.cls[c]["scenes"][1:]]

    def s_only(self, c, thr, min_shot_s=0.0) -> list[float]:
        d = self.cls[c]
        cand = np.flatnonzero(self.seg._local_peaks(d["s"]) & (d["s"] >= thr)).tolist()
        gap = max(1, int(round(min_shot_s / d["fps"]))) if min_shot_s > 0 else 1
        kept = self.seg._nms(cand, d["s"], gap)
        return [float(d["times"][k] + 1.0 / d["fps"]) for k in kept]

    # ---- 像素通道臂 ----
    def pixel_series(self, c, t0, t1):
        """走**生产同款**累加器（``engine.segment.scene_detect.PixelStream``）。

        尺子这边绝不能自己另写一份像素判据：2026-10-11 调参期两边各写一份，
        两份都带同一个 int16 溢出 bug 才让阈值选在了错的序列上。
        缓存里连每帧直方图一起存 —— A-B-A 持续性门要用它。
        """
        from engine.segment.scene_detect import PixelStream
        cache_f = SCRATCH / "pixel_series_cache_v3.json"
        ser = json.loads(cache_f.read_text(encoding="utf-8")) if cache_f.exists() else {}
        key = f"{c}|{t0}"
        if key not in ser:
            st = PixelStream(hist_weight=scene_cfg().pixel_hist_weight)
            for t, f in self.io.iter_frames(self.video[c], PIX_FPS, start=t0, end=t1,
                                            scale=PIX_SCALE):
                st.push(float(t), f)
            tt, mix = st.arrays()
            ser[key] = {"tt": [round(x, 3) for x in tt.tolist()],
                        "mix": [round(x, 4) for x in mix.tolist()],
                        "hist": st.hist_matrix().round(5).tolist()}
            SCRATCH.mkdir(parents=True, exist_ok=True)
            cache_f.write_text(json.dumps(ser), encoding="utf-8")
        return ser[key]

    def pixel_arm(self, c, gt_windows, use_cls: bool = True) -> list[float]:
        """像素腿（生产判据）：``detect_pixel_boundaries`` + A-B-A 门 + 可选 CLS 证据 + NMS。

        公式一律从 ``engine.segment.scene_detect`` 导入；本函数只做「按窗取序列 + 过滤窗界」
        的胶水，避免尺子与 runtime 两处实现漂移。
        """
        from engine.segment.scene_detect import (block_gate_ok, detect_pixel_boundaries,
                                                 local_peaks, nms_by_strength)
        cfg = scene_cfg()
        out: list[float] = []
        for w in [x for x in gt_windows if x["case"] == c]:
            rec = self.pixel_series(c, w["t0"], w["t1"])
            tt = np.asarray(rec["tt"]); mix = np.asarray(rec["mix"])
            hist = np.asarray(rec["hist"], dtype=np.float32)

            def gate(x, tt=tt, hist=hist):
                # 判据入口与 runtime 同一个函数，尺子这边只负责「时间 -> hist 行号」的换算
                if not cfg.block_gate or hist.shape[0] < 3:
                    return True
                k = int(np.clip(np.searchsorted(tt, x, side="left") + 1, 1, hist.shape[0] - 1))
                return block_gate_ok(hist, k, cfg)

            items = [(float(x), 1.0) for x in
                     detect_pixel_boundaries(tt, mix, thr=cfg.pixel_thr,
                                             abs_floor=cfg.pixel_abs_floor,
                                             rel_mult=cfg.pixel_rel_mult,
                                             rel_win=cfg.pixel_rel_win) if gate(x)]
            if use_cls:
                d = self.cls[c]
                s = d["s"]
                for k in np.flatnonzero(local_peaks(s) & (s >= cfg.cls_cut_abs)):
                    x = float(d["times"][int(k)] + 1.0 / d["fps"])
                    if w["t0"] <= x <= w["t1"] and gate(x):
                        items.append((x, cfg.cls_weight * float(s[int(k)])))
            out += [x for x, _ in nms_by_strength(items, cfg.min_gap_s)
                    if w["t0"] <= x <= w["t1"]]
        return sorted(out)


# --------------------------------------------------------------------------- #
# 各模式
# --------------------------------------------------------------------------- #
def mode_ablation(dt: Data, gt) -> None:
    legs = [
        ("现役（cut.15/z1.5/cw7/ms3.0）", {}),
        ("只把 min_shot_s 3.0 -> 1.0", dict(min_shot_s=1.0)),
        ("只把 context_window 7 -> 15", dict(context_window=15)),
        ("只把 z_thresh 1.5 -> 0.6", dict(z_thresh=0.6)),
        ("只把 z 判据关掉", dict(z_thresh=-1e9)),
        ("只把 cut_abs .15 -> .30", dict(cut_abs=0.30)),
        ("ms1.0 + z关", dict(min_shot_s=1.0, z_thresh=-1e9)),
        ("ms1.0 + z关 + cut.30", dict(min_shot_s=1.0, z_thresh=-1e9, cut_abs=0.30)),
        ("ms1.0 + z关 + cut.40", dict(min_shot_s=1.0, z_thresh=-1e9, cut_abs=0.40)),
    ]
    print("%-38s %-24s %-22s %s" % ("leg", "overall P/R/F1", "R: 2mkv/test1/test2/test3", "全片边界数"))
    for name, over in legs:
        pr = {c: dt.cls_arm(c, **over) for c in CASES}
        per, ov = score(pr, gt)
        print("%-38s %-24s %-22s %d" % (name, str(ov[:3]),
                                        "/".join("%.2f" % per[c][1] for c in CASES),
                                        sum(len(v) for v in pr.values())))


def mode_ceiling(dt: Data, gt) -> None:
    print("== 候选集天花板：真边界邻域内 CLS 距离序列是否存在局部极大（任何阈值的前提）==")
    for c in CASES:
        d = dt.cls[c]
        pk = dt.seg._local_peaks(d["s"])
        cands = [float(d["times"][k] + 1.0 / d["fps"]) for k in np.flatnonzero(pk)]
        row = {}
        for tol in (TOL_MAIN, TOL_SEC):
            tp = fn = 0
            for w in [x for x in gt if x["case"] == c]:
                a, b, cc, _ = match([p for p in cands if w["t0"] <= p <= w["t1"]], w["gt_times"], tol)
                tp += a; fn += cc
            row[tol] = round(tp / max(tp + fn, 1), 3)
        print(f"  {c}: ±1.0s 可达召回={row[TOL_MAIN]}  ±0.5s 可达召回={row[TOL_SEC]}")
    print("\n== CLS 盲区：真边界邻域（±2 格）内 s 的最大值分布 ==")
    for c in CASES:
        d = dt.cls[c]
        mx = []
        for w in [x for x in gt if x["case"] == c]:
            for b in w["boundaries"]:
                if b["conf"] != "high":
                    continue
                j = int(round(b["t"] - float(d["times"][0])))
                seg = d["s"][max(j - 2, 0):min(j + 2, len(d["s"]))]
                mx.append(float(seg.max()) if seg.size else 0.0)
        mx = np.array(mx)
        print(f"  {c}: n={mx.size} 中位={np.percentile(mx,50):.3f} "
              f"<0.15 占 {(mx < 0.15).mean():.0%}  <0.25 占 {(mx < 0.25).mean():.0%}")


def mode_arms(dt: Data, gt) -> None:
    print("%-44s %-26s %-26s %s" % ("arm", "P/R/F1 @±1.0s", "P/R/F1 @±0.5s", "全片边界数"))
    print("    （每片 P/R 单独打：2026-10-11 的教训 = 池化 P 0.70 掩盖了 2mkv 只有 0.57）")
    arms = {"现役 scenes.npy": {c: dt.scenes_now(c) for c in CASES}}
    for thr in (0.30, 0.40, 0.50):
        arms[f"CLS 纯 s 阈值 {thr:g}"] = {c: dt.s_only(c, thr) for c in CASES}
    for name, pr in arms.items():
        per, ov = score(pr, gt, TOL_MAIN)
        _, ov2 = score(pr, gt, TOL_SEC)
        n = sum(len(v) for v in pr.values())
        print("%-44s %-26s %-26s %d" % (name, str(ov[:3]), str(ov2[:3]), n))
        for c in CASES:
            gp = sum(len(w["gt_times"]) for w in gt if w["case"] == c)
            pp = sum(1 for x in pr[c] for w in gt
                     if w["case"] == c and w["t0"] <= x <= w["t1"])
            print("      %-8s P/R = %.3f / %.3f   （窗内预测 %d vs GT %d）"
                  % (c, per[c][0], per[c][1], pp, gp))
    print("\n== 分腿对照（生产判据：像素腿单独 / +CLS 证据融合）==")
    for name, kw in (("pix only", dict(use_cls=False)), ("pix + cls", dict(use_cls=True))):
        pr = {c: dt.pixel_arm(c, gt, **kw) for c in CASES}
        per, ov = score(pr, gt, TOL_MAIN)
        print("  %-10s pooled P/R/F1 = %s   每片 P %s" % (
            name, str(ov[:3]), "/".join("%.2f" % per[c][0] for c in CASES)))


def mode_holdout(dt: Data, gt) -> None:
    sel, hold = {}, {}
    for c in CASES:
        ws = sorted([x for x in gt if x["case"] == c], key=lambda w: w["t0"])
        sel[c], hold[c] = ws[0::2], ws[1::2]
    print("选参窗 %d / 留出窗 %d" % (sum(len(v) for v in sel.values()),
                                     sum(len(v) for v in hold.values())))
    grid = [dict(cut_abs=ca, z_thresh=z, min_shot_s=ms, context_window=cw)
            for ca in (0.15, 0.20, 0.25, 0.30, 0.40)
            for z in (-1e9, 0.6, 1.0, 1.5) for ms in (1.0, 2.0, 3.0) for cw in (7, 11, 15)]
    cache, scored = {}, []
    for g in grid:
        k = json.dumps(g, sort_keys=True)
        cache[k] = cache.get(k) or {c: dt.cls_arm(c, **g) for c in CASES}
        scored.append((score(cache[k], [w for c in CASES for w in sel[c]])[1][2], g))
    scored.sort(key=lambda x: -x[0])
    print("\n只在选参窗上选 TOP5，到留出窗上验：")
    print("%-46s %-24s %-24s" % ("params", "选参窗 P/R/F1", "留出窗 P/R/F1"))
    for _, g in scored[:5]:
        pr = {c: dt.cls_arm(c, **g) for c in CASES}
        a = score(pr, [w for c in CASES for w in sel[c]])[1][:3]
        b = score(pr, [w for c in CASES for w in hold[c]])[1][:3]
        print("%-46s %-24s %-24s" % (
            "cut=%g z=%s ms=%g cw=%d" % (g["cut_abs"], "关" if g["z_thresh"] < 0 else g["z_thresh"],
                                         g["min_shot_s"], g["context_window"]), a, b))
    cur = {c: dt.scenes_now(c) for c in CASES}
    print("%-46s %-24s %-24s" % ("现役 scenes.npy",
                                 score(cur, [w for c in CASES for w in sel[c]])[1][:3],
                                 score(cur, [w for c in CASES for w in hold[c]])[1][:3]))


def mode_region(dt: Data, gt) -> None:
    a0, a1 = 3285.0, 3333.0
    cov = dt.cls["test2"]["scenes"]
    cov = cov[(cov[:, 0] < a1) & (cov[:, 1] > a0)]
    print(f"test2 已知漏切区 {a0:.0f}-{a1:.0f}（48s）")
    print(f"  现役 scenes.npy 段数 = {len(cov)}")
    for row in cov:
        print(f"     {row[0]:.2f} -> {row[1]:.2f} 宽 {row[1]-row[0]:.1f}s")
    for thr in (0.30, 0.40):
        pr = [p for p in dt.s_only("test2", thr) if a0 <= p <= a1]
        print(f"  CLS 纯 s 阈值 {thr:g}: {len(pr)} 个边界")
    reg = [w for w in gt if w["case"] == "test2" and a0 <= w["t0"] < a1]
    pw = dt.pixel_arm("test2", reg)
    print(f"  生产像素臂(含 A-B-A 门)在该 4 窗: {len(pw)} 个边界 -> {[round(x,1) for x in pw]}")
    g = sorted(t for w in gt if w["case"] == "test2" and a0 <= w["t0"] < a1 for t in w["gt_times"])
    print(f"  目检 GT: {len(g)} 个边界 -> {g}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default="ablation",
                    choices=["ablation", "arms", "ceiling", "holdout", "region"])
    a = ap.parse_args()
    if not sys.stdout.encoding.lower().startswith("utf"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    gt = load_gt()
    print(f"尺子: {len(gt)} 窗 / {sum(len(w['gt_times']) for w in gt)} 条 conf=high 边界"
          f"（主容差 ±{TOL_MAIN}s）")
    dt = Data()
    t0 = time.time()
    {"ablation": mode_ablation, "arms": mode_arms, "ceiling": mode_ceiling,
     "holdout": mode_holdout, "region": mode_region}[a.mode](dt, gt)
    print(f"\n（{a.mode} 用时 {time.time()-t0:.1f}s）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
