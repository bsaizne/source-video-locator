# -*- coding: utf-8 -*-
"""方案1 多模态复核 — TN 喂饱探针翻转案例对照图（读图确证数字结论）。

数字（FINDINGS_TN_SAMPLING_COUPLING）主张：① 同 8fps 下两级切分(130) > TN(122)；② 喂饱 TN 从
116→122 证实采样耦合。本脚本按 GT 逐条 mark 找两类翻转并出对照图，逐张读图确证：
  A 两级胜TN：twofed_8=HIT 且 tnfed_8≠HIT  → 看 TN 定位帧是否真比两级错。
  B 喂饱救回：tnfed_8=HIT 且 tnfed_2≠HIT   → 看 8fps 喂饱后 TN 是否真锚对（ED 与 GT 同画面）。
每图 4 行：ED(GT编辑窗) | OG(GT真值) | OG(TN臂定位) | OG(两级臂定位)，逐帧读画面匹配。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import cv2

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BENCH = Path(r"D:\claudework\benchmark")
WORK = BENCH / "work"
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from media.ffmpeg import FFmpegIO  # noqa: E402
from measure_shot_recall import evaluate  # noqa: E402
from measure_mainspan_caliber import truncate_main  # noqa: E402

CASES = {"2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv", "ground_truth_v4.json"),
         "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv", "ground_truth_test1.json"),
         "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4", "ground_truth_test2.json"),
         "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4", "ground_truth_test3.json")}
OUT = WORK / "tnfed_visual"
MAX_SHEET = 8  # 每类每片最多出图数


def marks_and_results(batch_file, gt):
    raw = json.loads((WORK / batch_file).read_text(encoding="utf-8"))
    m = evaluate(gt, truncate_main(raw)["results"])
    return {x["id"]: x["mark"] for x in m["per_pos"]}, raw["results"]


def pick(res, e0, e1):
    best, bo = None, -1.0
    for r in res:
        s = float(r["edited_segment"]["start"]); t = float(r["edited_segment"]["end"])
        ov = min(t, e1) - max(s, e0)
        if ov > bo:
            best, bo = r, ov
    return best


def span_of(res, e0, e1):
    r = pick(res, e0, e1)
    if r is None:
        return (0.0, 0.0)
    return (float(r["original"]["candidate_start"]), float(r["original"]["candidate_end"]))


def strips(ff, path, span, H=210, step=0.04, nmax=12):
    """按 span 自适应密帧（约每 step 秒一帧，上限 nmax），时间戳精确到毫秒。"""
    a, b = span
    if b <= a:
        ts = [a]
    else:
        n = min(nmax, max(3, int(round((b - a) / step)) + 1))
        ts = [a + (b - a) * k / (n - 1) for k in range(n)]
    tiles = []
    for t in ts:
        img = np.asarray(ff.grab_frame(Path(path), max(0.0, t)))
        hh, ww = img.shape[:2]
        im = cv2.resize(img, (max(1, int(round(ww * H / hh))), H), interpolation=cv2.INTER_AREA)
        bar = np.full((20, im.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, "%.3f" % t, (3, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
        tiles.append(np.vstack([bar, im]))
    gap = np.full((tiles[0].shape[0], 4, 3), 255, np.uint8)
    row = tiles[0]
    for c in tiles[1:]:
        row = np.hstack([row, gap, c])
    return row


def label_row(row, text, color):
    lab = np.full((row.shape[0], 200, 3), 255, np.uint8)
    cv2.putText(lab, text, (5, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.46, color, 1, cv2.LINE_AA)
    return np.hstack([lab, row])


def sheet(ff, case, gid, ed, om, gt_ed, gt_og, rows_spec, tag):
    rows = []
    for label, span, color in rows_spec:
        rows.append(label_row(strips(ff, om if "OG" in label else ed, span), label, color))
    w = max(r.shape[1] for r in rows)

    def pad(r):
        return r if r.shape[1] == w else np.hstack([r, np.full((r.shape[0], w - r.shape[1], 3), 255, np.uint8)])
    rows = [pad(r) for r in rows]
    head = np.full((26, w, 3), 255, np.uint8)
    cv2.putText(head, "%s %s [%s] GTed %.2f-%.2f OG %.2f-%.2f" % (
        case, gid, tag, gt_ed[0], gt_ed[1], gt_og[0], gt_og[1]),
        (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    sep = np.full((3, w, 3), 200, np.uint8)
    out = np.vstack([head] + [x for r in rows for x in (r, sep)])
    fp = OUT / ("%s_%s_%s.png" % (case, gid, tag))
    cv2.imwrite(str(fp), out)
    return fp


def main() -> int:
    only = (sys.argv[1].upper() if len(sys.argv) > 1 else None)  # 'A' / 'B' / None=both
    OUT.mkdir(exist_ok=True)
    ff = FFmpegIO()
    n_a = n_b = 0
    for case, (ed, om, gt_name) in CASES.items():
        gt = json.loads((BENCH / "datasets/real" / gt_name).read_text(encoding="utf-8"))
        mt2, r_t2 = marks_and_results("tnfed_2_%s.results.json" % case, gt)
        mt8, r_t8 = marks_and_results("tnfed_8_%s.results.json" % case, gt)
        mw8, r_w8 = marks_and_results("twofed_8_%s.results.json" % case, gt)
        pos = {p["id"]: p for p in gt["positives"]}
        for gid, p in pos.items():
            gt_ed, gt_og = p["edited"], p["original"]
            # A 两级胜 TN
            if only in (None, "A") and mw8.get(gid) == "HIT" and mt8.get(gid) != "HIT" and n_a < MAX_SHEET:
                sheet(ff, case, gid, ed, om, gt_ed, gt_og, [
                    ("ED", gt_ed, (0, 0, 0)),
                    ("OG(GT)", gt_og, (140, 0, 140)),
                    ("OG(tnfed8=%s)" % mt8.get(gid), span_of(r_t8, *gt_ed), (0, 0, 180)),
                    ("OG(twofed8=%s)" % mw8.get(gid), span_of(r_w8, *gt_ed), (0, 130, 0)),
                ], "A_twoWin")
                n_a += 1
            # B 喂饱救回
            if only in (None, "B") and mt8.get(gid) == "HIT" and mt2.get(gid) != "HIT" and n_b < MAX_SHEET:
                sheet(ff, case, gid, ed, om, gt_ed, gt_og, [
                    ("ED", gt_ed, (0, 0, 0)),
                    ("OG(GT)", gt_og, (140, 0, 140)),
                    ("OG(tnfed2=%s)" % mt2.get(gid), span_of(r_t2, *gt_ed), (0, 0, 180)),
                    ("OG(tnfed8=%s)" % mt8.get(gid), span_of(r_t8, *gt_ed), (0, 130, 0)),
                ], "B_fedRescue")
                n_b += 1
    print("A 两级胜TN 出图 %d 张 | B 喂饱救回 出图 %d 张 -> %s" % (n_a, n_b, OUT), flush=True)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
