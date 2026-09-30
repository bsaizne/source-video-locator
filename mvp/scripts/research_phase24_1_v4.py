"""Phase 24-1 三探针重跑(修正 GT,v4/verified)—— 研究侧零 runtime 改动。

起因: FINDINGS_GT_CONTAMINATION_AUDIT.md(见 .agent/STATE.md 2026-09-22 条)——
原 phase24_1 预研 5 个探针中 3 个建立在已证伪数据上:
  * p08b 的「真值窗」1048-1050 = p38 旧错误 GT 区(已作废; p08b 正确 = p08 的 1108.15-1109.1);
  * p26 真值窗 2808-2811 = GT 标错(正确 1768.2-1770.05);
  * t4r01 属 test4 数据无效(test4-ed / test4-om 是两部不同电影) → 剔除。
本脚本用修正 GT 重跑探针①(视觉几何一致性)与探针②(时序运动签名)。

口径与原脚本 research_phase24_1.py 完全一致(仅换真值窗/兄弟窗), 便于与原存档逐帧对照:
候选集 = CLS top-40 ∪ 真值窗 ∪ 兄弟窗; 互近邻 + estimateAffinePartial2D(RANSAC, 5px) 内点率 + 单应内点率。
探针③(硬负例盘点)在 research_phase24_1_data.py 中, 其 GT 相关性仅限锚点场景 → 见独立的 v4 盘点。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" \
      mvp/scripts/research_phase24_1_v4.py [--probes p08,p26] [--skip-motion] [--motion-only]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import cv2

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from device.dinov2_model import DinoV2Small, _imagenet_preprocess
from media.ffmpeg import FFmpegIO

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FP = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
      / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
WEIGHTS = BENCH / "work" / "dinov2_weights" / "dinov2_vits14_pretrain.pth"
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"
IDX_T3 = IDX_DIR / "test3-om__074e2dcc.idx"

PAIRS = {
    "2mkv":  dict(orig="D:/video/2.mkv",  edit="D:/video/1.mp4", idx=IDX2),
    "test3": dict(orig="D:/ProjectXIXI/test3/test3-om.mp4",
                  edit="D:/ProjectXIXI/test3/test3-ed.mp4", idx=IDX_T3),
}

# (pair, id, query_t(编辑片), 真值窗[v4/verified], 兄弟/干扰窗, note)
# GT 来源: datasets/real/ground_truth_v4.json (2mkv) + datasets/real/ground_truth_test3.json (test3)
PROBES = [
    ("2mkv", "p08",  13.5, (1108.15, 1109.1), (1048.0, 1050.0),
     "瞭望塔机位(真值) vs 兄弟机位 1048-1050 [v3 原窗 1108-1110 基本一致]"),
    ("2mkv", "p08b", 13.9, (1108.15, 1109.1), (1048.0, 1050.0),
     "同一编辑段另一点; v3 把 1048-1050 当真值(=p38 旧错误 GT) 已作废"),
    ("2mkv", "p26",  76.8, (1768.2, 1770.05), None,
     "夜读; v3 原窗 2808-2811 系 GT 标错"),
    ("2mkv", "p01",   0.8, (2417.5, 2418.1), None, "金属球准备(sanity 易例)"),
    ("2mkv", "p04",   4.6, (839.0, 844.0),  None, "峡谷航拍(sanity 易例)"),
    ("test3", "t3r12", 64.75, (466.0, 478.0), (481.0, 488.0),
     "精灵王重复镜头(v3 原窗 454-480, 用户 09-02 人工定位修正为 466-478)"),
]

GRID = 37
TOPK = 40
QUERY_FRAMES = 3
RANSAC_THRESH = 5.0


def _l2(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


class Model:
    def __init__(self):
        import torch
        self.torch = torch
        self.m = DinoV2Small()
        self.m.load_state_dict(
            torch.load(str(WEIGHTS), map_location="cpu", weights_only=True),
            strict=False)
        self.m.eval()
        self._ff = FFmpegIO(FFMPEG, FP)
        self.cache = {}
        self._hooks = False

    def _feats(self, video: str, t: float):
        key = (video, float(t))
        if key in self.cache:
            return self.cache[key]
        f = self._ff.grab_frame(video, t)
        x = _imagenet_preprocess(f)
        with self.torch.no_grad():
            cls, pt = self.m.forward_features(x)
        out = (_l2(cls[0].numpy().astype(np.float32)),
               _l2(pt[0].numpy().astype(np.float32)))
        self.cache[key] = out
        return out

    def patches(self, video, t):
        return self._feats(video, t)[1]

    def cls(self, video, t):
        return self._feats(video, t)[0]


def mutual_nn(q: np.ndarray, c: np.ndarray):
    S = q @ c.T
    q2c = S.argmax(axis=1)
    c2q = S.argmax(axis=0)
    return [(i, int(q2c[i])) for i in range(len(q)) if int(c2q[int(q2c[i])]) == i]


def geometry_inlier(q: np.ndarray, c: np.ndarray) -> dict:
    pairs = mutual_nn(q, c)
    if len(pairs) < 8:
        return {"n_match": len(pairs), "inlier": 0.0, "homog": 0.0}
    qi = np.array([[i % GRID, i // GRID] for i, _ in pairs], dtype=np.float32)
    ci = np.array([[j % GRID, j // GRID] for _, j in pairs], dtype=np.float32)
    M, inl = cv2.estimateAffinePartial2D(qi, ci, method=cv2.RANSAC,
                                         ransacReprojThreshold=RANSAC_THRESH)
    inlier = float(inl.sum()) / len(pairs) if (M is not None and inl is not None) else 0.0
    H, inl2 = cv2.findHomography(qi, ci, cv2.RANSAC, RANSAC_THRESH)
    homog = float(inl2.sum()) / len(pairs) if inl2 is not None else 0.0
    return {"n_match": len(pairs), "inlier": inlier, "homog": homog}


def geometry_inlier_multi(q_frames, c) -> dict:
    per = [geometry_inlier(q, c) for q in q_frames]
    return {
        "per_frame_inlier": [round(p["inlier"], 4) for p in per],
        "inlier": round(float(np.mean([p["inlier"] for p in per])), 4),
        "homog": round(float(np.mean([p["homog"] for p in per])), 4),
        "n_match": max((p["n_match"] for p in per), default=0),
    }


def probe_geometry(m: Model, cfg: dict, qt: float, true_win, brother) -> dict:
    feats = np.load(cfg["idx"] / "features.npy").astype(np.float32)
    times = np.load(cfg["idx"] / "times.npy").astype(np.float64)

    q_ts = [qt - 0.4 + 0.4 * j for j in range(QUERY_FRAMES)]
    q_patches = [m.patches(cfg["edit"], t) for t in q_ts]
    # 与原脚本一致: 逐帧 L2 后取均值再归一化
    q_cls = _l2(np.mean([m.cls(cfg["edit"], t) for t in q_ts], axis=0))

    sims = feats @ q_cls
    order = np.argsort(-sims)
    cand_times = set()
    for i in order[:TOPK]:
        cand_times.add(float(times[i]))
    for w in ([true_win] + ([brother] if brother else [])):
        for i in np.where((times >= w[0]) & (times <= w[1]))[0]:
            cand_times.add(float(times[i]))
    cand_ts = sorted(cand_times)

    rows = []
    for t in cand_ts:
        cp = m.patches(cfg["orig"], t)
        pmax = float(np.sort((np.concatenate(q_patches) @ cp.T).max(axis=1))[-100:].mean())
        geom = geometry_inlier_multi(q_patches, cp)
        rows.append({
            "t": round(t, 2),
            "in_true": bool(true_win[0] - 0.5 <= t <= true_win[1] + 0.5),
            "in_brother": bool(brother) and (brother[0] - 0.5 <= t <= brother[1] + 0.5),
            "cls_sim": round(float(sims[int(np.argmin(np.abs(times - t)))]), 4),
            "patch_max": round(pmax, 4),
            "geom_inlier": geom["inlier"], "geom_homog": geom["homog"],
            "n_match": geom["n_match"],
        })

    def best_rank(key):
        pool = [r for r in rows if not r["in_brother"]]
        order2 = sorted(pool, key=lambda r: -r[key])
        for k, r in enumerate(order2):
            if r["in_true"]:
                return k + 1, len(pool)
        return None, len(pool)

    return {
        "id": None, "pair": None, "query_t": qt, "true_win": list(true_win),
        "brother": list(brother) if brother else None,
        "ranks": {k: best_rank(k) for k in
                  ("cls_sim", "patch_max", "geom_inlier", "geom_homog")},
        "true_frames": [r for r in rows if r["in_true"]],
        "brother_frames": [r for r in rows if r["in_brother"]],
        "frames": rows,
    }


def motion_signature(m: Model, cfg: dict, qt: float, true_win, brother,
                     win_s: float = 2.0, n: int = 8) -> dict:
    ff = FFmpegIO(FFMPEG, FP)

    def energy(video, t0, t1, npts):
        ts = np.linspace(t0, t1, npts)
        prev, e = None, []
        for t in ts:
            f = ff.grab_frame(video, t)
            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            if prev is not None:
                e.append(float(np.mean(np.abs(g.astype(np.float32) - prev.astype(np.float32)))))
            prev = g
        return np.array(e) if e else np.zeros(1)

    q0, q1 = qt - win_s / 2, qt + win_s / 2
    qe = energy(cfg["edit"], q0, q1, n)
    qe = qe / max(qe.max(), 1e-6)

    def sim_cand(a, b):
        ce = energy(cfg["orig"], a, b, n)
        ce = ce / max(ce.max(), 1e-6)
        if len(ce) != len(qe):
            ce = ce[np.linspace(0, len(ce) - 1, len(qe)).astype(int)]
        qm, cm = qe - qe.mean(), ce - ce.mean()
        denom = np.linalg.norm(qm) * np.linalg.norm(cm)
        corr = float(qm @ cm / denom) if denom > 1e-9 else 0.0
        return {"corr": round(corr, 4), "l2": round(float(np.linalg.norm(qe - ce)), 4)}

    rows = [{"win": [a, b], "in_true": True, **sim_cand(a, b)}
            for a, b in ([true_win] + ([brother] if brother else []))]
    feats = np.load(cfg["idx"] / "features.npy").astype(np.float32)
    times = np.load(cfg["idx"] / "times.npy").astype(np.float64)
    q_cls = _l2(np.mean([m.cls(cfg["edit"], t) for t in [qt - 0.4, qt, qt + 0.4]], axis=0))
    sims = feats @ q_cls
    seen = 0
    for i in np.argsort(-sims):
        t = float(times[i])
        if any(abs(t - c) < 8.0 for c in
               [r["win"][0] for r in rows] + ([brother[0]] if brother else [])):
            continue
        rows.append({"win": [round(max(0.0, t - 1), 1), round(t + 1, 1)],
                     "in_true": False, **sim_cand(max(0.0, t - 1), t + 1)})
        seen += 1
        if seen >= 5:
            break

    true_r = next((r for r in rows if r["in_true"]), None)
    distract = [r for r in rows if not r["in_true"]]
    return {
        "id": None, "query_t": qt, "true_win": list(true_win),
        "true_sig": true_r, "distract": distract,
        "corr_margin_true": (round(true_r["corr"] - max((d["corr"] for d in distract), default=0), 4)
                             if true_r else None),
        "l2_margin_true": (round(max((d["l2"] for d in distract), default=9) - true_r["l2"], 4)
                           if true_r else None),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", default=None, help="逗号分隔 id 子集(默认全部)")
    ap.add_argument("--skip-motion", action="store_true")
    ap.add_argument("--motion-only", action="store_true")
    ap.add_argument("--out", default=str(BENCH / "work" / "phase24_1_v4_probe_results.json"))
    args = ap.parse_args()

    t0 = time.time()
    m = Model()
    want = set(args.probes.split(",")) if args.probes else None
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "gt": "ground_truth_v4.json + ground_truth_test3.json (verified)",
              "device": "CPU torch (ViT-S/14 冻结 backbone, 与生产前向同口径)",
              "probes": []}
    out_path = Path(args.out)

    for pair, pid, qt, true_win, brother, note in PROBES:
        if want and pid not in want:
            continue
        cfg = PAIRS[pair]
        if not args.motion_only:
            g = probe_geometry(m, cfg, qt, true_win, brother)
            g.update(id=pid, pair=pair, note=note)
            report["probes"].append({"kind": "geometry", **g})
            tt = ", ".join("%s:INL %.3f/HOM %.3f(n=%d)" % (r["t"], r["geom_inlier"],
                                                          r["geom_homog"], r["n_match"])
                           for r in g["true_frames"])
            bb = ", ".join("%s:INL %.3f/HOM %.3f(n=%d)" % (r["t"], r["geom_inlier"],
                                                          r["geom_homog"], r["n_match"])
                           for r in g["brother_frames"])
            print("[geom %-6s] qt=%.2f true=%s brother=%s\n"
                  "    TRUE  : %s\n    BROTHE: %s\n    ranks: %s"
                  % (pid, qt, list(true_win), list(brother) if brother else None,
                     tt or "-", bb or "-", g["ranks"]), flush=True)
        if not args.skip_motion:
            ms = motion_signature(m, cfg, qt, true_win, brother)
            ms.update(id=pid, pair=pair, note=note)
            report["probes"].append({"kind": "motion", **ms})
            print("[mot  %-6s] true_corr=%s corr_margin=%s l2_margin=%s"
                  % (pid, ms["true_sig"]["corr"] if ms["true_sig"] else None,
                     ms["corr_margin_true"], ms["l2_margin_true"]), flush=True)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                            encoding="utf-8")

    report["elapsed_s"] = round(time.time() - t0, 1)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved %s  total %.0fs" % (out_path, report["elapsed_s"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
