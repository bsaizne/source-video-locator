"""研究验证 — 对召回优化后的输出抽样生成 contact sheet，多模态核验新增子 span 是否真镜头。

读 user_results.json（中间召回参数输出），对指定段生成：编辑帧 vs 定位原片帧 + 各子 span 原片帧。
运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/verify_recall_sample.py <seg_idx...>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))  # -> src (diagnostics)
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps
from diagnostics.contact_sheet import compose_sheet

BENCH = Path(__file__).resolve().parents[2]
EDIT = Path("D:/video/1.mp4")
ORIG = Path("D:/video/2.mkv")
OUT = BENCH / "mvp" / "benchmark" / "user_case"
TMP = OUT / "_frames2"
N = 3


def main() -> int:
    d = json.load(open(OUT / "user_results.json", encoding="utf-8"))
    res = d["results"]
    TMP.mkdir(parents=True, exist_ok=True)
    args = [int(a) for a in sys.argv[1:]] or [i for i, r in enumerate(res) if r["original_segments"]][:4]
    for idx in args:
        r = res[idx]
        es, o = r["edited_segment"], r["original"]
        os_ = r.get("original_segments", [])
        title = (f"seg[{idx}] edited({es['start']:.1f}..{es['end']:.1f}) -> "
                 f"orig({o['candidate_start']:.1f}..{o['candidate_end']:.1f}) "
                 f"{r['confidence']} {r.get('confidence_score', 0):.2f} mont={r['montage_flag']}")
        e_cells = []
        for j, t in enumerate(pick_reps(es["start"], es["end"], N)):
            p = TMP / f"s{idx}_e{j}.png"
            try:
                ffmpeg_frame(EDIT, t, p); e_cells.append((str(p), [fmt_ts(t)]))
            except Exception:
                e_cells.append(None)
        o_cells = []
        for j, t in enumerate(pick_reps(o["candidate_start"], o["candidate_end"], N)):
            p = TMP / f"s{idx}_o{j}.png"
            try:
                ffmpeg_frame(ORIG, t, p); o_cells.append((str(p), [fmt_ts(t)]))
            except Exception:
                o_cells.append(None)
        rows = [e_cells, o_cells]
        # 各子 span 一行（编辑段帧 vs 子 span 原片帧）
        for si, s in enumerate(os_):
            sc, oc = [], []
            for j, t in enumerate(pick_reps(es["start"], es["end"], N)):
                p = TMP / f"s{idx}_se{si}_{j}.png"; ffmpeg_frame(EDIT, t, p)
                sc.append((str(p), [fmt_ts(t)]))
            for j, t in enumerate(pick_reps(s["candidate_start"], s["candidate_end"], N)):
                p = TMP / f"s{idx}_so{si}_{j}.png"; ffmpeg_frame(ORIG, t, p)
                oc.append((str(p), [f"{fmt_ts(t)} cover{s['cover']:.2f}"]))
            rows.append(sc); rows.append(oc)
        out_png = OUT / f"recall_s{idx}.jpg"
        compose_sheet(rows, out_png, title)
        print(f"  seg[{idx}]: {out_png.name} ({r['confidence']}) sub_spans={len(os_)}")
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
