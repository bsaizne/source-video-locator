"""检索天花板审计的可视化: [QUERY | 窗内最佳帧(检索) | 运行期定位 span 帧 | GT 窗中点帧] (2026-09-26).

输入: work/loc_retrieval_audit.json(含每例窗内最佳帧 t_best) + 结果批(运行期 span) + GT.
用途: 落实"先看图再下结论" —— 确认 R1/R2 案例(定位层)的检索最佳帧与查询画面同内容,
      以及 R3(t2r05a) 的最佳帧确实不同(特征层失败).
零 runtime 改动.

用法: python mvp/scripts/visualize_loc_audit.py --case-id test2/t2r03b --case-id 2mkv/p30 ...
      python mvp/scripts/visualize_loc_audit.py --all-nonhit   # 22 例非 HIT 全部出图
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))

CASES = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv",
             "datasets/real/ground_truth_v4.json", "work/rerun_2mkv_perfopt.results.json"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv",
              "datasets/real/ground_truth_test1.json", "work/rerun_test1_perfopt.results.json"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4",
              "datasets/real/ground_truth_test2.json", "work/rerun_test2_perfopt.results.json"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4",
              "datasets/real/ground_truth_test3.json", "work/rerun_test3_perfopt.results.json"),
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case-id", action="append", default=[], help="形如 test2/t2r03b")
    ap.add_argument("--all-nonhit", action="store_true")
    ap.add_argument("--tol", type=float, default=0.5)
    ap.add_argument("--out-dir", default=str(BENCH / "work" / "loc_audit_visual"))
    args = ap.parse_args()

    import cv2
    from media.ffmpeg import FFmpegIO

    audit = json.loads((BENCH / "work" / "loc_retrieval_audit.json").read_text(encoding="utf-8"))
    want = set(args.case_id)
    if args.all_nonhit:
        for case, blk in audit["cases"].items():
            for row in blk["rows"]:
                if row["mark"] != "HIT":
                    want.add("%s/%s" % (case, row["id"]))
    if not want:
        print("no targets; use --case-id or --all-nonhit")
        return 1

    ff = FFmpegIO()
    out = Path(args.out_dir); out.mkdir(parents=True, exist_ok=True)
    cache = {}
    for key in sorted(want):
        case, pid = key.split("/")
        edit, orig, gt_rel, res_rel = CASES[case]
        if case not in cache:
            cache[case] = (json.loads((BENCH / gt_rel).read_text(encoding="utf-8")),
                           json.loads((BENCH / res_rel).read_text(encoding="utf-8"))["results"])
        gt, res = cache[case]
        p = next(x for x in gt["positives"] if x["id"] == pid)
        row = next(r for r in audit["cases"][case]["rows"] if r["id"] == pid)
        e0, e1 = [float(x) for x in p["edited"]]
        o0, o1 = [float(x) for x in p["original"]]
        # 运行期: 覆盖 GT 编辑段的结果里, 取原片侧离 GT 窗最近的 span
        best = None
        for i, r in enumerate(res):
            rs, re = r["edited_segment"]["start"], r["edited_segment"]["end"]
            if max(0.0, min(e1, re) - max(e0, rs)) <= 0 and (e1 - e0) > 1e-6:
                continue
            span = (r["original"]["candidate_start"], r["original"]["candidate_end"])
            d = 0.0 if span[1] >= o0 and span[0] <= o1 else min(abs(span[0] - o1), abs(o0 - span[1]))
            if best is None or d < best[0]:
                best = (d, i, span[0], span[1], r["confidence"])
        tiles, labels = [], []
        job = [(edit, (e0 + e1) / 2, "QUERY ed %.1fs" % ((e0 + e1) / 2)),
               (orig, float(row["t_best"]), "RETRIEVAL best %.1fs rank %d sim %.3f" % (
                   row["t_best"], row["retrieval_rank"], row["sim"]))]
        if best:
            job.append((orig, (best[2] + best[3]) / 2,
                        "RUNTIME s%d %.0f-%.0f (%s)" % (best[1], best[2], best[3], best[4])))
        job.append((orig, (o0 + o1) / 2, "GT mid %.1f" % ((o0 + o1) / 2)))
        for path, t, lab in job:
            img = np.asarray(ff.grab_frame(Path(path), float(max(t, 0.0))))
            h = 236
            hh, ww = img.shape[:2]
            im = cv2.resize(img, (max(1, int(round(ww * h / hh))), h), interpolation=cv2.INTER_AREA)
            bar = np.full((30, im.shape[1], 3), 255, np.uint8)
            cv2.putText(bar, lab, (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
            tiles.append(np.vstack([bar, im]))
        gap = np.full((tiles[0].shape[0], 8, 3), 255, np.uint8)
        sheet = tiles[0]
        for t in tiles[1:]:
            sheet = np.hstack([sheet, gap, t])
        head = np.full((30, sheet.shape[1], 3), 255, np.uint8)
        cv2.putText(head, "%s  mark=%s  GT ed[%.1f-%.1f] -> og[%.1f-%.1f]" % (
            key, row["mark"], e0, e1, o0, o1), (6, 21),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 200), 1, cv2.LINE_AA)
        fn = out / ("%s_%s.png" % (case, pid))
        cv2.imwrite(str(fn), np.vstack([head, sheet]))
        print("saved %s" % fn)
    return 0


if __name__ == "__main__":
    sys.exit(main())
