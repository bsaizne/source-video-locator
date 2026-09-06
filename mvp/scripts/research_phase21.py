"""Phase 21 检索层研究 E21:特征变体重排实验。

问题:CLS 全局特征在"同场景内不同镜头/字牌"上无分辨率(p26 真值 sim 0.31 vs 错误 0.87)。
实验:对 6 个 verified 探针,取 CLS top-50 候选 + 真值,测试 4 种特征变体的重排能力
(指标 = 真值位置在变体排序中的名次,目标 top-3)。
变体:V1=CLS+时序上下文 V2=patch均值池化 V3=patch最大匹配 V4=CLS+颜色直方图。
(V0=CLS 基线名次一并输出。)

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_phase21.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from device.dinov2_model import DinoV2Small, _imagenet_preprocess
from media.ffmpeg import FFmpegIO

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
WEIGHTS = BENCH / "work" / "dinov2_weights" / "dinov2_vits14_pretrain.pth"
EDIT = Path("D:/video/1.mp4")
ORIG = Path("D:/video/2.mkv")
APP_INDEX = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")

PROBES = [
    ("p26", 76.8, (2808, 2811), "夜读(书+手)"),
    ("p27", 85.5, (1808, 1815), "WHAT IS YOUR NAME? 问句字牌"),
    ("p08", 13.5, (1108, 1110), "瞭望塔+同桌机位(兄弟 1048-1050 亦真)"),
    ("p08b", 13.9, (1048, 1050), "对话场景士兵特写(兄弟 1108-1110 亦真)"),
    ("p01", 0.8, (2412, 2446), "金属球准备(sanity 易例)"),
    ("p17", 36.0, (1397, 1419), "铁丝网山脊"),
]


def main() -> int:
    ff = FFmpegIO(FFMPEG, FFPROBE)
    model = DinoV2Small()
    model.load_state_dict(torch.load(str(WEIGHTS), map_location="cpu", weights_only=True),
                          strict=False)
    model.eval()

    feats = np.load(APP_INDEX / "features.npy")
    times = np.load(APP_INDEX / "times.npy")
    print(f"index {feats.shape}", flush=True)

    @torch.no_grad()
    def embed_full(video, t):
        """帧 → (frame, cls(L2), patches(L2), hsv 直方图)。"""
        f = ff.grab_frame(video, t)
        x = _imagenet_preprocess(f)
        cls, patches = model.forward_features(x)
        cls = cls[0].numpy().astype(np.float32)
        patches = patches[0].numpy().astype(np.float32)
        patches = patches / np.maximum(np.linalg.norm(patches, axis=1, keepdims=True), 1e-8)
        cls = cls / max(np.linalg.norm(cls), 1e-8)
        hsv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1], None, [12, 4], [0, 181, 0, 256]).flatten()
        hist = (hist / max(hist.sum(), 1e-6)).astype(np.float32)
        return f, cls, patches, hist

    def rank_of(sim_vec, k):
        order = np.argsort(-sim_vec)
        return int(np.where(order == k)[0][0]) + 1

    results = []
    for pid, et, (o0, o1), note in PROBES:
        ed_data = [embed_full(EDIT, et - 0.4 + 0.4 * j) for j in range(3)]
        q_cls = np.mean([d[1] for d in ed_data], axis=0)
        q_cls = q_cls / max(np.linalg.norm(q_cls), 1e-8)
        q_patches = np.concatenate([d[2] for d in ed_data], axis=0)
        q_hist = np.mean([d[3] for d in ed_data], axis=0)
        q_hist = q_hist / max(q_hist.sum(), 1e-6)

        sims = feats @ q_cls
        order = np.argsort(-sims)
        cand_set = set(int(i) for i in order[:50])
        cand_idx = [int(i) for i in order[:50]]
        true_idx = np.where((times >= o0) & (times <= o1))[0]
        true_set = {int(x) for x in true_idx}
        t_pos = [k for k, ci in enumerate(cand_idx) if int(ci) in true_set]
        if not t_pos:
            print(f"{pid}: 真值不在 CLS top-50 —— 记 rank>50")
            results.append({"id": pid, "note": note, "ranks": {"V0_CLS": 51}})
            continue

        # V0 CLS
        s0 = feats[cand_idx] @ q_cls
        # V1 时序上下文(索引侧 ±2s 平均)
        ctx_mat = np.vstack([
            feats[np.clip([ci - 2, ci, ci + 2], 0, len(times) - 1)].mean(axis=0)
            for ci in cand_idx])
        ctx_mat = ctx_mat / np.maximum(np.linalg.norm(ctx_mat, axis=1, keepdims=True), 1e-8)
        s1 = ctx_mat @ q_cls
        # V2 patch 均值池化 / V3 patch 最大匹配 / V4 直方图(候选帧需前向)
        s2, s3, s4 = [], [], []
        for ci in cand_idx:
            f2, c2, p2, h2 = embed_full(ORIG, float(times[ci]))
            p2m = p2.mean(axis=0)
            p2m = p2m / max(np.linalg.norm(p2m), 1e-8)
            qpm = q_patches.mean(axis=0)
            qpm = qpm / max(np.linalg.norm(qpm), 1e-8)
            s2.append(float(qpm @ p2m))
            m = (q_patches @ p2.T).max(axis=1)
            s3.append(float(np.sort(m)[-100:].mean()))
            c_feat = np.concatenate([c2 * 0.85, h2 * 0.85])
            q_feat = np.concatenate([q_cls * 0.85, q_hist * 0.85])
            s4.append(float(q_feat @ c_feat / (np.linalg.norm(q_feat) * np.linalg.norm(c_feat))))
        s2, s3, s4 = np.array(s2), np.array(s3), np.array(s4)

        ranks = {
            "V0_CLS": min(rank_of(s0, k) for k in t_pos),
            "V1_CTX": min(rank_of(s1, k) for k in t_pos),
            "V2_PMEAN": min(rank_of(s2, k) for k in t_pos),
            "V3_PMAX": min(rank_of(s3, k) for k in t_pos),
            "V4_HIST": min(rank_of(s4, k) for k in t_pos),
        }
        results.append({"id": pid, "note": note, "true_region": [o0, o1],
                        "n_cand": int(len(cand_idx)), "ranks": ranks})
        print(f"{pid:5s} ({note[:14]:14s}) | " +
              " ".join(f"{k}={v:>3d}" for k, v in ranks.items()), flush=True)

    print("\n=== 汇总(真值名次,目标 ≤3)===")
    keys = ["V0_CLS", "V1_CTX", "V2_PMEAN", "V3_PMAX", "V4_HIST"]
    for k in keys:
        rs = [r["ranks"].get(k, 51) for r in results]
        top3 = sum(1 for x in rs if x <= 3)
        print(f"  {k:8s}: top3 {top3}/{len(results)}  名次 {rs}")

    out = BENCH / "mvp" / "benchmark" / "user_case" / "phase21_probe_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
