"""Phase 24-2 · 索引密度探针 M4 [v4 GT 重跑版, 2026-09-02, 仅 p26]/m —— 8fps 密帧 vs 1fps 稀疏索引的判别力实测。

用户 2026-09-01 质疑:帧数不能再提升吗?GPU 加速还能往上吗?(对标同类软件 30fps 全片解析)
关键澄清:此前 Phase 14C「2→4→8fps 零增益」是**查询侧(编辑片)**结论,索引侧(原片)帧率从未测过。
M4 直接实测:同一编辑段查询,在「原片 1fps 稀疏索引」vs「原片 8fps 密帧索引」的候选池上,
正确实例 vs 干扰实例的判别力(margin / top-N 命中 / best_rank)。

成本控制:仅对每个案例的正确窗+干扰窗做 8fps 密帧嵌入(不是全片),DML batch=1(实测 20.5fps),
~1400 帧 ≈ 1-2 分钟。零 runtime 改动。

判据:
  - 8fps 下正确窗 best_rank / top-N 命中 / margin 优于 1fps → 索引侧密度有判别增益(值得立项)
  - 无显著差异 → 瓶颈在信号层而非粒度(索引侧加密无收益)

输出: work/semantic_signal_M4_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_semantic_signal_M4_density.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
WORK = BENCH / "work"

# POC DML session(已验证正确性 cos>0.999)
POC = BENCH / "mvp" / "poc" / "amdgpu_onnx"
sys.path.insert(0, str(POC))
from common import MODEL_PATH, preprocess_np, l2norm  # noqa: E402

IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
IDX1 = IDX_DIR / "1__ffdc13d9.idx"          # 1.mp4 编辑片 (0.5fps)
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"          # 2.mkv 原片 (1fps)
IDX_T3E = IDX_DIR / "test3-ed__57a104a7.idx"  # test3 编辑片 (1fps)

ORIG_VIDEO = {
    "2mkv": "D:/video/2.mkv",
    "test3": "D:/ProjectXIXI/test3/test3-om.mp4",
    "test4": "D:/ProjectXIXI/test4/test4-om.mkv",
}
EDIT_VIDEO = {
    "2mkv": "D:/video/1.mp4",
    "test3": "D:/ProjectXIXI/test3/test3-ed.mp4",
    "test4": "D:/ProjectXIXI/test4/test4-ed.mp4",
}
# 原片 1fps 索引
ORIG_IDX = {
    "2mkv": IDX2,
    "test3": IDX_DIR / "test3-om__074e2dcc.idx",
    "test4": IDX_DIR / "test4-om__eb686e0c.idx",
}

# (pair, pid, 编辑段, 正确窗, 干扰窗, 说明)  —— v4 GT 修正版(2026-09-02 重跑, 仅 p26)
# v4: p26 真值=1768.2-1770.05(坐椅看书); 旧真值区 2809-2810(望远镜)=干扰。原探针窗口互换。
# p08(1108.15-1109.1 仍在 1106-1121 窗内)/t3r12 不受 GT 修正影响; t4r01 逻辑剔除。
CASES = [
    ("2mkv", "p26", (76.0, 78.0), (1766, 1813), (2786, 2822),
     "夜读(v4真值1768.2-1770.05) vs 旧真值区2809-2810望远镜(干扰)"),
]


def load_idx(idx: Path):
    feats = np.load(idx / "features.npy").astype(np.float32)
    times = np.load(idx / "times.npy")
    return feats, times


def make_dml_session():
    import onnxruntime as ort
    prov = [("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
    return ort.InferenceSession(str(MODEL_PATH), providers=prov)


def dml_embed(sess, video: str, t0: float, t1: float, fps: float = 8.0) -> tuple[np.ndarray, np.ndarray]:
    """抽 [t0,t1] 区间 @fps 帧 -> DML 嵌入, 返回 (feats[L2], times)。
    用 ffmpeg rawvideo 管道直读(bgr24, 固定 518x518), 避免 PNG 中间文件/cv2 解码瓶颈。
    帧数 clamp 到预期值, 逐帧预处理+嵌入(内存有界)。
    """
    W = H = 518
    n_expect = max(1, int((t1 - t0) * fps) + 1)
    proc = subprocess.run(
        [str(FFMPEG), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1-t0:.3f}",
         "-i", video, "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo",
         "-pix_fmt", "bgr24", "-frames:v", str(n_expect), "-"],
        capture_output=True)
    raw = proc.stdout
    if len(raw) == 0:
        return np.zeros((0, 384), np.float32), np.zeros((0,), np.float64)
    n = min(len(raw) // (H * W * 3), n_expect)
    if n <= 0:
        return np.zeros((0, 384), np.float32), np.zeros((0,), np.float64)
    buf = np.frombuffer(raw[:n * H * W * 3], dtype=np.uint8).reshape(n, H, W, 3)
    outs = []
    for i in range(n):
        inp = preprocess_np([buf[i]])  # 单帧, 内存有界
        o = sess.run(["embedding"], {"input": np.ascontiguousarray(inp)})[0]
        outs.append(o)
    feats = l2norm(np.concatenate(outs, axis=0))
    times = np.linspace(t0, t0 + n / fps, n)
    return feats, times


def embed_edit_seg(sess, video: str, e0: float, e1: float) -> np.ndarray:
    """编辑段查询 = 中心 ±0.3 三帧 CLS 均值(L2)。"""
    feats, _ = dml_embed(sess, video, max(0.0, e0), e1, fps=8.0)
    # 取编辑段中间帧
    if len(feats) == 0:
        return None
    mid = len(feats) // 2
    lo, hi = max(0, mid-1), min(len(feats), mid+2)
    q = feats[lo:hi].mean(axis=0)
    n = np.linalg.norm(q)
    return q / n if n > 1e-8 else q


def rank_metrics(query: np.ndarray, cand_feats: np.ndarray, cand_times: np.ndarray,
                 true_win, dist_win, margin_top=0.5):
    """候选池内: 正确窗 vs 干扰窗的判别。
    返回: correct_best_rank, correct_topN_hits, margin(correct_max_sim - dist_max_sim)。
    """
    sims = cand_feats @ query
    true_mask = np.array([(true_win[0] <= t <= true_win[1]) for t in cand_times])
    dist_mask = np.array([(dist_win[0] <= t <= dist_win[1]) for t in cand_times])
    order = np.argsort(-sims)
    ranks = np.empty(len(sims)); 
    for k, i in enumerate(order):
        ranks[i] = k + 1
    true_ranks = ranks[true_mask]
    dist_ranks = ranks[dist_mask]
    n_cand = len(sims)
    res = {
        "n_cand": n_cand,
        "n_true": int(true_mask.sum()), "n_dist": int(dist_mask.sum()),
        "correct_best_rank": int(true_ranks.min()) if true_ranks.size else None,
        "correct_top5_hits": int((true_ranks <= 5).sum()),
        "correct_top10_hits": int((true_ranks <= 10).sum()),
        "correct_max_sim": round(float(sims[true_mask].max()), 4) if true_mask.any() else None,
        "dist_max_sim": round(float(sims[dist_mask].max()), 4) if dist_mask.any() else None,
        "margin": round(float(sims[true_mask].max() - sims[dist_mask].max()), 4)
                  if (true_mask.any() and dist_mask.any()) else None,
    }
    return res


def main() -> int:
    import onnxruntime as ort
    t0 = time.time()
    sess = make_dml_session()
    print(f"providers: {sess.get_providers()}", flush=True)

    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "cases": []}

    for pair, pid, edit_span, true_win, dist_win, note in CASES:
        # 查询特征(编辑段)
        q = embed_edit_seg(sess, EDIT_VIDEO[pair], *edit_span)
        if q is None:
            print(f"[{pid}] 编辑段抽帧失败", flush=True)
            continue

        # 1fps 稀疏索引(现有 1fps 原片索引, 候选=正确窗∪干扰窗内帧)
        ofeats, otimes = load_idx(ORIG_IDX[pair])
        span = (min(true_win[0], dist_win[0]), max(true_win[1], dist_win[1]))
        m = (otimes >= span[0]) & (otimes <= span[1])
        if m.sum() == 0:
            print(f"[{pid}] 1fps 候选窗无帧", flush=True)
            continue
        sparse_feats, sparse_times = ofeats[m], otimes[m]
        sparse_res = rank_metrics(q, sparse_feats, sparse_times, true_win, dist_win)
        sparse_res["density"] = "1fps_sparse"

        # 8fps 密帧索引(候选窗内 8fps 抽帧嵌入)
        dfeats, dtimes = dml_embed(sess, ORIG_VIDEO[pair], span[0], span[1], fps=8.0)
        if len(dfeats) == 0:
            print(f"[{pid}] 8fps 抽帧失败", flush=True)
            continue
        dense_res = rank_metrics(q, dfeats, dtimes, true_win, dist_win)
        dense_res["density"] = "8fps_dense"

        improved = (
            dense_res["correct_best_rank"] is not None and sparse_res["correct_best_rank"] is not None
            and dense_res["correct_best_rank"] <= sparse_res["correct_best_rank"]
        )
        improved_top5 = (
            dense_res["correct_top5_hits"] is not None and sparse_res["correct_top5_hits"] is not None
            and dense_res["correct_top5_hits"] >= sparse_res["correct_top5_hits"]
        )
        improved_margin = (
            dense_res["margin"] is not None and sparse_res["margin"] is not None
            and dense_res["margin"] >= sparse_res["margin"]
        )

        entry = {
            "id": pid, "pair": pair, "note": note,
            "edit_span": list(edit_span), "true_win": list(true_win), "dist_win": list(dist_win),
            "sparse": sparse_res, "dense": dense_res,
            "verdict": {
                "dense_better_best_rank": improved,
                "dense_better_top5": improved_top5,
                "dense_better_margin": improved_margin,
            },
        }
        report["cases"].append(entry)
        print(f"[{pid}] 1fps: best_rank={sparse_res['correct_best_rank']}/{sparse_res['n_cand']} "
              f"top5={sparse_res['correct_top5_hits']} margin={sparse_res['margin']}", flush=True)
        print(f"[{pid}] 8fps: best_rank={dense_res['correct_best_rank']}/{dense_res['n_cand']} "
              f"top5={dense_res['correct_top5_hits']} margin={dense_res['margin']}", flush=True)
        print(f"    -> rank改善={improved} top5改善={improved_top5} margin改善={improved_margin}", flush=True)

    out = WORK / "semantic_signal_M4_results_v4.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())