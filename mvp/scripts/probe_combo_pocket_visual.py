# -*- coding: utf-8 -*-
"""复现链「同粒度独家命中」16 条的逐图复核出图（2026-09-29 续31）。

`probe_combo_caliber_all_cases.py` 给出四片合计 R2 复现链截等长 83/139 vs R4 我方截等长 105/139，
但逐 ID 差集里有 **16 条是复现链独家命中**（我方主 span 截等长打不中）。本脚本把这 16 条
逐条出四格图，判一件事：**复现链是真锚得准，还是窗口走运/口径假象**。

每行四格：
  1) GT 编辑窗中帧   2) GT 原片窗中帧   3) 复现链截等长落位中帧   4) 我方主 span 中帧
读法：3 与 1/2 同内容 ⇒ 复现链确实锚对；3 与 2 不同 ⇒ 命中是截窗碰巧覆盖（口径假象）。

零 runtime / 零 GT / 零 GPU。出图走 `src/diagnostics/frame_sampler`（FFmpeg 精确 seek）。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_combo_pocket_visual.py
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
SBOX = Path(r"D:\claudework\cutmatch-analysis\sandbox\out")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from diagnostics.contact_sheet import compose_sheet        # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402
from measure_shot_recall import evaluate                    # noqa: E402
from measure_mainspan_caliber import truncate_main          # noqa: E402
from probe_combo_dual_caliber import caliber2, load_rows    # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "combo_pocket_visual"
ROWS_PER_SHEET = 4
CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json", "localization_2mkv.json",
     "work/fastglobal_default_2mkv.results.json", "D:/video/2.mkv", "D:/video/1.mp4"),
    ("test1", "datasets/real/ground_truth_test1.json", "localization_comboA_test1.json",
     "work/fastglobal_default_test1.results.json", None, None),
    ("test2", "datasets/real/ground_truth_test2.json", "localization_test2.json",
     "work/fastglobal_default_test2.results.json", None, None),
    ("test3", "datasets/real/ground_truth_test3.json", "localization_test3.json",
     "work/fastglobal_default_test3.results.json", None, None),
]


def _cell(video, t, cap, tag):
    if video is None or t is None:
        return None
    p = OUT / "frames" / f"{tag}.png"
    try:
        ffmpeg_frame(video, max(0.0, float(t)), p)
        return (str(p), [f"{cap} {fmt_ts(t)}"])
    except Exception:
        return None


def main() -> int:
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    rep = json.loads((BENCH / "work/combo_caliber_all_cases.json").read_text(encoding="utf-8"))
    index = []
    for case, gt_rel, loc_name, ours_rel, src_ovr, ed_ovr in CASES:
        row = next((c for c in rep["cases"] if c["case"] == case), None)
        if not row:
            continue
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        src = Path(src_ovr or raw["original_video"])
        ed = Path(ed_ovr or raw["edited_video"])
        # 我方截等长口径的逐 GT 命中
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            m = evaluate(gt, truncate_main(raw)["results"])
        our_hit = {x["id"]: x["mark"] for x in m["per_pos"]}
        proxy = {x["id"]: x for x in caliber2(load_rows(SBOX / loc_name),
                                              gt["positives"], gt["negatives"])["per"]}
        pockets = [pid for pid, x in proxy.items() if x["hit"] and our_hit.get(pid) != "HIT"]
        if not pockets:
            continue
        rows = []
        for pid in pockets:
            p = next(x for x in gt["positives"] if x["id"] == pid)
            e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
            det = proxy[pid]["detail"]                      # {qid, t0, t1} 复现链截等长落位
            best, om0, om1 = 0.0, None, None
            for r in raw["results"]:                        # 我方与该 GT 编辑窗重叠最多的那段
                re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
                ov = min(e1, re1) - max(e0, re0)
                if ov > best:
                    best = ov
                    om0, om1 = (r["original"]["candidate_start"],
                                r["original"]["candidate_end"])
            rows.append([
                _cell(ed, (e0 + e1) / 2, f"GT {pid} ED", f"{case}_{pid}_gt_ed"),
                _cell(src, (o0 + o1) / 2, f"GT {pid} OG", f"{case}_{pid}_gt_om"),
                _cell(src, (det["t0"] + det["t1"]) / 2,
                      f"PROXY {det['t0']:.0f}-{det['t1']:.0f}", f"{case}_{pid}_proxy"),
                _cell(src, ((om0 + om1) / 2 if om0 is not None else None),
                      f"OURS {om0:.0f}-{om1:.0f}" if om0 is not None else "OURS none",
                      f"{case}_{pid}_ours")])
            index.append({"case": case, "id": pid, "gt_ed": [e0, e1], "gt_og": [o0, o1],
                          "proxy_span": [det["t0"], det["t1"]],
                          "our_main_span": [om0, om1], "our_mark": our_hit.get(pid)})
        for i in range(0, len(rows), ROWS_PER_SHEET):
            chunk = rows[i:i + ROWS_PER_SHEET]
            out = OUT / f"{case}_pockets_p{i // ROWS_PER_SHEET + 1}.png"
            compose_sheet(chunk, out, "%s pockets: GT_ED | GT_OG | PROXY | OURS" % case)
            print("[%s] %s (%d 行)" % (case, out.name, len(chunk)), flush=True)
    (OUT / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False),
                                    encoding="utf-8")
    print("\n共 %d 条复现链独家命中, 清单 -> %s" % (len(index), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
