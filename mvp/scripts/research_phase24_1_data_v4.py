"""Phase 24-1 探针 ③ 重跑(修正 GT)—— 硬负例可得性盘点。

起因: FINDINGS_GT_CONTAMINATION_AUDIT.md —— 原盘点(work/phase24_1_data.json)的锚点含
p26@2808(标错真值窗)与 p08b@1048(已作废的 p38 旧错误 GT 区), t3r12 锚点 476 落在
修正窗 466-478 内但原口径以 454-480 为真值。本次用修正 GT 重跑锚点盘点。
盘点方法(逐条与原脚本一致, 便于对照): 分块余弦, sim>=0.60 且 |Δt|>=2s 且跨场景
(scene_id 不同)= 潜在硬负例; 锚点场景内帧的跨场景同貌实例数。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_phase24_1_data_v4.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4")   # 与并行的 GPU 索引任务错开 CPU

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")

IDXES = {
    "2mkv": IDX_DIR / "2__4c6d4ab2.idx",
    "test1": IDX_DIR / "test1-om__5d4fdc2b.idx",
    "test2": IDX_DIR / "test2-om__35b9a58f.idx",
    "test3": IDX_DIR / "test3-om__074e2dcc.idx",
    "test4": IDX_DIR / "test4-om__eb686e0c.idx",
}

# 修正 GT 锚点: (index, anchor_t, note)
ANCHORS = [
    ("2mkv", 1108.0, "p08 瞭望塔机位(真值 1108.15-1109.1; 兄弟 1048-1050 为同场戏另一机位)"),
    ("2mkv", 1769.0, "p26 夜读(v4 修正真值 1768.2-1770.05)"),
    ("test3", 472.0, "t3r12 精灵王重复镜头(v4 修正真值 466-478)"),
]


def scene_id_at(scenes: np.ndarray, t: float):
    for i, (a, b) in enumerate(scenes):
        if a <= t <= b:
            return i
    return None


def hard_negatives(feats, times, scenes, *, sim_floor=0.60, min_dt=2.0, topk=20, stride=2):
    n = len(feats)
    scene_of = np.full(n, -1, dtype=np.int32)
    for i, (a, b) in enumerate(scenes):
        scene_of[(times >= a) & (times <= b)] = i
    sims_all, pairs = [], []
    for i0 in range(0, n, stride):
        i1 = min(i0 + stride, n)
        S = feats[i0:i1] @ feats.T
        for r, gi in enumerate(range(i0, i1)):
            S[r, np.abs(times - times[gi]) < min_dt] = -1
        for r, gi in enumerate(range(i0, i1)):
            for j in np.argsort(-S[r])[:topk]:
                if S[r, j] < sim_floor or scene_of[gi] == scene_of[j]:
                    continue
                sims_all.append(float(S[r, j]))
                pairs.append((gi, int(j)))
    pairs = list(dict.fromkeys(tuple(sorted(p)) for p in pairs))
    if not sims_all:
        return {"n_hard_pairs": 0, "sim_mean": None, "sim_floor": sim_floor,
                "sim_hist": [], "sample_pairs": []}
    arr = np.array(sims_all)
    hist, _ = np.histogram(arr, bins=[0.60, 0.70, 0.80, 0.90, 1.01])
    return {"n_hard_pairs": len(pairs), "sim_mean": round(float(arr.mean()), 4),
            "sim_floor": sim_floor, "sim_hist": [int(x) for x in hist],
            "sample_pairs": [[int(gi), int(j), round(float(sims_all[k]), 4)]
                             for k, (gi, j) in enumerate(pairs[:5])]}


def anchor_scene_repeats(feats, times, scenes, anchor_t, *, sim_floor=0.60,
                         topk=30, min_dt=3.0):
    si = scene_id_at(scenes, anchor_t)
    if si is None:
        return {"scene": None}
    a, b = scenes[si]
    anchor_feats = feats[(times >= a) & (times <= b)].mean(axis=0)
    anchor_feats /= max(np.linalg.norm(anchor_feats), 1e-8)
    sims = feats @ anchor_feats
    hits = []
    for j in np.argsort(-sims):
        t = float(times[j])
        if scene_id_at(scenes, t) == si or abs(t - anchor_t) < min_dt:
            continue
        if sims[j] < sim_floor:
            break
        hits.append({"t": round(t, 1), "sim": round(float(sims[j]), 4),
                     "scene": scene_id_at(scenes, t)})
        if len(hits) >= 15:
            break
    return {"scene": si, "scene_span": [round(float(a), 1), round(float(b), 1)],
            "n_repeats": len(hits), "top_sim": hits}


def main() -> int:
    t0 = time.time()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "gt": "修正口径(ground_truth_v4.json / ground_truth_test3.json)",
              "note": "锚点已更新: p26 2808->1769, 去掉 p08b@1048(非 GT), t3r12 476->472",
              "indexes": {}, "anchors": {}}
    for name, idx in IDXES.items():
        feats = np.load(idx / "features.npy").astype(np.float32)
        times = np.load(idx / "times.npy")
        scenes = np.load(idx / "scenes.npy") if (idx / "scenes.npy").exists() else np.zeros((0, 2))
        hn = hard_negatives(feats, times, scenes)
        report["indexes"][name] = {"frames": int(len(feats)), "scenes": int(len(scenes)),
                                   "hard_negatives": hn}
        print("[%-5s] n=%d scenes=%d hard_pairs(>=0.60,跨场景,dT>=2s)=%d sim_mean=%s hist=%s"
              % (name, len(feats), len(scenes), hn["n_hard_pairs"], hn["sim_mean"], hn["sim_hist"]),
              flush=True)
    for name, at, note in ANCHORS:
        idx = IDXES[name]
        feats = np.load(idx / "features.npy").astype(np.float32)
        times = np.load(idx / "times.npy")
        scenes = np.load(idx / "scenes.npy")
        rep = anchor_scene_repeats(feats, times, scenes, at)
        report["anchors"]["%s@%s" % (name, at)] = {"note": note, **rep}
        print("[anchor %s@%s] scene=%s span=%s n_repeats=%s top=%s"
              % (name, at, rep.get("scene"), rep.get("scene_span"), rep.get("n_repeats"),
                 [(h["t"], h["sim"]) for h in rep.get("top_sim", [])[:3]]), flush=True)
    out = BENCH / "work" / "phase24_1_v4_data.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved %s  total %.0fs" % (out, time.time() - t0), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
