"""export_dml_model_vitb — 从冻结 ViT-B/14 权重导出 DirectML CLS-768 ONNX 资产(研究侧)。

用途: 「该不该换更大基座」的产品级验证 —— 用 ViT-B 建全量索引 + 四片 runtime 回归。
与 mvp/scripts/export_dml_model.py 同法, 差别:
  * 模型实例化 DinoV2Small(embed_dim=768, num_heads=12) + dinov2_vitb14_pretrain.pth;
  * 资产写到 work/vitb_asset/(研究侧, 不进产品 models 目录, 不碰生产资产);
  * 输入名 "input" / 输出名 "embedding" 与 DirectMLBackend 契约一致; 图不含 L2(后端做 numpy L2)。

产物: work/vitb_asset/dinov2_cls_768.onnx(+ .onnx.data + asset.json)

用法:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/export_dml_model_vitb.py
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from device.dinov2_model import DinoV2Small, _imagenet_preprocess  # noqa: E402

WEIGHTS = BENCH / "work" / "dinov2_weights" / "dinov2_vitb14_pretrain.pth"
OUT_DIR = BENCH / "work" / "vitb_asset"
ONNX_BASENAME = "dinov2_cls_768.onnx"
OPSET = 17
DUMMY_SHAPE = (1, 3, 518, 518)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / ONNX_BASENAME
    print("[export] weights: %s" % WEIGHTS)
    print("[export] target : %s" % out_path)

    t0 = time.perf_counter()
    model = DinoV2Small(embed_dim=768, num_heads=12)
    missing, unexpected = model.load_state_dict(
        torch.load(str(WEIGHTS), map_location="cpu", weights_only=True), strict=False)
    model.eval()
    print("[export] ViT-B load: missing=%s unexpected=%s (%.2fs)"
          % (list(missing), list(unexpected), time.perf_counter() - t0))

    dummy = torch.randn(*DUMMY_SHAPE, dtype=torch.float32)
    try:
        with torch.no_grad():
            torch.onnx.export(
                model, dummy, str(out_path),
                input_names=["input"], output_names=["embedding"],
                dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"}},
                opset_version=OPSET, do_constant_folding=True)
    except Exception as exc:
        print("[export] ONNX EXPORT FAILED: %s: %s" % (type(exc).__name__, exc))
        return 1
    print("[export] exported -> %s (+ .data)" % out_path)

    import onnx
    m = onnx.load(str(out_path))
    onnx.checker.check_model(m)
    print("[export] checker OK opset=%s" % m.opset_import[0].version)

    meta = {
        "name": "dinov2_cls_768",
        "model": "dinov2_vitb14_cls_768",
        "feature_model": "dinov2_vitb14",
        "feature_version": "handwritten_vitb14_cls_768d@1_l2",
        "opset": m.opset_import[0].version,
        "input": {"name": "input", "shape": [1, 3, 518, 518], "dtype": "float32"},
        "output": {"name": "embedding", "shape": ["N", 768], "dtype": "float32"},
        "backend_compatibility": ["directml", "cpu"],
        "normalization": "L2 applied by the harness (matches DirectMLBackend.embed_frames)",
        "source": "dinov2_vitb14_pretrain.pth -> DinoV2Small(embed_dim=768, num_heads=12)",
        "purpose": "research-side asset for the ViT-B full-index / four-clip runtime regression",
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (OUT_DIR / "asset.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                        encoding="utf-8")

    import onnxruntime as ort
    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    frame = np.random.RandomState(0).randint(0, 256, (480, 640, 3), dtype=np.uint8)
    inp = _imagenet_preprocess(frame)
    with torch.no_grad():
        ref = model(inp).detach().cpu().numpy().astype(np.float32)
    out = sess.run(["embedding"], {"input": inp.numpy()})[0]
    md = float(np.max(np.abs(ref - out)))
    cos = float(np.sum(ref * out) / (np.linalg.norm(ref) * np.linalg.norm(out) + 1e-8))
    print("[export] torch-vs-onnx(raw CLS): max|d|=%.2e cos=%.6f shape=%s"
          % (md, cos, out.shape))
    if cos < 0.9999 or md > 1e-3:
        print("[export] WARNING: onnx diverges from torch reference")
        return 1
    print("[export] OK: %s" % OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
