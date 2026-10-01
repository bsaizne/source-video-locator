# -*- coding: utf-8 -*-
"""shot_split + patch_refine 双臂翻转读图（2026-09-30 续33 尾巴）。

与 visual_fastglobal_flip.py 的区别：① 读 work/spl_patch_arms/{arm}_{case}.results.json；
② **按 GT 行选行**（shot_split 会拆段并重发 uuid ⇒ 两臂结果数不同，不能按下标 zip）
—— 每臂取"编辑窗与 GT 编辑窗重叠最大"的结果行出图。

每行拼图 = ED 3 帧 / GT 原片窗 3 帧 / OFF 臂 span 3 帧 / ON 臂 span 3 帧（2x4 版 + 12 帧全帧图）。
用法:
  python mvp/scripts/review_spl_patch_flip.py --case test1 --gt t1r14c
  python mvp/scripts/review_spl_patch_flip.py --case test2 --gt t2r06c --a off --b on
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from visual_fastglobal_flip import EDS, GTS, OMS, grab, tile  # noqa: E402  (复用取帧/拼版)


def load(case: str, arm: str) -> list[dict]:
    """读某臂结果；off 臂缺失时回退现役默认批（本轮 test2/test3 的 off 臂即
    work/fastglobal_default_{case}.results.json —— 已实测与 off 臂逐位一致）。"""
    p = BENCH / "work" / "spl_patch_arms" / ("%s_%s.results.json" % (arm, case))
    if not p.exists() and arm == "off":
        p = BENCH / "work" / ("fastglobal_default_%s.results.json" % case)
        print("[note] off_%s 不在 spl_patch_arms, 回退现役默认批 %s" % (case, p.name))
    return json.loads(p.read_text(encoding="utf-8"))["results"]


def best_row(rows: list[dict], ed: tuple[float, float],
             og: tuple[float, float] | None = None) -> dict | None:
    """选行口径与 measure_shot_recall.evaluate 对齐。

    给了 GT 原片窗 og 时：按结果顺序取**第一条**其主 span 满足
    within(±2s) / mid_in / cov(>=0.4) 的行 —— 这才是让 main_hit 翻真的那行
    （shot_split 拆段后同一编辑窗可能有多行，按"编辑窗重叠最大"会选错行）。
    否则退回"编辑窗重叠最大"。
    """
    if og is not None:
        o0, o1 = og
        for r in rows:
            s = r["edited_segment"]
            if min(ed[1], s["end"]) - max(ed[0], s["start"]) <= 0:
                continue
            a = r["original"]["candidate_start"]
            b = r["original"]["candidate_end"]
            within = (a >= o0 - 2.0) and (b <= o1 + 2.0)
            mid_in = a <= (o0 + o1) / 2 <= b
            ov = max(0.0, min(o1, b) - max(o0, a)) / max(1e-9, o1 - o0)
            if within or mid_in or ov >= 0.4:
                return r
    best, bo = None, 0.0
    for r in rows:
        s = r["edited_segment"]
        ov = min(ed[1], s["end"]) - max(ed[0], s["start"])
        if ov > bo:
            best, bo = r, ov
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True)
    ap.add_argument("--gt", required=True, help="GT 行 id, 如 t1r14c")
    ap.add_argument("--a", default="off")
    ap.add_argument("--b", default="on")
    ap.add_argument("--out", default=str(BENCH / "work" / "spl_patch_visual"))
    args = ap.parse_args()

    gt = json.loads((BENCH / GTS[args.case]).read_text(encoding="utf-8"))
    g = next((x for x in gt["positives"] if x["id"] == args.gt), None)
    if g is None:
        print("GT id not found:", args.gt)
        return 2
    ed = (g["edited"][0], g["edited"][1])
    rows_a, rows_b = load(args.case, args.a), load(args.case, args.b)
    og = (g["original"][0], g["original"][1])
    ra, rb = best_row(rows_a, ed, og), best_row(rows_b, ed, og)
    if ra is None or rb is None:
        print("no overlapping result row; %s rows=%d %s rows=%d"
              % (args.a, len(rows_a), args.b, len(rows_b)))
        return 1
    for tag, r in ((args.a, ra), (args.b, rb)):
        subs = len(r.get("original_segments") or [])
        print("%-4s ed=[%.2f,%.2f] main=[%.2f,%.2f] subs=%d conf=%s not_in_source=%s id=%s"
              % (tag, r["edited_segment"]["start"], r["edited_segment"]["end"],
                 r["original"]["candidate_start"], r["original"]["candidate_end"],
                 subs, r.get("confidence", {}).get("level") if isinstance(r.get("confidence"), dict)
                 else r.get("confidence"), r.get("not_in_source"), r["result_id"][:8]))
    print("GT   %s ed=[%.2f,%.2f] og=[%.2f,%.2f]" % (g["id"], ed[0], ed[1],
                                                     g["original"][0], g["original"][1]))
    print("rows %s=%d %s=%d (shot_split 拆段 ⇒ 两臂行数可不同)" % (args.a, len(rows_a), args.b, len(rows_b)))

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frames = []
    for tag, src, rng in (
            ("ed", EDS[args.case], ed),
            ("gt", OMS[args.case], (g["original"][0], g["original"][1])),
            (args.a, OMS[args.case], (ra["original"]["candidate_start"], ra["original"]["candidate_end"])),
            (args.b, OMS[args.case], (rb["original"]["candidate_start"], rb["original"]["candidate_end"]))):
        t0, t1 = float(rng[0]), float(rng[1])
        for i, t in enumerate([t0 + 0.3, (t0 + t1) / 2, max(t1 - 0.3, t0)]):
            p = out / ("%s_%s_%s_%d.png" % (args.case, args.gt, tag, i))
            grab(src, t, p)
            frames.append(p)
    sheet = out / ("%s_%s_sheet12.png" % (args.case, args.gt))
    tile(frames, sheet, cols=4)
    print("sheet=%s" % sheet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
