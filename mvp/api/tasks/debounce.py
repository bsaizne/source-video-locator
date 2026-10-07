"""tasks.debounce — 进度发布层防抖（③ 六项立项，2026-10-07）。

竞品形态（`FINDINGS_CUTMATCH_ENTRY_LAYER_20261006.md` §2.4）：
`_make_stage_delay_progress_callback` 对会一闪而过的阶段延迟发布，避免进度条跳档噪声；
心跳（`Task.last_event_at`）独立证明「还在动」。

契约（纯类，clock 注入可测）：
- 同阶段连续帧按最小发布间隔合并（只保留最新一条 held 帧，旧 held 被新值覆盖）；
- **阶段切换**与**终态（percent ≥ 100）**立即直通，绝不因防抖丢失/延迟阶段边界；
- ``submit`` 返回应立即发布的帧列表（0 / 1 / 2 帧——阶段切换时先补发 held 再发本帧）。
"""
from __future__ import annotations

import time
from typing import Callable

Frame = tuple  # (TaskStage, float, str)


class ProgressDebouncer:
    def __init__(self, min_interval_s: float = 0.5,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._min_interval_s = min_interval_s
        self._clock = clock
        self._last_published_at: float | None = None
        self._last_stage: object = None
        self._held: Frame | None = None

    def submit(self, stage, percent: float, message: str = "") -> list[Frame]:
        now = self._clock()
        frame: Frame = (stage, percent, message)
        terminal = percent >= 100
        stage_changed = self._last_stage is not None and stage is not self._last_stage \
            and stage != self._last_stage
        if self._last_published_at is None or terminal or stage_changed:
            out = []
            if self._held is not None:
                out.append(self._held)          # 先补发上一条 held（旧值先于新值）
                self._held = None
            out.append(frame)
            self._last_published_at = now
            self._last_stage = stage
            return out
        elapsed = now - self._last_published_at
        if elapsed >= self._min_interval_s:
            out = []
            if self._held is not None:
                out.append(self._held)
                self._held = None
            out.append(frame)
            self._last_published_at = now
            self._last_stage = stage
            return out
        self._held = frame                       # 间隔未到：只留最新，旧 held 被覆盖
        return []

    def flush(self) -> list[Frame]:
        """收尾补发 held 帧（调用方在任务结束前调用；无 held 返回空）。"""
        if self._held is None:
            return []
        out = [self._held]
        self._held = None
        return out
