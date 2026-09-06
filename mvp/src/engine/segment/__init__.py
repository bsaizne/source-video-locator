"""engine.segment — 无 GT 编辑侧 shot 切分（Stage 1 第 6 项）。

导入即得：``detect_shots``（特征序列 -> 查询单元列表）、``detect_shots_two_level``
（长块二级细分）、``card_guard``（黑底文字卡检测）、``flash_guard``（白闪/亮度
突变守卫，C 项验证提取入库）、``adjacent_distances``、``ShotSegment``、以及切分
参数默认常量。无 confidence 依赖，直接从本包顶层导出（无需 localization 那种
隐藏子模块拆分）。
"""
from .card_guard import (card_frame_ratios, card_shot_ratio, is_card_frame,
                         max_card_run_ratio)
from .flash_guard import (BRIGHT_SPIKE_MEAN_DELTA, BRIGHT_SPIKE_PEAK_TH,
                          FLASH_DYN_MIN_SHOT_S, FLASH_FRAC_TH, FLASH_MEAN_TH,
                          FLASH_SEG_MERGE_FRAC, brightness_spike_regions,
                          drop_brightness_spike_cuts, drop_flash_cuts,
                          dynamic_min_shot, flash_flags_for_frames,
                          frame_mean_brightness, is_flash_frame,
                          merge_flash_segments)
from .segment import (SEG_CUT_ABS, SEG_MIN_SHOT_S, SEG_SMOOTH, SEG_Z_THRESH,
                      ShotSegment, adjacent_distances, detect_shots,
                      detect_shots_two_level)

__all__ = [
    "ShotSegment",
    "detect_shots",
    "detect_shots_two_level",
    "adjacent_distances",
    "is_card_frame",
    "card_frame_ratios",
    "card_shot_ratio",
    "max_card_run_ratio",
    "SEG_CUT_ABS",
    "SEG_Z_THRESH",
    "SEG_SMOOTH",
    "SEG_MIN_SHOT_S",
    # --- 白闪守卫（C 项验证提取入库）---
    "is_flash_frame",
    "flash_flags_for_frames",
    "frame_mean_brightness",
    "brightness_spike_regions",
    "drop_brightness_spike_cuts",
    "drop_flash_cuts",
    "dynamic_min_shot",
    "merge_flash_segments",
    "FLASH_MEAN_TH",
    "FLASH_FRAC_TH",
    "FLASH_DYN_MIN_SHOT_S",
    "FLASH_SEG_MERGE_FRAC",
    "BRIGHT_SPIKE_MEAN_DELTA",
    "BRIGHT_SPIKE_PEAK_TH",
]