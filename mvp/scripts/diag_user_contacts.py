"""诊断 Phase B — 对 12 段生成「编辑段 ↔ 定位原片区」多模态 contact sheet。

读 mvp/benchmark/user_case/summary.json 的 per-segment 定位，对每段抽
-edited[edited_span] 3 帧
-located_original[original_span] 3 帧
拼成对比图（行=EDITED / LOCATED，caption 带 confidence/rank/score/reasons）。

运行（venv python，需 D:/claudework/benchmark 下 tools/ffmpeg.exe + 素材存在）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/diag_user_contacts.py
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
CONTACT = OUT / "contact"
TMP = CONTACT / "_frames"

import subprocess  # noqa: E402  (verify ffmpeg available)


def main() -> int:
    summary = json.loads((OUT / "summary.json").read_text(encoding="utf-8"))
    segs = summary["segments"]
    CONTACT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    print(f"=== {len(segs)} segments ===")
    for s in segs:
        idx = s["idx"]
        e0, e1 = s["edited"]
        o0, o1 = s["original"]
        conf = s["confidence"]
        rank = s["candidate_rank"]
        score = s["score"]
        reasons = ",".join(s["reasons"]) if s["reasons"] else "-"
        title = (f"seg[{idx}] edited=({fmt_ts(e0)}..{fmt_ts(e1)})  "
                 f"located=({fmt_ts(o0)}..{fmt_ts(o1)})  {conf} score={score} rank={rank}")
        n = 3
        pad = 0.0  # no pad; exact query unit span
        # edited frames
        e_reps = pick_reps(e0, e1, n)
        e_cells = []
        for j, t in enumerate(e_reps):
            p = TMP / f"s{idx}_ed_{j}.png"
            try:
                ffmpeg_frame(EDIT, t, p)
                e_cells.append((str(p), [fmt_ts(t)]))
            except Exception as exc:
                print(f"  [skip edited seg{idx} t={t:.1f}: {exc}")
                e_cells.append(None)
        # located original frames
        o_reps = pick_reps(o0, o1, n)
        o_cells = []
        for j, t in enumerate(o_reps):
            p = TMP / f"s{idx}_orig_{j}.png"
            try:
                ffmpeg_frame(ORIG, t, p)
                o_cells.append((str(p), [fmt_ts(t)]))
            except Exception as exc:
                print(f"  [skip located seg{idx} t={t:.1f}: {exc}")
                o_cells.append(None)
        rows = [e_cells, o_cells]
        out_png = CONTACT / f"s{idx}_comparison.jpg"
        compose_sheet(rows, out_png, title)
        print(f"  seg[{idx}]: {out_png.name}  ({conf} score={score} rank={rank}) [{reasons}]")

        # also persist a case.json (machine-readable) for this segment
        payload = {
            "idx": idx, "edited": [e0, e1], "located": [o0, o1],
            "confidence": conf, "score": score, "reasons": s["reasons"],
            "montage_flag": s["montage_flag"], "failure_reason": s["failure_reason"],
            "candidate_rank": rank, "alternatives": s["alternatives"],
            "edited_reps": [round(x, 3) for x in e_reps],
            "located_reps": [round(x, 3) for x in o_reps],
        }
        (CONTACT / f"s{idx}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nDONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
