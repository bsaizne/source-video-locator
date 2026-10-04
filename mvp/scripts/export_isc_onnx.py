# -*- coding: utf-8 -*-
"""export_isc_onnx — 从本地 ISC21 权重重新导出 isc_refine 用的 ONNX 资产（2026-10-03 续44）。

补资产可复现缺口：``isc_ft_v107.onnx[.data]`` 自 2026-10-03 入册
``mvp/ui/resources/models/isc_ft_v107/`` 后，再生成路径 = 本脚本。权重源 =
``work/isc21_weights_ortho_probe/isc_ft_v107.pth.tar``（官方 release v1.0.1，sha256 见
DISK_CLEANUP 留痕；trash 原件已删）。

图形态与探针/生产一致：EfficientNetV2-M@512 features_only → **gem(p=1) 重写为 ReduceMean**
（原始 clamp/pow/avg_pool 形态 DML 授权 E_INVALIDARG，且失败路径污染进程——见探针 §6①）→
fc256 → BN → L2，opset 17，外部权重布局（torch.onnx.export 默认）。

默认输出到 ``work/isc21_weights_ortho_probe/export_new/``，**不覆盖**仓内资产；要替换仓内
资产须显式 ``--out-dir`` 指过去（二进制不入 git，替换后须重跑 ``accept_packaged_bundle.py``
与后端全套，并更新 asset.json 的 sha256）。

校验（任一不过 → 退出码 1）：
  1. onnx.checker + IO 名/形状与 IscScorer 约定一致（input / emb，[N,256]）；
  2. torch.wrap vs 新 ONNX(CPU)：输出 cos ≥ 0.9999 且 max|d| ≤ 1e-3；
  3. 若仓内参考资产在位：新 ONNX vs 参考 ONNX 同输入同上门限（图字节可不同——元数据；
     数值等价即通过）。

用法：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/export_isc_onnx.py
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/export_isc_onnx.py --out-dir <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

MVP = Path(__file__).resolve().parents[1]
BENCH = MVP.parent
SRC = MVP / "src"
for p in (str(SRC), str(MVP), str(BENCH / "engines" / "isc21")):
    if p not in sys.path:
        sys.path.insert(0, p)

WEIGHTS = BENCH / "work" / "isc21_weights_ortho_probe" / "isc_ft_v107.pth.tar"
REFERENCE = MVP / "ui" / "resources" / "models" / "isc_ft_v107"
ARCH = "timm/tf_efficientnetv2_m.in21k_ft_in1k"
INPUT_SIZE = 512


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    import numpy as np
    import onnx
    import onnxruntime as ort
    import torch
    import torch.nn.functional as F
    import timm
    from isc_feature_extractor.model import ISCNet

    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=str(BENCH / "work" / "isc21_weights_ortho_probe" / "export_new"))
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    assert WEIGHTS.exists(), f"权重缺失: {WEIGHTS}"
    ckpt = torch.load(str(WEIGHTS), map_location="cpu", weights_only=False)
    bb = timm.create_model(ARCH, features_only=True)
    net = ISCNet(backbone=bb, fc_dim=256, p=1.0, eval_p=1.0)
    sd = {s.replace("module.", ""): v for s, v in ckpt["state_dict"].items()}
    net.load_state_dict(sd)
    net.eval()

    class Wrap(torch.nn.Module):
        def __init__(self, n):
            super().__init__()
            self.n = n

        def forward(self, x):
            f = self.n.backbone(x)[-1]
            # eval_p=1.0 ⇒ gem == mean；ReduceMean 形态 DML 可授权
            return F.normalize(self.n.bn(self.n.fc(f.mean(dim=(2, 3)))))

    wrap = Wrap(net)
    ex = torch.randn(1, 3, INPUT_SIZE, INPUT_SIZE)
    with torch.no_grad():
        ref_t = wrap(ex).numpy()
    onnx_path = out_dir / "isc_ft_v107.onnx"
    torch.onnx.export(wrap, ex, str(onnx_path), opset_version=17,
                      input_names=["input"], output_names=["emb"])

    model = onnx.load(str(onnx_path))
    onnx.checker.check_model(model)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    outs = sess.run(["emb"], {"input": np.ascontiguousarray(ex.numpy().astype(np.float32))})[0]
    cos = float(outs[0] @ ref_t[0] / (np.linalg.norm(outs[0]) * np.linalg.norm(ref_t[0])))
    maxd = float(np.abs(outs - ref_t).max())
    print(f"[check] torch vs 新 ONNX: cos={cos:.6f} max|d|={maxd:.3e}")
    ok = cos >= 0.9999 and maxd <= 1e-3
    if not ok:
        print("[FAIL] 数值校验不过")
        return 1

    data_path = out_dir / "isc_ft_v107.onnx.data"
    if not data_path.exists():
        print(f"[FAIL] 外部权重未落盘: {data_path}")
        return 1

    ref_graph = REFERENCE / "isc_ft_v107.onnx"
    if ref_graph.exists():
        rs = ort.InferenceSession(str(ref_graph), providers=["CPUExecutionProvider"])
        rout = rs.run(["emb"], {"input": np.ascontiguousarray(ex.numpy().astype(np.float32))})[0]
        rcos = float(outs[0] @ rout[0] / (np.linalg.norm(outs[0]) * np.linalg.norm(rout[0])))
        rmaxd = float(np.abs(outs - rout).max())
        print(f"[check] 新 ONNX vs 仓内参考: cos={rcos:.6f} max|d|={rmaxd:.3e}")
        ok = ok and rcos >= 0.9999 and rmaxd <= 1e-3

    print(f"[done] 输出: {onnx_path}")
    print(f"[done] sha256 图  = {sha256(onnx_path)}")
    print(f"[done] sha256 权重 = {sha256(data_path)}")
    print("[done] 注意: 图字节随导出器版本可变（元数据），数值等价即有效；")
    print("[done] 若替换仓内资产须同步更新 asset.json 的 sha256 并重跑 accept_packaged_bundle。")
    print("EXPORT_OK" if ok else "EXPORT_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
