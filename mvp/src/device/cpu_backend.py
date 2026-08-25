"""device.cpu_backend — CPU 推理后端（PHASE H1 唯一要求）。

CPUBackend 是 Windows CPU MVP 的主推理后端：无 CUDA 依赖，线程数可配。AMDMPS
后端（H2/H3）将复用同一 :class:`DeviceBackend` 接口，CPU 数值为一致性基准
（DEVICE_BACKEND_SPEC §1 / §6）。
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import torch

from infrastructure.errors import DeviceError
from .dinov2_model import DinoV2Small, _imagenet_preprocess

_WEIGHTS_BASENAME = "dinov2_vits14_pretrain.pth"


def resolve_dinov2_weights(weights_path: str | Path | None = None) -> Path:
    """Resolve the DINOv2 pretrained weights file.

    优先级：显式 ``weights_path`` > env ``SVL_DINOV2_WEIGHTS`` > 仓库
    ``work/dinov2_weights/``（DEV 回退；打包时改为随包内嵌，见 MVP_ROADMAP 打包项）。
    找不到 -> :class:`DeviceError`。
    """
    if weights_path is not None:
        p = Path(weights_path)
        if not p.exists():
            raise DeviceError(f"DINOv2 weights not found: {p}")
        return p
    env = os.environ.get("SVL_DINOV2_WEIGHTS")
    if env and Path(env).exists():
        return Path(env)
    repo = Path(__file__).resolve().parents[3] / "work" / "dinov2_weights" / _WEIGHTS_BASENAME
    if repo.exists():
        return repo
    raise DeviceError(
        f"DINOv2 weights not found; set SVL_DINOV2_WEIGHTS or pass weights_path= (expected {repo})"
    )


class CPUBackend:
    """CPU DINOv2 特征提取。``embed_frames`` 返回 [N,384] L2 归一化 (float32)。"""

    def __init__(self, weights_path: str | Path | None = None, *,
                 num_threads: int | None = None, batch_size: int = 8,
                 model: DinoV2Small | None = None):
        self.weights_path = resolve_dinov2_weights(weights_path)
        self._model = model
        self.batch_size = batch_size
        self._num_threads = num_threads or max(1, torch.get_num_threads())

    # ---------------------------------------------------------------- #
    # DeviceBackend interface
    # ---------------------------------------------------------------- #
    def is_available(self) -> bool:
        return True  # CPU 恒可用（无硬件依赖）

    def device_name(self) -> str:
        return "cpu"

    def device_type(self) -> str:
        return "cpu"

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
            torch.set_num_threads(self._num_threads)
            ckpt = torch.load(str(self.weights_path), map_location="cpu")
            model = DinoV2Small()
            model.load_state_dict(ckpt)   # official state_dict is bare (no 'model' key)
            model.eval()
            self._model = model
        return self._model

    def embed_frames(self, bgr_frames: list[np.ndarray], batch_size: int = 8) -> np.ndarray:
        if not bgr_frames:
            return np.zeros((0, 384), dtype=np.float32)
        model = self.load_feature_model()
        bs = batch_size or self.batch_size
        chunks = []
        with torch.no_grad():
            for i in range(0, len(bgr_frames), bs):
                batch = bgr_frames[i:i + bs]
                imgs = torch.cat([_imagenet_preprocess(f) for f in batch], dim=0)
                out = model(imgs)  # B, 384
                chunks.append(out.cpu().numpy().astype(np.float32))
        feats = np.concatenate(chunks, axis=0)
        norms = np.linalg.norm(feats, axis=1, keepdims=True)
        return feats / np.maximum(norms, 1e-8)

    def cleanup(self) -> None:
        self._model = None

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"CPUBackend(device=cpu, threads={self._num_threads})"


def _sys_memory_gb() -> tuple[float, float]:
    """Return (total_gb, available_gb) without psutil (stdlib/cross-platform)."""
    if os.name == "nt":
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        m = MEMORYSTATUSEX()
        m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        total = m.ullTotalPhys / (1024 ** 3)
        avail = m.ullAvailPhys / (1024 ** 3)
        return float(total), float(avail)
    # unix / macOS
    page_size = os.sysconf("SC_PAGE_SIZE")
    total = os.sysconf("SC_PHYS_PAGES") * page_size / (1024 ** 3)
    avail = os.sysconf("SC_AVPHYS_PAGES") * page_size / (1024 ** 3)
    return float(total), float(avail)
