# -*- coding: utf-8 -*-
"""18 条 GT 复核工单的逐帧裁决出图（2026-09-30 续32 后续，用户令逐帧裁决）。

`probe_gt_tickets_retrieval.py` 用生产检索自动判别出 16 GT 疑错 / 2 同源重复 / 0 推翻，
但交接铁律 = 采纳/改 GT 结论不得只靠数据 ⇒ 本脚本把每条工单出成三格读图行，交用户逐帧确认：

每行三格：
  1) GT 编辑窗中帧（ED 里这段到底长什么样）
  2) 我方落位原片中帧（OURS 窗中帧）
  3) GT 登记原片窗中帧（GT 窗中帧）
读法：1≈2 且 1≠3 ⇒ GT 疑错坐实；1≈2 且 1≈3 ⇒ 同源重复坐实（镜头两处）；1 与 2 不像 ⇒ 我方错。

零 runtime / 零 GT 改动。出图走 `src/diagnostics/frame_sampler`（FFmpeg 精确 seek）。
产物 `work/gt_tickets_visual/`（文件名自带 case+行 ID 区分度）。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/review_gt_tickets_visual.py
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

from diagnostics.contact_sheet import compose_sheet   # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

TICKETS = BENCH / "work" / "gt_tickets_retrieval.json"
OUT = BENCH / "work" / "gt_tickets_visual"
SRC_OF_CASE = {"2mkv": "work/fastglobal_default_2mkv.results.json",
               "test1": "work/fastglobal_default_test1.results.json",
               "test2": "work/fastglobal_default_test2.results.json",
               "test3": "work/fastglobal_default_test3.results.json"}
ROWS_PER_SHEET = 3


def _cell(video, t, cap, tag):
    p = OUT / "frames" / f"{tag}.png"
    try:
        ffmpeg_frame(video, max(0.0, float(t)), p)
        return (str(p), [cap, fmt_ts(t)])
    except Exception as exc:
        return (None, [f"{cap} (取帧失败: {exc})", ""])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    tickets = json.loads(TICKETS.read_text(encoding="utf-8"))
    paths = {}
    for case in {t["case"] for t in tickets}:
        raw = json.loads((BENCH / SRC_OF_CASE[case]).read_text(encoding="utf-8"))
        paths[case] = (Path(raw["original_video"]), Path(raw["edited_video"]))

    index, rows = [], []
    for tk in tickets:
        src, ed = paths[tk["case"]]
        tag = f"{tk['case']}_{tk['gt_row']}_seg{tk['seg']}"
        e_mid = (tk["ed"][0] + tk["ed"][1]) / 2.0
        a_mid = (tk["ours"][0] + tk["ours"][1]) / 2.0
        g_mid = (tk["gt_og"][0] + tk["gt_og"][1]) / 2.0
        rows.append([
            _cell(ed, e_mid, f"GT {tk['gt_row']} ED", f"{tag}_ed"),
            _cell(src, a_mid, f"OURS {tk['ours'][0]:.0f}-{tk['ours'][1]:.0f}", f"{tag}_ours"),
            _cell(src, g_mid, f"GT窗 {tk['gt_og'][0]:.0f}-{tk['gt_og'][1]:.0f}", f"{tag}_gtog"),
        ])
        index.append({**{k: tk[k] for k in
                         ("case", "seg", "gt_row", "ed", "ours", "gt_og",
                          "offset_s", "verdict", "note")},
                      "sheet_tag": tag})
    for i in range(0, len(rows), ROWS_PER_SHEET):
        chunk = rows[i:i + ROWS_PER_SHEET]
        sub = index[i:i + ROWS_PER_SHEET]
        cases = sorted({s["case"] for s in sub})
        out = OUT / f"gt_tickets_{i // ROWS_PER_SHEET + 1:02d}_{'-'.join(cases)}.png"
        compose_sheet(chunk, out,
                      "GT tickets %d-%d: GT_ED | OURS | GT_OG  (1~2 same & != 3 => GT wrong)"
                      % (i + 1, min(i + ROWS_PER_SHEET, len(rows))))
        print("[%s] %s (%d 行: %s)" % (cases, out.name, len(chunk),
              ", ".join(f"{s['case']}/{s['gt_row']}/s{s['seg']}" for s in sub)), flush=True)
    (OUT / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False),
                                    encoding="utf-8")
    print("\n共 %d 行裁决证据, 产物 -> %s" % (len(index), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
