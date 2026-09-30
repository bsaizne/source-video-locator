# -*- coding: utf-8 -*-
"""D 段复现结果 多面复核出图 (2026-09-26, 用户指示: 不只靠数据/GT, 多模态逐图多方面检查).

五类桶(全部出图, 上限防爆):
  A GT翻转    proxy 与 baseline 在严格判据上的翻转(两方向) —— 指标变化的直接来源;
  B 反GT偏置  proxy 高置信命中但按 GT 判 MISS/part ⇒ **GT 错标候选**(t2r07c 型冤案检查), 不自动记 proxy 失败;
  C 拒绝行为  proxy not_in_source 的行: GT 负例=正确拒绝 / GT 正例=漏召回;
  D 双侧位移  双侧都命中但 span 中心差 >15s(选了不同实例/子镜头);
  E 一致HIT抽样 双侧一致 HIT 随机抽 6(防指标虚高, 验证"对"是否真对).

判据说明: 本脚本的选择判据是**简化版**(中点包含 or ≥50% 重叠), 只用于挑图;
最终三指标以 measure_four_results.py 为准; 谁对谁错由人读图裁决(先看图后查键, 不套 GT 单因素).

用法: python mvp/scripts/review_proxy_loc_visual.py [--cases 2mkv,test1,test2,test3] [--max-per-bucket 12]
产物: work/proxy_loc_review/*.png + review_manifest.json + verdicts_template.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from pathlib import Path

import cv2
import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
B = Path(__file__).resolve().parents[2]
WORK = B / "work"
OUT = WORK / "proxy_loc_review"
os.environ.setdefault("MEDIA_FFMPEG", str(B / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(B / "mvp" / "src"))
from media.ffmpeg import FFmpegIO  # noqa: E402

CASES = {"2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv", "ground_truth_v4.json"),
         "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv", "ground_truth_test1.json"),
         "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4", "ground_truth_test2.json"),
         "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4", "ground_truth_test3.json")}


def load_results(path: Path) -> list:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))["results"]


def spans_of(r: dict) -> list:
    """(kind, start, end) 主 span + 子 span(基线有, proxy 主 span-only 通常没有)."""
    out = [("main", float(r["original"]["candidate_start"]), float(r["original"]["candidate_end"]))]
    for s in r.get("original_segments") or []:
        out.append(("sub", float(s["candidate_start"]), float(s["candidate_end"])))
    return out


def judge(gt: dict, res: list) -> tuple[str, dict]:
    """简化严格判据(仅挑图用): HIT=编辑段对应且原片中点在 span 内或重叠>=0.5;
    part=原片 span 与 GT 中点差 <=15s; 否则 MISS. 返回 (verdict, 最佳行)."""
    es, ee = gt["edited"]
    os_, oe = gt["original"] if gt.get("original") else (None, None)
    if os_ is None:
        return ("NEG", {})
    mid = (os_ + oe) / 2.0
    glen = max(oe - os_, 0.1)
    best, bo = None, -1.0
    for r in res:
        s, e = float(r["edited_segment"]["start"]), float(r["edited_segment"]["end"])
        ov = min(e, ee) - max(s, es)
        if ov > bo:
            best, bo = r, ov
    if best is None or bo <= 0:
        return ("MISS", {})
    if best.get("not_in_source"):
        return ("MISS(rejected)", best)
    hit = False
    for kind, a, b in spans_of(best):
        if a <= mid <= b or (min(b, oe) - max(a, os_)) / glen >= 0.5:
            hit = True
            break
    if hit:
        return ("HIT", best)
    for kind, a, b in spans_of(best):
        c = (a + b) / 2.0
        if abs(c - mid) <= 15 or (min(b, oe) - max(a, os_)) > 0:
            return ("part", best)
    return ("MISS", best)


def strips(ff, path, span, n=4, H=150):
    a, b = span
    if b <= a:
        b = a + 0.1
    ts = [a + (b - a) * k / max(n - 1, 1) for k in range(n)]
    tiles = []
    for t in ts:
        img = np.asarray(ff.grab_frame(Path(path), max(0.0, t)))
        hh, ww = img.shape[:2]
        im = cv2.resize(img, (max(1, int(round(ww * H / hh))), H), interpolation=cv2.INTER_AREA)
        bar = np.full((20, im.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, "%.2f" % t, (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1, cv2.LINE_AA)
        tiles.append(np.vstack([bar, im]))
    row = tiles[0]
    for c in tiles[1:]:
        row = np.hstack([row, np.full((row.shape[0], 4, 3), 255, np.uint8), c])
    return row


def label_row(row, text, color):
    lab = np.full((row.shape[0], 240, 3), 255, np.uint8)
    for i, ln in enumerate(text.split("|")[:3]):
        cv2.putText(lab, ln[:36], (6, 22 + 20 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)
    return np.hstack([lab, row])


def sheet(case, gid, bucket, ed, om, gt_ed, gt_og, proxy_row, base_row, proxy_v, base_v):
    ff = FFmpegIO()
    r0 = label_row(strips(ff, ed, gt_ed), "ED(GT)|%s" % (gid,), (0, 0, 0))
    ps = None
    if proxy_row and not proxy_row.get("not_in_source"):
        ps = (float(proxy_row["original"]["candidate_start"]), float(proxy_row["original"]["candidate_end"]))
    r1 = label_row(strips(ff, om, ps) if ps else np.full((170, 320, 3), 220, np.uint8),
                   "OG(proxy)|%s conf=%s" % (proxy_v, (proxy_row or {}).get("confidence", "?")),
                   (0, 120, 0) if proxy_v == "HIT" else (0, 0, 180))
    bs = None
    if base_row:
        bs = (float(base_row["original"]["candidate_start"]), float(base_row["original"]["candidate_end"]))
    r2 = label_row(strips(ff, om, bs) if bs else np.full((170, 320, 3), 220, np.uint8),
                   "OG(baseline)|%s" % base_v, (0, 0, 180))
    r3 = label_row(strips(ff, om, gt_og), "OG(GT)", (140, 0, 140))
    rows = [r0, r1, r2, r3]
    w = max(r.shape[1] for r in rows)
    rows = [r if r.shape[1] == w else np.hstack([r, np.full((r.shape[0], w - r.shape[1], 3), 255, np.uint8)]) for r in rows]
    head = np.full((30, w, 3), 255, np.uint8)
    cv2.putText(head, "%s %s [%s] proxy=%s base=%s | GT og %.1f-%.1f" % (
        case, gid, bucket, proxy_v, base_v, gt_og[0], gt_og[1]),
        (6, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    sep = np.full((4, w, 3), 200, np.uint8)
    return np.vstack([head] + sum([[r, sep] for r in rows], [])[:-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", default="2mkv,test1,test2,test3")
    ap.add_argument("--max-per-bucket", type=int, default=12)
    ap.add_argument("--seed", type=int, default=20260926)
    args = ap.parse_args()
    random.seed(args.seed)
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, csv_rows = [], []
    for case in args.cases.split(","):
        ed, om, gt_name = CASES[case]
        gt = json.loads((B / "datasets" / "real" / gt_name).read_text(encoding="utf-8"))
        proxy = load_results(WORK / ("proxy_%s.results.json" % case))
        base = load_results(WORK / ("rerun_%s_perfopt.results.json" % case))
        if not proxy:
            print("[skip] %s: 无 proxy_%s.results.json (先跑 import --loc)" % (case, case))
            continue
        neg_ids = {n["id"] for n in gt.get("negatives", [])}
        pos = gt.get("positives", [])
        buckets = {"A翻转": [], "B反GT偏置": [], "C拒绝": [], "D双侧位移": [], "E一致HIT": []}
        for g in pos:
            pv, prow = judge(g, proxy)
            bv, brow = judge(g, base)
            key = (pv.split("(")[0], bv.split("(")[0])
            item = (g["id"], g, pv, prow, bv, brow)
            if pv != bv and "HIT" in (pv, bv):
                buckets["A翻转"].append(item)
            if key[0] != "HIT" and prow and not prow.get("not_in_source"):
                conf = str(prow.get("confidence", ""))
                if "HIGH" in conf:
                    buckets["B反GT偏置"].append(item)
            if prow and prow.get("not_in_source"):
                buckets["C拒绝"].append(item)
            if key == ("HIT", "HIT") and prow and brow:
                pc = (float(prow["original"]["candidate_start"]) + float(prow["original"]["candidate_end"])) / 2
                bc = (float(brow["original"]["candidate_start"]) + float(brow["original"]["candidate_end"])) / 2
                if abs(pc - bc) > 15:
                    buckets["D双侧位移"].append(item)
            if key == ("HIT", "HIT"):
                buckets["E一致HIT"].append(item)
        # 负例: proxy 是否拒绝(正确拒绝) —— 只挑"没拒"的出图
        for n in gt.get("negatives", []):
            es, ee = n["edited"]
            ov, best = -1.0, None
            for r in proxy:
                s, e = float(r["edited_segment"]["start"]), float(r["edited_segment"]["end"])
                o = min(e, ee) - max(s, es)
                if o > ov:
                    ov, best = o, r
            if best is not None and ov > 0 and not best.get("not_in_source"):
                buckets["C拒绝"].append((n["id"] + "(负例未拒)", {"edited": [es, ee], "original": None},
                                         "NEG-FP", best, "-", None))
        print("== %s ==" % case, {k: len(v) for k, v in buckets.items()})
        for bucket, items in buckets.items():
            take = items if bucket != "E一致HIT" else random.sample(items, min(6, len(items)))
            for gid, g, pv, prow, bv, brow in take[:args.max_per_bucket]:
                gt_ed = tuple(map(float, g["edited"]))
                gt_og = tuple(map(float, g["original"])) if g.get("original") else (0.0, 0.1)
                img = sheet(case, gid, bucket, ed, om, gt_ed, gt_og, prow, brow, pv, bv)
                fp = OUT / ("%s_%s_%s.png" % (case, gid, bucket[0]))
                cv2.imwrite(str(fp), img)
                manifest.append({"case": case, "gt_id": gid, "bucket": bucket,
                                 "proxy_verdict": pv, "baseline_verdict": bv, "png": fp.name})
                csv_rows.append({"png": fp.name, "case": case, "gt_id": gid, "bucket": bucket,
                                 "proxy_v": pv, "base_v": bv,
                                 "verdict_proxy": "", "verdict_baseline": "", "verdict_GT": "", "notes": ""})
    (OUT / "review_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    if csv_rows:
        with open(OUT / "verdicts_template.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
            w.writeheader()
            w.writerows(csv_rows)
    print("\n出图 %d 张 → %s (verdicts_template.csv 待人工逐张填)" % (len(manifest), OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
