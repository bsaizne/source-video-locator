"""engine.segment.card_guard — 黑底文字卡/logo 帧检测(像素层守卫,纯 numpy 零依赖)。

真实案例(GT v3 n04):编辑片 TikTok 片尾 logo(黑底白色居中 logo)与电影片尾版权卡
(黑底白 MPA 字卡)在 CLS 全局特征下 cos≈0.736,产出 HIGH 0.95「自信答错」。
这类「黑底 + 稀疏亮色图形」的版式帧,任何纯外观单信号都无法区分语义身份;
本模块在**像素层**识别版式,供 app 层跳过检索、直接输出 ``not_in_source``。

帧级判定:``black_ratio``(近黑像素占比)≥ card_black_ratio 且 亮像素占比
(max RGB≥200)∈ [card_bright_lo, card_bright_hi] → 文字卡帧。
段级判定:段内卡帧占比 ≥ card_shot_ratio → 文字卡段(不可定位)。

设计约束:
- 纯函数、无状态、确定性;4x4 降采样以把成本压到可忽略(每帧 <0.5ms)。
- 纯黑帧不算文字卡(bright < lo)——纯黑是"黑场转场",另一个失败类,不在此处理。
- 判别阈值全部走 PipelineConfig.card_*(config.py),无硬编码魔法数。
"""
from __future__ import annotations

import numpy as np

_CARD_DOWNSAMPLE = 4  # 降采样步长(帧太大时;足够判别版式)
_BLACK_MAX_VAL = 32   # 近黑像素:max(RGB) < 32(与 GrayBytesUtils.VerifyRgbFrameValues 同口径)
_BRIGHT_MIN_VAL = 200  # 亮像素:max(RGB) >= 200(白字/白 logo)
_BRIGHT_MAX_SPREAD = 48.0  # 亮像素通道扩散度(max-min)上限:白字≈0,橙色爆炸/暖光灯≫48
_BRIGHT_MIN_AREA_FRAC = 0.004  # 最大亮色连通域面积占比下限:logo/文字块是大实体,夜间高光是零星小点


def card_frame_ratios(frame: np.ndarray) -> tuple[float, float]:
    """单帧 → (black_ratio, bright_ratio)。BGR/RGB 均可(用通道 max,与通道序无关)。"""
    f = np.asarray(frame)
    if f.ndim == 3:
        f = f[::_CARD_DOWNSAMPLE, ::_CARD_DOWNSAMPLE]
    mx = f.max(axis=2) if f.ndim == 3 else f
    total = mx.size
    black = float((mx < _BLACK_MAX_VAL).sum()) / total
    bright = float((mx >= _BRIGHT_MIN_VAL).sum()) / total
    return black, bright


def _largest_component_area(mask: np.ndarray) -> int:
    """二值掩码最大 4-连通域面积(BFS,纯 python;掩码为降采样小图,成本可忽略)。"""
    m = mask.astype(np.bool_)
    h, w = m.shape
    seen = np.zeros_like(m)
    best = 0
    for sy, sx in zip(*np.nonzero(m)):
        if seen[sy, sx]:
            continue
        area = 0
        stack = [(sy, sx)]
        seen[sy, sx] = True
        while stack:
            y, x = stack.pop()
            area += 1
            for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                if 0 <= ny < h and 0 <= nx < w and m[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        best = max(best, area)
    return best


def is_card_frame(frame: np.ndarray, *, black_ratio: float = 0.85,
                  bright_lo: float = 0.01, bright_hi: float = 0.30,
                  bright_max_spread: float = _BRIGHT_MAX_SPREAD,
                  bright_min_area_frac: float = _BRIGHT_MIN_AREA_FRAC) -> bool:
    """帧级判定:黑底 + 稀疏**白色**(低扩散)**大块实体**(大连通域)亮斑 = 文字/logo。

    - ``bright_max_spread``:夜间误杀修复一——橙色爆炸/暖色灯斑通道扩散大,白字≈0。
    - ``bright_min_area_frac``:夜间误杀修复二——夜间散点高光(铁丝网反光/天空斑)是
      零星小点,TikTok logo/搜索框/字卡文字块是大实体连通域(实测两形态均出现)。
    - ``black_ratio`` 0.60→0.85:夜间误杀修复三(test1 r10)——夜间剧情画面
      black≈0.73-0.78,其解说字幕白字行恰是宽扁大连通域+窗光低扩散,骗过前两个
      判据;实测真卡 black≥0.93(n04 0.934-0.969 / test1 片尾卡 0.96-0.99),
      0.85 完成分离。全片扫描:1.mp4/test1 所有 KEEP 卡帧 ≥0.856,救回帧 ≤0.78。
    """
    f = np.asarray(frame)
    if f.ndim == 3:
        f = f[::_CARD_DOWNSAMPLE, ::_CARD_DOWNSAMPLE]
    if f.ndim != 3:
        mx = f
        spread = np.zeros_like(mx, dtype=np.float32)
    else:
        mx = f.max(axis=2)
        mn = f.min(axis=2)
        spread = (mx.astype(np.int16) - mn.astype(np.int16))
    total = mx.size
    black = float((mx < _BLACK_MAX_VAL).sum()) / total
    bright_mask = mx >= _BRIGHT_MIN_VAL
    bright = float(bright_mask.sum()) / total
    if bright < bright_lo or bright > bright_hi:
        return False
    if bright_mask.any():
        if float(spread[bright_mask].mean()) > bright_max_spread:
            return False
        if _largest_component_area(bright_mask) < bright_min_area_frac * total:
            return False
    return black >= black_ratio


def card_shot_ratio(frames: list[np.ndarray], *, black_ratio: float = 0.85,
                    bright_lo: float = 0.01, bright_hi: float = 0.30,
                    bright_max_spread: float = _BRIGHT_MAX_SPREAD,
                    bright_min_area_frac: float = _BRIGHT_MIN_AREA_FRAC) -> float:
    """段级:卡帧占比([0,1])。空输入返回 0.0。"""
    if not frames:
        return 0.0
    hits = sum(1 for f in frames
               if is_card_frame(f, black_ratio=black_ratio, bright_lo=bright_lo,
                                bright_hi=bright_hi, bright_max_spread=bright_max_spread,
                                bright_min_area_frac=bright_min_area_frac))
    return hits / len(frames)

def max_card_run_ratio(flags: list[bool]) -> float:
    """段内最长**连续**卡帧 run 的占比（[0,1]；空输入 0）。

    段级占比判据的补充维度（test4 r17 实证）：片尾卡常带 1-2 帧彩色淡入
    （TikTok logo 淡入帧 spread 大 → 非卡），把段占比稀释到门槛之下；
    而"尾部连续卡帧 run"是稳定形态。与占比判据取或使用。
    """
    if not flags:
        return 0.0
    best = run = 0
    for f in flags:
        run = run + 1 if f else 0
        best = max(best, run)
    return best / len(flags)
