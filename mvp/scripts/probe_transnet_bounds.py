# -*- coding: utf-8 -*-
"""A1-bounds —— 编辑侧边界三方对比(纯离线): GT 编辑段 vs 我方 twopass vs TransNetV2.

* GT: datasets/real/ground_truth_{v4,test1,test2,test3}.json 的 positives+negatives edited 区间;
* 我方 twopass: 基线结果 work/rerun_<case>_perfopt.results.json 的 edited_segment 边界
  (生产路径两级切分+白闪守卫的产物, 段数 69/41/54/67 与记录一致);
* TransNetV2: 官方权重原生 fps 出边界(见 tn_transnetv2.py)。

指标: 双向容差 0.5s 的 recall/precision(每个边界到对面最近边界的距离) 与中位距离。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

import numpy as np                                   # noqa: E402
from media.ffmpeg.ffmpeg_io import FFmpegIO          # noqa: E402
import tn_transnetv2 as tn                           # noqa: E402

CASES = [
    ("2mkv",  r"D:\video\1.mp4", "ground_truth_v4.json", "rerun_2mkv_perfopt.results.json"),
    ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", "ground_truth_test1.json", "rerun_test1_perfopt.results.json"),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", "ground_truth_test2.json", "rerun_test2_perfopt.results.json"),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", "ground_truth_test3.json", "rerun_test3_perfopt.results.json"),
]
TOL = 0.5


def gt_bounds(case_gt: str):
    d = json.loads((BENCH / "datasets" / "real" / case_gt).read_text(encoding="utf-8"))
    segs = []
    for k in ("positives", "negatives"):
        for it in d.get(k, []):
            a, b = it["edited"]
            segs.append([float(a), float(b)])
    segs.sort()
    return sorted({s for seg in segs for s in seg}), segs


def base_bounds(res_name: str):
    p = BENCH / "work" / res_name
    if not p.exists():
        return None, None
    rs = json.loads(p.read_text(encoding="utf-8"))["results"]
    segs = sorted([[float(r["edited_segment"]["start"]), float(r["edited_segment"]["end"])] for r in rs])
    return sorted({s for seg in segs for s in seg}), segs


def match(a: list[float], b: list[float], tol: float = TOL) -> dict:
    if not a or not b:
        return {"na": len(a), "nb": len(b), "recall": None, "precision": None, "med": None}
    da = [min(abs(x - y) for y in b) for x in a]
    db = [min(abs(y - x) for x in a) for y in b]
    return {"na": len(a), "nb": len(b),
            "recall": sum(x <= tol for x in da) / len(a),
            "precision": sum(x <= tol for x in db) / len(b),
            "med": float(np.median(da))}


def main() -> int:
    provider = sys.argv[1] if len(sys.argv) > 1 else "CPUExecutionProvider"
    ff = FFmpegIO()
    out = {}
    for name, ed, gt_f, res_f in CASES:
        g, g_segs = gt_bounds(gt_f)
        b, b_segs = base_bounds(res_f)
        t = tn.boundaries(ff, Path(ed), provider=provider)
        t_sec = t["cuts_sec"]
        row = {
            "case": name, "tn_provider": provider, "tn_fps": round(t["fps"], 3),
            "tn_frames": t["n_frames"], "tn_elapsed_s": round(t["elapsed"], 1),
            "n_gt_bounds": len(g), "n_gt_segments": len(g_segs),
            "n_base_bounds": len(b) if b else None, "n_base_segments": len(b_segs) if b_segs else None,
            "n_tn_bounds": len(t_sec), "n_tn_segments": len(t_sec),
            "gt_vs_base": match(g, b) if b else None,
            "gt_vs_tn": match(g, t_sec),
            "base_vs_tn": match(b, t_sec) if b else None,
        }
        out[name] = row
        print("\n=== %s (edited %s, fps=%.2f, %d 帧, TN %.1fs) ===" % (
            name, Path(ed).name, t["fps"], t["n_frames"], t["elapsed"]), flush=True)
        print("  边界数: GT=%d(段%d)  基线=%s(段%s)  TransNetV2=%d" % (
            len(g), len(g_segs), len(b) if b else "-", len(b_segs) if b_segs else "-", len(t_sec)), flush=True)
        for k, lbl in (("gt_vs_base", "GT vs 基线"), ("gt_vs_tn", "GT vs TN  "), ("base_vs_tn", "基线 vs TN")):
            r = row[k]
            if not r:
                print("  %s: -" % lbl, flush=True); continue
            rec = "-" if r["recall"] is None else "%.3f" % r["recall"]
            pre = "-" if r["precision"] is None else "%.3f" % r["precision"]
            med = "-" if r["med"] is None else "%.3fs" % r["med"]
            print("  %s recall=%s precision=%s med_dist=%s" % (lbl, rec, pre, med), flush=True)
    (BENCH / "work" / "tn_bounds_summary.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved work/tn_bounds_summary.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
