# -*- coding: utf-8 -*-
"""scn5 探针（只读）：TransNetV2 能不能切出我方**原片侧**漏掉的切点？"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                      r"\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from media.ffmpeg.ffmpeg_io import FFmpegIO          # noqa: E402
import tn_transnetv2 as tn                           # noqa: E402

ORIGINAL = Path(r"D:\ProjectXIXI\test1\test1-om.mkv")
IDX = Path(r"C:\Users\Bsaizne\AppData\Local\SourceVideoLocator\index\test1-om__5d4fdc2b.idx")
FINAL = BENCH / "work" / "boundary_20261018" / "gt_expand_final.json"
CACHE = BENCH / "work" / "boundary_20261018" / "scn5_tn_cuts_cache.json"
OUT = BENCH / "work" / "boundary_20261018" / "scn5_tn_probe.json"
FPS = 8.0


def get_tn_cuts(provider):
    if CACHE.exists():
        d = json.loads(CACHE.read_text(encoding="utf-8"))
        print("复用缓存 TN 切点 %d 条（provider=%s, %.1ffps）" % (
            len(d["tn_cuts_sec"]), d["provider"], d["sample_fps"]))
        return d["tn_cuts_sec"], d
    ff = FFmpegIO()
    meta = ff.metadata(ORIGINAL)
    print("原片: fps=%s dur=%s" % (meta.fps, meta.duration))
    t0 = time.monotonic()
    frames = [bgr[..., ::-1].copy() for _, bgr in ff.iter_frames(ORIGINAL, FPS, scale=(48, 27))]
    print("取帧 %d 帧 %.1fs" % (len(frames), time.monotonic() - t0), flush=True)
    arr = np.stack(frames, axis=0)
    t1 = time.monotonic()
    pred = tn.predict(arr, provider=provider)
    print("TN 推理 %.1fs" % (time.monotonic() - t1), flush=True)
    idx = tn.cuts_from_pred(pred)
    cuts = [i / FPS for i in idx if 0.5 < i / FPS < 8219.0]
    d = {"provider": provider, "sample_fps": FPS,
         "n_frames": len(frames), "n_tn": len(cuts),
         "pred_max": float(pred.max()), "pred_mean": float(pred.mean()),
         "tn_cuts_sec": [round(x, 3) for x in cuts]}
    CACHE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return cuts, d


def match_tol(a, b, tol=0.5):
    if not a or not b:
        return None
    da = [min(abs(x - y) for y in b) for x in a]
    return {"n": len(a), "recall": round(sum(d <= tol for d in da) / len(da), 3),
            "med_dist": round(float(np.median(da)), 3),
            "max_dist": round(float(max(da)), 3)}


def main():
    provider = "DmlExecutionProvider" if (len(sys.argv) > 1 and sys.argv[1].lower().startswith("dml")) else "CPUExecutionProvider"
    scenes = np.load(IDX / "scenes.npy")
    ours = sorted({float(x) for x in scenes[:, 0]} | {float(x) for x in scenes[:, 1]})
    ours = [x for x in ours if 0.5 < x < 8219.0]
    print("我方 scenes.npy: %d 段 / %d 条内部边界" % (scenes.shape[0], len(ours)))
    tn_sec, info = get_tn_cuts(provider)
    print("TN 切点 = %d 条 (阈值 %.2f)" % (len(tn_sec), tn.THRESH))
    print("")
    print("=== 一致性 (tol=0.5s) ===")
    print("  我方 -> TN : %s" % match_tol(ours, tn_sec))
    print("  TN -> 我方 : %s" % match_tol(tn_sec, ours))

    final = json.loads(FINAL.read_text(encoding="utf-8"))
    multi = [r for r in final if r["verdict"] == "multi"]
    print("")
    print("=== 15 段真漏切：段内 TN 切点 ===")
    rows = []
    hit = 0
    for r in multi:
        a, b = r["span"]
        inside = [x for x in tn_sec if a + 2.0 < x < b - 2.0]
        if inside:
            hit += 1
        rows.append({"idx": r["idx"], "span": [a, b], "width": round(b - a, 1),
                     "n_tn": len(inside), "tn": [round(x, 2) for x in inside]})
        print("  idx=%-4d [%6.0f,%6.0f] %4.0fs -> %2d  %s" % (
            r["idx"], a, b, b - a, len(inside), " ".join("%.1f" % x for x in inside[:8])))

    single = [r for r in final if r["verdict"] == "single"]
    print("")
    print("=== 反向对照：9 段单镜头（TN 应当不切） ===")
    fc = 0
    srows = []
    for r in single:
        a, b = r["span"]
        inside = [x for x in tn_sec if a + 2.0 < x < b - 2.0]
        fc += len(inside)
        srows.append({"idx": r["idx"], "span": [a, b], "n_tn": len(inside),
                      "tn": [round(x, 2) for x in inside]})
        print("  idx=%-4d [%6.0f,%6.0f] %4.0fs -> %2d" % (r["idx"], a, b, b - a, len(inside)))

    print("")
    print("=== 汇总 ===")
    print("  真漏切 15 段：TN 至少切出 1 个 = %d / %d" % (hit, len(multi)))
    print("  真漏切段内 TN 切点总数 = %d" % sum(x["n_tn"] for x in rows))
    print("  单镜头 9 段：TN 误切总数 = %d" % fc)
    print("  判别力 = 真漏切段均 %.2f 个 vs 单镜头段均 %.2f 个" % (
        sum(x["n_tn"] for x in rows) / max(len(rows), 1), fc / max(len(srows), 1)))

    OUT.write_text(json.dumps({**info, "n_ours": len(ours),
        "ours_to_tn": match_tol(ours, tn_sec), "tn_to_ours": match_tol(tn_sec, ours),
        "multi_rows": rows, "single_rows": srows, "single_false_cut": fc,
        "multi_hit": hit}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("")
    print("wrote " + str(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())