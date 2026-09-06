"""tasks.worker — 后台 worker：调用 SourceLocatorService.locate。

Worker 只做三件事：
1. 调 service（编排），
2. 把 service 的 ``ProgressEvent`` 映射成阶段级 TaskStage + 粗略 progress，
3. 捕获异常（错误→failed，取消→cancelled）。

**不复制/实现任何算法**——业务全部在 ``SourceLocatorService``。本阶段提供的是
“阶段级”progress（每次进入新阶段更新一次 stage + 一个阶段百分比），不是真实
DINO 逐帧进度（需后续 service hook）。
"""
from __future__ import annotations

from typing import Callable

from app.models import ProgressEvent, ProgressStage
from infrastructure.errors import ApplicationError

from .models import Task, TaskStage

LogFn = Callable[..., None]

# ProgressStage -> (TaskStage, 区间起点%, 区间宽度%)。worker 用事件自带的
# current/total 在区间内做真实插值（逐帧/逐段推进），不再阶段级跳变。
# 2026-08-30 重构：旧版每阶段一个固定百分比（45→60→75→85 跳变），且检索/
# 定位/置信（管线最长的逐段循环）完全无进度——长任务看起来像卡死。
_STAGE_RANGES: dict[ProgressStage, tuple[TaskStage, int, int]] = {
    ProgressStage.INDEX_BUILD: (TaskStage.INDEXING, 0, 12),
    ProgressStage.EDITED_FEATURE_EXTRACTION: (TaskStage.EMBEDDING, 12, 18),
    ProgressStage.SEGMENT_DETECTION: (TaskStage.SEGMENTING, 30, 8),
    # 检索/定位/置信同属一个逐段循环（事件 current=段下标 0-based、total=段数），
    # 共享 38-92 区间按段插值；三个阶段事件交错到达，靠 run_worker 的单调钳制保序。
    ProgressStage.CANDIDATE_RETRIEVAL: (TaskStage.RETRIEVAL, 38, 54),
    ProgressStage.LOCALIZATION: (TaskStage.RETRIEVAL, 38, 54),
    ProgressStage.CONFIDENCE: (TaskStage.RETRIEVAL, 38, 54),
    ProgressStage.EXPORT: (TaskStage.EXPORTING, 92, 7),
}


def map_progress_stage(ev: ProgressEvent) -> tuple[TaskStage, int]:
    """把一个 service 进度事件映射为 (TaskStage, 0-100 百分比)。

    事件带 current/total 时在阶段区间内插值：逐帧阶段（索引/特征提取，
    current=已处理数，1-based）用 ``current/total``；逐段阶段（current=段下标，
    0-based）用 ``(current+1)/total``——首段事件就前进、末段事件到达区间右端。
    无 total 的阶段事件取区间起点。未知阶段回退 IDLE。
    """
    stage, base, span = _STAGE_RANGES.get(ev.stage, (TaskStage.IDLE, 0, 0))
    if ev.total and ev.total > 0:
        if ev.stage in (ProgressStage.INDEX_BUILD, ProgressStage.EDITED_FEATURE_EXTRACTION):
            frac = ev.current / ev.total
        else:
            frac = (ev.current + 1) / ev.total
        frac = min(1.0, max(0.0, frac))
        return stage, round(base + span * frac)
    return stage, base


def run_worker(task: Task, service, *, log: LogFn | None = None) -> None:
    """后台线程入口：跑一次 locate 并更新 task 状态。永不抛出（异常转 task.error/failed）。"""
    if log is None:
        log = lambda *a, **k: None  # noqa: E731
    task.mark_running()
    last_pct = 0

    def on_progress(ev: ProgressEvent) -> None:
        nonlocal last_pct
        stage, pct = map_progress_stage(ev)
        # 单调钳制：检索/定位/置信事件交错、阶段边界事件缺 total 时百分比不回跳。
        pct = max(pct, last_pct)
        last_pct = pct
        task.update_progress(stage, pct, message=ev.message or "")

    try:
        batch = service.locate(
            task.edited_path,
            task.original_path,
            on_progress=on_progress,
            cancel_token=task.token,
        )
    except ApplicationError as exc:
        # cancellation 由 service 以 ApplicationError 穿透（_check_cancel）。
        if task.token.is_cancelled():
            task.mark_cancelled()
            log("task %s cancelled", task.task_id)
        else:
            task.mark_failed(f"{type(exc).__name__}: {exc}")
            log("task %s failed: %s", task.task_id, exc)
    except Exception as exc:  # noqa: BLE001 — worker 必须兜住一切，转为 failed
        task.mark_failed(f"{type(exc).__name__}: {exc}")
        log("task %s failed: %s", task.task_id, exc)
    else:
        result = batch.to_dict() if hasattr(batch, "to_dict") else batch
        task.mark_completed(result)
        log("task %s completed", task.task_id)
