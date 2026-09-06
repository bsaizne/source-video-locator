"""Phase 24-2 · 原片邻接唯一性探针 M8 [v4 GT 重跑版, 2026-09-04]/m —— 来源身份信息(provenance)能否消歧失败族。

问题(用户拍板): 外观三层(CLS/patch/局部描述子)全部无解后, 唯一未被否定的来源身份信息 =
「原片 Shot Graph 的原片侧邻接唯一性」(区别于已证伪的 P3 编辑上下文)。

判据:
  - 对每个失败案例, 定位真值窗/干扰窗在原片 scenes 表中的位置(按中点);
  - 若真值与干扰落在**同一 scene** -> 邻接唯一性无法区分(记录为 SAME_SCENE);
  - 否则取该 scene 的邻接子图指纹(前±1/±2), 全原片检索其唯一性:
      唯一性 = 该邻接向量在全原片所有邻接向量中的最大余弦(越低越唯一)
  - 鉴别 = 真值邻接 vs 干扰邻接 的余弦(越高越难分)

零 runtime 改动, 纯 numpy, 秒级。

输出: work/provenance_neighbor_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_provenance_neighbor.py
"""
import json
import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
WORK = BENCH / "work"
IDX_DIR = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")

ORIG_IDX = {
    "2mkv": IDX_DIR / "2__4c6d4ab2.idx",
    "test3": IDX_DIR / "test3-om__074e2dcc.idx",
    "test4": IDX_DIR / "test4-om__eb686e0c.idx",
}

# (pair, pid, 正确窗, 干扰窗|None, 说明)
# v4 GT 修正(2026-09-02 重跑): p26 真值=1768.2-1770.05(v4 用户精修)/干扰=2809-2810(旧真值区);
# p38 已删(v4); t4r01 因 test4 数据错误已逻辑剔除。
CASES = [
    ("2mkv", "p08", (1108.15, 1109.1), (1048, 1050), "兄弟机位: 瞭望塔(v4真值1108.15-1109.1) vs 士兵特写(干扰)"),
    ("2mkv", "p26", (1768.2, 1770.05), (2809, 2810), "夜读(v4真值1768.2-1770.05) vs 旧真值区2809-2810(干扰)"),
    ("test3", "t3r12", (454, 480), (481, 488), "精灵王重复镜头(真值) vs 另一实例(干扰)"),
]

NBR = [1, 2]  # 邻接半径


def l2(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


def main() -> int:
    report = {"started": __import__("time").strftime("%Y-%m-%d %H:%M:%S"), "cases": []}

    for pair, pid, true_win, dist_win, note in CASES:
        idx_dir = ORIG_IDX[pair]
        scenes = np.load(idx_dir / "scenes.npy").astype(np.float64)   # [S,2] 起止秒
        feats = np.load(idx_dir / "scene_feats.npy").astype(np.float32)  # [S,384]
        S = len(scenes)

        def scene_of(t: float) -> int:
            """返回包含 t 的 scene 下标(中点规则: 取最近 scene 中点)。"""
            mids = (scenes[:, 0] + scenes[:, 1]) / 2.0
            return int(np.abs(mids - t).argmin())

        s_true = scene_of((true_win[0] + true_win[1]) / 2.0)
        s_dist = scene_of((dist_win[0] + dist_win[1]) / 2.0) if dist_win else None

        def adj_vec(s: int, r: int) -> np.ndarray:
            """scene s 半径 r 邻接指纹向量: [feat_{s-r}..feat_{s+r}] 拼接后 L2。"""
            lo, hi = max(0, s - r), min(S, s + r + 1)
            return l2(feats[lo:hi].reshape(-1))

        def uniqueness(s: int, r: int) -> float:
            """该邻接向量在全原片所有同半径邻接向量中的最大余弦(越低越唯一)。"""
            v = adj_vec(s, r)
            sims = []
            for j in range(max(0, r), min(S, S - r)):
                if abs(j - s) <= r:      # 跳过自身及重叠邻接窗
                    continue
                sims.append(float(v @ adj_vec(j, r)))
            return float(max(sims)) if sims else None

        def diff(s, r) -> float:
            return float(adj_vec(s, r) @ adj_vec(s_dist, r)) if s_dist is not None else None

        entry = {"id": pid, "pair": pair, "note": note,
                 "s_true": s_true, "s_dist": s_dist, "n_scenes": S,
                 "same_scene": (s_dist is not None and s_true == s_dist)}
        for r in NBR:
            u_true = uniqueness(s_true, r)
            u_dist = uniqueness(s_dist, r) if s_dist is not None else None
            d_adj = diff(s_true, r)
            entry[f"nbr{r}"] = {
                "uniq_true_maxcos": round(u_true, 4) if u_true is not None else None,
                "uniq_dist_maxcos": round(u_dist, 4) if u_dist is not None else None,
                "adj_true_vs_dist_cos": round(d_adj, 4) if d_adj is not None else None,
            }
        # 判定
        if entry["same_scene"]:
            verdict = "SAME_SCENE (真值/干扰同一 scene, 邻接唯一性无法区分)"
        else:
            r1 = entry["nbr1"]
            verdict = "INDETERMINATE"
            if r1["uniq_true_maxcos"] is not None and r1["uniq_dist_maxcos"] is not None:
                if r1["uniq_true_maxcos"] < r1["uniq_dist_maxcos"] - 0.05:
                    verdict = "TRUE_UNIQUE (真值邻接更唯一 -> 可消歧)"
                elif r1["adj_true_vs_dist_cos"] is not None and r1["adj_true_vs_dist_cos"] > 0.90:
                    verdict = "NEIGHBOR_SAME (真值/干扰邻接几乎相同 -> 不可辨识)"
                else:
                    verdict = "AMBIGUOUS"
        entry["verdict"] = verdict
        report["cases"].append(entry)
        print(f"[{pid}] scenes={S} s_true={s_true} s_dist={s_dist} same={entry['same_scene']}", flush=True)
        for r in NBR:
            d = entry[f"nbr{r}"]
            print(f"    nbr{r}: uniq_true={d['uniq_true_maxcos']} uniq_dist={d['uniq_dist_maxcos']} "
                  f"adj_cos={d['adj_true_vs_dist_cos']}", flush=True)
        print(f"    -> {verdict}", flush=True)

    out = WORK / "provenance_neighbor_results_v4.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())