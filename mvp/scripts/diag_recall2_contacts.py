"""诊断(召回优化后复检)——为当前 user_results.json 的 14 段生成多模态对照图,
并出 GT 冲突裁决图(datasets/real GT 6599s/6350s 位置 vs 蒙太奇研究验证 GT 1126-1602s 位置)。

只做诊断,不碰算法。运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/diag_recall2_contacts.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "src"))  # research diagnostics helpers

from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps  # noqa: E402
from diagnostics.contact_sheet import compose_sheet  # noqa: E402

EDIT = Path("D:/video/1.mp4")
ORIG = Path("D:/video/2.mkv")
OUT = BENCH / "mvp" / "benchmark" / "user_case"
CONTACT = OUT / "contact2"
TMP = CONTACT / "_frames"


def cell(video, t, name):
    p = TMP / f"{name}.png"
    try:
        ffmpeg_frame(video, t, p)
        return (str(p), [fmt_ts(t)])
    except Exception as exc:
        print(f"  [skip {name} t={t:.1f}: {exc}]")
        return None


def main() -> int:
    CONTACT.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    res = json.loads((OUT / "user_results.json").read_text(encoding="utf-8"))["results"]

    # ---- A. 每段: edited / main / subs ----
    for i, r in enumerate(res):
        e0, e1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        o0, o1 = r["original"]["candidate_start"], r["original"]["candidate_end"]
        rows = [
            [cell(EDIT, t, f"r{i}_ed{j}") for j, t in enumerate(pick_reps(e0, e1, 3))],
            [cell(ORIG, t, f"r{i}_og{j}") for j, t in enumerate(pick_reps(o0, o1, 3))],
        ]
        subs = r.get("original_segments") or []
        if subs:
            rows.append([cell(ORIG, (s["candidate_start"] + s["candidate_end"]) / 2,
                              f"r{i}_sub{j}") for j, s in enumerate(subs[:6])])
        title = (f"r[{i}] ed({fmt_ts(e0)}..{fmt_ts(e1)}) main({fmt_ts(o0)}..{fmt_ts(o1)}) "
                 f"{r['confidence']} score={r['confidence_score']:.2f} "
                 f"montage={int(bool(r.get('montage_flag')))} subs={len(subs)}")
        compose_sheet(rows, CONTACT / f"r{i}_comparison.jpg", title)
        print(f"r[{i}] done")

    # ---- B. GT 冲突裁决 ----
    datasets_gt = [
        (7.5, 8.5, 6599.5, 6600.5), (19.0, 20.0, 6599.1, 6600.1),
        (27.0, 28.0, 6350.3, 6351.3), (28.5, 29.5, 6601.1, 6602.1),
        (30.0, 31.0, 1302.8, 1303.8), (35.5, 36.5, 6349.8, 6350.8),
        (46.5, 47.5, 6598.1, 6599.1),
    ]
    for k, (ea, eb, oa, ob) in enumerate(datasets_gt):
        rows = [
            [cell(EDIT, t, f"gtd{k}_ed{j}") for j, t in enumerate(pick_reps(ea, eb, 2))],
            [cell(ORIG, t, f"gtd{k}_og{j}") for j, t in enumerate(pick_reps(oa, ob, 2))],
        ]
        compose_sheet(rows, CONTACT / f"gtdatasets_{k}.jpg",
                      f"datasetsGT{k+1} ed({fmt_ts(ea)}..{fmt_ts(eb)}) vs ORIG({fmt_ts(oa)}..{fmt_ts(ob)})")
        print(f"gtdatasets_{k} done")

    verify_gt = [
        (6.5, 10.0, 1126.0, 1138.0), (19.0, 21.0, 1288.0, 1312.0),
        (26.0, 29.0, 1332.0, 1348.0), (28.0, 30.0, 1340.0, 1348.0),
        (30.0, 32.0, 1374.0, 1392.0), (35.0, 37.5, 1394.0, 1416.0),
        (46.0, 48.5, 1578.0, 1602.0),
    ]
    for k, (ea, eb, oa, ob) in enumerate(verify_gt):
        rows = [
            [cell(EDIT, t, f"gtv{k}_ed{j}") for j, t in enumerate(pick_reps(ea, eb, 2))],
            [cell(ORIG, t, f"gtv{k}_og{j}") for j, t in enumerate(pick_reps(oa, ob, 2))],
        ]
        compose_sheet(rows, CONTACT / f"gtverify_{k}.jpg",
                      f"verifyGT{k+1} ed({fmt_ts(ea)}..{fmt_ts(eb)}) vs ORIG({fmt_ts(oa)}..{fmt_ts(ob)})")
        print(f"gtverify_{k} done")

    print("ALL DONE ->", CONTACT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
