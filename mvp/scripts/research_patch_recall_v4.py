"""Phase 24-2 · M5 重跑(修正 GT,v4/verified)—— patch 特征作独立召回通道。

起因: FINDINGS_GT_CONTAMINATION_AUDIT.md —— 原 M5 6 个案例中
  * p08b「真值 1048-1050」= p38 旧错误 GT 区(已作废; 正确 = p08 的 1108.15-1109.1),
  * p26「真值 2808-2811」= GT 标错(正确 1768.2-1770.05),
  * t3r12「真值 454-480」= 用户 09-02 人工定位修正为 466-478,
  * t4r01 属 test4 数据无效(两部不同电影) → 剔除,
  * p01 原「宽窗 2412-2446」改为 v4 精确窗。
本脚本用修正 GT 重跑同一协议(候选池/打分/判据与原脚本逐条一致), 便于与原存档对照。

判据(与原脚本一致):
  - CLS 全索引 true_best_rank / 是否进 top-50/200(CLS 召回基线);
  - patch 在「CLS top-200 ∪ 全索引均匀采样 ∪ 真值窗 ∪ 干扰窗」混合池里的 best_rank / top-5/10 命中 / margin。

产物: work/patch_recall_v4_results.json    运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_patch_recall_v4.py
"""
from __future__ import annotations

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

ORIG_VIDEO = {"2mkv": "D:/video/2.mkv", "test3": "D:/ProjectXIXI/test3/test3-om.mp4"}
EDIT_VIDEO = {"2mkv": "D:/video/1.mp4", "test3": "D:/ProjectXIXI/test3/test3-ed.mp4"}
ORIG_IDX = {"2mkv": IDX_DIR / "2__4c6d4ab2.idx", "test3": IDX_DIR / "test3-om__074e2dcc.idx"}

# (pair, pid, 编辑中心, v4/verified 正确窗, 干扰窗|None, 说明)
CASES = [
    ("2mkv", "p08", 13.5, (1108.15, 1109.1), (1048.0, 1050.0),
     "兄弟机位: 瞭望塔(真值) vs 士兵特写(兄弟) — 与原口径同"),
    ("2mkv", "p08b", 13.9, (1108.15, 1109.1), (1048.0, 1050.0),
     "同一编辑段另一点; v3 把 1048-1050 当真值(=p38 旧错误 GT) 已作废"),
    ("2mkv", "p26", 77.0, (1768.2, 1770.05), (1237.0, 1264.0),
     "夜读(修正真值) vs 夜阳台干扰区(CLS top-40 聚区); v3 原窗 2808-2811 系标错"),
    ("2mkv", "p01", 0.8, (2417.5, 2418.1), None,
     "金属球准备(sanity 易例, 防 patch 回退); v3 原窗 2412-2446 为宽窗"),
    ("test3", "t3r12", 64.75, (466.0, 478.0), (481.0, 488.0),
     "精灵王重复镜头(用户 09-02 人工定位 466-478) vs 另一实例(干扰)"),
]

TOP_CLS = 200
SAMPLE_BUDGET = 250
PATCH_TOPK_AGG = 100


def load_idx(idx: Path):
    return (np.load(idx / "features.npy").astype(np.float32),
            np.load(idx / "times.npy").astype(np.float64))


def l2(x: np.ndarray) -> np.ndarray:
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-8)


def patch_score(q_patches: np.ndarray, cand_patch: np.ndarray) -> float:
    m = (q_patches @ cand_patch.T).max(axis=1)
    k = min(PATCH_TOPK_AGG, len(m))
    return float(np.sort(m)[-k:].mean())


def _preprocess_np_dml(frames):
    from device.dinov2_model import _imagenet_preprocess
    return np.stack([_imagenet_preprocess(f).numpy()[0] for f in frames]).astype(np.float32)


class Embedder:
    """patch 特征提取: 优先 DML ONNX(研究侧双输出资产), 否则回退 CPU torch。"""

    def __init__(self):
        from media.ffmpeg import FFmpegIO
        self.ff = FFmpegIO(FFMPEG, FFPROBE)
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
                    print("[embedder] DML ONNX (research asset) active", flush=True)
        except Exception as exc:
            print("[embedder] DML unavailable (%s); fallback CPU torch" % exc, flush=True)
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
        f = self.ff.grab_frame(video, t)
        if self._use_dml:
            inp = _preprocess_np_dml([f])
            oc, op = self.dml.run(["embedding", "patches"],
                                  {"input": np.ascontiguousarray(inp)})
            return (l2(oc[0].astype(np.float32)[None, :])[0],
                    l2(op[0].astype(np.float32)))
        x = self._preprocess(f)
        with self.torch.no_grad():
            cls, patches = self.model.forward_features(x)
        return (l2(cls[0].numpy().astype(np.float32)[None, :])[0],
                l2(patches[0].numpy().astype(np.float32)))


def main() -> int:
    t0 = time.time()
    emb = Embedder()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "gt": "ground_truth_v4.json + ground_truth_test3.json (verified)",
              "note": "M5 协议逐条不变, 仅换修正 GT 窗口; t4r01 剔除(test4 数据无效)",
              "cases": []}

    for pair, pid, e_mid, true_win, dist_win, note in CASES:
        print("\n===== %s (%s) %s" % (pid, pair, note), flush=True)
        feats, times = load_idx(ORIG_IDX[pair])
        n_total = len(times)

        q_cls_mean, q_patches = None, None
        for j in range(3):
            c, p = emb.embed(EDIT_VIDEO[pair], e_mid - 0.4 + 0.4 * j)
            q_cls_mean = c if q_cls_mean is None else q_cls_mean + c
            q_patches = p if q_patches is None else np.concatenate([q_patches, p], axis=0)
        q_cls_mean = l2(q_cls_mean[None, :])[0]
        q_patches = q_patches.astype(np.float32)

        sims = feats @ q_cls_mean
        order = np.argsort(-sims)
        true_mask = np.array([(true_win[0] <= t <= true_win[1]) for t in times])
        true_idx = set(int(i) for i in np.where(true_mask)[0])
        ranks = np.empty(n_total, np.int64)
        for k, i in enumerate(order):
            ranks[i] = k + 1
        best_cls = int(ranks[list(true_idx)].min()) if true_idx else None
        in_top50 = best_cls is not None and best_cls <= 50
        in_top200 = best_cls is not None and best_cls <= TOP_CLS

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

        patch_scores = np.zeros(len(pool), np.float32)
        for k, idx in enumerate(pool):
            _, p = emb.embed(ORIG_VIDEO[pair], float(times[idx]))
            patch_scores[k] = patch_score(q_patches, p)
            if k % 100 == 0:
                print("  %s pool %d/%d (%.0fs)" % (pid, k, len(pool), time.time() - t0),
                      flush=True)

        pt = pool_times
        p_true_mask = np.array([(true_win[0] <= t <= true_win[1]) for t in pt])
        p_dist_mask = (np.array([(dist_win[0] <= t <= dist_win[1]) for t in pt])
                       if dist_win is not None else np.zeros(len(pt), bool))
        po = np.argsort(-patch_scores)
        pranks = np.empty(len(pool), np.int64)
        for k, i in enumerate(po):
            pranks[i] = k + 1
        true_pranks = pranks[p_true_mask]
        dist_pranks = pranks[p_dist_mask] if dist_win is not None else np.array([], np.int64)
        best_patch = int(true_pranks.min()) if true_pranks.size else None
        top5 = int((true_pranks <= 5).sum()) if true_pranks.size else 0
        top10 = int((true_pranks <= 10).sum()) if true_pranks.size else 0
        true_max = float(patch_scores[p_true_mask].max()) if p_true_mask.any() else None
        dist_max = float(patch_scores[p_dist_mask].max()) if p_dist_mask.any() else None
        margin = (round(true_max - dist_max, 4)
                  if true_max is not None and dist_max is not None else None)
        co = np.argsort(-pool_cls_sim)
        cranks = np.empty(len(pool), np.int64)
        for k, i in enumerate(co):
            cranks[i] = k + 1
        cls_pool_rank = int(cranks[p_true_mask].min()) if p_true_mask.any() else None

        if best_cls is not None and best_cls > TOP_CLS:
            verdict = ("PATCH_RECALL_SIGNAL (CLS 漏, patch 捞进 top-10)"
                       if best_patch is not None and best_patch <= 10
                       else "NO_SIGNAL (CLS 漏, patch 也未捞进 top-10)")
        elif best_patch is not None and best_cls is not None:
            verdict = ("PATCH_RERANK_IMPROVES (CLS %d -> patch %d)" % (best_cls, best_patch)
                       if best_patch < best_cls else "NO_RERANK_GAIN")
        else:
            verdict = "TBD"

        entry = {
            "id": pid, "pair": pair, "note": note, "edit_mid": e_mid,
            "true_win": list(true_win), "dist_win": list(dist_win) if dist_win else None,
            "n_total": n_total,
            "cls_baseline": {"true_best_rank_full": best_cls,
                             "true_in_cls_top50": in_top50,
                             "true_in_cls_top200": in_top200},
            "patch_channel": {
                "pool_size": len(pool),
                "pool_covered": {"true_frames": int(p_true_mask.sum()),
                                 "dist_frames": int(p_dist_mask.sum())},
                "true_best_patch_rank": best_patch,
                "true_patch_top5_hits": top5, "true_patch_top10_hits": top10,
                "true_patch_max_sim": true_max, "dist_patch_max_sim": dist_max,
                "patch_margin": margin, "true_cls_pool_rank": cls_pool_rank},
            "verdict": verdict,
        }
        report["cases"].append(entry)
        (WORK / "patch_recall_v4_results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[%s] CLS full best_rank=%s/%d top50=%s top200=%s" %
              (pid, best_cls, n_total, in_top50, in_top200), flush=True)
        print("[%s] patch pool %d: best_rank=%s top5=%d top10=%d margin=%s cls_pool_rank=%s"
              % (pid, len(pool), best_patch, top5, top10, margin, cls_pool_rank), flush=True)
        print("    -> %s" % verdict, flush=True)

    report["elapsed_s"] = round(time.time() - t0, 1)
    out = WORK / "patch_recall_v4_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved %s  total %.0fs" % (out, report["elapsed_s"]), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
