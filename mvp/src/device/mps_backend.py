"""device.mps_backend — macOS Apple Silicon (PyTorch MPS) 推理后端（H3）。

关键约束（H3 POC 2026-08-26 实测, mvp/poc/macos_mps/）:
  - MPS **batch ≤ 4**（≥8 触发 5.37GiB buffer 限制且吞吐从 6.8fps 暴跌到 2.8fps）;
  - 数值与 CPU 对齐（cos mean=1.0, max_abs_diff 6.3e-7）;
  - 仅 macOS + ``torch.backends.mps.is_available()`` 时可用, 否则构造即抛
    :class:`DeviceError`（由 :func:`device.resolve_backend` 捕获并 fallback CPU）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from infrastructure.errors import DeviceError
from .cpu_backend import _sys_memory_gb, resolve_dinov2_weights
from .dinov2_model import DinoV2Small, _imagenet_preprocess

_MPS_BATCH_CAP = 4   # H3 POC 实测上限（见模块 docstring）


def _cap_batch(batch_size: int | None) -> int:
    """MPS 批量上限钳制（POC 实测 batch≤4）。"""
    return max(1, min(int(batch_size or _MPS_BATCH_CAP), _MPS_BATCH_CAP))


def mps_available() -> tuple[bool, str]:
    """MPS 能力探测：torch 可导入且 ``torch.backends.mps.is_available()``。"""
    try:
        import torch  # noqa: PLC0415 - 延迟导入（Windows 无 torch 也可用 DML 路径）
    except Exception as exc:  # pragma: no cover - import error
        return False, f"torch not installed: {exc}"
    try:
        if not torch.backends.mps.is_available():
            return False, "MPS not available (non-Apple-Silicon or torch build without MPS)"
    except Exception as exc:  # pragma: no cover
        return False, f"MPS probe failed: {exc}"
    return True, "ok"


class MPSBackend:
    """macOS Apple Silicon (MPS) DINOv2 特征提取。``embed_frames`` 返回 [N,384] L2 (float32)。"""

    def __init__(self, weights_path: str | Path | None = None, *,
                 batch_size: int | None = 4, model: DinoV2Small | None = None):
        ok, reason = mps_available()
        if not ok:
            raise DeviceError(f"MPS unavailable: {reason}")
        self.weights_path = resolve_dinov2_weights(weights_path)
        self.batch_size = _cap_batch(batch_size)
        self._model = model
        self._device = "mps"

    # ---------------------------------------------------------------- #
    # DeviceBackend interface
    # ---------------------------------------------------------------- #
    def is_available(self) -> bool:
        ok, _ = mps_available()
        return ok

    def device_name(self) -> str:
        return "mps"

    def device_type(self) -> str:
        return "mps"

    def memory_info(self) -> dict:
        total, avail = _sys_memory_gb()
        return {
            "device": self.device_name(),
            "total_gb": round(total, 1),
            "available_gb": round(avail, 1),
            "used_gb": round(total - avail, 1),
        }

    def load_feature_model(self) -> DinoV2Small:
        if self._model is None:
            ckpt = torch.load(str(self.weights_path), map_location="cpu")
            model = DinoV2Small()
            model.load_state_dict(ckpt)   # official state_dict is bare (no 'model' key)
            model.eval().to(self._device)
            self._model = model
        return self._model

    def embed_frames(self, bgr_frames: list[np.ndarray], batch_size: int | None = None) -> np.ndarray:
        if not bgr_frames:
            return np.zeros((0, 384), dtype=np.float32)
        model = self.load_feature_model()
        bs = _cap_batch(batch_size or self.batch_size)
        chunks = []
        with torch.no_grad():
            for i in range(0, len(bgr_frames), bs):
                batch = bgr_frames[i:i + bs]
                imgs = torch.cat([_imagenet_preprocess(f) for f in batch], dim=0).to(self._device)
                out = model(imgs)  # B, 384
                chunks.append(out.cpu().numpy().astype(np.float32))
        feats = np.concatenate(chunks, axis=0)
        norms = np.linalg.norm(feats, axis=1, keepdims=True)
        return feats / np.maximum(norms, 1e-8)

    def cleanup(self) -> None:
        self._model = None
        try:
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()
        except Exception:  # pragma: no cover - 旧 torch 无 torch.mps
            pass

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"MPSBackend(device=mps, batch_cap={_MPS_BATCH_CAP})"
