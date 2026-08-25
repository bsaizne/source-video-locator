"""device.directml_backend — Windows AMD GPU (DirectML) 推理后端（PHASE H2）。

复现 POC 已验证的能力（``mvp/poc/amdgpu_onnx/``，AMD_BACKEND_GO）：把冻结
DINOv2 ViT-S/14 CLS-384 的 forward 以 ONNX 图（含外部权重 ``.onnx.data``）在
``onnxruntime`` 的 ``DmlExecutionProvider`` 上推理，输出与 ``CPUBackend`` 一致的
``[N,384] float32 L2`` 特征。

契约与 :class:`CPUBackend` 相同（``embed_frames`` -> [N,384] L2；同一
``_imagenet_preprocess`` 语义）；**禁止** fp16 / 量化 / 改输入尺寸 / 改 dim / 改归一。

模型资产正式化（§4）：ONNX 图 + ``.onnx.data`` 作为**同一资产**由 ``resolve_dml_model``
解析，从产品 ``models`` 目录 / env ``SVL_DML_MODEL`` 找，绝不依赖 ``work/`` 或
``mvp/poc/``。由 ``mvp/scripts/export_dml_model.py`` 从冻结模型重新导出。
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from infrastructure import paths
from infrastructure.errors import DeviceError
from .cpu_backend import _sys_memory_gb
from .dinov2_model import _imagenet_preprocess

_ONNX_BASENAME = "dinov2_cls_384.onnx"
_DATA_BASENAME = "dinov2_cls_384.onnx.data"
ASSET_NAME = "dinov2_cls_384"
MODEL_NAME = "dinov2_vits14_cls_384"


def resolve_dml_model(model_path: str | Path | None = None) -> Path:
    """解析 DirectML ONNX 图的路径（须能找到；若图引用外部数据，``.onnx.data`` 必须同目录）。

    优先级：显式 ``model_path`` > env ``SVL_DML_MODEL`` > 产品 ``models`` 目录
    （``paths.dinov2_dml_asset_dir()``）。找不到 -> :class:`DeviceError`。
    """
    if model_path is not None:
        p = Path(model_path)
        if not p.exists():
            raise DeviceError(f"DirectML ONNX model not found: {p}")
        return p
    env = os.environ.get("SVL_DML_MODEL")
    if env and Path(env).exists():
        return Path(env)
    prod = paths.dinov2_dml_asset_dir() / _ONNX_BASENAME
    if prod.exists():
        return prod
    raise DeviceError(
        "DirectML ONNX model asset not found; run mvp/scripts/export_dml_model.py, "
        f"or set SVL_DML_MODEL (expected: {prod})"
    )


def asset_meta(model_path: str | Path) -> dict:
    """读取资产目录里的 ``asset.json``（model name/version/opset/shape 等）；缺失返回 {}。"""
    ap = Path(model_path).parent / "asset.json"
    if ap.exists():
        import json

        try:
            return json.loads(ap.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


class DirectMLBackend:
    """DirectML (DmlExecutionProvider) 特征提取。``embed_frames`` -> [N,384] L2 归一化 (float32)。

    仅在能力探测通过后由 ``device.resolve_backend`` 构造；任何构造失败都应被上游捕获并
    CPU fallback。``device_type()`` = ``"amd"``、``device_name()`` = ``"directml"``。
    """

    def __init__(self, *, model_path: str | Path | None = None,
                 device_id: int = 0, batch_size: int = 8,
                 num_threads: int | None = None, session=None):
        self.model_path = resolve_dml_model(model_path)
        self.batch_size = batch_size or 8
        self.device_id = device_id
        self._providers: list[str] = []
        self._session = session
        if self._session is None:
            self._session = self._build_session()

    # ------------------------------------------------------------------ #
    # Session construction
    # ------------------------------------------------------------------ #
    def _build_session(self):
        import onnxruntime as ort

        try:
            providers = ort.get_available_providers()
        except Exception as exc:
            raise DeviceError(f"onnxruntime not importable/get_providers failed: {exc}") from exc
        if "DmlExecutionProvider" not in providers:
            raise DeviceError("DmlExecutionProvider not available on this machine")
        opts = [("DmlExecutionProvider", {"device_id": self.device_id}), "CPUExecutionProvider"]
        try:
            sess = ort.InferenceSession(str(self.model_path), providers=opts)
        except Exception as exc:
            raise DeviceError(f"failed to init DirectML session: {exc}") from exc
        self._providers = list(sess.get_providers())
        return sess

    # ------------------------------------------------------------------ #
    # DeviceBackend interface
    # ------------------------------------------------------------------ #
    def is_available(self) -> bool:
        return self._session is not None

    def device_name(self) -> str:
        return "directml"

    def device_type(self) -> str:
        return "amd"

    def memory_info(self) -> dict:
        total, avail = _sys_memory_gb()
        return {
            "device": self.device_name(),
            "total_gb": round(total, 1),
            "available_gb": round(avail, 1),
            "used_gb": round(total - avail, 1),
            "vram_mb": "not_exposed_by_ort_dml",
        }

    def load_feature_model(self):
        """DirectML 没有 torch 模型；返回 ONNX Runtime session（充当"feature model"）。"""
        if self._session is None:
            self._session = self._build_session()
        return self._session

    def embed_frames(self, bgr_frames: list[np.ndarray], batch_size: int = 8) -> np.ndarray:
        if not bgr_frames:
            return np.zeros((0, 384), dtype=np.float32)
        sess = self.load_feature_model()
        bs = batch_size or self.batch_size
        chunks = []
        for i in range(0, len(bgr_frames), bs):
            batch = bgr_frames[i:i + bs]
            imgs = np.stack([_imagenet_preprocess(f).numpy()[0] for f in batch], axis=0)
            imgs = np.ascontiguousarray(imgs, dtype=np.float32)
            out = sess.run(["embedding"], {"input": imgs})[0]     # [B,384] raw CLS
            chunks.append(np.asarray(out, dtype=np.float32))
        feats = np.concatenate(chunks, axis=0)
        norms = np.linalg.norm(feats, axis=1, keepdims=True)
        return feats / np.maximum(norms, 1e-8)

    def cleanup(self) -> None:
        self._session = None

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (f"DirectMLBackend(device=directml, model={self.model_path.name}, "
                f"providers={self._providers})")
