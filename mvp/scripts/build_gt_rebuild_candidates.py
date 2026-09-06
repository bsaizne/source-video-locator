"""GT 重建专会话: 对 GT/C1 均不对的条目生成 top-N 候选窗辅助定位。

目标: p04 p10 p16 p18 p34 p35 p36 p37 p40
流程: 编辑段 3 帧 embed 均值 -> 1fps 原片索引检索 top-40 -> 聚簇 top-6 窗口 ->
为每条生成对照图(行1=ED 3帧, 行2..=候选窗各 3 帧)+ 输出 gt_rebuild_candidates.json。
不改算法。复用 build_gt_review.py 检索流程(DirectML auto)。
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "src"))

from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps  # noqa: E402
from diagnostics.contact_sheet import compose_sheet  # noqa: E402
from media.ffmpeg import FFmpegIO  # noqa: E402

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
IDX = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
APP_MODEL = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                 "dinov2_cls_384/dinov2_cls_384.onnx")
GT = BENCH / "datasets" / "real" / "ground_truth_v3.json"
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "gt_rebuild"
EDIT = "D:/video/1.mp4"
ORIG = "D:/video/2.mkv"
TOP_K = 40
WINDOW_GAP_S = 8.0
MAX_WINDOWS = 6

TARGETS = ["p04", "p10", "p16", "p18", "p34", "p35", "p36", "p37", "p40"]


def cluster_windows(top_idx, times, sims, max_windows):
    hits = sorted((float(times[i]), float(sims[i])) for i in top_idx)
    groups = []
    for t, s in hits:
        if groups and t - groups[-1][-1][0] <= WINDOW_GAP_S:
            groups[-1].append((t, s))
        else:
            groups.append([(t, s)])
    scored = []
    for g in groups:
        ts = [x[0] for x in g]
        ss = [x[1] for x in g]
        scored.append((round(min(ts), 1), round(max(ts) + 1.0, 1),
                       round(float(np.mean(ss)), 3), len(g)))
    scored.sort(key=lambda w: (-w[2], -w[3]))
    return scored[:max_windows]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_frames").mkdir(exist_ok=True)
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    from device import resolve_backend
    backend = resolve_backend(preferred="auto")
    ff = FFmpegIO(FFMPEG, FFPROBE)
    print("backend:", type(backend).__name__, flush=True)

    feats = np.load(IDX / "features.npy").astype(np.float32)
    times = np.load(IDX / "times.npy").astype(np.float64)
    gt = json.loads(Path(GT).read_text(encoding="utf-8"))
    by_id = {p["id"]: p for p in gt["positives"]}

    manifest = {"cases": []}
    for pid in TARGETS:
        p = by_id[pid]
        (e0, e1) = p["edited"]
        (o0, o1) = p["original"]
        e_mid = (e0 + e1) / 2.0
        ereps = [e_mid - 0.4, e_mid, e_mid + 0.4]
        ed_frames = [ff.grab_frame(EDIT, t) for t in ereps]
        ef = backend.embed_frames(ed_frames)
        q = ef.mean(axis=0)
        q /= max(np.linalg.norm(q), 1e-8)
        sims = feats @ q
        top = np.argsort(-sims)[:TOP_K]
        wins = cluster_windows(top, times, sims, MAX_WINDOWS)

        rows = [[(str(ffmpeg_frame(EDIT, t, OUT / "_frames" / f"{pid}_e{j}.png")),
                  [fmt_ts(t), "ED"]) for j, t in enumerate(ereps)]]
        cands = []
        for wi, (a, b, ms, n) in enumerate(wins):
            creps = pick_reps(a, b, 3)
            rows.append([(str(ffmpeg_frame(ORIG, t, OUT / "_frames" / f"{pid}_w{wi}_j{j}.png")),
                          [fmt_ts(t), f"W{wi} sim={ms}"]) for j, t in enumerate(creps)])
            cands.append({"idx": wi, "a": a, "b": b, "mean_sim": ms, "n": n})
        title = (f"{pid} [{p['tier']}] ed {fmt_ts(e0)}..{fmt_ts(e1)} | GT {o0:.0f}-{o1:.0f}")
        compose_sheet(rows, OUT / f"{pid}_candidates.jpg", title)
        manifest["cases"].append({"id": pid, "edited": list(p["edited"]),
                                  "gt": list(p["original"]), "candidates": cands})
        print(f"{pid}: GT {o0:.0f}-{o1:.0f} | " +
              " ".join(f"W{widx}[{wa},{wb}]s{wms}" for widx, (wa, wb, wms, wn) in enumerate(wins)), flush=True)

    (OUT / "gt_rebuild_candidates.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONE ->", OUT, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
