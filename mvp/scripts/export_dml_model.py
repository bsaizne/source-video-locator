"""export_dml_model — 从冻结模型重新导出 DirectML 可用的 ONNX 资产到产品 models 目录。

只读复用 ``device.dinov2_model.DinoV2Small`` 与 ``device.cpu_backend.resolve_dinov2_weights``
（不修改任何生产源码）。导出图 = patch_embed -> 12x_Block -> final LayerNorm -> **CLS 令牌**
(``x[:,0]``, [B,384], float32)；**不含 L2**（由 ``DirectMLBackend.embed_frames`` 做相同 numpy
L2，与 CPUBackend 逐位同语义）。

产物（同一模型资产）：<产品models>/dinov2_cls_384/dinov2_cls_384.onnx + .onnx.data + asset.json。
图 + 外部权重必须作为同一资产，由 ``device.resolve_dml_model`` 定位；绝不依赖 work/ 或 poc/。

用法：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/export_dml_model.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

SRC = Path(__file__).resolve().parents[1] / "src"     # -> mvp/src
sys.path.insert(0, str(SRC))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from device.cpu_backend import resolve_dinov2_weights  # noqa: E402
from device.dinov2_model import DinoV2Small, _imagenet_preprocess  # noqa: E402
from infrastructure import paths  # noqa: E402

OPSET = 17
DUMMY_SHAPE = (1, 3, 518, 518)
ONNX_BASENAME = "dinov2_cls_384.onnx"


def main() -> int:
    out_dir = paths.dinov2_dml_asset_dir()
    out_path = out_dir / ONNX_BASENAME
    weights = resolve_dinov2_weights()
    print(f"[export] weights: {weights}")
    print(f"[export] target: {out_path}")

    t0 = time.perf_counter()
    model = DinoV2Small()
    model.load_state_dict(torch.load(str(weights), map_location="cpu"))
    model.eval()
    print(f"[export] model loaded in {time.perf_counter() - t0:.2f}s")

    dummy = torch.randn(*DUMMY_SHAPE, dtype=torch.float32)
    try:
        with torch.no_grad():
            torch.onnx.export(
                model, dummy, str(out_path),
                input_names=["input"], output_names=["embedding"],
                dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
                opset_version=OPSET, do_constant_folding=True,
            )
    except Exception as exc:
        print(f"[export] ONNX EXPORT FAILED: {type(exc).__name__}: {exc}")
        return 1
    print(f"[export] exported -> {out_path} (+ {out_path.name}.data)")

    import onnx
    m = onnx.load(str(out_path))
    onnx.checker.check_model(m)
    print(f"[export] checker: OK  opset={m.opset_import[0].version}")

    # 资产元数据（§4：model name/version/opset/input/output shape/backend compatibility）
    meta = {
        "name": "dinov2_cls_384",
        "model": "dinov2_vits14_cls_384",
        "feature_model": "dinov2_vits14",
        "feature_version": "handwritten_vits14_cls_384d@0.5_l2",
        "opset": m.opset_import[0].version,
        "input": {"name": "input", "shape": [1, 3, 518, 518], "dtype": "float32"},
        "output": {"name": "embedding", "shape": ["N", 384], "dtype": "float32"},
        "backend_compatibility": ["directml", "cpu"],
        "normalization": "L2 applied at DirectMLBackend.embed_frames (matches CPUBackend)",
        "source": "frozen DinoV2Small (tanh-GELU, final LayerNorm, CLS token)",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "asset.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")

    # 回放校验：torch raw CLS vs ONNX CPU 同输入
    import onnxruntime as ort
    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    frame_bgr = np.random.RandomState(0).randint(0, 256, (480, 640, 3), dtype=np.uint8)
    inp = _imagenet_preprocess(frame_bgr)
    with torch.no_grad():
        ref = model(inp).detach().cpu().numpy().astype(np.float32)
    out = sess.run(["embedding"], {"input": inp.numpy()})[0]
    md = float(np.max(np.abs(ref - out)))
    cos = float(np.sum(ref * out) / (np.linalg.norm(ref) * np.linalg.norm(out) + 1e-8))
    print(f"[export] torch-vs-onnx(raw CLS): max|d|={md:.2e} cos={cos:.6f}")
    if cos < 0.9999 or md > 1e-3:
        print("[export] WARNING: onnx diverges from torch reference.")
        return 1
    print(f"[export] OK: asset written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
