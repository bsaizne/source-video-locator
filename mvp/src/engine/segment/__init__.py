"""engine.segment — 无 GT 编辑侧 shot 切分（Stage 1 第 6 项）。

导入即得：``detect_shots``（特征序列 -> 查询单元列表）、``adjacent_distances``、
``ShotSegment``、以及切分参数默认常量。无 confidence 依赖，直接从本包顶层导出
（无需 localization 那种隐藏子模块拆分）。
"""
from .segment import (SEG_CUT_ABS, SEG_MIN_SHOT_S, SEG_SMOOTH, SEG_Z_THRESH,
                      ShotSegment, adjacent_distances, detect_shots)

__all__ = [
    "ShotSegment",
    "detect_shots",
    "adjacent_distances",
    "SEG_CUT_ABS",
    "SEG_Z_THRESH",
    "SEG_SMOOTH",
    "SEG_MIN_SHOT_S",
]
