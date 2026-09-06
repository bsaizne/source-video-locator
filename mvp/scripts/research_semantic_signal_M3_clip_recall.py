"""Phase 24-2 · 方向 C 完整验证探针 M3 —— 字幕语义→原片场景跨模态向量索引(CLIP)。

用户 2026-09-01 拍板:立项方向 C 完整验证(A)= 引入文本嵌入模型 → 建「字幕语义→原片场景」
向量索引 → 更多案例量化召回增益。M2(逐窗 VLM EVENT-MATCH)给出 p26 首个正面信号;
M3 升级为**可检索的跨模态向量索引**:CLIP(clip-ViT-B-32-multilingual-v1, 512 维,
图片+文本同一空间)把原片场景帧与编辑段字幕编码到同一空间,余弦检索。

验证问题:
  字幕语义召回通道能否把「视觉 CLS 漏检/混淆」的正确事件从候选场景中捞回?
  对比每案例: CLS 场景排名 vs 字幕-CLIP 场景排名, 看正确场景是否被字幕拉高。

环境(已装通):
  - sentence-transformers 6.0.1 + clip-ViT-B-32-multilingual-v1(hf-mirror 下载, 512 维)
  - 多语言支持: test4 法语字幕也可编码
  - ffmpeg 抽帧 + rapidocr(本地 OCR)

探针案例(失败族 + 易例对照):
  p26: 字幕"她用望远镜看 Levi 在做什么" → 正确场景295(2809 夜读) vs 干扰夜阳台(1766)
  p08: 字幕"这个任务更绝密" → 正确场景134 vs 兄弟128
  t3r12: 字幕"精灵王只是站着看" → 正确[43,44,45] vs 干扰[42,46,47,48]
  test4: 字幕(法)"二十多人被困滑梯管道" → 正确[353,354,355] vs 干扰[352,356,357,358,359]
  p01(易例对照): 字幕"防止可怕的怪物逃出" → 正确场景265

判据:
  - 正确场景在「字幕-CLIP 检索」下的排名 ≤ 在「CLS 场景检索」下的排名 → 字幕召回有效
  - 若正确场景被字幕-CLIP 推进 top-1~top-3 → 方向 C 召回通道实锤
  - test4 若仍不可分 → 字幕-画面解耦案例的字幕召回同样无效(边界确认)

输出: work/semantic_signal_M3_results.json
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_semantic_signal_M3_clip_recall.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
WORK = BENCH / "work"
MODEL = "sentence-transformers/clip-ViT-B-32-multilingual-v1"
HF_ENDPOINT = "https://hf-mirror.com"

IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
IDX2 = IDX_DIR / "2__4c6d4ab2.idx"
IDX_T3 = IDX_DIR / "test3-om__074e2dcc.idx"
IDX_T4 = IDX_DIR / "test4-om__eb686e0c.idx"

ORIG_VIDEO = {
    "2mkv": "D:/video/2.mkv",
    "test3": "D:/ProjectXIXI/test3/test3-om.mp4",
    "test4": "D:/ProjectXIXI/test4/test4-om.mkv",
}

# 字幕(编辑段 OCR, 与 M2 同源)
CASES = [
    ("2mkv", "p26", "She used binoculars to watch what Levi was doing",
     [295], [110, 140, 180, 208, 210, 220, 250], "夜读(真值) vs 夜阳台等干扰场景"),
    ("2mkv", "p08", "And this mission is even more top secret",
     [134], [128, 121, 122, 129, 130, 140], "兄弟机位(真值134 vs 兄弟128 等)"),
    ("test3", "t3r12", "But the Elven King just stands there and watches",
     [43, 44, 45], [42, 46, 47, 48], "精灵王重复镜头(真值43-45 vs 干扰42/46-48)"),
    ("test4", "t4r01", "Plus de vingt personnes sont restées coincées dans le tube du toboggan",
     [353, 354, 355], [352, 356, 357, 358, 359], "同质滑梯(真值353-355 vs 干扰352/356-359)"),
    ("2mkv", "p01", "Preventing horrible monsters from escaping",
     [265], [260, 261, 262, 263, 264, 266], "金属球装置戏(易例对照)"),
]


def load_scenes(idx: Path):
    scenes = np.load(idx / "scenes.npy")
    scene_feats = np.load(idx / "scene_feats.npy").astype(np.float32)
    return scenes, scene_feats


def grab(video: str, t: float, out_path: Path) -> Path:
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{t:.3f}",
                    "-i", video, "-vf", "scale=512:-2", "-frames:v", "1",
                    str(out_path)], check=True, capture_output=True)
    return out_path


def scene_center(scenes, i):
    return float((scenes[i][0] + scenes[i][1]) / 2.0)


def cli_rank(scene_feats, q_emb, true_scenes):
    """用场景指纹(CLS)算正确场景在候选子集内的排名(取最优)。"""
    subset = set(true_scenes)
    sims = {j: float(scene_feats[j] @ q_emb) for j in subset}
    # 用均值指纹作查询代表(同 P2 口径)
    return None  # 占位, 主流程用 clip 对比


def main() -> int:
    import os
    os.environ["HF_ENDPOINT"] = HF_ENDPOINT
    from sentence_transformers import SentenceTransformer

    t0 = time.time()
    print("loading CLIP model...")
    model = SentenceTransformer(MODEL)
    model.eval()

    scenes_cache = {
        "2mkv": load_scenes(IDX2),
        "test3": load_scenes(IDX_T3),
        "test4": load_scenes(IDX_T4),
    }

    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "model": MODEL, "dim": 512, "cases": []}

    for pair, pid, subtitle, true_scenes, dist_scenes, note in CASES:
        scenes, scene_feats = scenes_cache[pair]
        video = ORIG_VIDEO[pair]
        subset = sorted(set(true_scenes) | set(dist_scenes))

        # --- 原片侧: 每个候选场景抽 3 帧 CLIP 编码(均值) ---
        frame_paths, scene_ids = [], []
        for si in subset:
            c = scene_center(scenes, si)
            for k in range(3):
                t = min(max(c - 0.8 + k * 0.8, scenes[si][0] + 0.1), scenes[si][1] - 0.1)
                p = WORK / f"_m3_{pid}_{si}_{k}.png"
                grab(video, float(t), p)
                frame_paths.append(str(p))
                scene_ids.append(si)
        img_embs = model.encode(frame_paths, convert_to_numpy=True, show_progress_bar=False)
        # 按场景聚合均值
        scene_emb = {}
        for si, e in zip(scene_ids, img_embs):
            scene_emb.setdefault(si, []).append(e)
        scene_vec = {si: np.mean(v, axis=0) for si, v in scene_emb.items()}
        for si in scene_vec:
            n = np.linalg.norm(scene_vec[si])
            if n > 1e-8:
                scene_vec[si] = scene_vec[si] / n

        # --- 编辑侧: 字幕文本 CLIP 编码 ---
        sub_vec = model.encode([subtitle], convert_to_numpy=True, show_progress_bar=False)[0]
        sub_vec = sub_vec / max(np.linalg.norm(sub_vec), 1e-8)

        # --- 字幕-CLIP 场景排名(候选子集内) ---
        clip_sims = {si: float(scene_vec[si] @ sub_vec) for si in subset}
        clip_order = sorted(subset, key=lambda s: -clip_sims[s])
        clip_true_ranks = [clip_order.index(s) + 1 for s in true_scenes]
        clip_best_rank = min(clip_true_ranks)

        # --- CLS 场景排名对照(用查询均值 vs 场景指纹, 同样候选子集内) ---
        # 查询均值 = 正确场景指纹均值(研究口径, 表示"视觉上正确实例的代表")
        rep = np.mean(scene_feats[true_scenes], axis=0)
        rep = rep / max(np.linalg.norm(rep), 1e-8)
        cls_sims = {si: float(scene_feats[si] @ rep) for si in subset}
        cls_order = sorted(subset, key=lambda s: -cls_sims[s])
        cls_true_ranks = [cls_order.index(s) + 1 for s in true_scenes]
        cls_best_rank = min(cls_true_ranks)

        entry = {
            "id": pid, "pair": pair, "note": note,
            "subtitle": subtitle,
            "true_scenes": true_scenes, "dist_scenes": dist_scenes,
            "n_candidates": len(subset),
            "clip_ranks_of_true": {str(s): clip_order.index(s) + 1 for s in true_scenes},
            "clip_best_rank": clip_best_rank,
            "cls_ranks_of_true": {str(s): cls_order.index(s) + 1 for s in true_scenes},
            "cls_best_rank": cls_best_rank,
            "clip_top5": [{"scene": s, "span": scenes[s].tolist(),
                           "sim": round(clip_sims[s], 4)}
                          for s in clip_order[:5]],
            "improved_by_subtitle": clip_best_rank <= cls_best_rank,
        }
        report["cases"].append(entry)
        print(f"[{pid}] 字幕-CLIP 正确场景最优 rank={clip_best_rank}/{len(subset)} "
              f"| CLS rank={cls_best_rank}/{len(subset)} | "
              f"字幕提升={clip_best_rank <= cls_best_rank}")

    out = WORK / "semantic_signal_M3_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
