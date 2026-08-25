"""bench — AMD 后端可行性 POC 主 runner。

路线：PyTorch CPU(参考) -> ONNX CPU -> ONNX DirectML -> Windows ML(本机未装,记为 NOT_INSTALLED)。
输出 report.json / report.md / 结论(AMD_BACKEND_GO / CONDITIONAL / NO_GO)。

只读复用冻结模型/preprocess；不改任何生产源码。用法：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/poc/amdgpu_onnx/bench.py
可选：--frames 500 --w 960 --h 540 --batch 8
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")
POC_DIR = Path(__file__).resolve().parent
if str(POC_DIR) not in sys.path:
    sys.path.insert(0, str(POC_DIR))

from common import (CPUExecutionProvider, DmlExecutionProvider, MODEL_PATH,  # noqa: E402
                    cosine, cosine_rowwise, gen_frames, l2norm, l2_norms,
                    list_gpu_names, make_session, max_abs_diff, mean_abs_diff,
                    preprocess_np, proc_mem_mb, run_onnx_forward, torch_model)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from device import CPUBackend  # noqa: E402
from device.cpu_backend import resolve_dinov2_weights  # noqa: E402

# --------------------------- 判定阈值（POC 用，非生产阈值） --------------------------- #
THRESH = {
    "cos_outlier_min": 0.999,     # 逐帧余弦最小可接受（DML vs CPU，L2 后）
    "max_abs_diff": 1e-3,         # max|Δ| 可接受上限（L2 后）
    "mean_abs_diff": 1e-4,        # mean|Δ| 可接受上限
    "norm_range": (0.999, 1.001),  # L2 归一后 norm 应≈1
    "speedup_go": 1.5,            # DML fps / CPU(torch,batch=8) 达到此值 -> GO 速度条件
}
WINML_NAMES = ("winml", "windows.ai.machinelearning")


def _timed_forward(forward_fn, inputs, batch, warmup_reps=2, timed_reps=3):
    small = inputs[:min(8, len(inputs))]
    for _ in range(warmup_reps):
        forward_fn(small, batch)
    t0 = time.perf_counter()
    for _ in range(timed_reps):
        forward_fn(inputs, batch)
    dt = (time.perf_counter() - t0) / timed_reps
    fps = len(inputs) / dt
    msf = dt / len(inputs) * 1000.0
    return fps, msf, dt


def _winml_probe() -> str:
    for name in WINML_NAMES:
        try:
            __import__(name)
            return f"{name}: AVAILABLE"
        except Exception:
            pass
    return "winml / windows.ai.machinelearning: NOT_INSTALLED"


def _providers_report(sess) -> list[str]:
    try:
        return list(sess.get_providers())
    except Exception as exc:
        return [f"<get_providers failed: {exc}>"]


def _neighbor_agreement(ref: np.ndarray, dml: np.ndarray, k: int = 5) -> float:
    """Top-1 邻居一致性：对 k 个查询帧，DML 与 CPU 在索引里的最近邻是否一致。"""
    agree = 0
    n = ref.shape[0]
    for qi in np.linspace(0, n - 1, k).astype(int):
        qr, qd = ref[qi], dml[qi]
        # 在索引(去掉自身)里找最近邻
        ir = np.argsort(-(ref @ qr))[:2]
        id_ = np.argsort(-(dml @ qd))[:2]
        skip = lambda arr: next(x for x in arr if x != qi)
        agree += 1 if skip(ir) == skip(id_) else 0
    return agree / k


def main() -> int:
    args = sys.argv
    n = int(os.environ.get("POC_FRAMES") or (args[args.index("--frames") + 1] if "--frames" in args else 500))
    w = int(args[args.index("--w") + 1] if "--w" in args else 960)
    h = int(args[args.index("--h") + 1] if "--h" in args else 540)
    batch = int(args[args.index("--batch") + 1] if "--batch" in args else 8)
    perf_n = int(args[args.index("--perf-n") + 1] if "--perf-n" in args else min(120, n))

    print(f"=== AMD DINOv2 ViT-S/14 CLS-384 POC ===")
    print(f"frames={n}  source_res={w}x{h}  batch={batch}")
    print(f"weights: {resolve_dinov2_weights()}")

    # ---------- GPU / 环境身份 ----------
    gpus = list_gpu_names()
    print(f"GPU (WMI): {gpus}")
    try:
        torch.set_num_threads(os.cpu_count() or 1)
    except Exception:
        pass
    print(f"torch {torch.__version__}  torch_threads={torch.get_num_threads()}  "
          f"cuda={'on' if torch.cuda.is_available() else 'off'}  (cpu-only build: {torch.version.cuda is None})")
    print(f"winml: {_winml_probe()}")

    # ---------- 帧 + 共享 preprocess ----------
    frames = gen_frames(n, size=(w, h))
    inputs = preprocess_np(frames)          # [N,3,518,518] float32（所有引擎同输入）
    core = inputs[:perf_n]                   # 正确性/性能用子集；稳定性用全 N 帧
    print(f"preprocessed inputs: {inputs.shape} dtype={inputs.dtype}  perf_frames={len(core)}")

    # ---------- 1) PyTorch CPU 参考 ----------
    def _torch_run(m, x, b):
        outs = []
        with torch.no_grad():
            for i in range(0, len(x), b):
                outs.append(m(torch.from_numpy(x[i:i + b])).detach().cpu().numpy())
        return np.concatenate(outs, axis=0)

    model = torch_model()
    ref_raw = _torch_run(model, core, batch)                 # [perf_n,384] raw CLS (LayerNorm 后, 未 L2)
    ref_l2 = l2norm(ref_raw)                                 # 与 embed_frames 相同的 numpy L2

    def _torch_fwd(x, b):
        return _torch_run(model, x, b)

    # 一致性校验（子集）：我的 ref_l2 应 == CPUBackend.embed_frames 输出（证明 preprocess 完全一致）
    cpu_embed = CPUBackend().embed_frames(frames[:8])
    fwd_gap = float(np.max(np.abs(ref_l2[:8] - cpu_embed)))
    print(f"[sanity] ref_l2[:8] vs CPUBackend.embed_frames max|Δ| = {fwd_gap:.2e} "
          f"(should be ~0; 非零=preprocess/线程差异)")
    if fwd_gap > 1e-5:
        print("  WARNING: my preprocess path diverges from embed_frames; semantics may differ")

    cpu_fps, cpu_msf, _ = _timed_forward(_torch_fwd, core, batch)

    # ---------- 2) ONNX CPU ----------
    try:
        sess_cpu = make_session(MODEL_PATH, providers=[CPUExecutionProvider])
        onnx_cpu_raw = run_onnx_forward(sess_cpu, core, batch)
        onnx_cpu_l2 = l2norm(onnx_cpu_raw)
        ort_cpu_fps, ort_cpu_msf, _ = _timed_forward(lambda x, b: run_onnx_forward(sess_cpu, x, b), core, batch)
        cpu_prov = _providers_report(sess_cpu)
    except Exception as exc:
        print(f"[ONNX-CPU] FAILED: {type(exc).__name__}: {exc}")
        onnx_cpu_raw = onnx_cpu_l2 = None
        ort_cpu_fps = ort_cpu_msf = float("nan")
        cpu_prov = [f"<failed: {exc}>"]

    # ---------- 3) ONNX DirectML ----------
    dml_toopts = [("DmlExecutionProvider", {"device_id": 0}), CPUExecutionProvider]
    try:
        sess_dml = make_session(MODEL_PATH, providers=dml_toopts)
        dml_prov = _providers_report(sess_dml)
    except Exception as exc:
        print(f"[ONNX-DML] tuple-provider failed ({type(exc).__name__}: {exc}); retry bare list")
        try:
            sess_dml = make_session(MODEL_PATH, providers=[DmlExecutionProvider, CPUExecutionProvider])
            dml_prov = _providers_report(sess_dml)
        except Exception as exc2:
            sess_dml = None
            print(f"[ONNX-DML] FAILED: {type(exc2).__name__}: {exc2}")
            dml_prov = [f"<failed: {exc2}>"]

    if sess_dml is not None:
        try:
            onnx_dml_raw = run_onnx_forward(sess_dml, core, batch)
            onnx_dml_l2 = l2norm(onnx_dml_raw)
            dml_fps, dml_msf, _ = _timed_forward(lambda x, b: run_onnx_forward(sess_dml, x, b), core, batch)
            # batch=1（单帧延迟）-> 看 per-call 开销
            dml_fps_b1, dml_msf_b1, _ = _timed_forward(lambda x, b: run_onnx_forward(sess_dml, x, 1), core, 1)
        except Exception as exc:
            print(f"[ONNX-DML] RUN FAILED: {type(exc).__name__}: {exc}")
            onnx_dml_raw = onnx_dml_l2 = None
            dml_fps = dml_msf = dml_fps_b1 = dml_msf_b1 = float("nan")
    else:
        onnx_dml_raw = onnx_dml_l2 = None
        dml_fps = dml_msf = dml_fps_b1 = dml_msf_b1 = float("nan")

    # ---------- 4) 正确性 ----------
    def correctness(name, cand_raw, cand_l2):
        if cand_l2 is None:
            return {"name": name, "ok": False, "reason": "no output"}
        cos = cosine(cand_l2, ref_l2)
        cos_rows = cosine_rowwise(cand_l2, ref_l2)
        maxd = max_abs_diff(cand_l2, ref_l2)
        meand = mean_abs_diff(cand_l2, ref_l2)
        norms = l2_norms(cand_l2)
        res = {
            "name": name,
            "cosine": round(cos, 6),
            "cos_rowwise_min": round(float(cos_rows.min()), 6),
            "cos_rowwise_mean": round(float(cos_rows.mean()), 6),
            "max_abs_diff": round(maxd, 7),
            "mean_abs_diff": round(meand, 8),
            "l2norm_min": round(float(norms.min()), 5),
            "l2norm_max": round(float(norms.max()), 5),
            "ok": bool(cos > THRESH["cos_outlier_min"] and maxd < THRESH["max_abs_diff"]
                       and THRESH["norm_range"][0] <= float(norms.min())
                       and float(norms.max()) <= THRESH["norm_range"][1]),
        }
        return res

    onnx_cpu_corr = correctness("onnx_cpu", onnx_cpu_raw, onnx_cpu_l2)
    onnx_dml_corr = correctness("onnx_dml", onnx_dml_raw, onnx_dml_l2)
    neighbor_ok = None
    if onnx_dml_l2 is not None:
        neighbor_ok = _neighbor_agreement(ref_l2, onnx_dml_l2)
    raw_dml_vs_raw_cpu = None
    if onnx_dml_raw is not None and onnx_cpu_raw is not None:
        raw_dml_vs_raw_cpu = round(max_abs_diff(onnx_dml_raw, onnx_cpu_raw), 7)

    # ---------- 5) 稳定性（DML 500 帧） ----------
    stability = {"ran": False, "reason": ""}
    if sess_dml is not None:
        try:
            mem0 = proc_mem_mb()
            max_norm_dev = 0.0
            finite = True
            for i in range(0, n, batch):
                chunk = run_onnx_forward(sess_dml, inputs[i:i + batch], batch)
                if not np.all(np.isfinite(chunk)):
                    finite = False
                    break
                # 对**归一后** embedding（产品语义）测 norm 是否稳定≈1
                nrm = l2_norms(l2norm(chunk))
                max_norm_dev = max(max_norm_dev, float(np.max(np.abs(nrm - 1.0))))
            mem1 = proc_mem_mb()
            stability = {
                "ran": True, "flags": "all_finite" if finite else "NON_FINITE",
                "max_norm_dev": round(max_norm_dev, 6),
                "mem_start_mb": mem0, "mem_end_mb": mem1,
                "mem_growth_mb": round((mem1 - mem0), 1) if (mem0 and mem1) else None,
                "ok": bool(finite and max_norm_dev < 5e-3),
            }
        except Exception as exc:
            stability = {"ran": False, "reason": f"{type(exc).__name__}: {exc}"}

    # ---------- 6) 判定 ----------
    speedup = (dml_fps / cpu_fps) if (dml_fps and cpu_fps) else float("nan")
    ok_corr = bool(onnx_dml_corr.get("ok"))
    ok_stab = bool(stability.get("ok"))
    ok_gpu = bool("DmlExecutionProvider" in str(dml_prov))
    ok_speed = bool(speedup >= THRESH["speedup_go"])
    ok_b1 = bool(dml_fps_b1 and cpu_fps and (dml_fps_b1 / cpu_fps) >= 1.0)

    reasons = []
    for cond, name in [(ok_corr, "correctness"), (ok_gpu, "gpu_used"),
                       (ok_stab, "stability"), (ok_speed, f"speed>={THRESH['speedup_go']}x"),
                       (ok_b1, "batch1_speed")]:
        reasons.append(f"{'+' if cond else '-'}{name}")
    if not ok_corr:
        verdict = "AMD_BACKEND_NO_GO"
        reason = "correctness violated (DML differs from CPU beyond threshold)"
    elif not ok_gpu:
        verdict = "AMD_BACKEND_NO_GO"
        reason = "cannot confirm DmlExecutionProvider active"
    elif not ok_stab:
        verdict = "AMD_BACKEND_NO_GO"
        reason = "stability failed (non-finite / norm drift)"
    elif ok_speed:
        verdict = "AMD_BACKEND_GO"
        reason = "runs, correct, GPU used, speedup>=1.5x, stable"
    else:
        verdict = "AMD_BACKEND_CONDITIONAL"
        reason = ("runs+correct+stable but speedup<1.5x; batching/tune needed "
                  f"(batch8 speedup={speedup:.2f}x, batch1 speedup={(dml_fps_b1 / cpu_fps if (dml_fps_b1 and cpu_fps) else float('nan')):.2f}x)")

    # ---------- 7) report ----------
    report = {
        "env": {"python": sys.version.split()[0], "torch": torch.__version__,
                "torch_cuda": torch.cuda.is_available(), "torch_threads": torch.get_num_threads(),
                "gpu_wmi": gpus, "winml": _winml_probe(), "onnxruntime_providers_available": None},
        "setup": {"frames": n, "perf_frames": perf_n, "stability_frames": n,
                  "source_res": f"{w}x{h}", "batch": batch,
                  "weights": str(resolve_dinov2_weights()), "model": str(MODEL_PATH)},
        "perf": {
            "cpu_torch": {"fps": round(cpu_fps, 2), "ms_per_frame": round(cpu_msf, 2)},
            "onnx_cpu": {"fps": round(ort_cpu_fps, 2), "ms_per_frame": round(ort_cpu_msf, 2)},
            "onnx_dml": {"fps": round(dml_fps, 2), "ms_per_frame": round(dml_msf, 2)},
            "onnx_dml_batch1": {"fps": round(dml_fps_b1, 2), "ms_per_frame": round(dml_msf_b1, 2)},
            "speedup_dml_vs_cpu": round(float(speedup), 2),
        },
        "providers": {"onnx_cpu": cpu_prov, "onnx_dml": dml_prov},
        "correctness": {"onnx_cpu": onnx_cpu_corr, "onnx_dml": onnx_dml_corr,
                        "dml_raw_vs_cpu_raw_max_abs": raw_dml_vs_raw_cpu,
                        "neighbor_agreement": neighbor_ok},
        "stability": stability,
        "verdict": {"reason": reason, "checks": reasons},
    }

    (POC_DIR / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_md(report, reasons, speedup)
    print("=== REPORT ===")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    print(f"\nVERDICT: {verdict}"
          f"\n  checks: {reasons}"
          f"\n  reason: {reason}"
          f"\n  correctness_ok={ok_corr} gpu_used={ok_gpu} stable={ok_stab} "
          f"speedup={speedup:.2f}x (batch1={(dml_fps_b1 / cpu_fps) if (dml_fps_b1 and cpu_fps) else float('nan'):.2f}x)")
    return 0


def _write_md(report, reasons, speedup):
    p = report["perf"]
    c = report["correctness"]
    s = report["stability"]

    def eng_line(ck):
        if not ck.get("ok"):
            return "FAILED / violates threshold"
        return (f"cosine={ck['cosine']}, max|Δ|={ck['max_abs_diff']}, "
                f"mean|Δ|={ck['mean_abs_diff']}, l2norm∈[{ck['l2norm_min']},{ck['l2norm_max']}]")

    md = f"""# AMD GPU Feasibility POC — Result

- 模型: DINOv2 ViT-S/14 CLS 384D (frozen)
- 硬件: {report['env']['gpu_wmi']}
- 输入: {report['setup']['source_res']} -> 518x518 x {report['setup']['stability_frames']} 帧, batch={report['setup']['batch']}
- torch {report['env']['torch']} (cpu-only), torch_threads={report['env']['torch_threads']}
- WinML: {report['env']['winml']}

## Perf (frames/s)
| engine | batch | fps | ms/frame |
|---|---|---|---|
| PyTorch CPU | {report['setup']['batch']} | {p['cpu_torch']['fps']} | {p['cpu_torch']['ms_per_frame']} |
| ONNX CPU | {report['setup']['batch']} | {p['onnx_cpu']['fps']} | {p['onnx_cpu']['ms_per_frame']} |
| ONNX DirectML | {report['setup']['batch']} | {p['onnx_dml']['fps']} | {p['onnx_dml']['ms_per_frame']} |
| ONNX DirectML | 1 | {p['onnx_dml_batch1']['fps']} | {p['onnx_dml_batch1']['ms_per_frame']} |

Speedup vs CPU(torch): **{p['speedup_dml_vs_cpu']}x** (batch=1: {p['onnx_dml_batch1']['fps'] / p['cpu_torch']['fps']:.2f}x)

## Correctness (vs PyTorch CPU, L2 后)
- ONNX CPU: {eng_line(c['onnx_cpu'])}
- ONNX DML: {eng_line(c['onnx_dml'])}
- DML raw vs CPU raw max|Δ|: {c['dml_raw_vs_cpu_raw_max_abs']}
- Top-1 neighbor agreement (DML vs CPU): {c['neighbor_agreement']}

## Stability (DML {report['setup']['stability_frames']} frames)
- {s.get('flags','n/a')} max_norm_dev={s.get('max_norm_dev')} mem_growth_mb={s.get('mem_growth_mb')}

## GPU actually used?
- providers: {report['providers']['onnx_dml']}
- GPU WMI: {report['env']['gpu_wmi']}

## Verdict
**{report['verdict']['reason']}**
- checks: {reasons}
"""
    (POC_DIR / "report.md").write_text(md, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
