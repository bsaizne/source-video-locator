"""GT v3 加固:A) loose 条目密集复核图 B) verified 盲复核图(不同帧位) C) 覆盖曲线边界精修。

C 的口径与 runtime finloc 一致:对确认窗 ±5s 内每个索引秒,取 max(该秒特征, 编辑rep帧特征)
的余弦,≥0.4 视为覆盖,取最长连续覆盖段为精修 span(索引特征直接复用,不重解码原片)。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/harden_gt_v3.py
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

from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps  # noqa: E402
from diagnostics.contact_sheet import compose_sheet  # noqa: E402
from media.ffmpeg import FFmpegIO  # noqa: E402

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
EDIT = Path("D:/video/1.mp4")
ORIG = Path("D:/video/2.mkv")
APP_INDEX = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
APP_MODEL = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                 "dinov2_cls_384/dinov2_cls_384.onnx")
GT = BENCH / "datasets" / "real" / "ground_truth_v3.json"
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "gt_v3" / "harden"
DUR = 126.79
COVER_TH = 0.4  # 冻结 finloc mask 阈值


def cell(video, t, name, w=None):
    p = OUT / "_frames" / f"{name}.png"
    try:
        ffmpeg_frame(video, t, p)
        caps = [fmt_ts(t)] + ([f"w={w:.2f}"] if w is not None else [])
        return (str(p), caps)
    except Exception as exc:
        print(f"  [skip {name}: {exc}]")
        return None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_frames").mkdir(exist_ok=True)
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    from device import resolve_backend
    backend = resolve_backend(preferred="auto")
    ff = FFmpegIO(FFMPEG, FFPROBE)
    feats = np.load(APP_INDEX / "features.npy")
    times = np.load(APP_INDEX / "times.npy")
    gt = json.loads(GT.read_text(encoding="utf-8"))
    pos = gt["positives"]
    by_id = {p["id"]: p for p in pos}

    # ---------- A) loose 密集复核 ----------
    loose_ids = [p["id"] for p in pos if p["tier"] == "loose"]
    print(f"A) loose 复核: {loose_ids}")
    need_frames: list[tuple[Path, float, str]] = []
    sheets_a = []
    for pid in loose_ids:
        p = by_id[pid]
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        reps = pick_reps(e0, e1, 3)
        o_reps = pick_reps(o0, o1, 6)
        for j, t in enumerate(reps):
            need_frames.append((EDIT, t, f"{pid}_e{j}"))
        for j, t in enumerate(o_reps):
            need_frames.append((ORIG, t, f"{pid}_o{j}"))
        sheets_a.append((pid, reps, o_reps, e0, e1, o0, o1))

    # ---------- B) verified 盲复核(四分位帧位,避开原 pick_reps 视角) ----------
    blind_ids = ["p01", "p13", "p19", "p25", "p33"]
    print(f"B) 盲复核: {blind_ids}")
    sheets_b = []
    for pid in blind_ids:
        p = by_id[pid]
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        e_qs = [e0 + (e1 - e0) * q for q in (0.2, 0.5, 0.8)]
        o_qs = [o0 + (o1 - o0) * q for q in (0.15, 0.5, 0.85)]
        for j, t in enumerate(e_qs):
            need_frames.append((EDIT, t, f"b_{pid}_e{j}"))
        for j, t in enumerate(o_qs):
            need_frames.append((ORIG, t, f"b_{pid}_o{j}"))
        sheets_b.append((pid, e_qs, o_qs, e0, e1, o0, o1))

    # 取帧(全部收集后统一执行)
    for video, t, name in need_frames:
        try:
            ffmpeg_frame(video, t, OUT / "_frames" / f"{name}.png")
        except Exception as exc:
            print(f"  [frame fail {name} t={t:.1f}: {exc}]")

    for pid, reps, o_reps, e0, e1, o0, o1 in sheets_a:
        rows = [
            [(str(OUT / "_frames" / f"{pid}_e{j}.png"), [fmt_ts(t)])
             for j, t in enumerate(reps)],
            [(str(OUT / "_frames" / f"{pid}_o{j}.png"), [fmt_ts(t)])
             for j, t in enumerate(o_reps)],
        ]
        compose_sheet(rows, OUT / f"loose_{pid}.jpg",
                      f"LOOSE {pid} ed({fmt_ts(e0)}..{fmt_ts(e1)}) og({fmt_ts(o0)}..{fmt_ts(o1)}) "
                      f"w={o1 - o0:.0f}s")
    print("A sheets done")

    for pid, e_qs, o_qs, e0, e1, o0, o1 in sheets_b:
        rows = [
            [(str(OUT / "_frames" / f"b_{pid}_e{j}.png"), [fmt_ts(t)])
             for j, t in enumerate(e_qs)],
            [(str(OUT / "_frames" / f"b_{pid}_o{j}.png"), [fmt_ts(t)])
             for j, t in enumerate(o_qs)],
        ]
        compose_sheet(rows, OUT / f"blind_{pid}.jpg",
                      f"BLIND {pid} ed({fmt_ts(e0)}..{fmt_ts(e1)}) og({fmt_ts(o0)}..{fmt_ts(o1)}) "
                      f"[{by_id[pid]['tier']}]")
    print("B sheets done")

    # ---------- C) 覆盖曲线边界精修(宽条目) ----------
    print("\nC) 边界精修(width>10s,覆盖阈值 0.4,窗=确认窗±5s)")
    # 先收集所有需要的编辑 rep 帧
    wide = [p for p in pos if (p["original"][1] - p["original"][0]) > 10]
    rep_map: dict[str, list[float]] = {}
    frames: list[np.ndarray] = []
    ids: list[str] = []
    for p in wide:
        reps = [min(t, DUR - 0.2) for t in pick_reps(p["edited"][0], p["edited"][1], 3)]
        rep_map[p["id"]] = reps
        for j, t in enumerate(reps):
            frames.append(ff.grab_frame(EDIT, t))
            ids.append(p["id"])
    efeats = backend.embed_frames(frames)
    print(f"embedded {len(frames)} rep frames for {len(wide)} wide entries")

    refinements = {}
    for p in wide:
        pid = p["id"]
        o0, o1 = p["original"]
        w0, w1 = max(0.0, o0 - 5.0), min(float(times.max()), o1 + 5.0)
        idx = np.where((times >= w0) & (times <= w1))[0]
        reps = rep_map[pid]
        sf = efeats[np.array([k for k, x in enumerate(ids) if x == pid])]
        cov = np.max(feats[idx] @ sf.T, axis=1)  # 每秒 max-over-rep 余弦
        tsec = times[idx]
        mask = cov >= COVER_TH
        # 最长连续覆盖段
        best_a = best_b = cur_a = None
        best_len = cur_len = 0
        for k, m in enumerate(mask):
            if m:
                if cur_a is None:
                    cur_a = k
                cur_len += 1
                if cur_len > best_len:
                    best_len, best_a, best_b = cur_len, cur_a, k
            else:
                cur_a, cur_len = None, 0
        if best_a is None:
            refinements[pid] = {"refined": None, "note": "no covered run >= th"}
            print(f"  {pid}: 无覆盖段(建议删除/降级)")
            continue
        r0, r1 = float(tsec[best_a]), float(tsec[best_b]) + 1.0
        refinements[pid] = {
            "old": [o0, o1], "refined": [round(r0, 1), round(r1, 1)],
            "cover_len_s": best_len, "window_w": round(len(idx), 0),
            "mean_cov_in_run": round(float(np.mean(cov[best_a:best_b + 1])), 3),
        }
        print(f"  {pid}: {o0:.0f}-{o1:.0f} -> {r0:.1f}-{r1:.1f} "
              f"(cover {best_len}s, mean {refinements[pid]['mean_cov_in_run']})")

    (OUT / "refine_proposal.json").write_text(
        json.dumps(refinements, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\nDONE ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
