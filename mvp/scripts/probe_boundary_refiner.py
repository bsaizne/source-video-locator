"""边界精修判据对照探针 (2026-09-26) —— 竞品已确证参数 vs 我方现行精修.

背景
  竞品(09 §8.1 字节确证 + 与我方 A7 7/7 一致): refine_commentary_scene_split_with_frame_diff
    min_segment_frames=32, min_side_frames=10, near_cut_frames=16, absolute_diff_min=45,
    mad_multiplier=4, max_move_frames=16, max_additions_per_segment=1; 代理尺寸 96x54.
  我方现行(_refine_cut_twopass): DINOv2 CLS 相邻距离峰, 切点 ±20 帧窗 @ fine_fps(vfps/2), 白闪守卫。
  => 两者是**不同判据**(像素帧差 vs 语义嵌入距离), 参数只确证了竞品那一侧; 其**规则形状是假设**(H-CM1)。

本探针: 对我方现行边界逐条施加 H-CM1 判据, 输出位移分布与"分歧点"清单, 并为分歧点出图供**视觉/多模态复审**。
  不做任何 runtime 改动; 不宣称谁对 —— 谁是真切换由画面裁决(先看图再下结论)。

用法: python mvp/scripts/probe_boundary_refiner.py [--out work/boundary_refiner_probe.json] [--sheets N]
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
from media.ffmpeg import FFmpegIO  # noqa: E402

CASES = [
    ("2mkv", r"D:\video\1.mp4", "work/rerun_2mkv_perfopt.results.json"),
    ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", "work/rerun_test1_perfopt.results.json"),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", "work/rerun_test2_perfopt.results.json"),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", "work/rerun_test3_perfopt.results.json"),
]
# H-CM1 (假设的竞品精修规则; 参数值来自 09 §8.1 字节确证)
NEAR_CUT = 16
ABS_DIFF_MIN = 45.0
MAD_MULT = 4.0
MAX_MOVE = 16
MIN_SEG = 32
MIN_SIDE = 10


def boundaries_from_results(path: Path) -> list[float]:
    res = json.loads(path.read_text(encoding="utf-8"))["results"]
    bs = set()
    for r in res:
        s, e = r["edited_segment"]["start"], r["edited_segment"]["end"]
        if s > 0.05:
            bs.add(round(s, 3))
        if e > 0.05:
            bs.add(round(e, 3))
    return sorted(bs)


def h_cm1(d: np.ndarray, f: int, n: int) -> tuple[int, dict]:
    """H-CM1: ±NEAR_CUT 帧窗内取帧差峰; 需 >= max(45, 4*MAD_local) 且位移 <= MAX_MOVE."""
    lo, hi = max(1, f - NEAR_CUT), min(n - 1, f + NEAR_CUT)
    if hi - lo < 3:
        return f, {"reason": "window_too_small"}
    seg = d[lo - 1:hi]                      # d[i] = |gray[i+1]-gray[i]|
    k = int(np.argmax(seg))
    cand = lo + k                           # 切点 = 第 cand 帧之后
    peak = float(seg[k])
    med = float(np.median(seg))
    mad = float(np.median(np.abs(seg - med))) * 1.4826
    thr = max(ABS_DIFF_MIN, MAD_MULT * mad)
    info = {"peak": peak, "mad": mad, "thr": thr, "cand": cand,
            "cand_t_shift_frames": cand - f}
    if abs(cand - f) > MAX_MOVE:
        return f, dict(info, reason="exceeds_max_move")
    if peak < thr:
        return f, dict(info, reason="below_threshold")
    return cand, dict(info, reason="moved")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(BENCH / "work" / "boundary_refiner_probe.json"))
    ap.add_argument("--sheets", type=int, default=16, help="为前 N 个最大分歧点出对照图")
    args = ap.parse_args()

    ff = FFmpegIO()
    report, disputed = {}, []
    for case, video, res_rel in CASES:
        meta = ff.metadata(video)
        vfps = float(meta.fps or 30.0)
        grays = []
        for _t, fr in ff.iter_frames(video, fps=vfps, scale=(96, 54)):
            grays.append(fr.mean(axis=2))
        g = np.asarray(grays, dtype=np.float32)
        d = np.abs(np.diff(g, axis=0)).mean(axis=(1, 2)) if len(g) > 1 else np.zeros(1, dtype=np.float32)
        bs = boundaries_from_results(BENCH / res_rel)
        rows = []
        for b in bs:
            f = int(round(b * vfps))
            if f < 2 or f > len(d) - 2:
                continue
            nf, info = h_cm1(d, f, len(d) + 1)
            rows.append({"boundary_s": b, "frame": f, "cm_frame": nf,
                         "shift_frames": nf - f, "shift_s": (nf - f) / vfps,
                         "diff_at_ours": float(d[f - 1]), "diff_at_cm": float(d[nf - 1]) if 0 < nf <= len(d) else None,
                         **info})
        shifts = np.array([abs(r["shift_frames"]) for r in rows]) if rows else np.zeros(0)
        report[case] = {"video": video, "vfps": round(vfps, 3), "frames": len(g),
                        "n_boundaries": len(rows),
                        "moved_any": int((shifts > 0).sum()) if len(shifts) else 0,
                        "moved_ge5": int((shifts >= 5).sum()) if len(shifts) else 0,
                        "moved_ge10": int((shifts >= 10).sum()) if len(shifts) else 0,
                        "shift_p50": float(np.percentile(shifts, 50)) if len(shifts) else 0.0,
                        "shift_p90": float(np.percentile(shifts, 90)) if len(shifts) else 0.0,
                        "diff_at_ours_p50": float(np.percentile([r["diff_at_ours"] for r in rows], 50)) if rows else 0.0,
                        "diff_at_ours_p90": float(np.percentile([r["diff_at_ours"] for r in rows], 90)) if rows else 0.0,
                        "rows": rows}
        print("=== %s: 边界 %d 条, 帧 %d @ %.2ffps | 位移>0: %d, >=5帧: %d, >=10帧: %d | |Δ| p50=%.1f p90=%.1f 帧"
              % (case, len(rows), len(g), vfps, report[case]["moved_any"], report[case]["moved_ge5"],
                 report[case]["moved_ge10"], report[case]["shift_p50"], report[case]["shift_p90"]), flush=True)
        print("    我方边界处帧差: p50=%.1f p90=%.1f (竞品 absolute_diff_min=45 的量纲参照)"
              % (report[case]["diff_at_ours_p50"], report[case]["diff_at_ours_p90"]), flush=True)
        for r in rows:
            if abs(r["shift_frames"]) >= 5:
                disputed.append({"case": case, **r})
    disputed.sort(key=lambda r: -abs(r["shift_frames"]))
    print("\n分歧点(位移>=5 帧) 合计 %d 条; 最大 10 条:" % len(disputed))
    for r in disputed[:10]:
        print("   %-6s t=%.2fs 我方->CM 位移 %+d 帧 (%.2fs) | 帧差@我方=%.1f @CM=%.1f (%s)" % (
            r["case"], r["boundary_s"], r["shift_frames"], r["shift_s"],
            r["diff_at_ours"], r["diff_at_cm"] or -1, r["reason"]))
    Path(args.out).write_text(json.dumps({"params": {"near_cut": NEAR_CUT, "abs_diff_min": ABS_DIFF_MIN,
                                                     "mad_multiplier": MAD_MULT, "max_move": MAX_MOVE},
                                          "cases": report, "disputed": disputed},
                                         ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
