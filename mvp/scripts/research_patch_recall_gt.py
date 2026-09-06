"""Phase 24-2 · GT 级 patch 召回覆盖探针 M6 —— 41 条 GT 正例的 CLS/patch 全索引召回统计。

决策探针(用户拍板):patch 召回 runtime 化值不值——统计到底有几条 GT 是
「CLS 全索引 rank>20(runtime 候选池外)但 patch 能排进混合池 top-20」的。

方法(与 M5 同口径):
  - 查询 = 编辑段中点 ±0.4s 三帧 → CLS 均值 + patch 拼接
  - CLS 全索引 rank: 现有 features.npy @ q_cls_mean, 真值窗内帧的 best_rank(免费)
  - patch 混合池 = CLS top-200 ∪ 全索引均匀采样(~250) ∪ 真值窗帧, 逐帧 V3 patch 打分
  - 判定: CLS rank>20 且 patch 混合池 best_rank<=20 → PATCH_RECALL_RESCUE
    (patch 第二检索通道能把 runtime 漏掉的正确实例捞进池)

成本: 41 正例 × ~450 帧混合池, DML 双输出 ONNX ~18fps, ≈ 17 min(后台)。零 runtime 改动。

输出: work/patch_recall_gt_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_patch_recall_gt.py
"""
import argparse
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
GT = BENCH / "datasets" / "real" / "ground_truth_v3.json"
OUT_JSON = BENCH / "work" / "patch_recall_gt_results.json"
IDX_DIR = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"
ORIG = "D:/video/2.mkv"
EDIT = "D:/video/1.mp4"

TOP_CLS = 200
SAMPLE_BUDGET = 250
PATCH_TOPK_AGG = 100
CLS_POOL_CUT = 20   # runtime 检索 top-20 池线


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
    """DML 双输出 ONNX(CLS+patch) 优先; 缺失回退 CPU torch。"""

    def __init__(self):
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
        from device.dinov2_model import _imagenet_preprocess
        f = self.ff.grab_frame(video, t)
        if self._use_dml:
            inp = np.stack([_imagenet_preprocess(f).numpy()[0]]).astype(np.float32)
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gt", default=str(GT))
    ap.add_argument("--out", default=str(OUT_JSON))
    args = ap.parse_args()
    gt_path = Path(args.gt)
    out_path = Path(args.out)
    t0 = time.time()

    # ---- resume: 若输出文件已存在, 跳过「已完成且窗口未变」的 case ----
    # 窗口校验: 旧 GT 窗口 != 当前 v4 窗口 → 需重算(如 A 段精修的 p05/p08/p20/p28)
    done_map = {}
    if out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
            done_map = {cc["id"]: list(cc.get("original") or []) for cc in prev.get("cases", [])}
            if done_map:
                print(f"[resume] 已有 {len(done_map)} 个 case 记录", flush=True)
        except Exception as exc:
            print(f"[resume] 读取旧输出失败({exc}), 全量重跑", flush=True)
    emb = Embedder()
    feats, times = load_idx(IDX2)
    n_total = len(times)
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    positives = [p for p in gt["positives"]]
    print(f"GT positives: {len(positives)} | index {n_total} 帧 | "
          f"embeddor={'DML' if emb._use_dml else 'CPU torch'}", flush=True)

    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "cls_pool_cut": CLS_POOL_CUT, "n_positives": len(positives),
              "cases": [], "summary": {}}
    # resume 打底: 把已完成的旧 case 预填进 report(跳过的不重写, 但保留在输出)
    if done_map:
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
            report["cases"] = [cc for cc in prev.get("cases", []) if cc["id"] in done_map]
        except Exception:
            pass

    for p in positives:
        pid = p["id"]
        (e0, e1) = p["edited"]
        (o0, o1) = p["original"]
        e_mid = (e0 + e1) / 2.0
        if pid in done_map and done_map[pid] == [o0, o1]:
            print(f"[skip] {pid} (resume, 窗口未变)", flush=True)
            continue
        if pid in done_map:
            print(f"[recompute] {pid} (窗口变化 {done_map[pid]} -> {[o0, o1]})", flush=True)

        # 查询: 编辑段中点 ±0.4s 三帧
        q_cls_mean, q_patches = None, None
        for j in range(3):
            c, pp = emb.embed(EDIT, e_mid - 0.4 + 0.4 * j)
            q_cls_mean = c if q_cls_mean is None else q_cls_mean + c
            q_patches = pp if q_patches is None else np.concatenate([q_patches, pp], axis=0)
        q_cls_mean = l2(q_cls_mean[None, :])[0]
        q_patches = q_patches.astype(np.float32)

        # CLS 全索引 rank(免费)
        sims = feats @ q_cls_mean
        order = np.argsort(-sims)
        true_mask = np.array([(o0 <= t <= o1) for t in times])
        true_idx = set(int(i) for i in np.where(true_mask)[0])
        ranks = np.empty(n_total, np.int64)
        for k, i in enumerate(order):
            ranks[i] = k + 1
        cls_best = int(ranks[list(true_idx)].min()) if true_idx else None
        cls_in_pool = cls_best is not None and cls_best <= CLS_POOL_CUT

        # 混合池
        pool = set(int(i) for i in order[:TOP_CLS])
        stride = max(1, n_total // SAMPLE_BUDGET)
        pool |= set(range(0, n_total, stride))
        pool |= true_idx
        pool = sorted(pool)
        pool_times = times[pool]

        patch_scores = np.zeros(len(pool), np.float32)
        for k, idx in enumerate(pool):
            _, pp = emb.embed(ORIG, float(times[idx]))
            patch_scores[k] = patch_score(q_patches, pp)
            if k % 60 == 0:
                print(f"  {pid} pool {k}/{len(pool)} ({time.time()-t0:.0f}s)", flush=True)

        pt = pool_times
        p_true_mask = np.array([(o0 <= t <= o1) for t in pt])
        po = np.argsort(-patch_scores)
        pranks = np.empty(len(pool), np.int64)
        for k, i in enumerate(po):
            pranks[i] = k + 1
        true_pr = pranks[p_true_mask]
        patch_best = int(true_pr.min()) if true_pr.size else None
        patch_in_pool = patch_best is not None and patch_best <= CLS_POOL_CUT
        rescue = (not cls_in_pool) and patch_in_pool

        entry = {
            "id": pid, "tier": p["tier"], "edited": list(p["edited"]),
            "original": list(p["original"]),
            "cls_best_rank_full": cls_best,
            "cls_in_top20": cls_in_pool,
            "patch_pool_size": len(pool),
            "patch_best_rank": patch_best,
            "patch_in_top20": patch_in_pool,
            "verdict": ("RESCUE (CLS 池外, patch 捞进 top-20)" if rescue else
                        ("IN_POOL (CLS 已在 top-20)" if cls_in_pool else
                         "NOT_RESCUED (CLS 池外, patch 也未进 top-20)")),
        }
        report["cases"].append(entry)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{pid}] CLS best={cls_best} in_pool={cls_in_pool} | "
              f"patch best={patch_best} in_pool={patch_in_pool} | {entry['verdict']}", flush=True)

    # 汇总(基于已完成的 report, 兼容 resume)
    n_rescue = sum(1 for c in report["cases"] if c["verdict"].startswith("RESCUE"))
    n_outside = sum(1 for c in report["cases"] if not c["cls_in_top20"])
    n_not = sum(1 for c in report["cases"] if c["verdict"] == "NOT_RESCUED (CLS 池外, patch 也未进 top-20)")
    report["summary"] = {
        "n_rescue": n_rescue,
        "n_cls_outside_pool": n_outside,
        "n_not_rescued": n_not,
        "n_cls_already_in_pool": len(report["cases"]) - n_outside,
        "resumed_skipped": len(done_map),
    }
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 汇总 ===", flush=True)
    print("RESCUE(CLS 池外→patch 捞进): %d/%d | CLS 池外总数: %d | 未救回: %d | CLS 已在池内: %d"
          % (n_rescue, len(positives), n_outside, n_not, len(positives) - n_outside), flush=True)
    print(f"saved {out_path}  total {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())