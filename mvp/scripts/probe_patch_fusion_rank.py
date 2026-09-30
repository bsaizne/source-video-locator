"""竞品融合机制探针 B: patch×global 加权融合打分 (2026-09-26).

背景(09 §4/§9.4 字节+代码级确证): 竞品有 global_weight=0.45 / patch_weight=0.55, 且二者出现在
  matching/feature_index/retrieval.py 的 match_commentary_scenes 的 co_consts 里 => **融合打分是真实机制**,
  但**融合形式未知**(加权和? 归一化? 门控前后?) = 假设 H-F1: score = w*cls + (1-w)*patch, w=0.45。
我方现状: patch 只做**池内门控重排**(patch_rerank / patch_v2), **没有**与 CLS 加权融合的打分。

本探针(零 runtime 改动)对每个案例:
  pool = CLS top-100 ∪ 全索引均匀采样 100 ∪ 真值窗 ∪ 自动干扰(CLS top 中非真值窗)
  对 pool 每帧算 CLS sim 与 patch sim; 扫 w ∈ {0, .25, .45, .55, .75, 1.0} 的融合分, 记录:
    - 真值窗内最佳帧在池内的排名 rank_true
    - 自动 margin = best_true - best_nontrue(池内非真值窗最高分)
    - argmax 是否落在真值窗(命中)
  与 CLS-only(w=0) / patch-only(w=1) 对照。
判据: 若融合在多数案例上同时提高 rank_true/margin 且不伤易例 => 值得进一步; 否则关闭该方向。
注意: 这是**判别性**实验(池内), 不等于端到端收益; 结论须配画面复核。

产物 work/patch_fusion_probe.json
运行: python mvp/scripts/probe_patch_fusion_rank.py [--pool-cls 100] [--pool-sample 100]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
WORK = BENCH / "work"
IDX_DIR = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
ORIG = {"2mkv": "D:/video/2.mkv", "test2": "D:/ProjectXIXI/test2/test2-om.mp4",
        "test3": "D:/ProjectXIXI/test3/test3-om.mp4"}
EDIT = {"2mkv": "D:/video/1.mp4", "test2": "D:/ProjectXIXI/test2/tset2-ed.mp4",
        "test3": "D:/ProjectXIXI/test3/test3-ed.mp4"}
IDX = {"2mkv": IDX_DIR / "2__4c6d4ab2.idx", "test2": IDX_DIR / "test2-om__35b9a58f.idx",
       "test3": IDX_DIR / "test3-om__074e2dcc.idx"}
# (pair, pid, 编辑查询中心, 真值窗) —— 取自 v4/verified GT; 覆盖兄弟机位/夜读/重复镜头/蒙太奇/易例
CASES = [
    ("2mkv", "p08", 13.5, (1108.15, 1109.1)),
    ("2mkv", "p26", 77.0, (1768.2, 1770.05)),
    ("2mkv", "p01", 0.8, (2417.5, 2418.1)),
    ("test3", "t3r12", 64.75, (466.0, 478.0)),
    ("test2", "t2r05a", 38.9, (4344.8, 4346.8)),
]
WEIGHTS = [0.0, 0.25, 0.45, 0.55, 0.75, 1.0]
from research_patch_recall_v4 import Embedder, l2, patch_score, load_idx  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool-cls", type=int, default=100)
    ap.add_argument("--pool-sample", type=int, default=100)
    ap.add_argument("--out", default=str(WORK / "patch_fusion_probe.json"))
    args = ap.parse_args()
    t0 = time.time()
    emb = Embedder()
    report = {"weights": WEIGHTS, "note": "H-F1 假设: score = w*cls + (1-w)*patch (patch 侧取 top-100 平均)",
              "cases": []}
    for pair, pid, e_mid, true_win in CASES:
        feats, times = load_idx(IDX[pair])
        q_cls, q_patch = None, None
        for j in range(3):
            c, p = emb.embed(EDIT[pair], e_mid - 0.4 + 0.4 * j)
            q_cls = c if q_cls is None else q_cls + c
            q_patch = p if q_patch is None else np.concatenate([q_patch, p], axis=0)
        q_cls = l2(q_cls[None, :])[0]
        cls_sim = feats @ q_cls
        order = np.argsort(-cls_sim)
        true_mask_all = (times >= true_win[0]) & (times <= true_win[1])
        true_idx = np.where(true_mask_all)[0]
        if len(true_idx) == 0:
            print("[%s] 真值窗内无索引帧, 跳过" % pid, flush=True)
            continue
        pool = set(int(i) for i in order[:args.pool_cls])
        stride = max(1, len(times) // max(1, args.pool_sample))
        pool |= set(range(0, len(times), stride))
        pool |= set(int(i) for i in true_idx)
        pool = sorted(pool)
        pt = times[pool]
        p_cls = cls_sim[pool]
        p_true = (pt >= true_win[0]) & (pt <= true_win[1])
        p_patch = np.zeros(len(pool), np.float32)
        for k, i in enumerate(pool):
            _, pp = emb.embed(ORIG[pair], float(times[i]))
            p_patch[k] = patch_score(q_patch, pp)
            if k % 50 == 0:
                print("  %s pool %d/%d (%.0fs)" % (pid, k, len(pool), time.time() - t0), flush=True)
        rows = []
        for w in WEIGHTS:
            fused = w * p_cls + (1.0 - w) * p_patch
            # patch 与 cls 量纲不同: 融合前各自 min-max 归一化(形式假设之一, 见报告 note)
            def mm(x):
                lo, hi = float(x.min()), float(x.max())
                return (x - lo) / max(1e-6, hi - lo)
            fused_norm = w * mm(p_cls) + (1.0 - w) * mm(p_patch)
            for tag, sc in (("raw", fused), ("minmax", fused_norm)):
                o = np.argsort(-sc)
                rank_true = int(np.where(np.isin(o, np.where(p_true)[0]))[0].min()) + 1
                best_true = float(sc[p_true].max())
                best_nt = float(sc[~p_true].max()) if (~p_true).any() else float("nan")
                rows.append({"w": w, "form": tag, "rank_true": rank_true,
                             "margin": round(best_true - best_nt, 5),
                             "argmax_in_true": bool(np.argmax(sc) in set(np.where(p_true)[0].tolist()))})
        # 基线
        clsun = [r for r in rows if r["form"] == "minmax" and r["w"] == 0.0][0]
        ptch = [r for r in rows if r["form"] == "minmax" and r["w"] == 1.0][0]
        report["cases"].append({"id": pid, "pair": pair, "true_win": list(true_win),
                                "pool_size": len(pool), "cls_baseline_pool_rank": clsun["rank_true"],
                                "patch_only_rank": ptch["rank_true"], "rows": rows})
        print("[%s] pool=%d | CLS-only rank_true=%d margin=%.4f | patch-only rank_true=%d margin=%.4f"
              % (pid, len(pool), clsun["rank_true"], clsun["margin"], ptch["rank_true"], ptch["margin"]), flush=True)
        for w in (0.45, 0.55):
            r = [x for x in rows if x["form"] == "minmax" and x["w"] == w][0]
            print("     w=%.2f(minmax): rank_true=%d margin=%.4f argmax_in_true=%s"
                  % (w, r["rank_true"], r["margin"], r["argmax_in_true"]), flush=True)
        Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["elapsed_s"] = round(time.time() - t0, 1)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved %s  total %.0fs" % (args.out, report["elapsed_s"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
