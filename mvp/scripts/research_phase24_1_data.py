"""Phase 24-1 探针 ③ 数据盘点:难例投影头微调的硬负例可得性。

问题:5 部片、个位数已知混淆对,全量微调过拟合风险高。可行缩法是冻结 backbone
只训小投影头,硬负例从现有索引自动挖。本脚本盘清:
  - 每索引的 CLS 高相似帧对中,「跨场景」(不同场景表单元)且时间不相邻的对数量与
    sim 分布 = 潜在硬负例量级;
  - 已知失败族(p08/p08b/p26/t3-r12)所在场景周边的重复实例对数量。

方法:分块余弦(内存安全),过滤条件 = sim≥0.60 且 |Δt|≥2s 且 scene_id 不同(用
scenes.npy 标注)。纯 numpy,无模型推理。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_phase24_1_data.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

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

# 已知失败族(可挖硬负例的场景锚点):(index, scene_anchor_t)
ANCHORS = [
    ("2mkv", 1108.0, "p08 瞭望塔机位"),
    ("2mkv", 1048.0, "p08b 士兵特写"),
    ("2mkv", 2808.0, "p26 夜读"),
    ("test3", 476.0, "t3-r12 精灵王重复镜头"),
]


def scene_id_at(scenes: np.ndarray, t: float) -> int | None:
    """t 落在哪个场景(起止秒),不在任何场景 → None。"""
    for i, (a, b) in enumerate(scenes):
        if a <= t <= b:
            return i
    return None


def hard_negatives(feats: np.ndarray, times: np.ndarray, scenes: np.ndarray,
                   *, sim_floor: float = 0.60, min_dt: float = 2.0,
                   topk: int = 20, stride: int = 2) -> dict:
    """分块扫描:每采样帧找 top-k 高相似帧,统计跨场景(不同 scene_id)且 |Δt|≥min_dt 的对。"""
    n = len(feats)
    scene_of = np.full(n, -1, dtype=np.int32)
    for i, (a, b) in enumerate(scenes):
        m = (times >= a) & (times <= b)
        scene_of[m] = i

    sims_all = []
    pairs = []
    for i0 in range(0, n, stride):
        i1 = min(i0 + stride, n)
        block = feats[i0:i1]
        S = block @ feats.T
        # 自己(±min_dt 内)掩掉
        for r, gi in enumerate(range(i0, i1)):
            S[r, np.abs(times - times[gi]) < min_dt] = -1
        for r, gi in enumerate(range(i0, i1)):
            top = np.argsort(-S[r])[:topk]
            for j in top:
                if S[r, j] < sim_floor:
                    continue
                if scene_of[gi] == scene_of[j]:
                    continue  # 同场景 = 同一内容,非难例
                sims_all.append(float(S[r, j]))
                pairs.append((gi, int(j)))
    pairs = list(dict.fromkeys(tuple(sorted(p)) for p in pairs))  # 去重
    if not sims_all:
        return {"n_hard_pairs": 0, "sim_mean": None, "sim_floor": sim_floor,
                "sim_hist": [], "sample_pairs": []}
    arr = np.array(sims_all)
    hist, _ = np.histogram(arr, bins=[0.60, 0.70, 0.80, 0.90, 1.01])
    return {
        "n_hard_pairs": len(pairs),
        "sim_mean": round(float(arr.mean()), 4),
        "sim_floor": sim_floor,
        "sim_hist": [int(x) for x in hist],
        "sample_pairs": [[int(gi), int(j), round(float(sims_all[k]), 4)]
                         for k, (gi, j) in enumerate(pairs[:5])],
    }


def anchor_scene_repeats(feats: np.ndarray, times: np.ndarray, scenes: np.ndarray,
                         anchor_t: float, *, radius: float = 30.0,
                         sim_floor: float = 0.60, topk: int = 30,
                         min_dt: float = 3.0) -> dict:
    """已知失败族锚点场景内部:该场景帧在全索引 top-k 相似帧中,有多少跨场景同貌实例。

    排除条件 = 同场景(scene_id 相同,同一内容非难例)或 |Δt|<min_dt(近邻帧)。
    """
    si = scene_id_at(scenes, anchor_t)
    if si is None:
        return {"scene": None}
    a, b = scenes[si]
    anchor_mask = (times >= a) & (times <= b)
    anchor_feats = feats[anchor_mask].mean(axis=0)
    anchor_feats /= max(np.linalg.norm(anchor_feats), 1e-8)
    sims = feats @ anchor_feats
    order = np.argsort(-sims)
    hits = []
    for j in order:
        t = float(times[j])
        if scene_id_at(scenes, t) == si:
            continue  # 同场景 = 同一内容,非难例
        if abs(t - anchor_t) < min_dt:
            continue  # 近邻帧
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
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "indexes": {}, "anchors": {}}

    for name, idx in IDXES.items():
        feats = np.load(idx / "features.npy").astype(np.float32)
        times = np.load(idx / "times.npy")
        scenes = np.load(idx / "scenes.npy") if (idx / "scenes.npy").exists() else np.zeros((0, 2))
        hn = hard_negatives(feats, times, scenes)
        report["indexes"][name] = {
            "frames": int(len(feats)), "scenes": int(len(scenes)),
            "hard_negatives": hn,
        }
        print(f"[{name:5s}] n={len(feats)} scenes={len(scenes)} "
              f"hard_pairs(≥0.60,跨场景,Δt≥2s)={hn['n_hard_pairs']} "
              f"sim_mean={hn['sim_mean']} hist(0.6/0.7/0.8/0.9+)={hn['sim_hist']}",
              flush=True)

    for name, at, note in ANCHORS:
        idx = IDXES[name]
        feats = np.load(idx / "features.npy").astype(np.float32)
        times = np.load(idx / "times.npy")
        scenes = np.load(idx / "scenes.npy")
        rep = anchor_scene_repeats(feats, times, scenes, at)
        report["anchors"][f"{name}@{at}"] = {"note": note, **rep}
        print(f"[anchor {name}@{at} {note}] scene={rep.get('scene')} "
              f"span={rep.get('scene_span')} n_repeats={rep.get('n_repeats')} "
              f"top_sim={rep.get('top_sim', [])[:3]}", flush=True)

    out = BENCH / "work" / "phase24_1_data.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
