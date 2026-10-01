"""export_patch_onnx — 从冻结模型重新导出 PatchReranker 用的 CLS+patch 双输出 ONNX 资产。

补 2026-10-01 续36 登记的缺口：``dinov2_cls_patch.onnx`` 自 2026-09-01 由 ``work/_patch_onnx_tmp/``
入册后，仓内无再生成脚本。本脚本与 ``export_dml_model.py`` 同法（同权重解析 / 同 opset / 同
torch.onnx.export 默认外部权重布局），差别只在导出图 = ``DinoV2Small.forward_features``：
patch_embed -> 12x_Block -> final LayerNorm -> (CLS ``x[:,0]`` [B,384], patch ``x[:,1:]`` [B,1369,384])，
float32，**不含 L2**（由 ``PatchReranker.frame_dual`` / ``_frame_patches_dml`` 做 numpy L2）。

只读复用生产源码，不改任何嵌入语义（CLS 路径与 ``forward`` 逐位同图，``feature_version`` 不变）。

默认输出到 ``work/_patch_onnx_export/``，**不覆盖**仓内资产 ``mvp/ui/resources/models/dinov2_cls_patch/``；
要替换仓内资产须显式 ``--out-dir`` 指过去（替换后须重跑 ``accept_packaged_bundle.py`` 与后端全套）。

校验（任一不过 → 退出码 1）：
  1. onnx.checker + IO 名/形状与 PatchReranker 约定一致（input / embedding / patches）；
  2. torch.forward_features vs 新 ONNX(CPU)：两路输出 cos ≥ 0.9999 且 max|d| ≤ 1e-3；
  3. 若仓内参考资产在位（图 + 同目录 .data）：新 ONNX vs 参考 ONNX 同输入两路输出同上门槛；
  4. 新 ``.onnx.data`` 与 CLS 资产 ``dinov2_cls_384.onnx.data`` 的 sha256 对比（仅报告，不判失败——
     外部权重字节布局取决于导出器版本）。

用法：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/export_patch_onnx.py
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/export_patch_onnx.py --out-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MVP = Path(__file__).resolve().parents[1]              # -> mvp
BENCH = MVP.parent
SRC = MVP / "src"
sys.path.insert(0, str(SRC))

import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch import nn  # noqa: E402

from device.cpu_backend import resolve_dinov2_weights  # noqa: E402
from device.dinov2_model import DinoV2Small, _imagenet_preprocess  # noqa: E402
from infrastructure import paths  # noqa: E402

OPSET = 17
DUMMY_SHAPE = (1, 3, 518, 518)
ONNX_BASENAME = "dinov2_cls_patch.onnx"
N_PATCH = 1369                                         # (518/14)^2
DEFAULT_OUT = BENCH / "work" / "_patch_onnx_export"
REPO_ASSET_DIR = MVP / "ui" / "resources" / "models" / "dinov2_cls_patch"
COS_MIN, MAXD_MAX = 0.9999, 1e-3


class _DualOutput(nn.Module):
    """把 forward_features 包成 ONNX 可导出的双输出 forward（不复制任何层）。"""

    def __init__(self, model: DinoV2Small):
        super().__init__()
        self.model = model

    def forward(self, x):
        return self.model.forward_features(x)


def _sha256(fp: Path) -> str:
    h = hashlib.sha256()
    with open(fp, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _compare(tag: str, ref: np.ndarray, out: np.ndarray) -> bool:
    md = float(np.max(np.abs(ref - out)))
    a, b = ref.reshape(-1), out.reshape(-1)
    cos = float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))
    ok = cos >= COS_MIN and md <= MAXD_MAX
    print(f"[export] {tag}: max|d|={md:.2e} cos={cos:.6f} {'OK' if ok else 'DIVERGED'}")
    return ok


def _check_io(m) -> bool:
    def dims(v):
        return [d.dim_param or d.dim_value for d in v.type.tensor_type.shape.dim]

    ins = {i.name: dims(i) for i in m.graph.input}
    outs = {o.name: dims(o) for o in m.graph.output}
    print(f"[export] io: in={ins} out={outs}")
    return (list(ins) == ["input"] and ins["input"][1:] == [3, 518, 518]
            and list(outs) == ["embedding", "patches"]
            and outs["embedding"][1:] == [384] and outs["patches"][1:] == [N_PATCH, 384])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT,
                    help=f"导出目录（默认 {DEFAULT_OUT}，不覆盖仓内资产）")
    args = ap.parse_args()
    out_dir: Path = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / ONNX_BASENAME
    weights = resolve_dinov2_weights()
    print(f"[export] weights: {weights}")
    print(f"[export] target : {out_path}")

    t0 = time.perf_counter()
    model = DinoV2Small()
    model.load_state_dict(torch.load(str(weights), map_location="cpu", weights_only=True))
    model.eval()
    wrapper = _DualOutput(model).eval()
    print(f"[export] model loaded in {time.perf_counter() - t0:.2f}s")

    dummy = torch.randn(*DUMMY_SHAPE, dtype=torch.float32)
    try:
        with torch.no_grad():
            torch.onnx.export(
                wrapper, dummy, str(out_path),
                input_names=["input"], output_names=["embedding", "patches"],
                dynamic_axes={"input": {0: "batch"}, "embedding": {0: "batch"},
                              "patches": {0: "batch"}},
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
    ok = _check_io(m)
    if not ok:
        print("[export] FAIL: IO 名/形状与 PatchReranker 约定不符")

    # 回放校验：torch forward_features vs 新 ONNX(CPU)，同一真实分布输入
    import onnxruntime as ort
    frame_bgr = np.random.RandomState(0).randint(0, 256, (480, 640, 3), dtype=np.uint8)
    inp = _imagenet_preprocess(frame_bgr)
    with torch.no_grad():
        rc, rp = (t.detach().cpu().numpy().astype(np.float32) for t in model.forward_features(inp))
    sess = ort.InferenceSession(str(out_path), providers=["CPUExecutionProvider"])
    oc, op = sess.run(["embedding", "patches"], {"input": inp.numpy()})
    ok &= _compare("torch-vs-onnx CLS    ", rc, oc)
    ok &= _compare("torch-vs-onnx patches", rp, op)

    # 与仓内参考资产对照（新旧图同输入同输出 = 再生成可替代入册资产）
    ref_onnx = REPO_ASSET_DIR / ONNX_BASENAME
    ref_data = REPO_ASSET_DIR / f"{ONNX_BASENAME}.data"
    if ref_onnx.resolve() == out_path and ok:
        print("[export] out-dir = 仓内资产目录：参考对照跳过（已被覆盖）")
    elif ref_onnx.exists() and ref_data.exists():
        rsess = ort.InferenceSession(str(ref_onnx), providers=["CPUExecutionProvider"])
        qc, qp = rsess.run(["embedding", "patches"], {"input": inp.numpy()})
        ok &= _compare("repo-vs-new   CLS    ", qc, oc)
        ok &= _compare("repo-vs-new   patches", qp, op)
    else:
        print(f"[export] 参考资产不全（需 {ref_onnx.name} + .data 同目录），跳过新旧对照")

    digests = {fp.name: _sha256(fp) for fp in sorted(out_dir.glob(f"{out_path.name}*"))
               if fp.is_file()}
    cls_data = paths.dinov2_dml_asset_dir() / "dinov2_cls_384.onnx.data"
    new_data = f"{ONNX_BASENAME}.data"
    if cls_data.exists() and new_data in digests:
        same = _sha256(cls_data) == digests[new_data]
        print(f"[export] .data vs CLS 资产 .data: {'字节相同' if same else '字节不同（仅报告）'}")

    if not ok:
        print("[export] FAILED: 校验未过，asset.json 不写")
        return 1

    # 资产元数据（字段与仓内 dinov2_cls_patch/asset.json 同 schema）
    meta = {
        "name": "dinov2_cls_patch",
        "model": "dinov2_vits14_cls_384_with_patch_tokens",
        "feature_model": "dinov2_vits14",
        "feature_version": "handwritten_vits14_cls_384d@0.5_l2",
        "opset": m.opset_import[0].version,
        "input": {"name": "input", "shape": [1, 3, 518, 518], "dtype": "float32"},
        "output": {"name": "embedding", "shape": ["N", 384], "dtype": "float32"},
        "outputs_extra": {"name": "patches", "shape": ["N", N_PATCH, 384], "dtype": "float32"},
        "backend_compatibility": ["directml", "cpu"],
        "consumed_by": "engine/localization/patch_rerank.py PatchReranker (SVL_PATCH_ONNX)",
        "normalization": "L2 applied at PatchReranker.frame_dual/_frame_patches_dml",
        "source": "mvp/scripts/export_patch_onnx.py (frozen DinoV2Small.forward_features)",
        "sha256": digests,
        "size_bytes": {n: (out_dir / n).stat().st_size for n in digests},
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out_dir / "asset.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False),
                                        encoding="utf-8")
    print(f"[export] OK: asset written to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
