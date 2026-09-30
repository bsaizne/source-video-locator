# -*- coding: utf-8 -*-
"""TransNetV2(a01) 共享推理工具 —— A1/A1+ 实验用(研究侧).

来源与可复现性:
  * 模型代码 = 官方 soCzech/TransNetV2 的 inference-pytorch/transnetv2_pytorch.py;
  * 权重     = 官方 transnetv2-pytorch-weights.pth(work/transnetv2/, 30,508,183 B;
                state_dict 90 张量 / 7,618,056 元素 == 竞品 a01 明文计数, 逐位一致);
  * 推理用 ONNX(work/transnetv2/probe_transnetv2.onnx), 已对拍官方 PyTorch:
    sigmoid 后 max|diff| = 6.1e-8(输出 534=single / 535=many_hot)。

输入约定(官方): [B, T, 27, 48, 3] float, 值域 0-255(RGB); 输出单帧切点概率与 many_hot 概率。
竞品口径(常量流取到, 见 FINDINGS/08): 描述子尺寸 48x27(与我们一致);
dual 判定候选阈值 0.55 / 0.35 / 0.62(证据等级: 中, 常量共现待 code-object 切帧确认)。
"""
from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
TN_DIR = BENCH / "work" / "transnetv2"
TN_ONNX = TN_DIR / "probe_transnetv2.onnx"
SRC_ONNX = Path(r"D:\claudework\cutmatch-analysis\data\probe_transnetv2.onnx")

WINDOW = 100      # 官方滑动窗(帧)
STEP = 50         # 官方步长(帧) = 50% overlap
THRESH = 0.5      # 官方 single-frame 阈值

_SESS: dict[str, object] = {}


def session(provider: str = "CPUExecutionProvider"):
    if provider not in _SESS:
        import onnxruntime as ort
        if not TN_ONNX.exists():
            TN_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(SRC_ONNX, TN_ONNX)
        so = ort.SessionOptions()
        so.log_severity_level = 3
        _SESS[provider] = ort.InferenceSession(str(TN_ONNX), sess_options=so, providers=[provider])
    return _SESS[provider]


def predict_both(frames_rgb: np.ndarray, provider: str = "CPUExecutionProvider"):
    """[N,27,48,3] uint8 RGB -> (single[N], many_hot[N]) 概率(重叠窗累加取均值, 官方同构)."""
    sess = session(provider)
    n = int(frames_rgb.shape[0])
    acc_s = np.zeros(n, dtype=np.float64)
    acc_m = np.zeros(n, dtype=np.float64)
    cnt = np.zeros(n, dtype=np.float64)
    for start in range(0, n, STEP):
        chunk = frames_rgb[start:start + WINDOW]
        if chunk.shape[0] == 0:
            break
        if chunk.shape[0] < WINDOW:
            chunk = np.concatenate([chunk, np.repeat(chunk[-1:], WINDOW - chunk.shape[0], axis=0)], axis=0)
        out = sess.run(None, {"input": chunk[None].astype(np.float32)})
        take = min(WINDOW, n - start)
        acc_s[start:start + take] += out[0][0, :take, 0]
        acc_m[start:start + take] += out[1][0, :take, 0]
        cnt[start:start + take] += 1.0
        if start + WINDOW >= n:
            break
    c = np.maximum(cnt, 1.0)
    return (acc_s / c).astype(np.float32), (acc_m / c).astype(np.float32)


def predict(frames_rgb: np.ndarray, provider: str = "CPUExecutionProvider") -> np.ndarray:
    """兼容旧调用: 只返回 single 概率."""
    return predict_both(frames_rgb, provider=provider)[0]


def cuts_from_pred(pred: np.ndarray, th: float = THRESH) -> list[int]:
    """官方 predictions_to_scenes 同构: flag=1 表示该帧为 cut; 返回各场景起始帧(含 0)."""
    flag = (pred > th).astype(np.uint8)
    starts = [0]
    for i in range(1, len(flag)):
        if flag[i] == 1 and flag[i - 1] == 0:
            starts.append(i)
    return starts


def boundaries(ffmpeg, edited: Path, provider: str = "CPUExecutionProvider") -> dict:
    """原生 fps 采样 48x27 RGB -> TransNetV2 边界(帧索引 + 秒)."""
    import time
    meta = ffmpeg.metadata(edited)
    vfps = float(meta.fps) if meta and meta.fps else 29.0
    t0 = time.monotonic()
    frames = [bgr[..., ::-1].copy() for _, bgr in ffmpeg.iter_frames(edited, vfps, scale=(48, 27))]
    if not frames:
        raise RuntimeError("no frames: %s" % edited)
    arr = np.stack(frames, axis=0)
    pred = predict(arr, provider=provider)
    idx = cuts_from_pred(pred)
    return {"fps": vfps, "n_frames": int(arr.shape[0]),
            "cuts_frame": idx, "cuts_sec": [i / vfps for i in idx],
            "pred_mean": float(pred.mean()), "pred_max": float(pred.max()),
            "elapsed": time.monotonic() - t0, "pred": pred}
