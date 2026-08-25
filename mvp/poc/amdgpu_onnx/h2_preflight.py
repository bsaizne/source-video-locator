"""h2_preflight — DirectML 长时索引稳定性验证（唯一目标：查无界内存增长）。

用与 POC **完全相同**的 ONNX graph / DirectML provider / preprocess / batch_size / L2 归一，
在**完整真实原片** datasets/real/originals/2.mkv @0.5fps(~3834帧) 上流式跑推理，模拟建索引的
特征提取负担（逐批 forward、丢弃原始帧、只保留瞬时特征做 norm 检查）。记录 checkpoint 处
RSS / fps / batch 时长 / all_finite / feature norm / shape。

关键判断：
  1) 内存是否趋于稳定  2) 是否近似线性增长  3) 后期 fps 是否明显下降
  4) 是否出现 DML device/allocator 错误  5) 能否完整跑完 3834 帧

结论标签（启发式，附原始数据供人工判断）：
  - warmup/cache overhead，可接受   -> MEMORY_STABLE
  - 持续近似线性增长                -> MEMORY_LEAK_RISK（不接入 MVP）

不改任何模型/batch/feature/算法；不解决代码；不调参；不进 UI。用法：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/poc/amdgpu_onnx/h2_preflight.py
可选：--batch 8  --max-frames 3834   （--max-frames 也可设小值做快速冒烟）
"""
from __future__ import annotations

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
SRC = POC_DIR.parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np  # noqa: E402

from common import (MODEL_PATH, l2norm, l2_norms, list_gpu_names,  # noqa: E402
                    make_session, preprocess_np, proc_mem_mb)

from media.ffmpeg import FFmpegIO  # noqa: E402

BENCH = Path(__file__).resolve().parents[3]                       # -> benchmark
ORIG = BENCH / "datasets" / "real" / "originals" / "2.mkv"
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")


def main() -> int:
    args = sys.argv
    batch = int(args[args.index("--batch") + 1] if "--batch" in args else 8)
    max_frames = int(args[args.index("--max-frames") + 1] if "--max-frames" in args else 3834)
    checkpoints = [250, 500, 1000, 2000, 3000, 3834]
    checkpoints = sorted({int(round(c)) for c in checkpoints if c <= max_frames} | {max_frames})

    print(f"=== H2-Preflight: DirectML long-run index stability ===")
    print(f"source: {ORIG}")
    print(f"batch={batch}  max_frames={max_frames}  checkpoints={checkpoints}")
    print(f"GPU (WMI): {list_gpu_names()}")
    print(f"model: {MODEL_PATH}")

    # --- DirectML session（与 POC 相同的 provider，device_id=0）---
    sess = make_session(MODEL_PATH, providers=[("DmlExecutionProvider", {"device_id": 0}),
                                               "CPUExecutionProvider"])
    print(f"providers: {sess.get_providers()}")
    # GPU VRAM：onnxruntime-directml 无公开 query API -> 记录 NOT_AVAILABLE
    vram_probe = "NOT_AVAILABLE_VIA_ORT_DML"

    ff = FFmpegIO(FFMPEG, FFPROBE)
    md = ff.metadata(ORIG)
    print(f"video: {md.width}x{md.height} fps={md.fps} duration={md.duration:.1f}s")

    # 起始 RSS（session 创建后、第一批 forward 前）
    start_rss = proc_mem_mb()
    print(f"[baseline] session_rss={start_rss} MB  (before first forward)")

    cp_records = []
    frame_iter = ff.iter_frames(ORIG, 0.5)
    acc: list[np.ndarray] = []
    done = 0
    first_forward_t = None
    last_forward_t = None
    last_batch_s = 0.0
    peak_rss = start_rss if start_rss is not None else 0.0
    remaining = sorted(checkpoints)
    failed = None
    t_start_all = None

    def _process(acc_batch):
        """跑一次 DML forward + norm/finite 检查；返回 (raw out, norms, finite)。"""
        nonlocal last_batch_s, first_forward_t, last_forward_t
        t0 = time.perf_counter()
        inputs = preprocess_np(acc_batch)                            # [B,3,518,518]
        out = sess.run(["embedding"], {"input": inputs})[0]          # [B,384] raw CLS
        last_batch_s = time.perf_counter() - t0
        if first_forward_t is None:
            first_forward_t = time.perf_counter()
        last_forward_t = time.perf_counter()
        feats_l2 = l2norm(out.astype(np.float32))
        finite = bool(np.all(np.isfinite(feats_l2)))
        norms = l2_norms(feats_l2)
        return out, norms, finite

    def _record(done, out, norms, finite):
        nonlocal peak_rss
        rss = proc_mem_mb()
        if rss is not None and rss > peak_rss:
            peak_rss = rss
        elapsed = (last_forward_t - first_forward_t) if first_forward_t else 0.0
        fps = done / elapsed if elapsed > 0 else float("nan")
        cp_records.append({
            "frames": done, "rss_mb": rss, "gpu_vram": vram_probe,
            "elapsed_s": round(elapsed, 2), "fps": round(float(fps), 2),
            "last_batch_ms": round(last_batch_s * 1000.0, 2),
            "all_finite": finite, "feature_norm_mean": round(float(norms.mean()), 6),
            "feature_norm_max": round(float(norms.max()), 6),
            "output_shape": [int(out.shape[0]), int(out.shape[1])],
        })
        print(f"  chk {done:5d}: rss={rss if rss is not None else 'n/a'} MB "
              f"fps={fps:.2f} batch_ms={last_batch_s*1000:.1f} "
              f"finite={finite} norm_max={norms.max():.4f}")

    def _flush_and_checkpoint():
        nonlocal acc
        if not acc:
            return
        out, norms, finite = _process(acc)
        acc = []
        while remaining and done >= remaining[0]:
            remaining.pop(0)
            _record(done, out, norms, finite)

    try:
        t_start_all = time.perf_counter()
        for t, bgr in frame_iter:
            if done >= max_frames:
                break
            acc.append(bgr)
            done += 1
            # 满 batch 或已达上限（尾帧可能不足 batch）即 flush
            if len(acc) == batch or done >= max_frames:
                _flush_and_checkpoint()
        # EOF：flush 残留 acc（视频提前结束时的尾帧）
        if failed is None:
            _flush_and_checkpoint()
    except Exception as exc:  # noqa: BLE001
        failed = f"{type(exc).__name__}: {exc}"
        print(f"[FAILED] {failed}")

    final_rss = proc_mem_mb()


    end_to_end_s = (last_forward_t - t_start_all) if (last_forward_t and t_start_all) else 0.0
    fps_total = done / end_to_end_s if end_to_end_s > 0 else float("nan")

    # ---- 判定 ----
    growth_mb = (final_rss - start_rss) if (final_rss is not None and start_rss is not None) else None
    # 逐 interval delta + 斜率
    deltas = []
    for i in range(1, len(cp_records)):
        df = cp_records[i]["frames"] - cp_records[i - 1]["frames"]
        dr = (cp_records[i]["rss_mb"] - cp_records[i - 1]["rss_mb"]) if cp_records[i]["rss_mb"] is not None and cp_records[i - 1]["rss_mb"] is not None else 0.0
        deltas.append({"interval_frames": df, "delta_mb": round(dr, 1),
                       "mb_per_1000f": round(dr / df * 1000.0, 2) if df else 0.0})

    # 稳定 vs 线性：取"最后两个 interval"的平均斜率与整体平均斜率对比
    last_interval_deltas = deltas[-2:] if len(deltas) >= 2 else deltas
    late_slope = float(np.mean([d["mb_per_1000f"] for d in last_interval_deltas])) if last_interval_deltas else 0.0
    all_frames = cp_records[-1]["frames"] - cp_records[0]["frames"] if len(cp_records) >= 2 else 0
    total_growth_interval = (cp_records[-1]["rss_mb"] - cp_records[0]["rss_mb"]) if len(cp_records) >= 2 and cp_records[-1]["rss_mb"] is not None and cp_records[0]["rss_mb"] is not None else 0.0
    all_slope = (total_growth_interval / all_frames * 1000.0) if all_frames else 0.0

    # 启发式判定（附原始数据供人工判断）
    if failed is not None:
        verdict, label = "MEMORY_LEAK_RISK", "run failed (DML error / incomplete)"
    else:
        # 后半程斜率相对整体明显收窄 (<25%) 或绝对很小 (<3 MB/1000帧) -> 已趋于稳定
        late_flat = late_slope < 0.25 * all_slope or late_slope < 3.0
        if late_flat:
            verdict, label = "MEMORY_STABLE", "warmup/cache overhead (one-time arena jump, then flat)"
        else:
            verdict, label = "MEMORY_LEAK_RISK", "near-linear growth continues"

    report = {
        "source": str(ORIG), "video_res": f"{md.width}x{md.height}", "duration_s": md.duration,
        "batch": batch, "max_frames_target": max_frames, "frames_processed": done,
        "completed": bool(failed is None and done >= max_frames),
        "did_complete_all_frames": bool(failed is None),
        "start_rss_mb": start_rss, "peak_rss_mb": peak_rss, "final_rss_mb": final_rss,
        "growth_mb": growth_mb,
        "end_to_end_s": round(end_to_end_s, 1), "avg_fps": round(float(fps_total), 2),
        "avg_batch_ms": round(np.mean([r["last_batch_ms"] for r in cp_records if r["last_batch_ms"] is not None]) if any(r["last_batch_ms"] is not None for r in cp_records) else 0.0, 2),
        "gpu_vram": vram_probe,
        "intervals": deltas,
        "late_slope_mb_per_1000f": round(float(late_slope), 2),
        "all_slope_mb_per_1000f": round(float(all_slope), 2),
        "checkpoints": cp_records,
        "failure": failed,
        "verdict": verdict, "verdict_label": label,
    }
    (POC_DIR / "report_h2.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_md(report, deltas)
    print("\n=== H2-PREFLIGHT REPORT ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nVERDICT: {verdict}  ({label})")
    return 0


def _write_md(report, deltas):
    cp = report["checkpoints"]
    rows = "\n".join(
        f"| {r['frames']} | {r['rss_mb'] if r['rss_mb'] is not None else '?'} | "
        f"{r['fps']} | {r['last_batch_ms']} | {r['all_finite']} | {r['feature_norm_max']} |"
        for r in cp)
    intr = "\n".join(
        f"| {d['interval_frames']} | {d['delta_mb']} | {d['mb_per_1000f']} |" for d in deltas)
    md = f"""# H2-Preflight — DirectML 长时索引稳定性

- 源: {report['source']} ({report['video_res']}, {report['duration_s']:.1f}s)
- batch={report['batch']}  目标帧={report['max_frames_target']}  完成帧={report['frames_processed']}
- completed_all_frames={report['did_complete_all_frames']}
- GPU VRAM: {report['gpu_vram']}

## checkpoint
| frames | RSS(MB) | fps | 上一批ms | all_finite | norm_max |
|---|---|---|---|---|---|
{rows}

## interval 增量
| 区间帧 | ΔMB | MB/1000帧 |
|---|---|---|
{intr}

## 汇总
- 起始 RSS {report['start_rss_mb']} MB | 峰值 {report['peak_rss_mb']} MB | 最终 {report['final_rss_mb']} MB
- 增长 {report['growth_mb']} MB
- 全片耗时 {report['end_to_end_s']} s | 平均 fps {report['avg_fps']} | 平均 batch {report['avg_batch_ms']} ms
- 后半程斜率 {report['late_slope_mb_per_1000f']} MB/1000帧 vs 整体 {report['all_slope_mb_per_1000f']} MB/1000帧

## Verdict
**{report['verdict']}** — {report['verdict_label']}
"""
    (POC_DIR / "report_h2.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
