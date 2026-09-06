"""Phase 24-2 · 局部 patch 级召回探针 M5 —— patch 特征作为独立召回通道(候选池构建者)。

问题(用户拍板 2026-09-01): E21/patch_rerank 都只在「CLS 已捞进池」的候选里做重排;
patch **从未参与候选池构建**(召回层)。本探针首次实测: patch 级检索能否把
失败族(p08/p08b/p26/t3r12/t4r01)的**正确实例捞进候选池**, 而 CLS 捞不到。

判据:
  - 正确窗在 CLS 全索引 best_rank / 是否进 CLS top-50/200 (CLS 召回基线)
  - patch 通道在「CLS top-200 ∪ 全索引均匀采样 ∪ 真值/干扰窗」混合池里,
    正确窗的 patch best_rank / top-N 命中 / 相对干扰 margin
  - 正确窗被 CLS top-200 漏掉、但 patch 池能捞进 top-N → patch 召回有信号

成本: 每案例候选池 ~480 帧, 优先 DML ONNX(双输出, ~18fps), 回退 CPU torch(1.4fps)。
零 runtime 改动。

输出: work/patch_recall_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_patch_recall.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
WORK = BENCH / "work"

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
WEIGHTS = BENCH / "work" / "dinov2_weights" / "dinov2_vits14_pretrain.pth"
PATCH_ONNX = BENCH / "work" / "_patch_onnx_tmp" / "dinov2_cls_patch.onnx"
IDX_DIR = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")


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
ORIG_IDX = {
    "2mkv": IDX_DIR / "2__4c6d4ab2.idx",
    "test3": IDX_DIR / "test3-om__074e2dcc.idx",
    "test4": IDX_DIR / "test4-om__eb686e0c.idx",
}

# (pair, pid, 编辑中心, 正确窗, 干扰窗|None, 说明)
CASES = [
    ("2mkv", "p08", 13.5, (1108, 1110), (1048, 1050), "兄弟机位: 瞭望塔(真值) vs 士兵特写(兄弟)"),
    ("2mkv", "p08b", 13.9, (1048, 1050), (1108, 1110), "兄弟机位: 士兵特写(真值) vs 瞭望塔(兄弟)"),
    ("2mkv", "p26", 77.0, (2808, 2811), (1766, 1770), "夜读(真值) vs 夜阳台(干扰, CLS 高 sim 误配)"),
    ("2mkv", "p01", 0.8, (2412, 2446), None, "金属球准备(sanity 易例, 防 patch 回退)"),
    ("test3", "t3r12", 64.75, (454, 480), (481, 488), "精灵王重复镜头(真值 454-480) vs 另一实例(干扰)"),
    ("test4", "t4r01", 1.8, (3329, 3355), (3355, 3398), "同质滑梯(真值) vs 紧邻同质干扰"),
]

TOP_CLS = 200        # CLS 召回基线阈值
SAMPLE_BUDGET = 250  # 全索引均匀采样帧数预算(混合池覆盖全局)
PATCH_TOPK_AGG = 100  # E21 V3 指标: 每查询 patch 最大余弦的 top-K 均值


def load_idx(idx: Path):
    feats = np.load(idx / "features.npy").astype(np.float32)
    times = np.load(idx / "times.npy").astype(np.float64)
    return feats, times


def l2(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


def patch_score(q_patches: np.ndarray, cand_patch: np.ndarray) -> float:
    m = (q_patches @ cand_patch.T).max(axis=1)
    k = min(PATCH_TOPK_AGG, len(m))
    return float(np.sort(m)[-k:].mean())


class Embedder:
    """patch 特征提取: 优先 DML ONNX(15.96fps), 缺资产回退 CPU torch(1.4fps)。"""

    def __init__(self):
        import cv2  # noqa
        from media.ffmpeg import FFmpegIO
        self.ff = FFmpegIO(FFMPEG, FFPROBE)
        self.dml = None
        self.torch = None
        self._use_dml = False
        try:
            import onnxruntime as ort
            if PATCH_ONNX.exists():
                self.dml = ort.InferenceSession(
                    str(PATCH_ONNX),
                    providers=[("DmlExecutionProvider", {"device_id": 0}),
                               "CPUExecutionProvider"])
                if "DmlExecutionProvider" in self.dml.get_providers():
                    self._use_dml = True
                    self._ort = ort
        except Exception as exc:
            print(f"[embedder] DML unavailable ({exc}); fallback CPU torch", flush=True)
        if not self._use_dml:
            import torch
            from device.dinov2_model import DinoV2Small, _imagenet_preprocess
            self.torch = torch
            self._preprocess = _imagenet_preprocess
            m = DinoV2Small()
            m.load_state_dict(torch.load(str(WEIGHTS), map_location="cpu",
                                         weights_only=True), strict=False)
            m.eval()
            self.model = m

    def embed(self, video: str, t: float):
        """grab_frame -> (cls[384] L2, patches[1369,384] L2)。"""
        import cv2  # noqa
        f = self.ff.grab_frame(video, t)
        if self._use_dml:
            inp = _preprocess_np_dml([f])
            oc, op = self.dml.run(["embedding", "patches"],
                                  {"input": np.ascontiguousarray(inp)})
            cls = oc[0].astype(np.float32)
            p = op[0].astype(np.float32)
            return l2(cls[None, :])[0], l2(p)
        x = self._preprocess(f)
        with self.torch.no_grad():
            cls, patches = self.model.forward_features(x)
        cls = cls[0].numpy().astype(np.float32)
        patches = patches[0].numpy().astype(np.float32)
        return l2(cls[None, :])[0], l2(patches)


def _preprocess_np_dml(frames):
    from device.dinov2_model import _imagenet_preprocess
    return np.stack([_imagenet_preprocess(f).numpy()[0] for f in frames]).astype(np.float32)


def l2(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


def main() -> int:
    t0 = time.time()
    emb = Embedder()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "cases": []}

    for pair, pid, e_mid, true_win, dist_win, note in CASES:
        print(f"\n===== {pid} ({pair}) {note}", flush=True)
        feats, times = load_idx(ORIG_IDX[pair])
        n_total = len(times)

        # ---- 查询: 编辑段 3 帧(中心±0.4s) patch 拼接 ----
        q_cls_mean, q_patches = None, None
        for j in range(3):
            c, p = emb.embed(EDIT_VIDEO[pair], e_mid - 0.4 + 0.4 * j)
            q_cls_mean = c if q_cls_mean is None else q_cls_mean + c
            q_patches = p if q_patches is None else np.concatenate([q_patches, p], axis=0)
        q_cls_mean = l2(q_cls_mean[None, :])[0]
        q_patches = q_patches.astype(np.float32)

        # ---- CLS 全索引基线(免费, 用现有 features.npy) ----
        sims = feats @ q_cls_mean
        order = np.argsort(-sims)
        true_mask = np.array([(true_win[0] <= t <= true_win[1]) for t in times])
        true_idx = set(int(i) for i in np.where(true_mask)[0])
        ranks = np.empty(n_total, np.int64)
        for k, i in enumerate(order):
            ranks[i] = k + 1
        true_best_cls_rank_full = int(ranks[list(true_idx)].min()) if true_idx else None
        true_in_cls_top50 = true_best_cls_rank_full is not None and true_best_cls_rank_full <= 50
        true_in_cls_top200 = true_best_cls_rank_full is not None and true_best_cls_rank_full <= TOP_CLS

        # ---- 混合池: CLS top-200 ∪ 均匀采样 ∪ 真值/干扰窗 ----
        pool = set(int(i) for i in order[:TOP_CLS])
        stride = max(1, n_total // SAMPLE_BUDGET)
        pool |= set(range(0, n_total, stride))
        pool |= true_idx
        if dist_win is not None:
            pool |= set(int(i) for i in np.where(
                (times >= dist_win[0]) & (times <= dist_win[1]))[0])
        pool = sorted(pool)
        pool_times = times[pool]
        pool_cls_sim = sims[pool]

        # ---- patch 逐帧打分(内存 O(1)) ----
        patch_scores = np.zeros(len(pool), np.float32)
        for k, idx in enumerate(pool):
            _, p = emb.embed(ORIG_VIDEO[pair], float(times[idx]))
            patch_scores[k] = patch_score(q_patches, p)
            if k % 50 == 0:
                print(f"  {pid} pool {k}/{len(pool)} ({time.time()-t0:.0f}s)", flush=True)

        # ---- 正确/干扰在混合池内的 patch 名次与 top-N 命中 ----
        pt = pool_times
        p_true_mask = np.array([(true_win[0] <= t <= true_win[1]) for t in pt])
        p_dist_mask = (np.array([(dist_win[0] <= t <= dist_win[1]) for t in pt])
                       if dist_win is not None else np.zeros(len(pt), bool))
        po = np.argsort(-patch_scores)
        pranks = np.empty(len(pool), np.int64)
        for k, i in enumerate(po):
            pranks[i] = k + 1
        true_patch_ranks = pranks[p_true_mask]
        dist_patch_ranks = pranks[p_dist_mask] if dist_win is not None else np.array([], np.int64)
        true_best_patch_rank = int(true_patch_ranks.min()) if true_patch_ranks.size else None
        true_patch_top5 = int((true_patch_ranks <= 5).sum()) if true_patch_ranks.size else 0
        true_patch_top10 = int((true_patch_ranks <= 10).sum()) if true_patch_ranks.size else 0
        true_patch_max_sim = float(patch_scores[p_true_mask].max()) if p_true_mask.any() else None
        dist_patch_max_sim = (float(patch_scores[p_dist_mask].max())
                              if p_dist_mask.any() else None)
        patch_margin = (round(true_patch_max_sim - dist_patch_max_sim, 4)
                        if true_patch_max_sim is not None and dist_patch_max_sim is not None
                        else None)
        # 同池 CLS 名次(对照)
        co = np.argsort(-pool_cls_sim)
        cranks = np.empty(len(pool), np.int64)
        for k, i in enumerate(co):
            cranks[i] = k + 1
        true_cls_pool_rank = int(cranks[p_true_mask].min()) if p_true_mask.any() else None

        verdict = "TBD"
        if true_best_cls_rank_full is not None and true_best_cls_rank_full > TOP_CLS:
            # CLS 漏掉正确窗 → 看 patch 能否捞进
            if true_best_patch_rank is not None and true_best_patch_rank <= 10:
                verdict = "PATCH_RECALL_SIGNAL (CLS 漏, patch 捞进 top-10)"
            else:
                verdict = "NO_SIGNAL (CLS 漏, patch 也未捞进 top-10)"
        else:
            # CLS 已捞进 → 重排问题; patch 若把名次拉高同样有意义
            if true_best_patch_rank is not None and true_best_cls_rank_full is not None:
                if true_best_patch_rank < true_best_cls_rank_full:
                    verdict = f"PATCH_RERANK_IMPROVES (CLS {true_best_cls_rank_full} -> patch {true_best_patch_rank})"
                else:
                    verdict = "NO_RERANK_GAIN"

        entry = {
            "id": pid, "pair": pair, "note": note,
            "edit_mid": e_mid, "true_win": list(true_win), "dist_win": (list(dist_win) if dist_win else None),
            "n_total": n_total,
            "cls_baseline": {
                "true_best_rank_full": true_best_cls_rank_full,
                "true_in_cls_top50": true_in_cls_top50,
                "true_in_cls_top200": true_in_cls_top200,
            },
            "patch_channel": {
                "pool_size": len(pool),
                "pool_covered": {
                    "true_frames": int(p_true_mask.sum()),
                    "dist_frames": int(p_dist_mask.sum()),
                    "cls_top200_frames": TOP_CLS,
                    "other_sampled_frames": int(len(pool) - int(p_true_mask.sum())
                                               - (int(p_dist_mask.sum()) if dist_win else 0)),
                },
                "true_best_patch_rank": true_best_patch_rank,
                "true_patch_top5_hits": true_patch_top5,
                "true_patch_top10_hits": true_patch_top10,
                "true_patch_max_sim": true_patch_max_sim,
                "dist_patch_max_sim": dist_patch_max_sim,
                "patch_margin": patch_margin,
                "true_cls_pool_rank": true_cls_pool_rank,
            },
            "verdict": verdict,
        }
        report["cases"].append(entry)
        (WORK / "patch_recall_results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{pid}] CLS full best_rank={true_best_cls_rank_full}/{n_total} "
              f"in_top50={true_in_cls_top50} in_top200={true_in_cls_top200}", flush=True)
        print(f"[{pid}] patch pool {len(pool)}: true_best_rank={true_best_patch_rank} "
              f"top5={true_patch_top5} top10={true_patch_top10} margin={patch_margin} "
              f"cls_pool_rank={true_cls_pool_rank}", flush=True)
        print(f"    -> {verdict}", flush=True)

    out = WORK / "patch_recall_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s", flush=True)
    return 0



if __name__ == "__main__":
    sys.exit(main())