# -*- coding: utf-8 -*-
"""L4 FP16 ONNX 探针（2026-10-06 续57，FINDINGS_COST_STRUCTURE §2 L4「未测·便宜」销项）。

对三个产品推理资产做 FP32 vs FP16（keep_io_types）DML 对照：
  ① DINOv2 ViT-S CLS-384（产品单输出，%LOCALAPPDATA% models/dinov2_cls_384）
  ② patch 双输出 dinov2_cls_patch（embedding+patches）
  ③ ISC isc_ft_v107（512 输入）

判据（证据级，不改 runtime / 不 bump feature_version）：
  - 数值：同帧同输入 cos(FP32,FP16) mean/min + max|Δ|（嵌入语义是否漂移的决定依据）
  - 吞吐：batch=1 逐帧 fps（DML batch1 是现役口径）
真实帧 = test1-om.mkv 1s 网格 32 帧（与生产同源同预处理）。

用法: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_fp16_ab.py
输出: work/fp16_probe/<name>.fp16.onnx + summary.json + 控制台表
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

OUT = BENCH / "work" / "fp16_probe"
ORIG = r"D:\ProjectXIXI\test1\test1-om.mkv"
N_FRAMES = 32
REPS = 3

MODELS = [
    {
        "name": "dinov2_cls_384",
        "path": Path(os.environ["SVL_DATA_DIR"]) / "models" / "dinov2_cls_384" / "dinov2_cls_384.onnx",
        "outputs": ["embedding"],
        "prep": "dinov2",
    },
    {
        "name": "dinov2_cls_patch",
        "path": BENCH / "mvp" / "ui" / "resources" / "models" / "dinov2_cls_patch" / "dinov2_cls_patch.onnx",
        "outputs": ["embedding", "patches"],
        "prep": "dinov2",
    },
    {
        "name": "isc_ft_v107",
        "path": BENCH / "work" / "isc21_weights_ortho_probe" / "isc_ft_v107.onnx",
        "outputs": ["emb"],
        "prep": "isc",
    },
]


def grab_frames() -> list[np.ndarray]:
    from media.ffmpeg.ffmpeg_io import FFmpegIO

    ff = FFmpegIO()
    ts = [1382.5 + i * 1.0 for i in range(N_FRAMES)]   # 续50 基准窗起点
    got = ff.grab_grid_times(ORIG, ts)
    return [got[t] for t in ts]


def prep_dinov2(frame: np.ndarray) -> np.ndarray:
    from device.dinov2_model import _imagenet_preprocess

    return _imagenet_preprocess(frame).numpy()[0][None].astype(np.float32)


def prep_isc(frame: np.ndarray) -> np.ndarray:
    import cv2
    from engine.localization.isc_refine import ISC_INPUT_SIZE, ISC_MEAN, ISC_STD

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (ISC_INPUT_SIZE, ISC_INPUT_SIZE), interpolation=cv2.INTER_CUBIC)
    x = (rgb.astype(np.float32) / 255.0 - np.asarray(ISC_MEAN, np.float32)) \
        / np.asarray(ISC_STD, np.float32)
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None])


def to_fp16(src: Path, dst: Path) -> None:
    import onnx
    from onnxconverter_common import float16

    m = onnx.load(str(src), load_external_data=True)
    m16 = float16.convert_float_to_float16(m, keep_io_types=True)
    onnx.save(m16, str(dst))


def bench(model: dict, inputs: list[np.ndarray]) -> dict:
    import onnxruntime as ort

    providers = [("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
    out_names = model["outputs"]
    prep = prep_dinov2 if model["prep"] == "dinov2" else prep_isc
    inps = [prep(f) for f in inputs]

    s32 = ort.InferenceSession(str(model["path"]), providers=providers)
    in_name = s32.get_inputs()[0].name
    prov32 = s32.get_providers()[0]

    t0 = time.monotonic()
    ref = [s32.run(out_names, {in_name: x}) for x in inps]
    t32_first = time.monotonic() - t0
    t0 = time.monotonic()
    for _ in range(REPS):
        for x in inps:
            s32.run(out_names, {in_name: x})
    t32 = (time.monotonic() - t0) / (REPS * len(inps))

    fp16_path = OUT / (model["name"] + ".fp16.onnx")
    if not fp16_path.exists():
        to_fp16(model["path"], fp16_path)
    s16 = ort.InferenceSession(str(fp16_path), providers=providers)
    prov16 = s16.get_providers()[0]
    t0 = time.monotonic()
    for _ in range(REPS):
        for x in inps:
            s16.run(out_names, {in_name: x})
    t16 = (time.monotonic() - t0) / (REPS * len(inps))

    # 数值：同帧同输入，逐帧比主输出（cls/emb）
    out16 = [s16.run(out_names, {in_name: x}) for x in inps]
    cos_all, maxd_all = [], []
    for r32, r16 in zip(ref, out16):
        a = np.asarray(r32[0][0], np.float32).ravel()
        b = np.asarray(r16[0][0], np.float32).ravel()
        na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
        cos_all.append(float(a @ b / max(na * nb, 1e-8)))
        maxd_all.append(float(np.max(np.abs(a - b))))
    return {
        "provider_fp32": prov32, "provider_fp16": prov16,
        "fp32_first_batch_s": round(t32_first, 3),
        "fp32_ms_per_frame": round(t32 * 1000, 2),
        "fp16_ms_per_frame": round(t16 * 1000, 2),
        "fp32_fps": round(1.0 / t32, 2), "fp16_fps": round(1.0 / t16, 2),
        "speedup": round(t32 / max(t16, 1e-9), 3),
        "cos_mean": round(float(np.mean(cos_all)), 6),
        "cos_min": round(float(np.min(cos_all)), 6),
        "max_abs_diff": round(float(np.max(maxd_all)), 6),
        "n_frames": len(inps),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = grab_frames()
    print("frames=%d (test1-om 1382.5s+1s grid)" % len(frames), flush=True)
    summary = {}
    for m in MODELS:
        if not m["path"].exists():
            print("[%-18s] MISSING %s" % (m["name"], m["path"]), flush=True)
            summary[m["name"]] = {"status": "BLOCKED", "reason": "asset missing"}
            continue
        try:
            r = bench(m, frames)
            summary[m["name"]] = {"status": "OK", **r}
            print("[%-18s] fp32 %6.2f ms/帧 (%5.1f fps) → fp16 %6.2f ms/帧 (%5.1f fps) = %s×  "
                  "cos_mean=%.6f cos_min=%.6f max|d|=%.6f  [%s→%s]"
                  % (m["name"], r["fp32_ms_per_frame"], r["fp32_fps"], r["fp16_ms_per_frame"],
                     r["fp16_fps"], r["speedup"], r["cos_mean"], r["cos_min"],
                     r["max_abs_diff"], r["provider_fp32"], r["provider_fp16"]), flush=True)
        except Exception as e:      # noqa: BLE001 —— 探针逐模型隔离，单模型失败不拖垮其余
            summary[m["name"]] = {"status": "BLOCKED", "reason": repr(e)[:300]}
            print("[%-18s] BLOCKED %r" % (m["name"], e), flush=True)
    (OUT / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
