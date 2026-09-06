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
    - ``scenes``：[S,2] float32 场景起止秒（Phase 21 召回扩展层）；None=旧索引无场景表（扩池降级）。
    - ``scene_feats``：[S,384] float32 L2 场景指纹，与 scenes 行对齐；None 同上。
    - ``events``：[E,2] float32 事件单元起止秒（方向 A 完整阶段 2026-09-05）；None=旧索引无事件表。
    - ``event_feats``：[E,384] float32 L2 事件代表指纹，与 events 行对齐；None 同上。
    """

    meta: IndexMeta
    features: np.ndarray
    times: np.ndarray
    scenes: np.ndarray | None = None
    scene_feats: np.ndarray | None = None
    events: np.ndarray | None = None
    event_feats: np.ndarray | None = None

    @property
    def num_frames(self) -> int:
        return int(self.features.shape[0]) if self.features.ndim else 0
