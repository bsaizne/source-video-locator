# -*- coding: utf-8 -*-
"""patch 召回 v2 判决探针: 对 7 条检索池外条目跑 M6 式混合池 patch 召回(研究侧, 零 runtime)。

协议(沿 M6): 池 = CLS top-200 ∪ 索引均匀采样(1/5) ∪ GT 窗±2s 帧;
查询 = 覆盖段的 2fps 均值帧代表点 3 帧 patch; 判决 = GT 窗帧在 patch 分数下的排名。
RESCUE = 最优 GT 帧 rank=1(或与 top1 同分)。"""
import json
import os
import sys
from pathlib import Path

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
os.environ.setdefault("SVL_DML_MODEL", r"C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

import numpy as np  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from engine.localization.patch_rerank import PatchReranker, patch_score, resolve_patch_onnx, resolve_weights  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

FRAME_N = {"2mkv": 7668, "test1": 8221, "test2": 5051, "test3": 10177}
FILM_META = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
}
# (film, gt_id, gt_ed0, gt_ed1, gt_o0, gt_o1)
CASES = [
    ("2mkv", "p14", None, None, 1380.0, 1382.0),
    ("2mkv", "p26", None, None, 1768.2, 1770.0),
    ("test1", "t1r02", 5.0, 9.0, 2183.0, 2184.0),
    ("test1", "t1r14d", 50.5, 52.0, 3171.7, 3172.7),
    ("test2", "t2r05a", 34.0, 43.8, 4344.8, 4346.8),
    ("test2", "t2r05b", 43.8, 53.5, 1619.1, 1620.0),
    ("test2", "t2r07c", 65.0, 65.5, 4092.2, 4097.0),
]


def main():
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    rr = PatchReranker(resolve_weights(cfg.pipeline.patch_weights_path or None),
                       resolve_patch_onnx((cfg.pipeline.patch_onnx_model or "").strip() or None),
                       dml_device_id=cfg.device.dml_device_id)
    assert rr.ensure(), "patch reranker unavailable"
    print("patch device:", rr.device, flush=True)
    IDX = Path(os.environ["SVL_DATA_DIR"]) / "index"
    idx_by_film = {}
    for d in IDX.glob("*.idx"):
        try:
            f = np.load(d / "features.npy", mmap_mode="r")
            n = f.shape[0]
            if n in FRAME_N.values():
                idx_by_film[ [k for k, v in FRAME_N.items() if v == n][0] ] = (
                    np.asarray(f), np.load(d / "times.npy"))
        except Exception:
            continue

    def rep_times(a, b, n=3):
        return [round(a + (b - a) * (i + 0.5) / n, 2) for i in range(n)]

    for film, gid, ge0, ge1, go0, go1 in CASES:
        gt = json.loads(Path("datasets/real", f"ground_truth_{film if film != '2mkv' else 'v4'}.json")
                        .read_text(encoding="utf-8"))
        if ge0 is None:
            for p in gt["positives"]:
                if p["id"] == gid:
                    ge0, ge1 = p["edited"]; break
        ed_vid, og_vid = FILM_META[film]
        feats, times = idx_by_film[film]
        # 查询: 覆盖段代表 3 帧 patch + CLS(主后端, 对齐 M6 协议)
        q_frames = [srv.ffmpeg.grab_frame(ed_vid, t) for t in rep_times(ge0, ge1)]
        q_patches = np.vstack([rr.frame_patches(f) for f in q_frames])
        q_cls_feats = srv.backend.embed_frames(q_frames)
        q_cls = q_cls_feats.mean(axis=0)
        q_cls = q_cls / max(float(np.linalg.norm(q_cls)), 1e-8)
        # 池: CLS top-200 ∪ 索引均匀采样(1/5) ∪ GT 窗±2s 帧(M6 混合池协议)
        sims = feats @ q_cls
        top200 = set(int(i) for i in np.argsort(-sims)[:200])
        uni = set(range(0, len(times), 20))  # 1/20 均匀采样(池控规模)
        gt_idx = set(int(i) for i in np.where((times >= go0 - 2.0) & (times <= go1 + 2.0))[0])
        pool = sorted(top200 | uni | gt_idx)
        # 打分
        scored = []
        for i in pool:
            t = float(times[i])
            f = srv.ffmpeg.grab_frame(og_vid, t)
            s = patch_score(q_patches, rr.frame_patches(f))
            scored.append((s, i, t))
        scored.sort(reverse=True)
        gt_best_rank = None
        gt_best_score = None
        top1 = None
        for rank, (s, i, t) in enumerate(scored, start=1):
            if i in gt_idx and gt_best_rank is None:
                gt_best_rank, gt_best_score = rank, s
            if rank == 1:
                top1 = (s, t)
        in_gt = top1 is not None and (go0 - 2 <= top1[1] <= go1 + 2)
        print(f"  [{gid}] scoring pool...", flush=True)
        scored = []
        if True:
            print(f"{gid:8s} pool={len(pool):4d} GT帧rank={gt_best_rank} gt_score={gt_best_score} "
              f"top1={top1[1]:.0f}s({top1[0]:.3f}) {'✅RESCUE' if in_gt else '❌'}", flush=True)


if __name__ == "__main__":
    main()
