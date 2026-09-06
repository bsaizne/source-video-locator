"""研究验证 — 对蒙太奇多段定位原型恢复的子 span 做多模态逐帧核验。

读 montage_research/montage_localize.json，对指定段构建 contact sheet：
行 = 该段的每个子 span：〔edited_sub 帧 | 原片 span 帧〕。
用于确认恢复出的子 span 是否真对应编辑子区间的内容（非相似外观误配）。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/research_verify_montage.py 2 3 5
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
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "montage_research"
TMP = OUT / "_frames"
N = 3


def main() -> int:
    segs = json.loads((OUT / "montage_localize.json").read_text(encoding="utf-8"))["segments"]
    by_idx = {s["idx"]: s for s in segs}
    TMP.mkdir(parents=True, exist_ok=True)
    args = [int(a) for a in sys.argv[1:]] or [2, 3]
    for idx in args:
        seg = by_idx.get(idx)
        if not seg:
            print(f"[{idx}] not found"); continue
        sub = seg["sub_spans"]
        title = (f"seg[{idx}] edited={seg['edited']} mode={seg['mode']} "
                 f"sig_clusters={seg['n_clusters']}")
        rows = []
        for si, s in enumerate(sub):
            es, ee = s["edited_sub"]
            sp = s["span"]
            ed_cells, or_cells = [], []
            if sp:
                o0, o1 = sp
                t_reps = pick_reps(o0, o1, N)
            else:
                t_reps = pick_reps(es, ee, N)
            for j, t in enumerate(t_reps):
                p = TMP / f"s{idx}_{si}_e{j}.png"
                try:
                    ffmpeg_frame(EDIT, t, p) if sp else None
                except Exception:
                    pass
            # edited_sub frames
            e_reps = pick_reps(es, ee, N)
            for j, t in enumerate(e_reps):
                p = TMP / f"s{idx}_{si}_ed{j}.png"
                try:
                    ffmpeg_frame(EDIT, t, p)
                    ed_cells.append((str(p), [fmt_ts(t)]))
                except Exception as exc:
                    print(f"  skip e seg{idx} s{si} t={t:.1f}: {exc}"); ed_cells.append(None)
            # original span frames
            if sp:
                for j, t in enumerate(pick_reps(sp[0], sp[1], N)):
                    p = TMP / f"s{idx}_{si}_or{j}.png"
                    try:
                        ffmpeg_frame(ORIG, t, p)
                        or_cells.append((str(p), [fmt_ts(t)]))
                    except Exception as exc:
                        print(f"  skip o seg{idx} s{si} t={t:.1f}: {exc}"); or_cells.append(None)
            else:
                or_cells = [None] * N
            rows.append(ed_cells)
            rows.append(or_cells)
        out = OUT / f"verify_s{idx}.jpg"
        compose_sheet(rows, out, title)
        print(f"  seg[{idx}]: {out.name} ({len(sub)} sub-spans)")
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
