# -*- coding: utf-8 -*-
"""方案1 验证 v2 —— 用 TransNetV2 切点**重划导出片段边界**(几何正确的镜头切分), 定位结果不动.

背景(FINDINGS_TN_CUT_QUALITY_VS_METRIC.md):
  * 盲判: TN 切点几何上明显更准(仅 TN 独有 8/8 真切换; 仅基线独有 2/8);
  * 但基线切点与 TN 切点本就有 ~87% 重合(双向 recall) -> 只"插入细分"收益极小;
  * 正确落点: **导出/展示层的片段边界改成 TN 切点**(用户看到的那一层几何正确),
    定位/指标完全不动(定位查询单元仍由生产切分器决定)。

做法:
  1. 载入生产结果批 -> build_export_plan() 得父 clips(定位产物, 不改);
  2. TN 切点 + [0, 视频时长] -> 记录侧重划为 N 个镜头片段;
  3. 每个镜头片段: 取与其重叠最长的父 clip, 源片侧按**比例映射**(段内 offset 恒定假设, 近似);
     无重叠父 clip 的片段 -> 标 unlocated(导出时可选择丢弃/仅展示);
  4. 统计: 片段数 / 时长分布 / 有定位比例 / 与 GT 编辑段边界一致性(参考) / 与父批边界的位移量。

用法: python mvp/scripts/probe_export_cut_split.py [case]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from app.exporters import build_export_plan                # noqa: E402
from app.locator_service import SourceLocatorService       # noqa: E402
from infrastructure.config import load_config              # noqa: E402
from infrastructure.logging import configure_logging       # noqa: E402
import tn_transnetv2 as tn                                 # noqa: E402

CASES = [
    ("2mkv",  r"D:\video\1.mp4", "work/rerun_2mkv_perfopt.results.json", "datasets/real/ground_truth_v4.json"),
    ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", "work/rerun_test1_perfopt.results.json", "datasets/real/ground_truth_test1.json"),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", "work/rerun_test2_perfopt.results.json", "datasets/real/ground_truth_test2.json"),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", "work/rerun_test3_perfopt.results.json", "datasets/real/ground_truth_test3.json"),
]
TN_PROVIDER = "DmlExecutionProvider"
EPS = 1e-6


def gt_bounds(gt_rel):
    d = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
    b = []
    for k in ("positives", "negatives"):
        for it in d.get(k, []):
            b += [float(it["edited"][0]), float(it["edited"][1])]
    return sorted(set(b))


def cover(bounds, ref, tol=0.5):
    if not bounds or not ref:
        return 0.0
    return sum(1 for x in bounds if min(abs(x - y) for y in ref) <= tol) / len(bounds)


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def resplit(clips, cuts, dur):
    """按 TN 切点重划记录侧; 每个镜头片段继承重叠最长父 clip 的源片位置(比例映射)."""
    pts = [0.0] + [c for c in sorted(cuts) if 0.0 < c < dur] + [float(dur)]
    segs = []
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if b - a <= EPS:
            continue
        best, best_ov = None, 0.0
        for c in clips:
            ov = overlap(a, b, c.edited_start, c.edited_end)
            if ov > best_ov + EPS:
                best, best_ov = c, ov
        if best is None:
            segs.append({"edited": [round(a, 3), round(b, 3)], "located": False})
            continue
        w_e = max(best.edited_end - best.edited_start, EPS)
        w_o = best.orig_end - best.orig_start
        fa = max(0.0, (a - best.edited_start) / w_e)
        fb = min(1.0, (b - best.edited_start) / w_e)
        segs.append({"edited": [round(a, 3), round(b, 3)], "located": True,
                     "orig": [round(best.orig_start + fa * w_o, 3), round(best.orig_start + fb * w_o, 3)],
                     "kind": best.kind, "confidence": best.confidence,
                     "seg_index": best.seg_index})
    return segs


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    configure_logging(stream=sys.stdout)
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    summary = {}
    for case, ed, res_rel, gt_rel in CASES:
        if only and case != only:
            continue
        dur = float(srv.ffmpeg.metadata(Path(ed)).duration or 0.0)
        batch = srv.load_results(BENCH / res_rel)
        clips = build_export_plan(batch, min_confidence="MEDIUM", low_policy="exclude", include_subs=False)
        t = tn.boundaries(srv.ffmpeg, Path(ed), provider=TN_PROVIDER)
        cuts = [float(x) for x in t["cuts_sec"]]
        segs = resplit(clips, cuts, dur)
        loc = [s for s in segs if s["located"]]
        unl = [s for s in segs if not s["located"]]
        w = np.array([s["edited"][1] - s["edited"][0] for s in segs]) if segs else np.zeros(1)
        base_b = sorted({b for c in clips for b in (c.edited_start, c.edited_end)})
        new_b = sorted({b for s in segs for b in s["edited"]})
        gt_b = gt_bounds(gt_rel)
        # 新边界相对父边界的位移(仅统计"被移动"的边界)
        shifts = [min(abs(b - x) for x in base_b) for b in new_b]
        row = {
            "case": case, "duration": round(dur, 2),
            "parent_clips": len(clips), "tn_cuts": len(cuts),
            "shot_segments": len(segs), "located": len(loc), "unlocated": len(unl),
            "located_ratio": round(len(loc) / max(len(segs), 1), 3),
            "width": {"min": round(float(w.min()), 2), "p50": round(float(np.median(w)), 2),
                      "max": round(float(w.max()), 2)},
            "gt_cover_parent": round(cover(base_b, gt_b), 3),
            "gt_cover_tn": round(cover(new_b, gt_b), 3),
            "bound_shift_med": round(float(np.median(shifts)), 3) if shifts else None,
        }
        summary[case] = row
        (BENCH / "work" / ("shot_cut_%s.json" % case)).write_text(
            json.dumps(segs, ensure_ascii=False, indent=1), encoding="utf-8")
        print("\n=== %s (dur=%.1fs) ===" % (case, dur), flush=True)
        print("  父 clips(定位产物)=%d -> 镜头片段(TN 重划)=%d | 有定位 %d (%.0f%%) / 无定位 %d" % (
            len(clips), len(segs), len(loc), 100 * len(loc) / max(len(segs), 1), len(unl)), flush=True)
        print("  片段时长: min=%.2f p50=%.2f max=%.2fs | 与 GT 编辑段边界一致率 %.3f" % (
            w.min(), np.median(w), w.max(), cover(new_b, gt_b)), flush=True)
        print("  边界位移: 相对父批中位 %.3fs | 写出 work/shot_cut_%s.json" % (
            float(np.median(shifts)) if shifts else -1, case), flush=True)
    (BENCH / "work" / "export_cut_split_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved work/export_cut_split_summary.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
