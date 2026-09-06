"""Phase 24-2 语义级第二信号 · 第六路候选探针 P3 —— 镜头序列上下文匹配。

用户 2026-09-01 提出:五路信号+方向 A 都没覆盖「镜头序列上下文」——
用目标镜头前后各 1~2 个镜头的内容做联合匹配,而非只看目标片段本身。
即使兄弟机位画面不可分,前后镜头序列是独立证据源。

本探针 = 用户要求的「离线最小验证」:取 p08 查询片段,扩展为
「前镜头 + 目标镜头 + 后镜头」的 CLS 序列,与原片对应位置滑动匹配,
看真值排名是否被拉高。零 runtime 改动,仅用现有 CLS 特征 + 镜头边界。

数据事实(侦查已确认):
  - 编辑侧 1.mp4 索引 scenes.npy 只有 2 个粗场景(0-90/90-126),无细镜头边界;
    但 GT v3 已按镜头给出编辑段边界(如 p07/p08/p09 的 edited 区间),可当查询镜头用。
  - p08 编辑段 [12.6,14.3] 仅覆盖原片场景134(1106-1121)内部 1108-1110 两秒,非完整边界。
  - 编辑片里 p08 的相邻镜头:p07->原片[1010,1030], p09->原片[1048,1082]——后者恰为
    兄弟机位 p38(1048-1050)所在区域!编辑上下文自身就混着兄弟内容。
  - p26 相邻:p40/p41/p27->原片[1772,1815], 真值2809 在 ~1000s 之外。

验证内容:
  P3a 上下文在原片的邻接性:编辑相邻镜头(p07/p09)的原片位置是否与真值(1108)
      时间相邻?(若不相邻,则「序列匹配」没有合法的原片目标)
  P3b 序列滑动匹配:查询序列[p07+p08+p09 CLS] 在原片场景上下文(前+中+后)上滑动,
      对比单镜头匹配,看真值场景134 排名是否被拉高、能否压过兄弟场景128。
  P3c p26 对照:同样的序列匹配在 p26 上的行为(预期上下文把答案拉向 1772 而非 2809)。

输出: work/semantic_signal_P3_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_semantic_signal_P3_seq_context.py
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
IDX1 = IDX_DIR / "1__ffdc13d9.idx"   # 1.mp4 编辑片 (0.5fps)
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"   # 2.mkv 原片 (1fps)


def load(idx: Path) -> dict:
    return {
        "features": np.load(idx / "features.npy").astype(np.float32),
        "times": np.load(idx / "times.npy"),
        "scenes": np.load(idx / "scenes.npy"),
        "scene_feats": np.load(idx / "scene_feats.npy").astype(np.float32),
    }


def seg_cls(d: dict, t0: float, t1: float) -> np.ndarray | None:
    """编辑段 [t0,t1] 内帧的 CLS 均值(L2)。"""
    m = (d["times"] >= t0) & (d["times"] <= t1)
    if m.sum() == 0:
        return None
    q = d["features"][m].mean(axis=0)
    n = np.linalg.norm(q)
    return q / n if n > 1e-8 else q


def rank_of(scores: np.ndarray, correct_idx: int) -> dict:
    order = np.argsort(-scores)
    ranks = {int(o): k + 1 for k, o in enumerate(order)}
    return {"best_rank": int(ranks[int(correct_idx)]), "n": int(len(scores))}


def p3a_context_adjacency(do, de) -> dict:
    """编辑相邻镜头原片位置 vs 真值位置的邻接性。"""
    gt = {
        # 编辑片镜头 -> (编辑区间, 原片真值)
        "p07": ((11.2, 12.6), (1010.0, 1030.0)),
        "p08": ((12.6, 14.3), (1108.0, 1110.0)),
        "p09": ((14.3, 18.2), (1048.0, 1082.0)),
        "p25": ((59.5, 62.5), (1705.0, 1711.0)),
        "p26": ((76.0, 78.0), (2809.0, 2810.0)),
        "p40": ((72.5, 74.5), (1774.0, 1776.0)),
        "p41": ((78.5, 80.5), (1772.0, 1780.0)),
        "p27": ((84.5, 86.0), (1808.0, 1815.0)),
    }
    out = {}
    for pid, (_, orig) in gt.items():
        best_scene, best_sim = None, -1.0
        q = seg_cls(de, *gt[pid][0])
        if q is None:
            out[pid] = {"error": "编辑段无帧"}
            continue
        sims = do["scene_feats"] @ q
        order = np.argsort(-sims)
        best_scene = int(order[0])
        out[pid] = {
            "orig_true": list(orig),
            "best_scene": best_scene,
            "best_scene_span": [float(do["scenes"][best_scene][0]),
                                float(do["scenes"][best_scene][1])],
            "best_sim": round(float(sims[best_scene]), 4),
        }
    return out


def p3b_sequence_match(do, de) -> dict:
    """查询序列[前+目标+后] 在原片场景上下文(前+中+后)上滑动。

    假设编辑序列顺序映射原片序列顺序(待验证的假设):
      对每个原片场景 k, 上下文向量 = [feat[k-1], feat[k], feat[k+1]],
      查询向量 = [CLS(前编辑镜头), CLS(目标), CLS(后编辑镜头)],
      序列相似度 = 逐位置余弦和。
    p08: 查询=[p07,p08,p09], 真值=场景134, 兄弟=场景128。
    """
    def seq_sim(qs: list[np.ndarray], ctx: list[np.ndarray]) -> float:
        return sum(float(a @ b) for a, b in zip(qs, ctx))

    # 查询序列(编辑侧 CLS)
    q_p07 = seg_cls(de, 11.2, 12.6)
    q_p08 = seg_cls(de, 12.6, 14.3)
    q_p09 = seg_cls(de, 14.3, 18.2)
    if any(q is None for q in (q_p07, q_p08, q_p09)):
        return {"error": "查询段缺帧"}

    sf = do["scene_feats"]
    scenes = do["scenes"]
    n = len(scenes)

    # 单镜头基线: 目标 CLS vs 各场景
    single = sf @ q_p08
    single_truth = rank_of(single, 134)
    single_sib = rank_of(single, 128)

    # 序列: 原片场景 k 的上下文 [k-1, k, k+1]
    seq_scores = np.zeros(n)
    for k in range(1, n - 1):
        ctx = [sf[k - 1], sf[k], sf[k + 1]]
        seq_scores[k] = seq_sim([q_p07, q_p08, q_p09], ctx)
    seq_truth = rank_of(seq_scores, 134)
    seq_sib = rank_of(seq_scores, 128)

    # 逆序对照(编辑序列可能映射原片逆序): [后,目标,前] vs [k-1,k,k+1]
    seq_rev_scores = np.zeros(n)
    for k in range(1, n - 1):
        ctx = [sf[k - 1], sf[k], sf[k + 1]]
        seq_rev_scores[k] = seq_sim([q_p09, q_p08, q_p07], ctx)
    seq_rev_truth = rank_of(seq_rev_scores, 134)
    seq_rev_sib = rank_of(seq_rev_scores, 128)

    return {
        "query_edges": {"p07": "11.2-12.6", "p08": "12.6-14.3", "p09": "14.3-18.2"},
        "single_target_vs_scenes": {
            "truth_scene134": single_truth, "sib_scene128": single_sib},
        "seq_before_target_after": {
            "truth_scene134": seq_truth, "sib_scene128": seq_sib},
        "seq_rev": {
            "truth_scene134": seq_rev_truth, "sib_scene128": seq_rev_sib},
        "truth_scene134_span": scenes[134].tolist(),
        "sib_scene128_span": scenes[128].tolist(),
        "top3_seq": [{"scene": int(j), "span": scenes[j].tolist(),
                      "sim": round(float(seq_scores[j]), 4)}
                     for j in np.argsort(-seq_scores)[:3]],
    }


def p3c_p26(do, de) -> dict:
    """p26 对照:查询[p40? or p25?] 注意 p26 编辑片相邻 = p40(72.5-74.5)在编辑时间
    上更靠近,但 p26 之前一段是 p25(59.5-62.5)。取编辑时间上紧邻:
    前=p40(72.5-74.5)?? 不对——p40 是 72.5-74.5, p26 是 76.0-78.0, 之间 74.5-76.0 未标注;
    编辑时间上 p26 的前一镜头最近的是 p40, 后一镜头是 p41(78.5-80.5)。
    """
    q_pre = seg_cls(de, 72.5, 74.5)   # p40
    q_tgt = seg_cls(de, 76.0, 78.0)   # p26
    q_post = seg_cls(de, 78.5, 80.5)  # p41
    if any(q is None for q in (q_pre, q_tgt, q_post)):
        return {"error": "查询段缺帧"}
    sf = do["scene_feats"]
    n = len(sf)
    single = sf @ q_tgt
    single_truth = rank_of(single, 295)  # p26 真值场景 295
    seq_scores = np.zeros(n)
    for k in range(1, n - 1):
        ctx = [sf[k - 1], sf[k], sf[k + 1]]
        seq_scores[k] = sum(float(a @ b) for a, b in
                            zip([q_pre, q_tgt, q_post], ctx))
    seq_truth = rank_of(seq_scores, 295)
    return {
        "query_edges": {"pre_p40": "72.5-74.5", "tgt_p26": "76.0-78.0", "post_p41": "78.5-80.5"},
        "single_target_vs_scenes": {"truth_scene295": single_truth},
        "seq_before_target_after": {"truth_scene295": seq_truth},
        "truth_scene295_span": do["scenes"][295].tolist(),
        "top3_seq": [{"scene": int(j), "span": do["scenes"][j].tolist(),
                      "sim": round(float(seq_scores[j]), 4)}
                     for j in np.argsort(-seq_scores)[:3]],
    }


def main() -> int:
    t0 = time.time()
    do = load(IDX2)  # 原片
    de = load(IDX1)  # 编辑片
    report = {
        "started": time.strftime("%Y-%m-%d %H:%M:%S"),
        "P3a_context_adjacency": p3a_context_adjacency(do, de),
        "P3b_p08_sequence_match": p3b_sequence_match(do, de),
        "P3c_p26_control": p3c_p26(do, de),
    }
    out = BENCH / "work" / "semantic_signal_P3_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
