"""export_onnx — 把冻结的 DINOv2 ViT-S/14 CLS(384D) forward 导出为 ONNX.

只读复用 ``device.dinov2_model.DinoV2Small`` 与 ``device.cpu_backend.resolve_dinov2_weights``
（不修改任何生产源码）。导出的图 = patch_embed -> 12x_Block -> final LayerNorm -> **CLS token**
(``x[:,0]``, shape [B,384], float32)；**不含 L2 归一化**——L2 在 Python 侧由所有引擎统一做，
与 ``embed_frames`` 输出语义逐位对齐。

导出后立即用 onnxruntime CPU EP 对同一 dummy 输入回放一次，与 torch 参考 raw CLS 对比，
尽早捕捉导出漂移。

用法：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/poc/amdgpu_onnx/export_onnx.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

# Windows 控制台默认 GBK，torch.onnx 导出日志会打印 emoji(✅) 导致 UnicodeEncodeError。
# 统一 UTF-8 输出，避免"导出被日志打印误杀"。
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

POC_DIR = Path(__file__).resolve().parent
SRC = POC_DIR.parents[1] / "src"            # -> mvp/src
sys.path.insert(0, str(SRC))

import numpy as np
import torch

# --- 冻结模型 + 权重解析（只读复用）---
from device.cpu_backend import resolve_dinov2_weights
from device.dinov2_model import DinoV2Small, _imagenet_preprocess

MODEL_PATH = POC_DIR / "export_model" / "dinov2_cls_384.onnx"
OPSET = 17
DUMMY_SHAPE = (1, 3, 518, 518)


def main() -> int:
    weights = resolve_dinov2_weights()
    print(f"[export] weights: {weights}")
    t0 = time.perf_counter()
    model = DinoV2Small()
    model.load_state_dict(torch.load(str(weights), map_location="cpu"))
    model.eval()
    print(f"[export] model loaded in {time.perf_counter() - t0:.2f}s")

    dummy = torch.randn(*DUMMY_SHAPE, dtype=torch.float32)
    try:
        with torch.no_grad():
            torch.onnx.export(
                model,
                dummy,
                str(MODEL_PATH),
                input_names=["input"],
                output_names=["embedding"],
                dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
                opset_version=OPSET,
                do_constant_folding=True,
            )
    except Exception as exc:
        print(f"[export] ONNX EXPORT FAILED: {type(exc).__name__}: {exc}")
        return 1
    print(f"[export] exported -> {MODEL_PATH} ({MODEL_PATH.stat().st_size / 1e6:.1f} MB)")

    # 校验 graph 合法性
    import onnx
    m = onnx.load(str(MODEL_PATH))
    try:
        onnx.checker.check_model(m)
        print(f"[export] checker: OK  opset={m.opset_import[0].version}")
    except Exception as exc:
        print(f"[export] checker FAILED: {type(exc).__name__}: {exc}")
        return 1

    # 立即回放：torch raw CLS vs ONNX CPU 同输入 -> 捕获导出漂移
    import onnxruntime as ort
    sess = ort.InferenceSession(str(MODEL_PATH), providers=["CPUExecutionProvider"])
    frame_bgr = np.random.RandomState(0).randint(0, 256, (480, 640, 3), dtype=np.uint8)
    inp = _imagenet_preprocess(frame_bgr)                              # [1,3,518,518] tensor
    with torch.no_grad():
        ref = model(inp).detach().cpu().numpy().astype(np.float32)     # [1,384] raw CLS
    out = sess.run(["embedding"], {"input": inp.numpy()})[0]           # [1,384]
    md = float(np.max(np.abs(ref - out)))
    cos = float(np.sum(ref * out) / (np.linalg.norm(ref) * np.linalg.norm(out) + 1e-8))
    print(f"[export] torch-vs-onnx(raw CLS): max|d|={md:.2e}  cos={cos:.6f}")
    if cos < 0.9999 or md > 1e-3:
        print("[export] WARNING: onnx diverges from torch reference (> threshold).")
        return 1
    print("[export] OK: onnx matches torch raw CLS to within tolerance.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
