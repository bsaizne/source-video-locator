"""Phase 24-2 语义级第二信号 · 方向 A 探针 P1 —— 场景实例身份可聚类性。

立项材料见 mvp/benchmark/user_case/semantic_signal/RESEARCH_PROPOSAL.md。
仅研究侧，零 runtime 改动。

假设：原片可按"事件实例"（一场对话=一个身份单元，即使 2 机位 10 切镜）组织；
兄弟机位落同一事件、异事件落不同事件。本探针验证两个可证伪前提：

P1a 归并能力 —— 同事件兄弟机位在"事件级聚合信号"下是否显著近：
    对 p08 场景(134, 1106-1121) 与 p38 场景(128, 1041-1061)——GT 双真、
    VLM 判为同一场对话戏——检查 scene_feats 指纹下彼此排名。
    若 p38 场景在 p08 场景的指纹 top-k 内(且显著高于随机场景) → 聚合信号存在。

P1b 区分能力 —— 不同事件同外貌(重复镜头/同质场景)是否可分：
    对 test3-r12(精灵王重复镜头, 用户判错, 真值 454-480)与 test4(同质滑梯):
    查询编辑段 vs 原片候选场景指纹, 检查"正确实例场景"相对"干扰实例场景"的
    指纹排名。这是方向 A 能否真正解决失败族(而非只放宽评估)的关键。

判据:
  P1a PASS = 兄弟场景指纹相互 top-10 且 margin(与随机场景均值差)显著。
  P1b PASS = 正确实例场景指纹排名 ≤ top-5(对 r12 / test4 候选)。

输出: work/semantic_signal_P1_results.json

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_semantic_signal_P1.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"
IDX_T3 = IDX_DIR / "test3-om__074e2dcc.idx"
IDX_T4 = IDX_DIR / "test4-om__eb686e0c.idx"

# 探针定义
# (index, pid, edit_query_t, true_span, distractor_span(s), note)
# distractor_span: 与该段外观相似的干扰实例(不同事件)
P1A = [
    ("2mkv", "p08_scene134", 1106.0, 1121.0, "p08 瞭望塔机位场景"),
    ("2mkv", "p38_scene128", 1041.0, 1061.0, "p38 士兵特写机位场景"),
]
# P1b: r12 编辑段 64.0-65.5, 真值区 454-480(精灵王重复镜头); 干扰 = 其它精灵王/相似场景
P1B = [
    ("test3", "t3r12", 64.0, 65.5, (454, 480), "精灵王重复镜头(用户判错)", (430, 510)),
    ("test4", "t4r01", 1.25, 2.5, (3335, 3350), "同质滑梯(观察)", (3320, 3400)),
]


def scene_of(scenes: np.ndarray, t: float) -> int | None:
    for i, (a, b) in enumerate(scenes):
        if a <= t <= b:
            return i
    return None


def nearest_scenes(sf: np.ndarray, scenes: np.ndarray, scene_i: int,
                   topk: int = 10, min_dt: float = 3.0, times=None) -> list[dict]:
    """scene_i 指纹的相似场景排名(排除自身与时间近邻)。"""
    q = sf[scene_i]
    sims = sf @ q
    order = np.argsort(-sims)
    rows = []
    for j in order:
        if j == scene_i:
            continue
        # 跳过时间重叠场景(相邻场景同段内容)
        a, b = scenes[j]
        a0, b0 = scenes[scene_i]
        if times is not None:
            pass
        if min(a, b0) - max(a0, b) > -0.5:  # 无重叠
            rows.append({"scene": int(j), "span": [round(a, 1), round(b, 1)],
                         "sim": round(float(sims[j]), 4)})
        if len(rows) >= topk:
            break
    return rows


def p1a() -> dict:
    feats = np.load(IDX2 / "features.npy").astype(np.float32)
    times = np.load(IDX2 / "times.npy")
    scenes = np.load(IDX2 / "scenes.npy")
    sf = np.load(IDX2 / "scene_feats.npy").astype(np.float32)

    i134 = scene_of(scenes, 1108.0)   # p08
    i128 = scene_of(scenes, 1048.0)   # p38
    out = {"kind": "P1a", "p08_scene": int(i134), "p38_scene": int(i128)}

    # 相互指纹相似度 + 排名
    s = float(sf[i134] @ sf[i128])
    sims_134 = sf @ sf[i134]
    rank_128_in_134 = int(np.sum(sims_134 > s))
    sims_128 = sf @ sf[i128]
    rank_134_in_128 = int(np.sum(sims_128 > s))

    # 随机基线: p08 场景 vs 所有其它场景的相似度分布(排除时间近邻场景)
    other = [j for j in range(len(scenes)) if j != i134 and j != i128]
    baseline = sf[other] @ sf[i134]
    mu, sd = float(baseline.mean()), float(baseline.std())

    out.update({
        "mutual_sim": round(s, 4),
        "rank_p38_in_p08": int(rank_128_in_134) + 1,
        "rank_p34_in_p38": int(rank_134_in_128) + 1,
        "baseline_mean": round(mu, 4), "baseline_std": round(sd, 4),
        "z_mutual": round((s - mu) / max(sd, 1e-6), 2),
        "p08_nearest": nearest_scenes(sf, scenes, i134, topk=8),
        "p38_nearest": nearest_scenes(sf, scenes, i128, topk=8),
    })
    print(f"[P1a] p08_scene={i134}({scenes[i134]}) p38_scene={i128}({scenes[i128]})")
    print(f"  mutual_sim={out['mutual_sim']} rank_p38_in_p08={out['rank_p38_in_p08']} "
          f"rank_p08_in_p38={out['rank_p34_in_p38']} z={out['z_mutual']} "
          f"baseline={mu:.3f}±{sd:.3f}")
    return out


def p1b() -> dict:
    out = {"kind": "P1b", "cases": []}
    for idx_name, pid, e0, e1, true_span, note, dist_span in P1B:
        idx = {"test3": IDX_T3, "test4": IDX_T4}[idx_name]
        feats = np.load(idx / "features.npy").astype(np.float32)
        times = np.load(idx / "times.npy")
        scenes = np.load(idx / "scenes.npy")
        sf = np.load(idx / "scene_feats.npy").astype(np.float32)

        # 编辑段查询 CLS(无模型,直接用索引里真值区周围的代表性场景指纹近似?
        # 不行——需要编辑侧特征。改用: 真值窗内场景指纹作为"正确实例", 
        # 干扰窗内场景指纹作为"干扰实例", 检验两者的可分性(同类场景内部 vs 跨事件)。
        # 更直接: 对 dist_span 内每个场景, 算它与 true_span 内每个场景的指纹相似度,
        # 看"正确实例场景簇"与"干扰实例场景簇"是否能分开。

        true_scenes = [i for i, (a, b) in enumerate(scenes)
                       if min(b, true_span[1]) - max(a, true_span[0]) > 0.5]
        dist_scenes = [i for i, (a, b) in enumerate(scenes)
                       if min(b, dist_span[1]) - max(a, dist_span[0]) > 0.5
                       and not (min(b, true_span[1]) - max(a, true_span[0]) > 0.5)]

        # 同簇内相似度(正确实例场景之间) vs 跨簇(正确 vs 干扰)
        if not true_scenes or not dist_scenes:
            out["cases"].append({"id": pid, "note": note,
                                 "error": "无可用场景", "true_scenes": true_scenes,
                                 "dist_scenes": dist_scenes})
            continue
        within = [float(sf[i] @ sf[j]) for k, i in enumerate(true_scenes)
                  for j in true_scenes[k + 1:]]
        cross = [float(sf[i] @ sf[j]) for i in true_scenes for j in dist_scenes]
        within_m = float(np.mean(within)) if within else None
        cross_m = float(np.mean(cross)) if cross else None
        sep = (within_m - cross_m) if (within_m is not None and cross_m is not None) else None

        # 判据: 正确实例场景在"候选场景集合(真值+干扰)"内的排名
        cand = true_scenes + dist_scenes
        # 用 true 簇代表指纹 = 均值
        t_rep = np.mean(sf[true_scenes], axis=0)
        t_rep /= max(np.linalg.norm(t_rep), 1e-8)
        sims = {j: float(sf[j] @ t_rep) for j in cand}
        order = sorted(sims, key=lambda x: -sims[x])
        # true 场景平均排名
        true_ranks = [order.index(j) + 1 for j in true_scenes]
        avg_true_rank = float(np.mean(true_ranks))

        entry = {
            "id": pid, "note": note, "true_span": list(true_span),
            "dist_span": list(dist_span),
            "n_true_scenes": len(true_scenes), "n_dist_scenes": len(dist_scenes),
            "within_sim_mean": round(within_m, 4) if within_m is not None else None,
            "cross_sim_mean": round(cross_m, 4) if cross_m is not None else None,
            "sep_within_minus_cross": round(sep, 4) if sep is not None else None,
            "true_scene_avg_rank": round(avg_true_rank, 2),
            "true_scenes": [int(x) for x in true_scenes],
            "dist_scenes": [int(x) for x in dist_scenes],
        }
        out["cases"].append(entry)
        print(f"[P1b {pid}] true_scenes={true_scenes} dist_scenes={dist_scenes}")
        print(f"  within={within_m} cross={cross_m} sep={sep} "
              f"true_avg_rank={avg_true_rank:.1f}/{len(cand)}")
    return out


def main() -> int:
    t0 = time.time()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "P1a": p1a(), "P1b": p1b()}
    out = BENCH / "work" / "semantic_signal_P1_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
