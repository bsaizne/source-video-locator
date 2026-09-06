"""多案例裁决图生成——对 cases/<case>_results.json 的每段生成「编辑 vs 定位原片」对照图。

用法:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/gen_case_sheets.py <case> [only_high]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "src"))

from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps  # noqa: E402
from diagnostics.contact_sheet import compose_sheet  # noqa: E402

OUT = BENCH / "mvp" / "benchmark" / "user_case" / "cases"


def main() -> int:
    case = sys.argv[1]
    only_high = len(sys.argv) > 2 and sys.argv[2] == "only_high"
    res = json.loads((OUT / f"{case}_results.json").read_text(encoding="utf-8"))["results"]
    video = json.loads((OUT / f"{case}_results.json").read_text(encoding="utf-8"))["edited_video"]
    original = json.loads((OUT / f"{case}_results.json").read_text(encoding="utf-8"))["original_video"]
    TMP = OUT / case / "_frames"
    TMP.mkdir(parents=True, exist_ok=True)
    n = 0
    for i, r in enumerate(res):
        if only_high and r["confidence"] != "HIGH":
            continue
        e0, e1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        o0, o1 = r["original"]["candidate_start"], r["original"]["candidate_end"]
        rows = []
        for tag, vid, a, b in (("ed", Path(video), e0, e1), ("og", Path(original), o0, o1)):
            cells = []
            for j, t in enumerate(pick_reps(a, b, 3)):
                p = TMP / f"{case}_r{i}_{tag}{j}.png"
                try:
                    ffmpeg_frame(vid, t, p)
                    cells.append((str(p), [fmt_ts(t)]))
                except Exception:
                    cells.append(None)
            rows.append(cells)
        subs = r.get("original_segments") or []
        if subs:
            rows.append([(str(OUT / case / "_frames" / f"{case}_r{i}_s{j}.png"), [])
                         for j in range(0)])
        title = (f"{case} r[{i}] ed({fmt_ts(e0)}..{fmt_ts(e1)}) og({fmt_ts(o0)}..{fmt_ts(o1)}) "
                 f"{r['confidence']} score={r['confidence_score']:.2f} "
                 f"nis={int(bool(r.get('not_in_source')))}")
        compose_sheet(rows, OUT / case / f"r{i:02d}.jpg", title)
        n += 1
    print(f"{case}: {n} sheets -> {OUT / case}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
