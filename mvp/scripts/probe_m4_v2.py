# -*- coding: utf-8 -*-
"""M4 v2: 索引密度重跑（最新 GT + 当前失败族）——8fps 窗口采样能否把池外条目拉回池内。

背景: M4(2026-09-01) 关闭时旧 GT/旧管线; 现发现 26 条未严格命中中 7 条检索 top-20 池外,
且多条 GT 窗仅 0.3~2s 宽（1fps 索引在窗内只有 0~2 帧, 8fps 会有 2~16 帧）。
协议: 覆盖段均值查询(2fps, 与今日池检查同口径) → 对 GT 窗±0.5s @8fps 逐帧算 rank;
判据 = 窗内 8fps 帧的最好排名（1fps 基线 = 今日池检查的池外/池内状态）。
"""
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
from infrastructure.config import load_config  # noqa: E402

FRAME_N = {"2mkv": 7668, "test1": 8221, "test2": 5051, "test3": 10177}
FILM_META = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
GT_FILE = {"2mkv": "ground_truth_v4.json", "test1": "ground_truth_test1.json",
           "test2": "ground_truth_test2.json", "test3": "ground_truth_test3.json"}

# 今日池检查判定的 7 条池外 + 5 条场景级 part（同场景偏移）
CASES = [
    ("2mkv", "p14", "池外"), ("2mkv", "p26", "池外"),
    ("2mkv", "p30", "part"), ("2mkv", "p35", "part"),
    ("test1", "t1r02", "池外"), ("test1", "t1r14d", "池外"),
    ("test2", "t2r05a", "池外"), ("test2", "t2r05b", "池外"), ("test2", "t2r07c", "池外"),
    ("test3", "t3r03a", "part"), ("test3", "t3r04b", "part"),
    ("test3", "t3r06b", "part"), ("test3", "t3r25", "part"), ("test3", "t3r29", "part"),
]


def main():
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

    print(f"{'case':8s}{'状态':6s}{'窗宽s':>6}{'1fps窗内帧':>9}{'8fps帧数':>8}"
          f"{'1fps最优rank':>12}{'8fps最优rank':>12}  判定", flush=True)
    fixed = 0
    for film, gid, status in CASES:
        gt = json.loads(Path("datasets/real", GT_FILE[film]).read_text(encoding="utf-8"))
        p = next(x for x in gt["positives"] if x["id"] == gid)
        e0, e1 = p["edited"]; o0, o1 = p["original"]; om = (o0 + o1) / 2
        ed_vid, og_vid = FILM_META[film]
        feats, times = idx_by_film[film]
        res = json.loads(Path(f"work/rerun_{film}_perfopt.results.json").read_text(encoding="utf-8"))["results"]
        cov = [r for r in res if min(e1, r["edited_segment"]["end"]) - max(e0, r["edited_segment"]["start"]) > 0]
        if not cov:
            print(f"{gid:8s} 无覆盖段", flush=True)
            continue
        r0 = cov[0]
        frames = [f for _, f in srv.ffmpeg.iter_frames(ed_vid, 2.0,
                  start=r0["edited_segment"]["start"], end=r0["edited_segment"]["end"])]
        if not frames:
            print(f"{gid:8s} 查询抽帧失败", flush=True)
            continue
        embs = srv.backend.embed_frames(frames)
        q = embs.mean(axis=0); q /= max(float(np.linalg.norm(q)), 1e-8)
        sims = feats @ q
        order = np.argsort(-sims)
        rank_of = np.empty(len(times), dtype=np.int64)
        rank_of[order] = np.arange(1, len(times) + 1)
        # 1fps 基线: 窗内(±2s)索引帧的最优 rank
        win1 = np.where((times >= o0 - 2.0) & (times <= o1 + 2.0))[0]
        r1 = int(rank_of[win1].min()) if len(win1) else 99999
        # 混合索引: 1fps 全片 + GT 邻域 ±30s @8fps → 查询对 GT 窗帧的真实排名
        NB = 30.0
        wf, wt = [], []
        for t, f in srv.ffmpeg.iter_frames(og_vid, 8.0, start=max(0.0, o0 - NB), end=o1 + NB):
            wf.append(f); wt.append(t)
        r8 = None
        if wf:
            e8 = srv.backend.embed_frames(wf)
            e8 = e8 / np.maximum(np.linalg.norm(e8, axis=1, keepdims=True), 1e-8)
            gt8 = np.array([o0 - 2.0 <= t <= o1 + 2.0 for t in wt])
            sims8 = e8 @ q
            best_gt_sim = float(sims8[gt8].max()) if gt8.any() else None
            if best_gt_sim is not None:
                # 非窗候选(1fps 全片非窗帧 + 8fps 邻域非窗帧)中比 best_gt_sim 更高的数量
                higher = int(((sims > best_gt_sim) & ~((times >= o0 - 2.0) & (times <= o1 + 2.0))).sum())
                higher += int(((sims8 > best_gt_sim) & ~gt8).sum())
                r8 = higher + 1
        fixed_flag = r8 is not None and r8 <= 20 and r1 > 20
        if fixed_flag:
            fixed += 1
        v = "✅ 8fps 拉回池内" if fixed_flag else (f"❌ 仍池外(rank {r8})" if r1 > 20 else f"— 本就池内(rank {r1})")
        print(f"{gid:8s}{status:6s}{o1-o0:>6.1f}{len(win1):>9}{len(wf):>8}{r1:>12}{r8 if r8 is not None else -1:>12}  {v}",
              flush=True)
    print(f"\n池外条目中 8fps 密采样可拉回: {fixed} 条", flush=True)


if __name__ == "__main__":
    main()
