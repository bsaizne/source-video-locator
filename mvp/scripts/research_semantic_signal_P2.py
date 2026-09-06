"""Phase 24-2 语义级第二信号 · 方向 A 探针 P2 —— 事件归并规则 + 编辑段→事件单元端到端排序。

立项材料: mvp/benchmark/user_case/semantic_signal/RESEARCH_PROPOSAL.md
P1 结论:  mvp/benchmark/user_case/semantic_signal/FINDINGS_P1.md
仅研究侧, 零 runtime 改动。

P2 目标(用户 2026-09-01 拍板 A1 继续):
  1. 设计"事件归并规则"(时序近邻 + 指纹相似度联合聚类), 把原片场景表聚合成"事件单元";
  2. 验证"编辑段 → 事件单元"端到端排序, 对比帧级/场景级基线, 看正确事件是否被推到 top-1。

P2a(归并规则): 对每部原片, 以「场景中心时间差 ≤ T_gap AND 场景指纹余弦 ≥ S_sim」为边做连通分量,
  得事件单元。度量三族:
    - 兄弟机位族(2.mkv p08 scene134 + p38 scene128, GT 双真): 两场景是否同单元;
    - 重复镜头族(test3 t3-r12): 正确实例场景[43,44,45]是否同单元, 且与干扰[42,46,47,48]分单元;
    - 同质场景族(test4 t4r01, 对照组): 预期不可分(353-355 vs 352,356-359)。
P2b(端到端排序): 编辑段查询(编辑侧索引 CLS 特征均值) → 事件单元代表(单元内场景指纹 L2 均值),
  排序正确事件单元, 对比: 帧级 CLS 排名 / 场景级(不归并)排名 / 事件级(归并)排名。

判据:
  - P2a: 兄弟机位同单元 = 归并规则捕获"同一事件多机位";
         t3-r12 正确实例同单元且与干扰分单元 = 归并不破坏重复镜头可分性。
  - P2b: 事件级正确单元排名 ≤ 场景级且尽量 top-1 = 方向 A 端到端有真实价值。

输出: work/semantic_signal_P2_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_semantic_signal_P2.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"          # 2.mkv 原片
IDX1 = IDX_DIR / "1__ffdc13d9.idx"          # 1.mp4 编辑片 (2.mkv 对应, 0.5fps)
IDX_T3 = IDX_DIR / "test3-om__074e2dcc.idx" # test3 原片
IDX_T3E = IDX_DIR / "test3-ed__57a104a7.idx"# test3 编辑片 (1fps)
IDX_T4 = IDX_DIR / "test4-om__eb686e0c.idx" # test4 原片

# ---- 事件归并规则参数扫描网格 ----
T_GAPS = [30.0, 60.0, 120.0]
S_SIMS = [0.55, 0.60, 0.65, 0.70]

# ---- GT 案例(场景索引来自 P1 已核实) ----
SIBLING = {"idx": "2mkv", "scene_a": 134, "scene_b": 128,
           "note": "p08(1106-1121 了望塔/桌边) vs p38(1041-1061 士兵特写), 同场对话双真"}
R12 = {"idx": "test3", "true": [43, 44, 45], "dist": [42, 46, 47, 48],
       "note": "精灵王重复镜头, 正确实例[454,481] vs 干扰[420,510]"}
T4 = {"idx": "test4", "true": [353, 354, 355], "dist": [352, 356, 357, 358, 359],
      "note": "同质滑梯(对照组, P1b sep=-0.035 预期不可分)"}

# ---- 端到端查询定义(编辑侧帧区间 → 原片正确场景/单元) ----
# (idx_orig, idx_edit, edit_t0, edit_t1, orig_scenes_correct, label)
E2E = [
    ("2mkv", "1mp4", 12.0, 15.0, [134, 128],
     "p08+p38 兄弟机位对话(编辑 12.5-14.3, 正确事件含两机位)"),
    ("2mkv", "1mp4", 0.0, 1.5, [265],
     "p01 金属球装置戏(易例对照)"),
    ("2mkv", "1mp4", 3.5, 6.0, [101],
     "p04 峡谷航拍(易例对照)"),
    ("2mkv", "1mp4", 36.5, 40.0, [168],
     "p17 武器站枪塔(易例对照)"),
    ("2mkv", "1mp4", 75.0, 79.0, [295],
     "p26 男主夜读(特征上限参考)"),
    ("test3", "test3ed", 64.0, 66.0, [43, 44, 45],
     "t3-r12 精灵王重复镜头(方向 A 主目标)"),
]


def load(idx: Path) -> dict:
    return {
        "features": np.load(idx / "features.npy").astype(np.float32),
        "times": np.load(idx / "times.npy"),
        "scenes": np.load(idx / "scenes.npy"),
        "scene_feats": np.load(idx / "scene_feats.npy").astype(np.float32),
    }


def merge_events(scenes: np.ndarray, scene_feats: np.ndarray,
                 T_gap: float, S_sim: float) -> list[list[int]]:
    """时序近邻 + 指纹联合聚类 → 事件单元(连通分量)。

    边判据: 场景中心时间差 ≤ T_gap AND 指纹余弦 ≥ S_sim。
    场景按时间有序, 只需扫描中心时间差 ≤ T_gap 的近邻对。
    """
    n = len(scenes)
    centers = (scenes[:, 0] + scenes[:, 1]) / 2.0
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        j = i + 1
        while j < n and centers[j] - centers[i] <= T_gap:
            if float(scene_feats[i] @ scene_feats[j]) >= S_sim:
                union(i, j)
            j += 1
    comps: dict[int, list[int]] = {}
    for i in range(n):
        comps.setdefault(find(i), []).append(i)
    return [sorted(m) for m in comps.values()]


def unit_of(units: list[list[int]], scene_i: int) -> int | None:
    for k, u in enumerate(units):
        if scene_i in u:
            return k
    return None


def unit_reps(units: list[list[int]], scene_feats: np.ndarray) -> np.ndarray:
    """事件单元代表 = 单元内场景指纹 L2 均值。"""
    reps = []
    for u in units:
        r = scene_feats[u].mean(axis=0)
        n = np.linalg.norm(r)
        reps.append(r / n if n > 1e-8 else r)
    return np.stack(reps)


def p2a_merge_rule() -> dict:
    """P2a: 归并规则网格扫描, 验证三族在事件单元下的行为。"""
    datas = {
        "2mkv": load(IDX2),
        "test3": load(IDX_T3),
        "test4": load(IDX_T4),
    }
    cases = [
        {"name": "sibling_2mkv", "idx": "2mkv", "true": [SIBLING["scene_a"]],
         "true2": [SIBLING["scene_b"]], "dist": []},
        {"name": "t3r12", "idx": "test3", "true": R12["true"], "true2": [], "dist": R12["dist"]},
        {"name": "t4r01_control", "idx": "test4", "true": T4["true"], "true2": [], "dist": T4["dist"]},
    ]
    grid = []
    for T_gap in T_GAPS:
        for S_sim in S_SIMS:
            row = {"T_gap": T_gap, "S_sim": S_sim, "cases": {}}
            for c in cases:
                d = datas[c["idx"]]
                units = merge_events(d["scenes"], d["scene_feats"], T_gap, S_sim)
                unit_sizes = [len(u) for u in units]
                true_units = {i: unit_of(units, i) for i in c["true"]}
                true2_units = {i: unit_of(units, i) for i in c["true2"]}
                dist_units = {i: unit_of(units, i) for i in c["dist"]}
                entry = {
                    "n_scenes": len(d["scenes"]),
                    "n_units": len(units),
                    "max_unit": max(unit_sizes),
                    "avg_unit": round(float(np.mean(unit_sizes)), 2),
                    "true_scenes_same_unit": (len(set(true_units.values())) == 1),
                    "true_units": {str(k): v for k, v in true_units.items()},
                    "true2_units": {str(k): v for k, v in true2_units.items()},
                    "dist_units": {str(k): v for k, v in dist_units.items()},
                    "dist_share_unit_with_true": bool(
                        set(dist_units.values()) & set(true_units.values())),
                }
                row["cases"][c["name"]] = entry
            grid.append(row)
    return grid


def _query_feats(idx_edit: Path, t0: float, t1: float):
    d = load(idx_edit)
    mask = (d["times"] >= t0) & (d["times"] <= t1)
    if mask.sum() == 0:
        return None
    q = d["features"][mask].mean(axis=0)
    n = np.linalg.norm(q)
    return q / n if n > 1e-8 else q


def _rank(scores: np.ndarray, correct: list[int]) -> dict:
    """correct 索引集合在 scores(越大越好)中的排名(1-based, 取集合内最优)。"""
    order = np.argsort(-scores)
    ranks = {int(o): k + 1 for k, o in enumerate(order)}
    best = min(ranks[i] for i in correct)
    return {"best_rank": int(best), "n": int(len(scores)),
            "ranks_of_correct": {int(i): int(ranks[i]) for i in correct}}


def p2b_end_to_end() -> dict:
    """P2b: 编辑段→事件单元端到端排序, 对比帧级/场景级/事件级。

    帧级基线: 查询 vs 原片全部帧特征, 正确帧=正确场景窗内帧(取最优排名)。
    场景级:   查询 vs 原片全部场景指纹, 正确场景集合。
    事件级:   查询 vs 归并后事件单元代表, 正确单元=含任一正确场景的单元。
    """
    datas_orig = {
        "2mkv": load(IDX2),
        "test3": load(IDX_T3),
    }
    idx_edit = {"1mp4": IDX1, "test3ed": IDX_T3E}
    out = []
    for orig_name, edit_name, e0, e1, true_scenes, label in E2E:
        do = datas_orig[orig_name]
        q = _query_feats(idx_edit[edit_name], e0, e1)
        if q is None:
            out.append({"label": label, "error": "编辑段无帧"})
            continue
        # 正确帧集合: 场景窗 [start,end] 内的原片帧
        correct_frames = []
        for si in true_scenes:
            a, b = do["scenes"][si]
            correct_frames += [int(i) for i in range(len(do["times"]))
                               if a <= do["times"][i] <= b]
        # 1) 帧级
        frame_scores = do["features"] @ q
        fr = _rank(frame_scores, correct_frames)
        # 2) 场景级
        scene_scores = do["scene_feats"] @ q
        sr = _rank(scene_scores, true_scenes)
        # 3) 事件级(在 S_sim/T_gap 网格上分别算)
        ev_grid = {}
        for T_gap in T_GAPS:
            for S_sim in S_SIMS:
                units = merge_events(do["scenes"], do["scene_feats"], T_gap, S_sim)
                reps = unit_reps(units, do["scene_feats"])
                unit_scores = reps @ q
                correct_units = sorted({unit_of(units, si) for si in true_scenes})
                ev = _rank(unit_scores, correct_units)
                ev_grid[f"{T_gap:.0f}/{S_sim:.2f}"] = ev
        out.append({
            "label": label,
            "orig": orig_name, "edit": edit_name,
            "edit_span": [e0, e1],
            "true_scenes": true_scenes,
            "true_frames": correct_frames,
            "n_frames": int(len(do["times"])),
            "frame_level": fr,
            "scene_level": sr,
            "event_level_grid": ev_grid,
        })
        print(f"[P2b] {label}")
        print(f"  frame best_rank={fr['best_rank']}/{fr['n']}  "
              f"scene best_rank={sr['best_rank']}/{sr['n']}")
        for k, v in ev_grid.items():
            print(f"    event[{k}] best_rank={v['best_rank']}/{v['n']}")
    return out


def summarize(p2a: list[dict], p2b: list[dict]) -> dict:
    """汇总三族结论 + 端到端最好成绩。"""
    # P2a 三族在代表性参数(60s/0.60)下的归并行为
    rep = next(r for r in p2a if r["T_gap"] == 60.0 and r["S_sim"] == 0.60)
    sibling = rep["cases"]["sibling_2mkv"]
    r12 = rep["cases"]["t3r12"]
    t4 = rep["cases"]["t4r01_control"]
    # P2b 事件级 vs 场景级最好提升(取 grid 中事件级最优排名)
    e2e_best = []
    for e in p2b:
        if "error" in e:
            e2e_best.append({"label": e["label"], "error": e["error"]})
            continue
        ev_best = min(v["best_rank"] for v in e["event_level_grid"].values())
        e2e_best.append({
            "label": e["label"],
            "scene_best_rank": e["scene_level"]["best_rank"],
            "event_best_rank": ev_best,
            "event_improved": ev_best <= e["scene_level"]["best_rank"],
        })
    return {
        "P2a_rep_60_0.60": {
            "sibling_2mkv": {
                "134_unit": sibling["true_units"].get("134"),
                "128_unit": sibling["true2_units"].get("128"),
                "same_unit": sibling["true_scenes_same_unit"]
                             and sibling["true_units"].get("134") == sibling["true2_units"].get("128"),
            },
            "t3r12": {
                "true_same_unit": r12["true_scenes_same_unit"],
                "dist_share_unit_with_true": r12["dist_share_unit_with_true"],
            },
            "t4r01_control": {
                "true_same_unit": t4["true_scenes_same_unit"],
                "dist_share_unit_with_true": t4["dist_share_unit_with_true"],
            },
        },
        "P2b_best": e2e_best,
    }


def main() -> int:
    t0 = time.time()
    p2a = p2a_merge_rule()
    p2b = p2b_end_to_end()
    summ = summarize(p2a, p2b)
    report = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "P2a_merge_rule_grid": p2a,
        "P2b_end_to_end": p2b,
        "summary": summ,
    }
    out = BENCH / "work" / "semantic_signal_P2_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
