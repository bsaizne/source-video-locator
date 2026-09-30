"""口径修正评估层 (V5) —— 同一批结果上并行输出多种命中判据, 用于剥离口径伪影.

背景 (2026-09-25/26 竞品对标会话 + HANDOFF_CUTMATCH_AND_METRIC_AUDIT §3):
  现行"严格"判据接受三种情形之一: (a) 结果 span 落在 GT 窗 ±2s 内;
  (b) GT 窗中点落在 span 内 (mid_in); (c) span 覆盖 GT 窗 >=40%.
  另有编辑侧前置条件 ed_inter > 0. 当 GT 窗跨镜头/很窄/零宽时, 这两处都可能
  把"实际命中"判成 MISS/part. 本脚本在**不改 runtime** 的前提下, 用同一批结果文件
  同时给出多组判据(只读结果 JSON + GT):

  S_strict   现行口径 (自检: 应逐位等于 measure_shot_recall.evaluate 的 mark)
  Z_point    零宽/点状 GT 编辑窗用"点包含"而非"重叠>0" (结构性公式修复, 合法)
  T_tol05    原片窗 ±0.5s 容差 (1fps 粒度边界容差)
  R_rec      推荐口径 = Z_point + 原片窗 ±0.5s
  O_overlap  + 原片侧实质重叠 (>=0.5s 且 >=50% min(span,GT))
  A_any      + 任意重叠 (>=0.5s) —— 最宽上界
  SE_diag    编辑窗 ±0.5s —— **膨胀对照, 不作为修正**: 会让"相邻编辑段"用大场景 span
             认领命中 (2026-09-26 逐例结构核查: 6 例翻转中 5 例严判 ed 重叠 = 0.00)

判据越往下越宽, 用于量化"有多少命中被旧口径吃掉"; **不等于新基线**.
翻转案例必须 --visual 出图人工确认(先看图再下结论).

用法:
  python mvp/scripts/measure_recall_v5.py \
      --batch "baseline=work/rerun_{case}_perfopt.results.json" \
      --batch "tn=work/tn_{case}.results.json" --visual

零 runtime 改动: 只读结果 JSON + GT, 不导入 mvp/src 的任何定位逻辑.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]

CASES = [
    ("2mkv", "datasets/real/ground_truth_v4.json"),
    ("test1", "datasets/real/ground_truth_test1.json"),
    ("test2", "datasets/real/ground_truth_test2.json"),
    ("test3", "datasets/real/ground_truth_test3.json"),
]
CRITERIA = ["S_strict", "Z_point", "T_tol05", "R_rec", "O_overlap", "A_any", "SE_diag"]


def overlap_sec(a0, a1, b0, b1) -> float:
    return max(0.0, min(a1, b1) - max(a0, b0))


def result_spans(r: dict):
    out = [("main", r["original"]["candidate_start"], r["original"]["candidate_end"])]
    for s in r.get("original_segments") or []:
        out.append(("sub", s["candidate_start"], s["candidate_end"]))
    return [x for x in out if x[2] - x[1] > 0.01]


def _union_covers(spans, o0, o1, min_frac=0.5) -> bool:
    inter = sum(overlap_sec(a0, a1, o0, o1) for a0, a1 in spans)
    return (inter / max(1e-6, o1 - o0)) >= min_frac


def _ed_ok(e0, e1, re0, re1, ed_kind: str) -> float:
    """编辑侧可计入的重叠长度; ed_kind: strict | zero_point | tol05."""
    if ed_kind == "tol05":
        return overlap_sec(e0 - 0.5, e1 + 0.5, re0, re1)
    if ed_kind == "zero_point" and (e1 - e0) < 1e-6:
        return 1e-3 if (re0 <= e0 <= re1) else 0.0
    return overlap_sec(e0, e1, re0, re1)


def _hits(e0, e1, o0, o1, res, ed_kind: str, orig_tol: float) -> dict:
    """在给定编辑侧口径/原片窗容差下求 base(现行三选一)/O(实质重叠)/A(任意重叠) 命中."""
    ed_tol = 0.5 if ed_kind == "tol05" else 0.0
    g0, g1 = o0 - orig_tol, o1 + orig_tol
    glen = max(1e-6, o1 - o0)
    covering, ed_intervals = [], []
    flags = {"base": False, "O": False, "A": False}
    detail = {}
    for i, r in enumerate(res):
        re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
        if _ed_ok(e0, e1, re0, re1, ed_kind) <= 0:
            continue
        ed_intervals.append((max(e0 - ed_tol, re0), min(e1 + ed_tol, re1)))
        for kind, a, b in result_spans(r):
            within = (a >= g0 - 2.0) and (b <= g1 + 2.0)
            mid_in = a <= (g0 + g1) / 2 <= b
            ov = overlap_sec(a, b, o0, o1)
            cov = ov / glen >= 0.4
            ov_rel = ov / min(max(1e-6, b - a), glen)
            base = within or mid_in or cov
            for k, v in (("base", base), ("O", base or (ov >= 0.5 and ov_rel >= 0.5)),
                         ("A", base or ov >= 0.5)):
                if v and not flags[k]:
                    flags[k] = True
                    detail[k] = (i, kind, a, b, ov, ov_rel)
            if ov > 0:
                covering.append((a, b))
    # 联合覆盖回退 (与 evaluate 的 union 分支同口径)
    if ed_intervals and covering:
        ed_union = _union_covers(ed_intervals, e0 - ed_tol, e1 + ed_tol, 0.5)
        if ed_union and _union_covers(covering, o0, o1):
            for k in ("base", "O", "A"):
                if not flags[k]:
                    flags[k] = True
                    detail.setdefault(k, ("union", "joint", covering[0][0], covering[-1][1], 0.0, 0.0))
    return {"flags": flags, "detail": detail}


def classify(p: dict, res: list[dict]) -> dict:
    e0, e1 = [float(x) for x in p["edited"]]
    o0, o1 = [float(x) for x in p["original"]]
    h00 = _hits(e0, e1, o0, o1, res, "strict", 0.0)
    hzp = _hits(e0, e1, o0, o1, res, "zero_point", 0.0)
    h05 = _hits(e0, e1, o0, o1, res, "strict", 0.5)
    hr = _hits(e0, e1, o0, o1, res, "zero_point", 0.5)
    hsd = _hits(e0, e1, o0, o1, res, "tol05", 0.0)
    flags = {
        "S_strict": h00["flags"]["base"],
        "Z_point": hzp["flags"]["base"],
        "T_tol05": h05["flags"]["base"],
        "R_rec": hr["flags"]["base"],
        "O_overlap": h00["flags"]["O"],
        "A_any": h00["flags"]["A"],
        "SE_diag": hsd["flags"]["base"],
    }
    detail = {}
    for name, h in (("S_strict", h00), ("Z_point", hzp), ("T_tol05", h05),
                    ("R_rec", hr), ("SE_diag", hsd)):
        if h["flags"]["base"]:
            detail[name] = h["detail"]["base"]
    for name, h in (("O_overlap", h00), ("A_any", h00)):
        k = "O" if name == "O_overlap" else "A"
        if h["flags"][k]:
            detail[name] = h["detail"][k]
    return {"flags": flags, "detail": detail}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", action="append", required=True,
                    help='名称=结果路径模板, 可重复; 例如 "baseline=work/rerun_{case}_perfopt.results.json"')
    ap.add_argument("--out", default=None)
    ap.add_argument("--visual", action="store_true", help="对 S 未命中但 R_rec 命中的案例出对照图")
    ap.add_argument("--visual-dir", default=str(BENCH / "work" / "caliber_v5"))
    args = ap.parse_args()

    batches = []
    for spec in args.batch:
        name, _, pattern = spec.partition("=")
        batches.append((name.strip(), pattern.strip()))

    report = {"criteria": CRITERIA, "batches": {}, "deltas": {}, "flips": {}}
    per_batch_marks = {}
    for name, pattern in batches:
        rows, marks_all = [], {}
        for case, gt_rel in CASES:
            rp = BENCH / pattern.format(case=case)
            if not rp.exists():
                print("[MISSING] %s" % rp, flush=True)
                continue
            gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
            res = json.loads(rp.read_text(encoding="utf-8"))["results"]
            counts = {k: 0 for k in CRITERIA}
            per_pos = []
            for p in gt["positives"]:
                c = classify(p, res)
                for k in CRITERIA:
                    counts[k] += bool(c["flags"][k])
                per_pos.append({"id": p["id"], "tier": p["tier"],
                                **{k: bool(c["flags"][k]) for k in CRITERIA}})
                marks_all[(case, p["id"])] = c
            scene = sum(1 for p in gt["positives"] if any(_scene_hit(p, r) for r in res))
            rows.append({"case": case, "n_pos": len(gt["positives"]),
                         "n_neg": len(gt["negatives"]), "counts": counts,
                         "scene_hit": scene, "per_pos": per_pos,
                         "results": str(rp), "gt": gt_rel})
        tot = {k: sum(r["counts"][k] for r in rows) for k in CRITERIA}
        tot["n_pos"] = sum(r["n_pos"] for r in rows)
        tot["scene_hit"] = sum(r["scene_hit"] for r in rows)
        report["batches"][name] = {"rows": rows, "total": tot, "pattern": pattern}
        per_batch_marks[name] = marks_all

    print("=" * 116)
    print("口径修正评估 (V5) —— 同一批结果的多组命中判据 (S=现行严格, R_rec=推荐口径)")
    print("-" * 116)
    print("%-10s %-8s" % ("batch", "case") + "".join(" %-11s" % k for k in CRITERIA))
    for name, _ in batches:
        b = report["batches"].get(name)
        if not b:
            continue
        for r in b["rows"]:
            print("%-10s %-8s" % (name, r["case"])
                  + "".join(" %-11s" % ("%d/%d" % (r["counts"][k], r["n_pos"])) for k in CRITERIA))
        t = b["total"]
        print("%-10s %-8s" % (name, "合计")
              + "".join(" %-11s" % ("%d/%d" % (t[k], t["n_pos"])) for k in CRITERIA))
        print("-" * 116)

    base = batches[0][0]
    if len(batches) > 1:
        print("对照 (相对 %s): 各判据下的 Δ命中数 (改善/退化 逐案例翻转)" % base)
        for name, _ in batches[1:]:
            if name not in report["batches"]:
                continue
            for k in CRITERIA:
                d = report["batches"][name]["total"][k] - report["batches"][base]["total"][k]
                up = dn = 0
                for key, mb in per_batch_marks[name].items():
                    m0 = per_batch_marks[base].get(key)
                    if not m0:
                        continue
                    if mb["flags"][k] and not m0["flags"][k]:
                        up += 1
                    elif m0["flags"][k] and not mb["flags"][k]:
                        dn += 1
                print("  %-12s %-10s Δ=%+4d  (改善 %d / 退化 %d)" % (name, k, d, up, dn))
                report["deltas"].setdefault(name, {})[k] = {"delta": d, "up": up, "down": dn}
        print("-" * 116)

    base_rows = report["batches"].get(base, {}).get("rows", [])
    flips = []
    for r in base_rows:
        for pp in r["per_pos"]:
            key = (r["case"], pp["id"])
            c = per_batch_marks[base][key]
            if not c["flags"]["S_strict"] and c["flags"]["R_rec"]:
                flips.append({"case": r["case"], "id": pp["id"],
                              "Z": c["flags"]["Z_point"], "T": c["flags"]["T_tol05"],
                              "detail": {k: (list(v) if v else None)
                                         for k, v in c["detail"].items() if v}})
    report["flips"][base] = flips
    print("口径翻转案例 (%s): S=未命中 且 R_rec=命中 → %d 例" % (base, len(flips)))
    for f in flips:
        d = f["detail"].get("R_rec") or f["detail"].get("Z_point") or f["detail"].get("T_tol05")
        print("  %-8s %-8s Z=%-5s T=%-5s span %s[%.1f-%.1f]" % (
            f["case"], f["id"], f["Z"], f["T"], d[1] if d else "-",
            d[2] if d else -1, d[3] if d else -1))
    print("=" * 116)

    if args.visual and flips:
        _visual(base, flips, per_batch_marks[base], args.visual_dir)

    out = args.out or str(BENCH / "work" / "recall_v5.json")
    Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved %s" % out)
    return 0


def _scene_hit(p: dict, r: dict) -> bool:
    o0, o1 = [float(x) for x in p["original"]]
    e0, e1 = [float(x) for x in p["edited"]]
    if overlap_sec(e0, e1, r["edited_segment"]["start"], r["edited_segment"]["end"]) <= 0:
        return False
    for _, a, b in result_spans(r):
        if o0 - 15.0 <= (a + b) / 2 <= o1 + 15.0:
            return True
    return False


def _visual(base_name, flips, marks, out_dir):
    """对翻转案例出图: [QUERY 编辑段中点 | 结果 span 中点帧 | GT 窗中点帧] (先看图再下结论)."""
    import os
    import numpy as np
    import cv2
    os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
    os.environ.setdefault("MEDIA_FFPROBE",
                          r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
    sys.path.insert(0, str(BENCH / "mvp" / "src"))
    from media.ffmpeg import FFmpegIO
    out = Path(out_dir); out.mkdir(parents=True, exist_ok=True)
    ff = FFmpegIO()
    EDIT = {"2mkv": r"D:\video\1.mp4", "test1": r"D:\ProjectXIXI\test1\test1-ed.mp4",
            "test2": r"D:\ProjectXIXI\test2\tset2-ed.mp4", "test3": r"D:\ProjectXIXI\test3\test3-ed.mp4"}
    ORIG = {"2mkv": r"D:\video\2.mkv", "test1": r"D:\ProjectXIXI\test1\test1-om.mkv",
            "test2": r"D:\ProjectXIXI\test2\test2-om.mp4", "test3": r"D:\ProjectXIXI\test3\test3-om.mp4"}
    for f in flips:
        case, pid = f["case"], f["id"]
        gt = json.loads((BENCH / dict(CASES)[case]).read_text(encoding="utf-8"))
        p = next(x for x in gt["positives"] if x["id"] == pid)
        e0, e1 = [float(x) for x in p["edited"]]
        o0, o1 = [float(x) for x in p["original"]]
        d = f["detail"].get("R_rec") or f["detail"].get("Z_point") or f["detail"].get("T_tol05")
        a, b = float(d[2]), float(d[3])
        tiles = []
        for path, t, lab in ((EDIT[case], (e0 + e1) / 2, "QUERY ed %.1fs" % ((e0 + e1) / 2)),
                             (ORIG[case], (a + b) / 2, "span %.1f-%.1f" % (a, b)),
                             (ORIG[case], (o0 + o1) / 2, "GT mid %.1f" % ((o0 + o1) / 2))):
            try:
                img = np.asarray(ff.grab_frame(Path(path), float(t)))
            except Exception as exc:  # noqa: BLE001
                print("  [visual] %s/%s grab fail %s: %s" % (case, pid, t, exc))
                tiles = []
                break
            tiles.append(img)
        if not tiles:
            continue
        h = 236
        row = []
        for img, lab in zip(tiles, ("QUERY", base_name, "GT")):
            hh, ww = img.shape[:2]
            im = cv2.resize(img, (max(1, int(round(ww * h / hh))), h), interpolation=cv2.INTER_AREA)
            bar = np.full((30, im.shape[1], 3), 255, np.uint8)
            cv2.putText(bar, lab, (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
            row.append(np.vstack([bar, im]))
        gap = np.full((row[0].shape[0], 8, 3), 255, np.uint8)
        sheet = row[0]
        for c in row[1:]:
            sheet = np.hstack([sheet, gap, c])
        head = np.full((30, sheet.shape[1], 3), 255, np.uint8)
        cv2.putText(head, "%s/%s GT ed[%.1f-%.1f] -> OG[%.1f-%.1f] span[%.1f-%.1f] Z=%s T=%s" % (
            case, pid, e0, e1, o0, o1, a, b, f["Z"], f["T"]), (6, 21),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 200), 1, cv2.LINE_AA)
        cv2.imwrite(str(out / ("%s_%s.png" % (case, pid))), np.vstack([head, sheet]))
    print("visual sheets -> %s" % out)


if __name__ == "__main__":
    sys.exit(main())
