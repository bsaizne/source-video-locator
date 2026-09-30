# -*- coding: utf-8 -*-
"""GT 16 行（12 唯一行）镜头级边界精修 · 出证（2026-09-30，用户令）。

背景：续32 GT 工单裁决把 12 行重锚定到「我方落位区间」（2s 管线 span 或并集），
口径约定「镜头级边界精修后续另做」。本脚本产出精修提案 + 逐行读图证据，
**不改 GT**——用户逐帧确认后才应用（apply_gt_boundary_refine 另一步）。

方法（每行）：
  1. ED 编辑窗 4fps 采帧（≤20），GT 窗 ±5s 源片 4fps 采帧，DINOv2 CLS（DML 硬断言）；
  2. 每 ED 帧在源片网格上 argmax 对位 → 偏移中位数 δ（鲁棒）；
  3. 精修窗 = [e0+δ, e1+δ]（1:1 直切语义）；
  4. 边界切割度 = 跨精修边界 ±0.25s 两源帧的余弦（低 = 真实镜头切换）。
证据：每行四格 GT_ED | 精修起点 | 精修中点 | 精修终点（work/gt_boundary_refine/）。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_gt_boundary_refine.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))

import numpy as np  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend   # noqa: E402
from diagnostics.contact_sheet import compose_sheet   # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402
from infrastructure.config import load_config          # noqa: E402
from media.ffmpeg import FFmpegIO                      # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "gt_boundary_refine"
GT_OF_CASE = {"2mkv": "datasets/real/ground_truth_v4.json",
              "test1": "datasets/real/ground_truth_test1.json",
              "test2": "datasets/real/ground_truth_test2.json",
              "test3": "datasets/real/ground_truth_test3.json"}
ROWS = [("2mkv", "p10"), ("2mkv", "p31"), ("2mkv", "p33"),
        ("test1", "t1r08a"), ("test2", "t2r01b"), ("test2", "t2r02a"),
        ("test2", "t2r03a"), ("test2", "t2r05a"), ("test2", "t2r05b"),
        ("test2", "t2r07a"), ("test3", "t3r03a"), ("test3", "t3r04b")]
SRC_FPS, ED_FPS, PAD = 4.0, 4.0, 5.0
MAX_SRC = 90


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
    print("BACKEND_SELECTED type=%s" % type(svc.backend).__name__, flush=True)
    fio = FFmpegIO(Path(os.environ["MEDIA_FFMPEG"]), Path(os.environ["MEDIA_FFPROBE"]))

    def embed(frame):
        v = svc.backend.embed_frames([frame])[0]
        return v / max(1e-8, float(np.linalg.norm(v)))

    gts = {c: json.loads((BENCH / g).read_text(encoding="utf-8"))
           for c, g in GT_OF_CASE.items()}
    paths = {}
    index, rows = [], []
    for case, pid in ROWS:
        gt = gts[case]
        if case not in paths:
            # 源片/编辑片路径从生产结果批取（2mkv 特例与其一致）
            raw = json.loads((BENCH / f"work/fastglobal_default_{case}.results.json")
                             .read_text(encoding="utf-8"))
            paths[case] = (Path(raw["original_video"]), Path(raw["edited_video"]))
        src, ed = paths[case]
        p = next(x for x in gt["positives"] if x["id"] == pid)
        e0, e1 = p["edited"][0], p["edited"][1]
        o0, o1 = p["original"][0], p["original"][1]
        # 源片稠密网格（±PAD）
        s0, s1 = max(0.0, o0 - PAD), o1 + PAD
        n_src = min(MAX_SRC, max(20, int((s1 - s0) * SRC_FPS)))
        src_t = np.array([s0 + (s1 - s0) * (i + 0.5) / n_src for i in range(n_src)])
        src_f = np.stack([embed(fio.grab_frame(src, float(t))) for t in src_t])
        # ED 帧
        dur = e1 - e0
        n_ed = max(3, min(20, int(dur * ED_FPS)))
        ed_t = [e0 + dur * (i + 0.5) / n_ed for i in range(n_ed)]
        ed_f = np.stack([embed(fio.grab_frame(ed, float(t))) for t in ed_t])
        S = ed_f @ src_f.T                                # n_ed × n_src
        offs = [float(src_t[int(np.argmax(S[i]))]) - et for i, et in enumerate(ed_t)]
        offs.sort()
        delta = float(np.median(offs))
        agree = sum(1 for o in offs if abs(o - delta) <= 0.5) / len(offs)
        r0, r1 = e0 + delta, e1 + delta
        # 边界切割度：跨边界 ±0.25s 两源帧余弦（低 = 真切换）
        def cutness(boundary):
            a = src_t[np.argmin(np.abs(src_t - (boundary - 0.25)))]
            b2 = src_t[np.argmin(np.abs(src_t - (boundary + 0.25)))]
            fa = src_f[int(np.argmin(np.abs(src_t - a)))]
            fb = src_f[int(np.argmin(np.abs(src_t - b2)))]
            return float(fa @ fb)
        row = {"case": case, "id": pid, "gt_ed": [e0, e1], "gt_og_cur": [o0, o1],
               "delta": round(delta, 2), "agree": round(agree, 2),
               "proposed": [round(r0, 2), round(r1, 2)],
               "cut_start": round(cutness(r0), 3), "cut_end": round(cutness(r1), 3),
               "offsets": [round(o, 1) for o in offs]}
        index.append(row)
        tag = f"{case}_{pid}"
        cells = []
        for vid, t, cap in ((ed, (e0 + e1) / 2, "GT ED"),
                            (src, r0, "START"),
                            (src, (r0 + r1) / 2, "MID"),
                            (src, r1, "END")):
            pp = OUT / "frames" / f"{tag}_{cap}.png"
            try:
                ffmpeg_frame(vid, max(0.0, float(t)), pp)
                cells.append((str(pp), [f"{cap} {fmt_ts(t)}",
                                        f"{t:.2f}s" if cap != "GT ED" else ""]))
            except Exception:
                cells.append(None)
        rows.append(cells)
        print("[%-5s %-7s] GT=%s-%s → 提案 %s-%s (δ=%.2f agree=%.2f "
              "cut_start=%.2f cut_end=%.2f)" % (
                  case, pid, o0, o1, row["proposed"][0], row["proposed"][1],
                  delta, agree, row["cut_start"], row["cut_end"]), flush=True)
    for i in range(0, len(rows), 3):
        compose_sheet(rows[i:i + 3], OUT / f"refine_{i // 3 + 1:02d}.png",
                      "GT boundary refine %d-%d: GT_ED | START | MID | END"
                      % (i + 1, i + 3))
    (OUT / "proposals.json").write_text(json.dumps(index, ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    print("\n%d 行精修提案 -> %s (proposals.json + refine_*.png)" % (len(index), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
