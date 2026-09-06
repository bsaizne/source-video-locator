# -*- coding: utf-8 -*-
"""方向 A 探针：场景实例身份建模（事件级聚类 + 事件身份端到端排序）。

立项：RESEARCH_PROPOSAL_SECOND_SIGNAL.md §6（2026-09-05 用户拍板重启研究侧）。
性质：研究侧探针，零 runtime 改动。GPU 约定：启动打印 BACKEND_SELECTED（DirectML/amd 生效）。

P1（事件级聚类，2.mkv）：
  scenes 表 + scene_feats 指纹，按「时序近邻 + 指纹联合」归并事件单元（连通分量），
  验证 p08 场景(1106-1121) 与 p38 场景(1041-1061) 能否聚为同一「对话事件」身份
  （P1a 归并能力），且该事件与邻近事件可分（P1b 区分能力, 同口径场景对级别）。

P2（事件身份端到端排序）：
  编辑段查询（编辑索引 CLS 帧特征均值, L2）→ 三档基线对照：
    帧级（查询 vs 原片全帧） / 场景级（查询 vs 原片全场景指纹） /
    事件级（查询 vs 归并后事件单元代表）。
  案例：p08（2.mkv 编辑 12.6-14.3s，v4 正确=1108.15-1109.1=p08；p08b 已并入，
  旧 1048 士兵特写=p38 旧错误 GT 区，v4 已删）+ t3r12（test3 编辑 64-65.5s → 466-478）。

判据：
  P1a PASS = 兄弟场景同事件单元（网格稳健）；
  P1b PASS = 单元内场景对相似度均值 - 跨单元场景对相似度均值（sep_pairs）> 0。
  P2 PASS = 事件级正确单元排名 <= 场景级且尽量 top-1（p08/t3r12）。

输出：work/event_identity_P1_P2_results.json
运行：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_event_identity.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
IDX_DIR = Path(r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data\index")
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"            # 2.mkv 原片 (1fps, directml, scn1)
IDX1 = IDX_DIR / "1__ffdc13d9.idx"            # 1.mp4 编辑片 (0.5fps)
IDX_T3 = IDX_DIR / "test3-om__074e2dcc.idx"   # test3 原片 (1fps)
IDX_T3E = IDX_DIR / "test3-ed__57a104a7.idx"  # test3 编辑片 (1fps)

# ---- 事件归并参数网格（与 research_semantic_signal_P2.py 一致） ----
T_GAPS = [30.0, 60.0, 120.0]
S_SIMS = [0.55, 0.60, 0.65, 0.70]

# ---- P1 案例（2.mkv 兄弟机位, 场景编号用时间查找, 不硬编码） ----
P1_CASES = [
    {"name": "sibling_p08_p38", "idx": "2mkv",
     "a": (1106.0, 1121.0), "b": (1041.0, 1061.0),
     "note": "p08 瞭望塔/桌边(1106-1121) vs p38 士兵特写(1041-1061), 同场对话戏 GT 双真(v4 p38 已删, 正确=1108.15-1109.1)"},
]

# ---- P2 端到端案例 ----
# (orig_name, edit_idx, edit_t0, edit_t1, true_orig_span(s), correct_scene_spans, label)
E2E = [
    ("2mkv", IDX1, 12.6, 14.3, (1108.15, 1109.1),
     [(1106.0, 1121.0), (1041.0, 1061.0)],
     "p08 兄弟机位对话（编辑 12.6-14.3, v4 正确=1108.15-1109.1; 正确事件含两机位场景）"),
    ("test3", IDX_T3E, 64.0, 65.5, (466.0, 478.0),
     [(466.0, 478.0)],
     "t3r12 精灵王重复镜头（编辑 64-65.5, 正确=466-478）"),
]


def load(idx: Path) -> dict:
    return {
        "features": np.load(idx / "features.npy").astype(np.float32),
        "times": np.load(idx / "times.npy"),
        "scenes": np.load(idx / "scenes.npy"),
        "scene_feats": np.load(idx / "scene_feats.npy").astype(np.float32),
    }


def scene_of(scenes: np.ndarray, t: float) -> int | None:
    for i, (a, b) in enumerate(scenes):
        if a <= t <= b:
            return i
    return None


def merge_events(scenes: np.ndarray, scene_feats: np.ndarray,
                 T_gap: float, S_sim: float) -> list[list[int]]:
    """时序近邻 + 指纹联合聚类 → 事件单元（连通分量）。"""
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
    reps = []
    for u in units:
        r = scene_feats[u].mean(axis=0)
        nn = np.linalg.norm(r)
        reps.append(r / nn if nn > 1e-8 else r)
    return np.stack(reps)


def p1_event_clustering() -> dict:
    """P1：2.mkv 事件级聚类, 验证 p08/p38 同事件 + 邻近可分。"""
    d = load(IDX2)
    scenes, sf = d["scenes"], d["scene_feats"]
    out = {"kind": "P1_event_clustering", "n_scenes": int(len(scenes)), "cases": []}

    for case in P1_CASES:
        ia = scene_of(scenes, (case["a"][0] + case["a"][1]) / 2.0)
        ib = scene_of(scenes, (case["b"][0] + case["b"][1]) / 2.0)
        sa = float(sf[ia] @ sf[ib])
        sims_a = sf @ sf[ia]
        rank_b_in_a = int(np.sum(sims_a > sa))
        entry = {
            "name": case["name"], "note": case["note"],
            "scene_a": int(ia), "span_a": [round(float(x), 1) for x in scenes[ia]],
            "scene_b": int(ib), "span_b": [round(float(x), 1) for x in scenes[ib]],
            "mutual_sim": round(sa, 4),
            "rank_b_in_a": int(rank_b_in_a) + 1,
            "grid": [],
        }
        same_unit_all = True
        for T_gap in T_GAPS:
            for S_sim in S_SIMS:
                units = merge_events(scenes, sf, T_gap, S_sim)
                ua, ub = unit_of(units, ia), unit_of(units, ib)
                same = (ua is not None and ua == ub)
                same_unit_all = same_unit_all and same
                u_sizes = [len(u) for u in units]
                entry["grid"].append({
                    "T_gap": T_gap, "S_sim": S_sim,
                    "same_unit": bool(same),
                    "unit_a": int(ua) if ua is not None else None,
                    "unit_b": int(ub) if ub is not None else None,
                    "n_units": len(units),
                    "max_unit": max(u_sizes),
                })
        entry["P1a_same_unit_all_grid"] = bool(same_unit_all)
        entry["P1a_pass"] = bool(same_unit_all)

        # ---- P1b 区分能力（同口径场景对级别）----
        units = merge_events(scenes, sf, 60.0, 0.60)
        ua = unit_of(units, ia)
        unit = units[ua]
        reps = unit_reps(units, sf)
        # 单元内场景对相似度（同口径）
        within = [float(sf[x] @ sf[y]) for k, x in enumerate(unit) for y in unit[k + 1:]]
        within_m = float(np.mean(within)) if within else None
        # 场景对级别跨单元：兄弟单元内场景 vs 其它单元内场景（同口径对比）
        cross_pairs = []
        for j, u2 in enumerate(units):
            if j == ua:
                continue
            cross_pairs += [float(sf[x] @ sf[y]) for x in unit for y in u2]
        cross_m = float(np.mean(cross_pairs)) if cross_pairs else None
        sep_pairs = (within_m - cross_m) if (within_m is not None and cross_m is not None) else None
        # 单元代表级别最近跨单元（均值向量口径, 天然偏高, 仅作参考）
        u_rep = reps[ua]
        cross_reps = [float(u_rep @ reps[j]) for j in range(len(reps)) if j != ua]
        nearest_cross_rep = float(max(cross_reps)) if cross_reps else None
        entry["P1b_rep_60_0.60"] = {
            "unit_scenes": [int(x) for x in unit],
            "unit_span": [round(float(scenes[unit[0]][0]), 1),
                          round(float(scenes[unit[-1]][1]), 1)],
            "unit_size": len(unit),
            "within_sim_mean": round(within_m, 4) if within_m is not None else None,
            "cross_sim_mean_pairs": round(cross_m, 4) if cross_m is not None else None,
            "sep_within_minus_cross_pairs": round(sep_pairs, 4) if sep_pairs is not None else None,
            "nearest_cross_rep_ref": round(nearest_cross_rep, 4)
                                     if nearest_cross_rep is not None else None,
        }
        entry["P1b_pass"] = bool(sep_pairs is not None and sep_pairs > 0)
        out["cases"].append(entry)

        print(f"[P1] {case['name']}: scene_a={ia}{list(scenes[ia])} scene_b={ib}{list(scenes[ib])}")
        print(f"  mutual_sim={sa:.4f} rank_b_in_a={entry['rank_b_in_a']} "
              f"P1a same_unit_all_grid={same_unit_all}")
        print(f"  P1b(60/0.60): within={within_m} cross_pairs={cross_m} "
              f"sep={sep_pairs} pass={entry['P1b_pass']}")
    out["P1_pass"] = bool(all(c["P1a_pass"] and c["P1b_pass"] for c in out["cases"]))
    return out


def _query_feats(d_edit: dict, t0: float, t1: float):
    mask = (d_edit["times"] >= t0) & (d_edit["times"] <= t1)
    if mask.sum() == 0:
        return None
    q = d_edit["features"][mask].mean(axis=0)
    nn = np.linalg.norm(q)
    return q / nn if nn > 1e-8 else q


def _rank(scores: np.ndarray, correct: list[int]) -> dict:
    order = np.argsort(-scores)
    ranks = {int(o): k + 1 for k, o in enumerate(order)}
    best = min(ranks[i] for i in correct if i in ranks)
    return {"best_rank": int(best), "n": int(len(scores)),
            "ranks_of_correct": {int(i): int(ranks[i]) for i in correct}}


def p2_end_to_end() -> dict:
    datas_orig = {"2mkv": load(IDX2), "test3": load(IDX_T3)}
    out = {"kind": "P2_event_identity_ranking", "cases": []}
    for orig_name, idx_edit, e0, e1, true_span, corr_spans, label in E2E:
        do = datas_orig[orig_name]
        de = load(idx_edit)
        q = _query_feats(de, e0, e1)
        if q is None:
            out["cases"].append({"label": label, "error": "编辑段无帧"})
            continue
        correct_frames = [int(i) for i in range(len(do["times"]))
                          if true_span[0] <= do["times"][i] <= true_span[1]]
        correct_scenes = sorted({scene_of(do["scenes"], (a + b) / 2.0)
                                 for a, b in corr_spans})
        # 1) 帧级
        fr = _rank(do["features"] @ q, correct_frames)
        # 2) 场景级
        sr = _rank(do["scene_feats"] @ q, correct_scenes)
        # 3) 事件级（网格最优）
        ev_grid = {}
        ev_best = None
        for T_gap in T_GAPS:
            for S_sim in S_SIMS:
                units = merge_events(do["scenes"], do["scene_feats"], T_gap, S_sim)
                reps = unit_reps(units, do["scene_feats"])
                correct_units = sorted({unit_of(units, si) for si in correct_scenes
                                        if unit_of(units, si) is not None})
                if not correct_units:
                    continue
                ev = _rank(reps @ q, correct_units)
                ev_grid[f"{T_gap:.0f}/{S_sim:.2f}"] = ev
                if ev_best is None or ev["best_rank"] < ev_best["best_rank"]:
                    ev_best = ev
        entry = {
            "label": label, "orig": orig_name,
            "edit_span": [e0, e1], "true_span": list(true_span),
            "correct_scenes": correct_scenes,
            "n_frames": int(len(do["times"])), "n_scenes": int(len(do["scenes"])),
            "frame_level": fr, "scene_level": sr,
            "event_level_best": ev_best,
            "event_level_grid": ev_grid,
        }
        entry["P2_pass"] = bool(
            ev_best is not None
            and ev_best["best_rank"] <= sr["best_rank"]
            and ev_best["best_rank"] == 1)
        out["cases"].append(entry)

        print(f"[P2] {label}")
        print(f"  frame best_rank={fr['best_rank']}/{fr['n']}  "
              f"scene best_rank={sr['best_rank']}/{sr['n']}  "
              f"event best_rank={ev_best['best_rank'] if ev_best else '-'}/{ev_best['n'] if ev_best else '-'}")
        for k, v in ev_grid.items():
            print(f"    event[{k}] best_rank={v['best_rank']}/{v['n']}")
    out["P2_pass"] = bool(all(c.get("P2_pass", False) for c in out["cases"] if "error" not in c))
    return out


def main() -> int:
    t0 = time.time()
    # GPU 约定：能力探测 + BACKEND_SELECTED 打印（探针计算纯 numpy, 复用索引特征）
    try:
        sys.path.insert(0, str(BENCH / "mvp" / "src"))
        from device import resolve_backend
        b = resolve_backend("auto")
        print(f"BACKEND_SELECTED type={type(b).__name__} "
              f"device={b.device_name()} dtype={b.device_type()}", flush=True)
    except Exception as bexc:
        print(f"BACKEND_SELECTED ERROR: {bexc}", flush=True)

    p1 = p1_event_clustering()
    p2 = p2_end_to_end()
    report = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "P1": p1,
        "P2": p2,
        "verdict": {
            "P1_pass": p1["P1_pass"],
            "P2_pass": p2["P2_pass"],
            "direction_A_probe": "POSITIVE" if (p1["P1_pass"] and p2["P2_pass"]) else "NEGATIVE",
        },
    }
    out = BENCH / "work" / "event_identity_P1_P2_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
