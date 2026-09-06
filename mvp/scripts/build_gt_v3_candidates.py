"""GT v3 候选生成——镜头级细标注第一步。

流程:scdet 细切分 1.mp4 → 每镜头 3 代表帧 embed(DirectML/CPU auto)→ 在 1fps
原片索引上检索 top 候选窗(聚簇)→ 每镜头生成「编辑帧 vs top-3 候选窗」对照图
+ gt_v3_candidates.json(供人工裁决后生成 ground_truth_v3.json)。

只做诊断/标注辅助,不改算法。运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/build_gt_v3_candidates.py
"""
from __future__ import annotations

import json
import re
import subprocess
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
EDIT = Path("D:/video/1.mp4")
APP_INDEX = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
APP_MODEL = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                 "dinov2_cls_384/dinov2_cls_384.onnx")
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "gt_v3"
CUT_TH = 0.18
MERGE_GAP_S = 0.7
MIN_SHOT_S = 0.5
TOP_WINDOWS = 3
WINDOW_GAP_S = 8.0


def detect_cuts() -> list[float]:
    """scdet/select scene 分数取切点。"""
    cmd = [str(FFMPEG), "-hide_banner", "-nostats", "-i", str(EDIT),
           "-vf", f"select='gt(scene,{CUT_TH})',metadata=print", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    times = []
    for m in re.finditer(r"pts_time:([0-9.]+)", proc.stderr):
        times.append(float(m.group(1)))
    # select 的 pts_time 是帧 pts;metadata 打印的 scene_score 行紧跟其后,这里
    # 简化:直接取 select 触发的帧时间(即切点)。去重+排序。
    times = sorted(set(round(t, 2) for t in times))
    merged: list[float] = []
    for t in times:
        if not merged or t - merged[-1] > MERGE_GAP_S:
            merged.append(t)
    return merged


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_frames").mkdir(exist_ok=True)

    import os
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    from device import resolve_backend
    backend = resolve_backend(preferred="auto")
    ff = FFmpegIO(FFMPEG, FFPROBE)

    feats = np.load(APP_INDEX / "features.npy")   # (N,384) L2
    times = np.load(APP_INDEX / "times.npy")      # (N,)
    print(f"index: {feats.shape}, backend={type(backend).__name__}")

    cuts = detect_cuts()
    dur = 126.79
    bounds = [0.0] + [c for c in cuts if 0.3 < c < dur - 0.3] + [dur]
    shots = []
    for a, b in zip(bounds[:-1], bounds[1:]):
        if b - a >= MIN_SHOT_S:
            shots.append((round(a, 2), round(b, 2)))
    print(f"cuts={len(cuts)} -> shots={len(shots)}")

    # 批量取代表帧并 embed
    rep_times: list[list[float]] = []
    for a, b in shots:
        reps = [min(t, dur - 0.2) for t in pick_reps(a, b, 3)]
        rep_times.append(reps)
    flat = [t for reps in rep_times for t in reps]
    frames = [ff.grab_frame(EDIT, t) for t in flat]
    ffeats = backend.embed_frames(frames)
    print(f"embedded {len(frames)} frames")

    out_shots = []
    for si, (a, b) in enumerate(shots):
        reps = rep_times[si]
        start = sum(len(r) for r in rep_times[:si])
        end = sum(len(r) for r in rep_times[:si + 1])
        sf = ffeats[start:end]
        shot_feat = sf.mean(axis=0)
        shot_feat /= max(np.linalg.norm(shot_feat), 1e-8)
        sims = feats @ shot_feat
        top = np.argsort(-sims)[:24]
        # 聚簇成窗口
        hits = sorted((float(times[i]), float(sims[i])) for i in top)
        groups: list[list[tuple[float, float]]] = []
        for t, s in hits:
            if groups and t - groups[-1][-1][0] <= WINDOW_GAP_S:
                groups[-1].append((t, s))
            else:
                groups.append([(t, s)])
        scored = []
        for g in groups:
            ts = [x[0] for x in g]
            ss = [x[1] for x in g]
            scored.append({
                "a": round(min(ts), 1), "b": round(max(ts) + 1.0, 1),
                "mean_sim": round(float(np.mean(ss)), 3),
                "max_sim": round(float(np.max(ss)), 3),
                "n": len(g),
            })
        scored.sort(key=lambda w: (-w["mean_sim"], -w["n"]))
        cands = scored[:TOP_WINDOWS]
        out_shots.append({"id": si, "span": [a, b], "reps": reps, "cands": cands})

        # 对照图:row1=编辑 3 帧;row2-4=候选窗各 2 帧
        rows = [[(str(ffmpeg_frame(EDIT, t, OUT / "_frames" / f"s{si}_e{j}.png")),
                  [fmt_ts(t)]) for j, t in enumerate(reps)]]
        for wi, w in enumerate(cands):
            cells = []
            for j, t in enumerate(pick_reps(w["a"], w["b"], 2)):
                p = OUT / "_frames" / f"s{si}_c{wi}_{j}.png"
                try:
                    ffmpeg_frame(Path("D:/video/2.mkv"), t, p)
                    cells.append((str(p), [fmt_ts(t), f"sim={w['mean_sim']}"]))
                except Exception as exc:
                    print(f"  [skip {p.name}: {exc}]")
                    cells.append(None)
            rows.append(cells)
        compose_sheet(rows, OUT / f"shot_{si:02d}.jpg",
                      f"shot{si:02d} ed({fmt_ts(a)}..{fmt_ts(b)}) "
                      + " | ".join(f"c{wi}:{w['a']:.0f}-{w['b']:.0f} sim{w['mean_sim']}"
                                   for wi, w in enumerate(cands)))
        print(f"shot{si:02d} ({a:.1f}-{b:.1f}) cands: "
              + "; ".join(f"{w['a']:.0f}-{w['b']:.0f}({w['mean_sim']})" for w in cands))

    (OUT / "gt_v3_candidates.json").write_text(
        json.dumps({"cut_threshold": CUT_TH, "shots": out_shots}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print("DONE ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
