"""engine.feature_store.index_bundle — 索引加载结果（含 numpy，不属于纯数据 domain）。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from domain import IndexMeta


@dataclass
class IndexBundle:
    """``load_index`` 的返回：metadata + 特征 + 时间轴（行对齐）。

    - ``features``：[T, 384] float32，L2 归一化 DINOv2 CLS。
    - ``times``：[T] float32，每帧绝对时间(秒)。与 features 行完全对齐，供定位/预览换算。
    """

    meta: IndexMeta
    features: np.ndarray
    times: np.ndarray

    @property
    def num_frames(self) -> int:
        return int(self.features.shape[0]) if self.features.ndim else 0
