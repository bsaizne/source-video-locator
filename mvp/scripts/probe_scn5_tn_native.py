# -*- coding: utf-8 -*-
"""scn5 探针 v2：只用**原生 fps** 重跑那 15 段 + 对照段。

为什么：v1 用 8fps 降采样跑全片（省时间），结果 15 段真漏切里 TN 切点 = 0。
但 TN 是在**原生 fps(24~30)** 上训练的切点检测器，降到 8fps 等于把时间轴压 3 倍，
破坏了模型前提 => v1 的 0 不能当证据。本脚本用原生 fps 逐段复核。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import tn_transnetv2 as tn                           # noqa: E402

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
SRC = Path(r"D:\ProjectXIXI\test1\test1-om.mkv")
FINAL = BENCH / "work" / "boundary_20261018" / "gt_expand_final.json"
OUT = BENCH / "work" / "boundary_20261018" / "scn5_tn_native.json"


def frames_native(t0, t1, fps):
    """按原生 fps 取 [t0,t1] 的 48x27 RGB 帧。"""
    cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error",
           "-ss", "%.3f" % t0, "-t", "%.3f" % (t1 - t0), "-i", str(SRC),
           "-vf", "fps=%g,scale=48:27" % fps, "-pix_fmt", "rgb24",
           "-f", "rawvideo", "-"]
    p = subprocess.run(cmd, capture_output=True, timeout=900)
    buf = np.frombuffer(p.stdout, dtype=np.uint8)
    n = buf.size // (48 * 27 * 3)
    return buf[:n * 48 * 27 * 3].reshape(n, 27, 48, 3)


def probe_one(idx, span, fps, provider):
    t0, t1 = span
    arr = frames_native(t0, t1, fps)
    if arr.shape[0] < tn.WINDOW:
        return {"idx": idx, "n_frames": int(arr.shape[0]), "cuts": [], "note": "too few frames"}
    pred = tn.predict(arr, provider=provider)
    idxs = tn.cuts_from_pred(pred)
    cuts = [round(t0 + i / fps, 2) for i in idxs if i > 0]
    return {"idx": idx, "n_frames": int(arr.shape[0]), "fps": fps,
            "pred_max": round(float(pred.max()), 4),
            "pred_p99": round(float(np.percentile(pred, 99)), 4),
            "cuts": cuts, "n_cuts": len(cuts)}


def main():
    provider = "DmlExecutionProvider"
    fps = 23.976023976023978   # 原片原生 fps
    final = json.loads(FINAL.read_text(encoding="utf-8"))
    multi = [r for r in final if r["verdict"] == "multi"]
    single = [r for r in final if r["verdict"] == "single"]
    only = sys.argv[1:] or None
    print("原生 fps = %.3f，逐段取帧（不走全片降采样）" % fps)
    print("")
    res_m, res_s = [], []
    for r in multi:
        if only and str(r["idx"]) not in only:
            continue
        t = time.monotonic()
        x = probe_one(r["idx"], r["span"], fps, provider)
        x["width"] = round(r["span"][1] - r["span"][0], 1)
        res_m.append(x)
        print("  MULTI idx=%-4d [%6.0f,%6.0f] %4.0fs %6d帧 pred99=%.3f -> 切点 %d %s (%.1fs)" % (
            r["idx"], r["span"][0], r["span"][1], x["width"], x["n_frames"],
            x.get("pred_p99", 0), len(x["cuts"]),
            " ".join("%.1f" % c for c in x["cuts"][:6]), time.monotonic() - t), flush=True)
    print("")
    for r in single:
        if only and str(r["idx"]) not in only:
            continue
        x = probe_one(r["idx"], r["span"], fps, provider)
        x["width"] = round(r["span"][1] - r["span"][0], 1)
        res_s.append(x)
        print("  SINGLE idx=%-4d [%6.0f,%6.0f] %4.0fs %6d帧 pred99=%.3f -> 切点 %d %s" % (
            r["idx"], r["span"][0], r["span"][1], x["width"], x["n_frames"],
            x.get("pred_p99", 0), len(x["cuts"]), " ".join("%.1f" % c for c in x["cuts"][:6])), flush=True)
    print("")
    nm = sum(x["n_cuts"] for x in res_m)
    ns = sum(x["n_cuts"] for x in res_s)
    hm = sum(1 for x in res_m if x["n_cuts"] > 0)
    hs = sum(1 for x in res_s if x["n_cuts"] > 0)
    print("=== 汇总（原生 fps） ===")
    print("  真漏切 %d 段：有切点的 %d 段，切点共 %d 个（段均 %.2f）" % (
        len(res_m), hm, nm, nm / max(len(res_m), 1)))
    print("  单镜头 %d 段：有切点的 %d 段，切点共 %d 个（段均 %.2f）" % (
        len(res_s), hs, ns, ns / max(len(res_s), 1)))
    OUT.write_text(json.dumps({"fps": fps, "multi": res_m, "single": res_s,
                               "summary": {"multi_segs": len(res_m), "multi_hit": hm,
                                           "multi_cuts": nm, "single_segs": len(res_s),
                                           "single_hit": hs, "single_cuts": ns}},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print("")
    print("wrote " + str(OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())