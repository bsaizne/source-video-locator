"""device.base — 统一推理后端抽象（Protocol）。

业务层不得关心当前是 AMD / CPU / MPS / CUDA，只依赖 :class:`DeviceBackend`。
GPU 只是加速，不改变算法逻辑（DEVICE_BACKEND_SPEC §1 / §5）。
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class DeviceBackend(Protocol):
    """所有后端实现必须满足的接口。

    硬件阶段：H1 CPU -> H2 AMD -> H3 MPS（+ 未来 CUDA），见 DEVICE_BACKEND_SPEC。
    """

    def is_available(self) -> bool: ...                 # 该 backend 在本机是否可用
    def device_name(self) -> str: ...                   # "cpu" | "cuda:0" | "mps" | ...
    def device_type(self) -> str: ...                   # "cpu" | "amd" | "mps" | "cuda"
    def memory_info(self) -> dict: ...                  # total/available/used (GB)
    def load_feature_model(self) -> Any: ...            # DinoV2Small, .eval(), 已放 device
    def embed_frames(self, bgr_frames: list[np.ndarray],
                     batch_size: int = 8) -> np.ndarray: ...  # [N,384] L2-norm
    def cleanup(self) -> None: ...
