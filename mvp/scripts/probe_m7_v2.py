# -*- coding: utf-8 -*-
"""M7 v2: ALIKED 局部特征按最新标准重跑（twopass+最新 GT+当前失败族 12 案例）。

协议（对齐 patch 召回 v2, 结果可直接对比）:
  查询 = 覆盖段代表 3 帧 ALIKED 描述子;
  池   = CLS top-100 ∪ 1/20 均匀 ∪ GT 窗±2s 帧;
  打分 = 逐池帧 mutual_nn 匹配数(vs 查询描述子);
  判决 = GT 窗帧的最好排名（rank 1 = 救回; 对照: 当前主定位帧的排名）。
案例 = 当前 12 条非严格命中（7 池外 + 5 场景级 part）。M7 原结论（兄弟机位同刚性场景不可分）
针对的是机位变化; 本轮问的是「同场景相邻时刻」ALIKED 是否有判别力。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
os.environ.setdefault("SVL_DML_MODEL", r"C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

WORK = BENCH / "work"
FFMPEG = str(BENCH / "tools" / "ffmpeg.exe")
WEIGHTS = WORK / "local_feature_weights" / "aliked-n32.pth"
FRAME_N = {"2mkv": 7668, "test1": 8221, "test2": 5051, "test3": 10177}
FILM_META = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
GT_FILE = {"2mkv": "ground_truth_v4.json", "test1": "ground_truth_test1.json",
           "test2": "ground_truth_test2.json", "test3": "ground_truth_test3.json"}
SCORE_THR = 0.3
IMG_SIZE = 512

# 当前 12 条非严格命中（patch v2 + GT 修正后的最新口径）
CASES = [
    ("2mkv", "p14", "池外"), ("2mkv", "p20", "part"), ("2mkv", "p30", "part"), ("2mkv", "p35", "part"),
    ("test1", "t1r02", "池外"), ("test1", "t1r14d", "池外"),
    ("test2", "t2r05a", "池外"), ("test2", "t2r05b", "池外"), ("test2", "t2r07c", "池外"),
    ("test3", "t3r03a", "part"), ("test3", "t3r06b", "part"), ("test3", "t3r29", "part"),
]


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


def main():
    from kornia.feature import ALIKED
    ex = ALIKED(model_name="aliked-n32")
    sd = torch.load(str(WEIGHTS), map_location="cpu", weights_only=True)
    ex.load_state_dict(sd, strict=False)
    ex.eval()

    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    IDX = Path(os.environ["SVL_DATA_DIR"]) / "index"
    idx_by_film = {}
    for d in IDX.glob("*.idx"):
        try:
            f = np.load(d / "features.npy", mmap_mode="r")
            n = f.shape[0]
            if n in FRAME_N.values():
                idx_by_film[[k for k, v in FRAME_N.items() if v == n][0]] = (
                    np.asarray(f), np.load(d / "times.npy"))
        except Exception:
            continue

    def grab(video, t):
        out = WORK / "_m7v2_grab.png"
        subprocess.run([FFMPEG, "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
                        "-vf", f"scale={IMG_SIZE}:-2", "-frames:v", "1", str(out)],
                       check=True, capture_output=True, timeout=60)
        return cv2.imread(str(out))

    def aliked(img):
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        x = torch.from_numpy(rgb).permute(2, 0, 1).unsqueeze(0).float() / 255.0
        with torch.no_grad():
            out = ex(x)[0]
        return out.descriptors.numpy(), out.keypoint_scores.numpy()

    print(f"{'case':10s}{'状态':6s}{'池':>5}{'GT最优':>7}{'主定位':>7}{'GT分':>7}{'主分':>7}  判定", flush=True)
    rescued = 0
    for film, gid, status in CASES:
        gt = json.loads(Path("datasets/real", GT_FILE[film]).read_text(encoding="utf-8"))
        p = next(x for x in gt["positives"] if x["id"] == gid)
        e0, e1 = p["edited"]; o0, o1 = p["original"]; om = (o0 + o1) / 2
        ed_vid, og_vid = FILM_META[film]
        feats, times = idx_by_film[film]
        res = json.loads(Path(f"work/rerun_{film}_perfopt.results.json").read_text(encoding="utf-8"))["results"]
        cov = [r for r in res if min(e1, r["edited_segment"]["end"]) - max(e0, r["edited_segment"]["start"]) > 0]
        if not cov:
            print(f"{gid:10s} 无覆盖段", flush=True)
            continue
        r0 = cov[0]
        main_mid = (r0["original"]["candidate_start"] + r0["original"]["candidate_end"]) / 2.0

        q_desc, q_score = [], []
        for t in (e0 + (e1 - e0) * (j + 0.5) / 3 for j in range(3)):
            img = grab(ed_vid, t)
            if img is None:
                continue
            dsc, sc = aliked(img)
            q_desc.append(dsc); q_score.append(sc)
        if not q_desc:
            print(f"{gid:10s} 查询抽帧失败", flush=True)
            continue
        q_desc = np.concatenate(q_desc); q_score = np.concatenate(q_score)

        q_cls_frames = [grab(ed_vid, t) for t in (e0 + (e1 - e0) * (j + 0.5) / 3 for j in range(3))]
        q_cls = srv.backend.embed_frames(q_cls_frames).mean(axis=0)
        q_cls /= max(float(np.linalg.norm(q_cls)), 1e-8)
        cls_sims = feats @ q_cls
        top100 = set(int(i) for i in np.argsort(-cls_sims)[:100])
        uni = set(range(0, len(times), 20))
        gt_idx = set(int(i) for i in np.where((times >= o0 - 2.0) & (times <= o1 + 2.0))[0])
        main_i = int(np.argmin(np.abs(times - main_mid)))
        pool = sorted(top100 | uni | gt_idx | {main_i})

        scored = []
        for i in pool:
            t = float(times[i])
            img = grab(og_vid, t)
            if img is None:
                continue
            dsc, sc = aliked(img)
            scored.append((mutual_nn(q_desc, dsc, q_score, sc), i, t))
        scored.sort(reverse=True)
        gt_rank = next((r for r, (m, i, t) in enumerate(scored, 1) if i in gt_idx), None)
        gt_best = next((m for m, i, t in scored if i in gt_idx), 0)
        main_rank = next((r for r, (m, i, t) in enumerate(scored, 1) if i == main_i), None)
        main_best = next((m for m, i, t in scored if i == main_i), 0)
        top1 = scored[0]
        rescue = gt_rank == 1
        if rescue:
            rescued += 1
        v = "✅ RESCUE(rank1)" if rescue else (f"❌ GT rank{gt_rank}" if gt_rank else "❌ GT 无匹配")
        print(f"{gid:10s}{status:6s}{len(pool):>5}{str(gt_rank):>7}{str(main_rank):>7}"
              f"{gt_best:>7}{main_best:>7}  {v}  top1={top1[2]:.0f}s({top1[0]})", flush=True)

    print(f"\nALIKED RESCUE: {rescued}/{len(CASES)}（对比: patch v2 已修 3 条——t3r25/t3r04b/t2r07c 为 GT 修正）", flush=True)


if __name__ == "__main__":
    main()
