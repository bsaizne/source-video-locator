"""Phase 21 路径1 可行性实验:场景级索引与检索。

问题:p26 型失败(真值 2809 帧级 sim 仅 0.31,错误场景 0.87)——场景级匹配能否把
真值位置救回 top-3?方法:
  1) 索引侧:对 7668 帧 1fps 特征跑 detect_shots → 场景/镜头分割 → 场景指纹(均值,L2)
  2) 查询侧:编辑段帧 embed 后均值 → L2
  3) 口径:
     A) 帧级基线:真值秒在全部帧相似度中的名次
     B) 场景指纹:真值场景在场景指纹相似度中的名次
     C) 场景投票:查询帧 top-100 命中按场景加权投票,真值场景名次
     D) 两阶段:场景指纹 top-5 场景内做帧级精排,真值名次(场景名次×场景内名次近似)

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_scene_retrieval.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "src"))

from diagnostics.frame_sampler import ffmpeg_frame  # noqa: E402
from engine.feature_store import IndexBundle  # noqa: E402
from engine.segment import detect_shots  # noqa: E402
from domain import IndexMeta  # noqa: E402
from media.ffmpeg import FFmpegIO  # noqa: E402

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
EDIT = Path("D:/video/1.mp4")
ORIG = Path("D:/video/2.mkv")
APP_INDEX = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
APP_MODEL = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                 "dinov2_cls_384/dinov2_cls_384.onnx")

PROBES = [
    ("p26", 76.8, (2808, 2811), "夜读(书+手)"),
    ("p27", 85.5, (1808, 1815), "问句字牌"),
    ("p08", 13.5, (1108, 1110), "瞭望塔机位"),
    ("p17", 36.0, (1397, 1419), "铁丝网山脊"),
    ("p01", 0.8, (2412, 2446), "金属球(sanity)"),
]


def main() -> int:
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    from device import resolve_backend  # noqa: E402

    backend = resolve_backend(preferred="auto")
    ff = FFmpegIO(FFMPEG, FFPROBE)
    feats = np.load(APP_INDEX / "features.npy")   # (N,384) L2
    times = np.load(APP_INDEX / "times.npy")
    meta = IndexMeta("2.mkv", 0, float(times[-1]) + 1.0, "hash")
    bundle = IndexBundle(meta, feats, times)
    N = len(times)
    print(f"index {feats.shape}", flush=True)

    # ---- 索引侧场景分割 ----
    shots = detect_shots(feats, times, cut_abs=0.15, z_thresh=1.5,
                         min_shot_s=3.0, smooth=1, fps=1.0)
    bounds = [0] + [int(round(s.span.end)) + 1 for s in shots]
    bounds = sorted(set(min(b, N) for b in bounds))
    if bounds[0] != 0:
        bounds.insert(0, 0)
    if bounds[-1] < N:
        bounds.append(N)
    scenes = [(bounds[i], bounds[i + 1]) for i in range(len(bounds) - 1)]
    fp = np.vstack([feats[a:b].mean(axis=0) for a, b in scenes])
    fp = fp / np.maximum(np.linalg.norm(fp, axis=1, keepdims=True), 1e-8)
    sizes = [b - a for a, b in scenes]
    print(f"场景分割: {len(scenes)} 个场景, 尺寸 mean={np.mean(sizes):.0f}s "
          f"median={np.median(sizes):.0f}s max={max(sizes)}s", flush=True)

    def scene_of(sec: float) -> int:
        for k, (a, b) in enumerate(scenes):
            if a <= sec < b:
                return k
        return len(scenes) - 1

    print("\n=== 探针结果(名次,目标:场景级 ≤5 / 帧级对照)===")
    rows = []
    for pid, et, (o0, o1), note in PROBES:
        reps = [et - 0.5 + 0.5 * j for j in range(3)]
        frames = [ff.grab_frame(EDIT, t) for t in reps]
        q = backend.embed_frames(frames)
        qf = q.mean(axis=0)
        qf = qf / max(np.linalg.norm(qf), 1e-8)

        # A) 帧级基线
        sims = feats @ qf
        order = np.argsort(-sims)
        true_secs = [int(t) for t in times if o0 <= t <= o1]
        frame_rank = min(int(np.where(order == s)[0][0]) + 1 for s in true_secs)

        # B) 场景指纹
        true_scene = scene_of((o0 + o1) / 2)
        ssims = fp @ qf
        sorder = np.argsort(-ssims)
        scene_rank = int(np.where(sorder == true_scene)[0][0]) + 1

        # C) 场景投票(帧 top-100 加权)
        top = order[:100]
        votes = np.zeros(len(scenes))
        for ti in top:
            votes[scene_of(int(times[ti]))] += max(0.0, float(sims[ti]) - 0.30)
        vorder = np.argsort(-votes)
        vote_rank = int(np.where(vorder == true_scene)[0][0]) + 1

        # D) 两阶段:场景指纹 top-5 内帧级精排
        top5 = sorder[:5]
        if true_scene in top5.tolist():
            in_scene = [ti for ti in true_secs if scene_of(int(times[ti])) == true_scene]
            s_in = sims[in_scene]
            frame_in = int(np.argsort(-s_in)[0]) if len(s_in) else -1
            # 全局两阶段名次 = 前面 4 个场景的帧数 + 场景内名次(近似)
            before_frames = sum(scenes[k][1] - scenes[k][0] for k in top5.tolist()[:top5.tolist().index(true_scene)])
            two_stage = before_frames + (int(np.where(np.argsort(-sims[in_scene]))[0][0]) + 1 if len(s_in) else 1)
        else:
            two_stage = 9999

        rows.append({"id": pid, "note": note, "true_scene": true_scene,
                     "frame_rank": frame_rank, "scene_rank": scene_rank,
                     "vote_rank": vote_rank, "two_stage": two_stage})
        print(f"{pid:5s} ({note[:12]:12s}) 帧级={frame_rank:>4d} 场景指纹={scene_rank:>3d} "
              f"投票={vote_rank:>3d} 两阶段={two_stage:>4d} (真值场景#{true_scene}, "
              f"尺寸{scenes[true_scene][1]-scenes[true_scene][0]}s)", flush=True)

    print("\n=== 汇总 ===")
    for key in ("frame_rank", "scene_rank", "vote_rank", "two_stage"):
        rs = [r[key] for r in rows]
        top5 = sum(1 for x in rs if x <= 5)
        print(f"  {key:11s}: ≤5 命中 {top5}/{len(rs)}  名次 {rs}")
    out = BENCH / "mvp" / "benchmark" / "user_case" / "scene_retrieval_results.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved ->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
