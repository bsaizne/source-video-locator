"""Phase 24-2 · 局部特征召回探针 M7 —— ALIKED 局部空间结构证据能否区分失败族。

目标(承接 FAILURE_TAXONOMY.md): 用现代局部特征(ALIKED n32, kornia)验证
「局部空间结构证据」能否把失败族(p08/p38 兄弟机位、p26 夜读、t3r12 重复镜头、t4r01 同质)
的正确实例捞进候选池 / 排到干扰之前——对照 M6 的 CLS/patch 基线。

方法(与 M5/M6 同口径):
  - 查询 = 编辑段 GT 窗中点 ±0.4s 三帧 → ALIKED(keypoints+128D descriptors+scores)
  - 候选池 = 均匀采样(~250) ∪ 真值/干扰窗 ∪ 稀疏补足 ~450 帧(ALIKED 无 CLS, 池不依赖 CLS top-200)
  - 帧间相似度 = 互近邻(mutual-NN)匹配数(score_thr 0.3 过滤低分关键点); 查询多帧拼接后一次匹配
  - 输出: 真值窗 best_rank / top-N 命中 / margin vs 干扰

零 runtime 改动。成本: 6 案例 × ~450 帧 CPU ALIKED(~0.17s/帧) ≈ 10-15min(后台)。

输出: work/local_feature_results.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

BENCH = Path(__file__).resolve().parents[2]
WORK = BENCH / "work"
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
WEIGHTS = WORK / "local_feature_weights" / "aliked-n32.pth"
IDX_DIR = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")

ORIG_VIDEO = {"2mkv": "D:/video/2.mkv", "test3": "D:/ProjectXIXI/test3/test3-om.mp4",
              "test4": "D:/ProjectXIXI/test4/test4-om.mkv"}
EDIT_VIDEO = {"2mkv": "D:/video/1.mp4", "test3": "D:/ProjectXIXI/test3/test3-ed.mp4",
              "test4": "D:/ProjectXIXI/test4/test4-ed.mp4"}
ORIG_IDX = {"2mkv": IDX_DIR / "2__4c6d4ab2.idx",
            "test3": IDX_DIR / "test3-om__074e2dcc.idx",
            "test4": IDX_DIR / "test4-om__eb686e0c.idx"}

# (pair, pid, 编辑中心, 正确窗, 干扰窗|None, 说明)
CASES = [
    ("2mkv", "p08", 13.5, (1108, 1110), (1048, 1050), "兄弟机位: 瞭望塔(真值) vs 士兵特写(兄弟)"),
    ("2mkv", "p38", 13.25, (1048, 1050), (1108, 1110), "兄弟机位: 士兵特写(真值, M6 CLS340/patch225) vs 瞭望塔"),
    ("2mkv", "p26", 77.0, (2808, 2811), (1766, 1770), "夜读(真值, M6 CLS22/patch24) vs 夜阳台(干扰)"),
    ("2mkv", "p01", 0.8, (2412, 2446), None, "金属球(sanity 易例)"),
    ("test3", "t3r12", 64.75, (454, 480), (481, 488), "精灵王重复镜头(真值) vs 另一实例(干扰)"),
    ("test4", "t4r01", 1.8, (3329, 3355), (3355, 3398), "同质滑梯(真值) vs 紧邻同质干扰"),
]

SAMPLE_BUDGET = 250
SCORE_THR = 0.3
IMG_SIZE = 512


def load_idx(idx: Path):
    feats = np.load(idx / "features.npy").astype(np.float32)
    times = np.load(idx / "times.npy").astype(np.float64)
    return feats, times


class AlikedExtractor:
    def __init__(self):
        from kornia.feature import ALIKED
        self.model = ALIKED(model_name="aliked-n32")
        sd = torch.load(str(WEIGHTS), map_location="cpu", weights_only=True)
        self.model.load_state_dict(sd, strict=False)
        self.model.eval()

    def grab(self, video: str, t: float):
        out = WORK / "_lf_grab.png"
        subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{t:.3f}",
                        "-i", video, "-vf", f"scale={IMG_SIZE}:-2", "-frames:v", "1",
                        str(out)], check=True, capture_output=True)
        return cv2.imread(str(out))

    @torch.no_grad()
    def feats(self, img):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        x = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        out = self.model(x)[0]
        return out.keypoints.numpy(), out.descriptors.numpy(), out.keypoint_scores.numpy()


def mutual_nn(dq, dr, sq, sr) -> int:
    a = dq[sq >= SCORE_THR]
    b = dr[sr >= SCORE_THR]
    if len(a) == 0 or len(b) == 0:
        return 0
    a = a / np.maximum(np.linalg.norm(a, axis=1, keepdims=True), 1e-8)
    b = b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-8)
    sim = a @ b.T
    nn_r = sim.argmax(1)
    nn_q = sim.argmax(0)
    return int(sum(1 for i in range(len(nn_r)) if nn_q[nn_r[i]] == i))


def main() -> int:
    t0 = time.time()
    ex = AlikedExtractor()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "cases": []}

    for pair, pid, e_mid, true_win, dist_win, note in CASES:
        print()
        print(f"===== {pid} ({pair}) {note}", flush=True)
        _, times = load_idx(ORIG_IDX[pair])
        n_total = len(times)

        q_desc, q_score = [], []
        for j in range(3):
            img = ex.grab(EDIT_VIDEO[pair], e_mid - 0.4 + 0.4 * j)
            if img is None:
                continue
            _, d, s = ex.feats(img)
            q_desc.append(d)
            q_score.append(s)
        if not q_desc:
            print(f"[{pid}] 编辑抽帧失败", flush=True)
            continue
        q_desc = np.concatenate(q_desc)
        q_score = np.concatenate(q_score)

        stride = max(1, n_total // SAMPLE_BUDGET)
        pool = set(range(0, n_total, stride))
        pool |= set(int(i) for i in np.where((times >= true_win[0]) & (times <= true_win[1]))[0])
        if dist_win is not None:
            pool |= set(int(i) for i in np.where((times >= dist_win[0]) & (times <= dist_win[1]))[0])
        pool = sorted(pool)
        pool_times = times[pool]

        scores = np.zeros(len(pool), np.float32)
        for k, idx in enumerate(pool):
            img = ex.grab(ORIG_VIDEO[pair], float(times[idx]))
            if img is None:
                continue
            _, d, s = ex.feats(img)
            scores[k] = mutual_nn(q_desc, d, q_score, s)
            if k % 60 == 0:
                print(f"  {pid} pool {k}/{len(pool)} ({time.time()-t0:.0f}s)", flush=True)

        pt = pool_times
        tm = np.array([(true_win[0] <= t <= true_win[1]) for t in pt])
        dm = (np.array([(dist_win[0] <= t <= dist_win[1]) for t in pt]) if dist_win is not None
              else np.zeros(len(pt), bool))
        order = np.argsort(-scores)
        ranks = np.empty(len(pool), np.int64)
        for k, i in enumerate(order):
            ranks[i] = k + 1
        tr = ranks[tm]
        dr = ranks[dm] if dm.any() else np.array([], np.int64)
        true_best = int(tr.min()) if tr.size else None
        true_top5 = int((tr <= 5).sum()) if tr.size else 0
        true_top10 = int((tr <= 10).sum()) if tr.size else 0
        ts = float(scores[tm].max()) if tm.any() else None
        ds = float(scores[dm].max()) if dm.any() else None
        margin = round(ts - ds, 4) if ts is not None and ds is not None else None

        entry = {"id": pid, "pair": pair, "note": note,
                 "edit_mid": e_mid, "true_win": list(true_win),
                 "dist_win": (list(dist_win) if dist_win else None),
                 "pool_size": len(pool),
                 "true_frames_in_pool": int(tm.sum()),
                 "true_best_rank": true_best,
                 "true_top5_hits": true_top5, "true_top10_hits": true_top10,
                 "true_max_sim": ts, "dist_max_sim": ds, "margin": margin,
                 "ref_m6": "p38 CLS340/patch225; p26 CLS22/patch24; t4r01 CLS1; t3r12 CLS1"}
        report["cases"].append(entry)
        (WORK / "local_feature_results.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{pid}] ALIKED pool {len(pool)}: true_best={true_best} top5={true_top5} "
              f"top10={true_top10} margin={margin}", flush=True)

    out = WORK / "local_feature_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"saved {out}  total {time.time()-t0:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
