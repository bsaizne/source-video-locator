"""stability — H2 长时稳定性验证（DirectML 大 N 流式推理，内存曲线判定）。

目标：回答 POC 遗留 caveat —— DML 500 帧内进程内存 +528MB，是 onnxruntime 执行栈 arena
**一次性预热**（之后平台期，可接受），还是**随帧数无界增长**（真实泄漏，阻断 H2）。

方法（贴近产品 FeatureStore.create_index 的流式行为，避免一次性 [N,3,518,518] 占 9GB）：
逐 batch 生成/预处理帧 -> DML forward -> L2 归一 -> 数值健康检查 -> 释放对象，
每 ``sample_every`` 帧采样一次进程工作集内存，画 mem-vs-frame 曲线并做趋势判读：
  尾部斜率≈0 且后段涨幅远小于前段 -> 平台期(arena 预热,PASS)
  尾部持续线性增长               -> 无界增长(FAIL)

只读复用冻结模型/预处理；不改任何生产源码；产物在本目录。

用法：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/poc/amdgpu_onnx/stability.py
  [--frames 3000] [--batch 8] [--sample 100] [--w 960] [--h 540]
"""
from __future__ import annotations

import gc
import json
import os
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
POC_DIR = Path(__file__).resolve().parent
if str(POC_DIR) not in sys.path:
    sys.path.insert(0, str(POC_DIR))

import numpy as np  # noqa: E402
from common import (CPUExecutionProvider, DmlExecutionProvider, MODEL_PATH,  # noqa: E402
                    gen_frames, l2norm, l2_norms, make_session, preprocess_np,
                    proc_mem_mb, run_onnx_forward)

# 判读阈值（POC 判定用，非生产阈值）
TAIL_SLOPE_PASS_MB_PER_FRAME = 0.002   # 尾部线性斜率低于此(MB/帧) -> 视为平台期
TAIL_GROWTH_VS_HEAD_RATIO = 0.5        # 后 20% 涨幅 / 前 20% 涨幅 低于此 -> 平台期


def _tail_slope(ys, xs):
    """最后 50% 点的线性拟合斜率 (MB/帧)。"""
    import numpy as np
    half = max(3, len(ys) // 2)
    x = np.asarray(xs[-half:], dtype=np.float64)
    y = np.asarray(ys[-half:], dtype=np.float64)
    if x.std() < 1e-9:
        return 0.0
    return float(np.polyfit(x, y, 1)[0])


def main() -> int:
    args = sys.argv
    n = int(args[args.index("--frames") + 1] if "--frames" in args else 3000)
    batch = int(args[args.index("--batch") + 1] if "--batch" in args else 8)
    sample = int(args[args.index("--sample") + 1] if "--sample" in args else 100)
    w = int(args[args.index("--w") + 1] if "--w" in args else 960)
    h = int(args[args.index("--h") + 1] if "--h" in args else 540)

    print(f"=== H2 长时稳定性 (DirectML) ===")
    print(f"frames={n} batch={batch} sample_every={sample} source_res={w}x{h}")
    sess = make_session(MODEL_PATH, providers=[("DmlExecutionProvider", {"device_id": 0}),
                                               CPUExecutionProvider])
    print("providers:", sess.get_providers())

    # warmup：先跑一个 batch，让 DML 执行栈完成一次初始化/arena 分配
    wf = gen_frames(batch, size=(w, h))
    wx = preprocess_np(wf)
    run_onnx_forward(sess, wx, batch)
    del wf, wx
    gc.collect()

    mem0 = proc_mem_mb()
    # 流式逐 batch（N 总帧，非一次性大张量）
    curve: list[dict] = []
    mem_ys: list[float] = []
    mem_xs: list[int] = []
    frame_i = 0
    max_norm_dev = 0.0
    nonfinite = 0
    t0 = time.perf_counter()
    print(f"[warmup done] mem={mem0:.0f}MB")
    while frame_i < n:
        bs = min(batch, n - frame_i)
        frames = gen_frames(bs, size=(w, h))
        xin = preprocess_np(frames)
        out = run_onnx_forward(sess, xin, bs)
        rm = l2norm(out)
        nrm = l2_norms(rm)
        if not np.all(np.isfinite(out)):
            nonfinite += 1
        max_norm_dev = max(max_norm_dev, float(np.max(np.abs(nrm - 1.0))))
        del frames, xin, out, rm, nrm
        frame_i += bs
        if frame_i % sample == 0 or frame_i >= n:
            gc.collect()
            m = proc_mem_mb()
            el = time.perf_counter() - t0
            curve.append({"frame": frame_i, "elapsed_s": round(el, 1), "mem_mb": m})
            mem_ys.append(m)
            mem_xs.append(frame_i)
            print(f"  frame={frame_i}/{n}  mem={m:.0f}MB  elapsed={el:.0f}s")
    mem_end = proc_mem_mb()

    # ---- 判读 ----
    head = mem_ys[: max(1, len(mem_ys) // 5)]
    tail = mem_ys[-max(1, len(mem_ys) // 5):]
    head_mean = float(np.mean(head)) if head else mem0
    tail_mean = float(np.mean(tail)) if tail else mem_end
    head_growth = head_mean - mem0
    tail_growth = tail_mean - (float(np.mean(mem_ys[: len(mem_ys) - len(tail)]))
                               if len(mem_ys) > len(tail) else mem0)
    tail_slope = _tail_slope(mem_ys, mem_xs)
    ratio = (tail_growth / head_growth) if head_growth > 1 else 0.0

    if tail_slope < TAIL_SLOPE_PASS_MB_PER_FRAME and ratio < TAIL_GROWTH_VS_HEAD_RATIO:
        verdict = "PLATEAU"
        ok = True
        why = (f"尾部斜率 {tail_slope:.5f} MB/帧 (<{TAIL_SLOPE_PASS_MB_PER_FRAME}) "
               f"且后段涨幅/前段涨幅 {ratio:.2f} (<{TAIL_GROWTH_VS_HEAD_RATIO}) -> DML arena 一次性预热")
    elif tail_slope >= TAIL_SLOPE_PASS_MB_PER_FRAME:
        verdict = "UNBOUNDED"
        ok = False
        why = f"尾部斜率 {tail_slope:.5f} MB/帧 (>=阈值) -> 疑似随帧数无界增长"
    else:
        verdict = "PARTIAL_GROWTH"
        ok = False
        why = (f"后段涨幅/前段涨幅 {ratio:.2f} (>=阈值) 但尾部斜率 {tail_slope:.5f} "
               f"仍较低 -> 中间仍有明显增长，未确认平台期")
    overall = {
        "ran": True, "verdict": verdict, "ok": ok, "why": why,
        "frames": n, "batch": batch,
        "mem_start_mb": mem0, "mem_end_mb": mem_end,
        "mem_growth_mb": round(mem_end - mem0, 1),
        "head_mean_mb": round(head_mean, 1), "tail_mean_mb": round(tail_mean, 1),
        "tail_slope_mb_per_frame": round(tail_slope, 5),
        "tail_vs_head_growth_ratio": round(ratio, 3),
        "max_norm_dev": round(max_norm_dev, 6), "nonfinite_batches": nonfinite,
        "curve": curve,
    }
    report = {"stability_longrun": overall}
    (POC_DIR / "stability.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                            encoding="utf-8")

    print("\n=== 长时稳定性判读 ===")
    print(f"verdict: {verdict}  ok={ok}")
    print(f"  mem {mem0:.0f} -> {mem_end:.0f} MB (+{mem_end - mem0:.1f}MB)")
    print(f"  head_mean={head_mean:.1f}  tail_mean={tail_mean:.1f}")
    print(f"  tail_slope={tail_slope:.5f} MB/帧  tail/head_growth_ratio={ratio:.2f}")
    print(f"  max_norm_dev={max_norm_dev:.6f}  nonfinite_batches={nonfinite}")
    print(f"  why: {why}")
    # 简要文本曲线
    print("\nmem curve:")
    for c in curve:
        bar = "#" * max(0, int((c["mem_mb"] - mem0) / 10))
        print(f"  {c['frame']:>5}  {c['mem_mb']:>7.0f}MB  {c['elapsed_s']:>6}s  {bar}")
    print(f"\nLONGRUN_STABILITY: {verdict}  ({'PASS' if ok else 'FAIL'})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
