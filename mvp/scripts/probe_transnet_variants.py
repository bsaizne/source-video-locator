# -*- coding: utf-8 -*-
"""A1+ 变体筛选 —— 按竞品常量流口径改造编辑侧切分, 先做「边界级」筛选(不跑检索).

竞品口径来源(证据等级见 FINDINGS/08):
  * 描述子 48x27(与官方/我方一致, 强);
  * dual 判定候选阈值 single/many/combined = 0.55 / 0.35 / 0.62(中);
  * 帧差精修 refine_commentary_scene_split_with_frame_diff 默认值(强, 顺序匹配):
    min_segment_frames=32, min_side_frames=10, near_cut_frames=16,
    absolute_diff_min=45.0, mad_multiplier=4.0, max_move_frames=16, max_additions_per_segment=1;
  * 短场景合并 commentary_short_scene_merge_enabled + commentary_short_scene_min_frames(=180? 中).

变体:
  raw            single > 0.5 (A1 已测口径)
  s055           single > 0.55
  dualA          single > 0.55 或 many > 0.35
  dualB          single > 0.55 或 (many > 0.35 且 (s+m)/2 > 0.62)
  dualC          max(single, many) > 0.62
  dualB_ref      dualB + 帧差精修(移动/补漏, 不删)
  dualB_ref_drop dualB + 帧差精修(不满足判据的切点删除)
  raw_merge      raw + 短段合并(180 帧)
  dualB_ref_merge dualB_ref + 短段合并(180 帧)

指标(与 GT 编辑段比): 边界数 / 段数 / 平均段长 / GT 边界覆盖(0.5s) / 切进 GT 段内部数 / 被切碎 GT 段数.
用法: python mvp/scripts/probe_transnet_variants.py [case]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

import cv2                                              # noqa: E402
from media.ffmpeg.ffmpeg_io import FFmpegIO             # noqa: E402
import tn_transnetv2 as tn                              # noqa: E402

CASES = [
    ("2mkv",  r"D:\video\1.mp4", "ground_truth_v4.json"),
    ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", "ground_truth_test1.json"),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", "ground_truth_test2.json"),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", "ground_truth_test3.json"),
]
# 竞品常量(见 FINDINGS/08)
DUAL_S, DUAL_M, DUAL_C = 0.55, 0.35, 0.62
R_MIN_SEG, R_NEAR, R_ABS, R_MAD, R_MOVE, R_ADD = 32, 16, 45.0, 4.0, 16, 1
SHORT_MERGE_FRAMES = 180
TOL, MARGIN = 0.5, 0.3


def gt_of(gt_file):
    d = json.loads((BENCH / "datasets" / "real" / gt_file).read_text(encoding="utf-8"))
    segs = []
    for k in ("positives", "negatives"):
        for it in d.get(k, []):
            segs.append([float(it["edited"][0]), float(it["edited"][1])])
    segs.sort()
    return segs, sorted({b for s in segs for b in s})


def cuts_flag(pred, th):
    f = (pred > th).astype(np.uint8)
    return [i for i in range(1, len(f)) if f[i] == 1 and f[i - 1] == 0]


def cuts_dual(rule, s, m):
    out = []
    for i in range(1, len(s)):
        if rule == "s055":
            hit = s[i] > DUAL_S
        elif rule == "dualA":
            hit = (s[i] > DUAL_S) or (m[i] > DUAL_M)
        elif rule == "dualB":
            hit = (s[i] > DUAL_S) or ((m[i] > DUAL_M) and (0.5 * (s[i] + m[i]) > DUAL_C))
        elif rule == "dualC":
            hit = max(s[i], m[i]) > DUAL_C
        else:
            raise ValueError(rule)
        if hit and not (s[i - 1] > DUAL_S or m[i - 1] > DUAL_M):
            out.append(i)          # 只在上升沿取一次(与 raw 口径一致)
    return out


def frame_diffs(grays):
    g = grays.astype(np.float32)
    d = np.zeros(len(g), dtype=np.float32)
    if len(g) > 1:
        d[1:] = np.abs(g[1:] - g[:-1]).mean(axis=(1, 2))
    return d


def refine(cuts, d, n, drop_unmatched=False):
    n = len(d)
    out = []
    for c in cuts:
        lo, hi = max(1, c - R_NEAR), min(n - 1, c + R_NEAR)
        seg = d[lo:hi + 1]
        if seg.size == 0:
            out.append(c); continue
        mad = float(np.median(np.abs(seg - np.median(seg))))
        ok = (seg >= R_ABS) | (seg >= R_MAD * mad)
        if ok.any():
            j = int(np.argmax(np.where(ok, seg, -1.0)))
            shift = int(np.clip((lo + j) - c, -R_MOVE, R_MOVE))
            out.append(c + shift)
        elif not drop_unmatched:
            out.append(c)
    out = sorted(set(out))
    # 补漏: 每段最多加 1 个强峰
    if R_ADD > 0:
        pts = [0] + out + [n]
        for k in range(len(pts) - 1):
            a, b = pts[k], pts[k + 1]
            if b - a < R_MIN_SEG:
                continue
            seg = d[a + 1:b]
            if seg.size == 0:
                continue
            j = int(np.argmax(seg))
            if seg[j] >= R_ABS and seg[j] >= R_MAD * float(np.median(np.abs(seg - np.median(seg)))):
                pos = a + 1 + j
                if all(abs(pos - x) >= R_NEAR for x in out):
                    out.append(pos)
        out = sorted(set(out))
    return out


def merge_short(cuts, n, min_frames):
    c = sorted(set(x for x in cuts if 0 < x < n))
    changed = True
    while changed and c:
        changed = False
        pts = [0] + c + [n]
        worst, wlen = None, None
        for k in range(1, len(pts) - 1):
            ln = pts[k + 1] - pts[k]
            if ln < min_frames and (wlen is None or ln < wlen):
                wlen, worst = ln, k
        if worst is not None:
            c.pop(worst - 1)
            changed = True
    return c


def to_bounds(cuts, fps):
    return sorted(set([0.0] + [c / fps for c in cuts]))


def stats(bounds, gt_segs, gt_b, total_s):
    nseg = len(bounds)
    inner = 0; split = 0
    for a, b in gt_segs:
        if b - a < 1.0:
            continue
        hits = [x for x in bounds if a + MARGIN < x < b - MARGIN]
        inner += len(hits)
        if hits:
            split += 1
    cov = (sum(1 for g in gt_b if min(abs(g - x) for x in bounds) <= TOL) / len(gt_b)) if gt_b and bounds else 0.0
    return {"nb": len(bounds), "nseg": nseg, "avglen": round(total_s / max(nseg, 1), 2),
            "cov": round(cov, 3), "inner": inner, "split": split}


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    ff = FFmpegIO()
    out = {}
    for case, ed, gt_f in CASES:
        if only and case != only:
            continue
        gt_segs, gt_b = gt_of(gt_f)
        meta = ff.metadata(Path(ed))
        fps = float(meta.fps) if meta and meta.fps else 30.0
        # ① TN 输入: 直接 48x27 原生 fps(与官方/我方 A1 口径一致)
        arr = np.stack([b[..., ::-1].copy() for _, b in ff.iter_frames(Path(ed), fps, scale=(48, 27))], axis=0)
        # ② 帧差: 160x90 灰度(竞品 commentary_boundary_refine_proxy_* 未绑定, 取常用代理尺寸)
        grays = np.stack([cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
                          for _, b in ff.iter_frames(Path(ed), fps, scale=(160, 90))], axis=0)
        n = int(arr.shape[0])
        n = min(n, int(grays.shape[0]))
        s, m = tn.predict_both(arr[:n], provider="DmlExecutionProvider")
        d = frame_diffs(grays[:n])[:n]
        total_s = n / fps

        variants = {}
        variants["raw"] = tn.cuts_from_pred(s, 0.5)[1:]
        variants["s055"] = cuts_dual("s055", s, m)
        variants["dualA"] = cuts_dual("dualA", s, m)
        variants["dualB"] = cuts_dual("dualB", s, m)
        variants["dualC"] = cuts_dual("dualC", s, m)
        variants["dualB_ref"] = refine(variants["dualB"], d, n, drop_unmatched=False)
        variants["dualB_ref_drop"] = refine(variants["dualB"], d, n, drop_unmatched=True)
        variants["raw_merge"] = merge_short(variants["raw"], n, SHORT_MERGE_FRAMES)
        variants["dualB_ref_merge"] = merge_short(variants["dualB_ref"], n, SHORT_MERGE_FRAMES)

        print("\n=== %s (fps=%.2f, %d 帧, %.1fs) | GT 段 %d / 边界 %d ===" % (
            case, fps, n, total_s, len(gt_segs), len(gt_b)), flush=True)
        print("  %-16s %5s %5s %8s %7s %6s %6s" % ("variant", "nb", "nseg", "avg_len", "GTcov", "inner", "split"), flush=True)
        row = {"case": case, "fps": round(fps, 3), "n_frames": n, "gt_seg": len(gt_segs), "gt_bounds": len(gt_b), "variants": {}}
        for name, cuts in variants.items():
            b = to_bounds(cuts, fps)
            st = stats(b, gt_segs, gt_b, total_s)
            row["variants"][name] = st
            print("  %-16s %5d %5d %8.2f %7.3f %6d %6d" % (
                name, st["nb"], st["nseg"], st["avglen"], st["cov"], st["inner"], st["split"]), flush=True)
        out[case] = row
    (BENCH / "work" / "tn_variants_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved work/tn_variants_summary.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
