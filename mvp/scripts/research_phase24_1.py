"""Phase 24-1 视觉几何一致性 + 时序运动签名 预研（研究侧，不改 runtime）。

背景（STATE 2026-08-31 交接 + 用户提案）：剩余失败族 = 同场戏不同机位（p08/p08b）、
重复镜头互混（t3-r12）、同质场景（p26 夜读）。Phase 21 E21 的 patch-max 重排只做
「每查询 patch 对候选帧 patch 的全局最大余弦，top-100 均值」——丢弃了空间对应关系。
本研究探两个新信号：

Probe 1 视觉几何一致性（主探针）：
  查询帧（编辑片）与候选帧（原片）做 patch 互近邻匹配 → 宽松仿射 RANSAC → 内点率。
  判别逻辑：真值机位（同一帧内容）的 patch 空间对应满足单一仿射 → 内点率高；
  兄弟机位（同场戏不同机位，如 p08↔p08b）空间布局不同 → 互近邻对应大量违反单一仿射
  → 内点率低。这正是 patch-max 余弦分不出来、但几何一致性分得出来的「相似≠同一镜头」。

Probe 2 时序运动签名（廉价）：
  帧差幅度序列（mean abs diff）的窗口级统计（归一化能量曲线），查询窗 vs 候选窗比对。
  对 t3-r12（重复镜头剪辑节奏不同）预期有判别力；对 p26（静态夜读）预期无效。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" \
      mvp/scripts/research_phase24_1.py [--probes p08,p08b --skip-motion]
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

# 探针: (pair, id, query_t(编辑片), true_win, note, brother_win?)
PROBES = [
    ("2mkv", "p08",  13.5, (1108, 1110), "瞭望塔+同桌机位(真值)", (1048, 1050)),
    ("2mkv", "p08b", 13.9, (1048, 1050), "士兵特写(真值)", (1108, 1110)),
    ("2mkv", "p26",  76.8, (2808, 2811), "夜读书(CLS 硬混淆)", None),
    ("2mkv", "p01",   0.8, (2417, 2428), "金属球准备(sanity 易例)", None),
    ("2mkv", "p04",   4.6, (833, 845),   "峡谷航拍(sanity 易例)", None),
    ("test3", "t3r12", 64.75, (454, 480), "精灵王重复镜头(r12 用户判错)", None),
]

GRID = 37          # 518/14 patch 网格
TOPK = 40          # CLS top-K 候选
QUERY_FRAMES = 3   # 查询侧帧数(±0.4s)
RANSAC_THRESH = 5.0


def _l2(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


class Model:
    def __init__(self):
        import torch
        self.torch = torch
        self.m = DinoV2Small()
        sd = torch.load(str(WEIGHTS), map_location="cpu", weights_only=True)
        self.m.load_state_dict(sd, strict=False)
        self.m.eval()
        self._ff = FFmpegIO(FFMPEG, FP)

    @__import__("functools").lru_cache(maxsize=4096)
    def _feats(self, key: tuple):
        """(video, t) -> (cls[384] L2, patches[1369,384] L2)。lru 缓存避免重复解码。"""
        f = self._ff.grab_frame(key[0], key[1])
        x = _imagenet_preprocess(f)
        with self.torch.no_grad():
            cls, pt = self.m.forward_features(x)
        return (_l2(cls[0].numpy().astype(np.float32)),
                _l2(pt[0].numpy().astype(np.float32)))

    def patches(self, video, t):
        return self._feats((video, t))[1]

    def cls(self, video, t):
        return self._feats((video, t))[0]


def mutual_nn(q: np.ndarray, c: np.ndarray, k: int = 1):
    """互近邻匹配:q 的每 patch 在 c 中的最近邻,且反向一致。返回 (q_idx, c_idx)。"""
    S = q @ c.T                      # (Pq, Pc)
    q2c = S.argmax(axis=1)
    c2q = S.argmax(axis=0)
    pairs = []
    for i in range(len(q)):
        j = int(q2c[i])
        if int(c2q[j]) == i:
            pairs.append((i, j))
    return pairs


def geometry_inlier(q: np.ndarray, c: np.ndarray):
    """patch 互近邻 + 仿射 RANSAC 内点率。q/c 各为单帧 (P,384) patch。返回 dict。"""
    pairs = mutual_nn(q, c)
    if len(pairs) < 8:
        return {"n_match": len(pairs), "inlier": 0.0, "homog": 0.0}
    qi = np.array([[i % GRID, i // GRID] for i, _ in pairs], dtype=np.float32)
    ci = np.array([[j % GRID, j // GRID] for _, j in pairs], dtype=np.float32)
    # 宽松仿射(2D rigid+scale):estimateAffinePartial2D
    M, inl = cv2.estimateAffinePartial2D(qi, ci, method=cv2.RANSAC,
                                         ransacReprojThreshold=RANSAC_THRESH)
    if M is None or inl is None:
        inlier = 0.0
    else:
        inlier = float(inl.sum()) / len(pairs)
    # 参考:单应(8DOF,更宽松)内点率
    H, inl2 = cv2.findHomography(qi, ci, cv2.RANSAC, RANSAC_THRESH)
    homog = float(inl2.sum()) / len(pairs) if inl2 is not None else 0.0
    return {"n_match": len(pairs), "inlier": inlier, "homog": homog}


def geometry_inlier_multi(q_frames: list[np.ndarray], c: np.ndarray) -> dict:
    """对多帧查询分别算几何内点率,返回逐帧值 + 均值(每帧独立互近邻,空间网格正确)。"""
    per = [geometry_inlier(q, c) for q in q_frames]
    return {
        "per_frame_inlier": [round(p["inlier"], 4) for p in per],
        "inlier": round(float(np.mean([p["inlier"] for p in per])), 4),
        "homog": round(float(np.mean([p["homog"] for p in per])), 4),
        "n_match": max((p["n_match"] for p in per), default=0),
    }


def probe_geometry(m: Model, cfg: dict, qt: float, true_win, brother) -> dict:
    """对一探针:查询帧 vs 候选帧的几何内点率 + patch_max + CLS 对比。"""
    ff = FFmpegIO(FFMPEG, FP)
    feats = np.load(cfg["idx"] / "features.npy")
    times = np.load(cfg["idx"] / "times.npy")

    # 查询 patch(3 帧)
    q_ts = [qt - 0.4 + 0.4 * j for j in range(QUERY_FRAMES)]
    q_patches = [m.patches(cfg["edit"], t) for t in q_ts]
    q_cls = np.mean([m.cls(cfg["edit"], t) for t in q_ts], axis=0)
    q_cls = _l2(q_cls)

    # 候选集 = CLS top-K ∪ 真值窗 ∪ 兄弟窗(去重)
    sims = feats @ q_cls
    order = np.argsort(-sims)
    cand_times = set()
    for i in order[:TOPK]:
        cand_times.add(float(times[i]))
    for a, b in [true_win] + ([brother] if brother else []):
        for i in np.where((times >= a) & (times <= b))[0]:
            cand_times.add(float(times[i]))
    cand_ts = sorted(cand_times)

    rows = []
    for t in cand_ts:
        cp = m.patches(cfg["orig"], t)
        pmax = float(np.sort((np.concatenate(q_patches) @ cp.T).max(axis=1))[-100:].mean())
        geom = geometry_inlier_multi(q_patches, cp)
        in_true = (true_win[0] - 0.5 <= t <= true_win[1] + 0.5)
        in_bro = bool(brother) and (brother[0] - 0.5 <= t <= brother[1] + 0.5)
        cls_sim = float(sims[np.argmin(np.abs(times - t))])
        rows.append({"t": round(t, 2), "in_true": in_true, "in_brother": in_bro,
                     "cls_sim": round(cls_sim, 4), "patch_max": round(pmax, 4),
                     "geom_inlier": geom["inlier"],
                     "geom_homog": geom["homog"],
                     "n_match": geom["n_match"]})

    def best_rank(key):
        """真值帧在该特征排序中的名次(越小越好;排除 in_brother 干扰帧后)。"""
        pool = [r for r in rows if not r["in_brother"]]
        order = sorted(pool, key=lambda r: -r[key])
        for k, r in enumerate(order):
            if r["in_true"]:
                return k + 1, len(pool)
        return None, len(pool)

    out = {
        "id": None, "pair": None, "query_t": qt, "true_win": list(true_win),
        "brother": list(brother) if brother else None,
        "ranks": {
            "CLS": best_rank("cls_sim"),
            "PATCH_MAX": best_rank("patch_max"),
            "GEOM_INLIER": best_rank("geom_inlier"),
            "GEOM_HOMOG": best_rank("geom_homog"),
        },
        "true_frame": next((r for r in rows if r["in_true"]), None),
        "frames": rows,
    }
    return out


def motion_signature(m: Model, cfg: dict, qt: float, true_win, brother,
                     win_s: float = 2.0, n: int = 8) -> dict:
    """窗口级帧差能量签名比对。查询(编辑)窗 vs 候选(原片)窗。

    编辑段可能被快剪压缩(压缩比>1):运动签名按时间归一化后比较形状而非绝对帧对齐。
    """
    ff = FFmpegIO(FFMPEG, FP)

    def energy(video, t0, t1, npts):
        ts = np.linspace(t0, t1, npts)
        prev = None
        e = []
        for t in ts:
            f = ff.grab_frame(video, t)
            g = cv2.cvtColor(f, cv2.COLOR_BGR2GRAY)
            if prev is not None:
                e.append(float(np.mean(np.abs(g.astype(np.float32)
                                           - prev.astype(np.float32)))))
            prev = g
        return np.array(e) if e else np.zeros(1)

    # 查询窗(编辑片):以 query_t 为中心 ±win_s/2
    q0, q1 = qt - win_s / 2, qt + win_s / 2
    qe = energy(cfg["edit"], q0, q1, n)
    qe = qe / max(qe.max(), 1e-6)

    def sim_cand(a, b):
        ce = energy(cfg["orig"], a, b, n)
        ce = ce / max(ce.max(), 1e-6)
        # 对齐长度(压缩比>1 → 重采样到同一长度)
        if len(ce) != len(qe):
            idx = np.linspace(0, len(ce) - 1, len(qe)).astype(int)
            ce = ce[idx]
        # 皮尔逊相关(形状) + L2(幅度,已归一化)
        qm, cm = qe - qe.mean(), ce - ce.mean()
        denom = np.linalg.norm(qm) * np.linalg.norm(cm)
        corr = float(qm @ cm / denom) if denom > 1e-9 else 0.0
        l2 = float(np.linalg.norm(qe - ce))
        return {"corr": round(corr, 4), "l2": round(l2, 4)}

    rows = []
    for a, b in [true_win] + ([brother] if brother else []):
        rows.append({"win": [a, b], "in_true": True, **sim_cand(a, b)})
    # 干扰窗:CLS top 里与真值窗同数量级的若干候选(取 top-5 的非真值窗,±8s)
    feats = np.load(cfg["idx"] / "features.npy")
    times = np.load(cfg["idx"] / "times.npy")
    q_cls = np.mean([m.cls(cfg["edit"], t) for t in [qt - 0.4, qt, qt + 0.4]], axis=0)
    q_cls = _l2(q_cls)
    sims = feats @ q_cls
    order = np.argsort(-sims)
    seen = 0
    for i in order:
        t = float(times[i])
        if any(abs(t - c) < 8.0 for c in
               [a for w in rows for a, _ in [w["win"]]] +
               ([brother[0]] if brother else [])):
            continue
        rows.append({"win": [round(max(0, t - 1), 1), round(t + 1, 1)],
                     "in_true": False, **sim_cand(max(0, t - 1), t + 1)})
        seen += 1
        if seen >= 5:
            break

    true_r = next((r for r in rows if r["in_true"]), None)
    distract = [r for r in rows if not r["in_true"]]
    out = {"id": None, "query_t": qt, "true_win": list(true_win),
           "true_sig": true_r, "distract": distract,
           "corr_margin_true": (round(true_r["corr"] - max((d["corr"] for d in distract), default=0), 4)
                                if true_r else None),
           "l2_margin_true": (round(max((d["l2"] for d in distract), default=9) - true_r["l2"], 4)
                              if true_r else None)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probes", default=None, help="逗号分隔 id 子集(默认全部)")
    ap.add_argument("--skip-motion", action="store_true")
    ap.add_argument("--motion-only", action="store_true")
    args = ap.parse_args()

    t0 = time.time()
    m = Model()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "probes": []}

    want = set(args.probes.split(",")) if args.probes else None
    for pair, pid, qt, true_win, note, brother in PROBES:
        if want and pid not in want:
            continue
        cfg = PAIRS[pair]
        if not args.motion_only:
            g = probe_geometry(m, cfg, qt, true_win, brother)
            g["id"], g["pair"], g["note"] = pid, pair, note
            report["probes"].append({"kind": "geometry", **g})
            print(f"[geom {pid:6s}] ranks: CLS={g['ranks']['CLS']} "
                  f"PMAX={g['ranks']['PATCH_MAX']} INL={g['ranks']['GEOM_INLIER']} "
                  f"HOMOG={g['ranks']['GEOM_HOMOG']}", flush=True)
        if not args.skip_motion:
            ms = motion_signature(m, cfg, qt, true_win, brother)
            ms["id"], ms["pair"], ms["note"] = pid, pair, note
            report["probes"].append({"kind": "motion", **ms})
            print(f"[mot  {pid:6s}] true_corr={ms['true_sig']['corr'] if ms['true_sig'] else None} "
                  f"corr_margin={ms['corr_margin_true']} l2_margin={ms['l2_margin_true']}",
                  flush=True)

    out = BENCH / "work" / "phase24_1_probe_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
