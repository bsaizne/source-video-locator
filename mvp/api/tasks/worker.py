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

import traceback
from typing import Callable

from app.models import ProgressEvent, ProgressStage
from infrastructure.errors import ApplicationError, public_error

from .debounce import ProgressDebouncer
from .models import Task, TaskKind, TaskStage

LogFn = Callable[..., None]

# ProgressStage -> (TaskStage, 区间起点%, 区间宽度%)。worker 用事件自带的
# current/total 在区间内做真实插值（逐帧/逐段推进），不再阶段级跳变。
# 2026-08-30 重构：旧版每阶段一个固定百分比（45→60→75→85 跳变），且检索/
# 定位/置信（管线最长的逐段循环）完全无进度——长任务看起来像卡死。
_STAGE_RANGES: dict[ProgressStage, tuple[TaskStage, int, int]] = {
    # 多原片合并发生在建索引之前（2026-09-29 video.concat 移植），复用 INDEXING 展示区间；
    # 后续 INDEX_BUILD 事件被 run_worker 单调钳制，百分比不回跳。
    ProgressStage.MERGE_SOURCES: (TaskStage.INDEXING, 0, 12),
    ProgressStage.INDEX_BUILD: (TaskStage.INDEXING, 0, 12),
    ProgressStage.EDITED_FEATURE_EXTRACTION: (TaskStage.EMBEDDING, 12, 18),
    ProgressStage.SEGMENT_DETECTION: (TaskStage.SEGMENTING, 30, 8),
    # 检索/定位/置信同属一个逐段循环（事件 current=段下标 0-based、total=段数），
    # 共享 38-92 区间按段插值；三个阶段事件交错到达，靠 run_worker 的单调钳制保序。
    ProgressStage.CANDIDATE_RETRIEVAL: (TaskStage.RETRIEVAL, 38, 54),
    ProgressStage.LOCALIZATION: (TaskStage.RETRIEVAL, 38, 54),
    ProgressStage.CONFIDENCE: (TaskStage.RETRIEVAL, 38, 54),
    # 深度复核（2026-10-02 续40 UX）：段循环结束后的全局修复+拆分+精排链独占 92→98，
    # 逐事件插值推进 ⇒ 修复此前「92% 静默钳死 30+ 分钟」的卡感。导出收尾 98→99.5。
    ProgressStage.REFINE: (TaskStage.RETRIEVAL, 92, 6),
    ProgressStage.EXPORT: (TaskStage.EXPORTING, 98, 1.5),
    # 成片渲染是**独立任务**（kind=render），独占整条进度区间；定位任务永不发该阶段。
    ProgressStage.RENDER_MOVIE: (TaskStage.EXPORTING, 0, 99),
}

# 子阶段切片（2026-10-06 修「92% 卡死」）：REFINE 的 6 个点原先被修复链/拆分/精排/ISC
# **共用同一条 0→1 ramp**，而修复链只发一条 current=0 的事件 ⇒ 实测整段几分钟停在 92.1，
# 真正耗时的逐段精排又被单调钳制挡住。⇒ 按 phase 切成互不重叠的小段，各自推进且不回退。
# 该表内 current 语义 = **已完成数**（0-based），插值用 current/total（不再 +1）。
_PHASE_RANGES: dict[tuple[ProgressStage, str], tuple[TaskStage, float, float]] = {
    (ProgressStage.REFINE, "fix"): (TaskStage.RETRIEVAL, 92, 2),      # 全局修复链（逐步）
    (ProgressStage.REFINE, "split"): (TaskStage.RETRIEVAL, 94, 1),    # 切镜拆分
    (ProgressStage.REFINE, "patch"): (TaskStage.RETRIEVAL, 95, 2),    # patch 逐段精排
    (ProgressStage.REFINE, "isc"): (TaskStage.RETRIEVAL, 97, 1),      # ISC 第二意见逐段
}


def map_progress_stage(ev: ProgressEvent) -> tuple[TaskStage, float]:
    """把一个 service 进度事件映射为 (TaskStage, 0-100 百分比，一位小数)。

    事件带 current/total 时在阶段区间内插值：逐帧阶段（索引/特征提取，
    current=已处理数，1-based）用 ``current/total``；逐段阶段（current=段下标，
    0-based）用 ``(current+1)/total``——首段事件就前进、末段事件到达区间右端。
    无 total 的阶段事件取区间起点。带 ``phase`` 的事件改走 :data:`_PHASE_RANGES`
    的子区间，且 current 一律按**已完成数**解释（``current/total``）。
    一位小数（2026-10-02 续40 UX）：逐段阶段在短区间内整数百分比会长时间不动。
    """
    keyed = (ev.stage, ev.phase)
    if ev.phase and keyed in _PHASE_RANGES:
        stage, base, span = _PHASE_RANGES[keyed]
        if ev.total and ev.total > 0:
            frac = min(1.0, max(0.0, ev.current / ev.total))
            return stage, round(base + span * frac, 1)
        return stage, float(base)
    stage, base, span = _STAGE_RANGES.get(ev.stage, (TaskStage.IDLE, 0, 0))
    if ev.total and ev.total > 0:
        if ev.stage in (ProgressStage.MERGE_SOURCES, ProgressStage.INDEX_BUILD,
                        ProgressStage.EDITED_FEATURE_EXTRACTION,
                        ProgressStage.RENDER_MOVIE):
            frac = ev.current / ev.total
        else:
            frac = (ev.current + 1) / ev.total
        frac = min(1.0, max(0.0, frac))
        return stage, round(base + span * frac, 1)
    return stage, float(base)


def run_worker(task: Task, service, *, log: LogFn | None = None) -> None:
    """后台线程入口：跑一次 locate 并更新 task 状态。永不抛出（异常转 task.error/failed）。"""
    if task.kind is TaskKind.RENDER:
        run_render_worker(task, service, log=log)
        return
    if log is None:
        log = lambda *a, **k: None  # noqa: E731
    task.mark_running()
    last_pct = 0
    # ③ 防抖（2026-10-07 立项）：同阶段连续帧按最小间隔合并（阶段切换/终态直通）。
    deb = ProgressDebouncer()

    def on_progress(ev: ProgressEvent) -> None:
        nonlocal last_pct
        stage, pct = map_progress_stage(ev)
        # 单调钳制：检索/定位/置信事件交错、阶段边界事件缺 total 时百分比不回跳。
        pct = max(pct, last_pct)
        last_pct = pct
        for st, p, msg in deb.submit(stage, pct, message=ev.message or ""):
            task.update_progress(st, p, message=msg)

    try:
        # 多原片输入（2026-09-29 video.concat 移植）：≥2 段先物理合并为单文件，
        # 产物回写 task.original_path，下游 locate/结果/导出维持单原片口径。
        original = task.original_path
        sources = [p for p in task.original_paths if str(p).strip()]
        if len(sources) > 1:
            info = service.merge_originals(sources, on_progress=on_progress,
                                           cancel_token=task.token)
            original = str(info["merged_path"])
            task.original_path = original
        elif len(sources) == 1 and not original:
            original = sources[0]
        batch = service.locate(
            task.edited_path,
            original,
            on_progress=on_progress,
            cancel_token=task.token,
            refine=task.refine,
        )
    except ApplicationError as exc:
        # cancellation 由 service 以 ApplicationError 穿透（_check_cancel）。
        if task.token.is_cancelled():
            task.mark_cancelled()
            log("task %s cancelled", task.task_id)
        else:
            # task.error 直接进前端错误条幅 → 存对外话术（码），技术细节走日志（T1-2 同源）。
            pub = public_error(exc)
            task.mark_failed(f"{pub['message']}（{pub['code']}）")
            log("task %s failed [%s] %s: %s", task.task_id, pub["code"], type(exc).__name__, exc)
    except Exception as exc:  # noqa: BLE001 — worker 必须兜住一切，转为 failed
        pub = public_error(exc)
        task.mark_failed(f"{pub['message']}（{pub['code']}）")
        # 堆栈必须留痕（2026-10-05：r8 打包态 E2E 失败时只有一行异常串，无堆栈无从归因）
        log("task %s failed [%s] %s: %s\n%s", task.task_id, pub["code"],
            type(exc).__name__, exc, traceback.format_exc())
    else:
        result = batch.to_dict() if hasattr(batch, "to_dict") else batch
        task.mark_completed(result)
        log("task %s completed", task.task_id)


def run_render_worker(task: Task, service, *, log: LogFn | None = None) -> None:
    """后台线程入口（``kind=render``）：渲染成片并更新任务状态。永不抛出。

    渲染目标是**提交时**锁定的结果批（``task.render_batch``），不读会话"最新批"——
    否则用户在渲染排队期间又跑了一次定位就会渲染错批（竞态）。缺失则回退 service
    最近一次 locate 的结果批（与 ``/api/export`` 同口径）。
    """
    if log is None:
        log = lambda *a, **k: None  # noqa: E731
    task.mark_running()
    last_pct = 0
    deb = ProgressDebouncer()   # ③ 防抖（同 analyze；渲染帧率低，防抖是保险）

    def on_progress(ev: ProgressEvent) -> None:
        nonlocal last_pct
        stage, pct = map_progress_stage(ev)
        pct = max(pct, last_pct)
        last_pct = pct
        for st, p, msg in deb.submit(stage, pct, message=ev.message or ""):
            task.update_progress(st, p, message=msg)

    batch = task.render_batch
    if batch is None:
        batch = getattr(service, "last_result_batch", lambda: None)()
    if batch is None:
        task.mark_failed("没有可渲染的结果批（请先完成一次分析）")
        log("task %s failed: no batch to render", task.task_id)
        return
    params = dict(task.render_params or {})
    try:
        info = service.render_movie(
            batch,
            out_dir=params.get("out_dir") or None,
            min_confidence=params.get("min_confidence"),
            low_policy=params.get("low_policy"),
            snap_scenes=params.get("snap_scenes"),
            on_progress=on_progress,
            cancel_token=task.token)
    except ApplicationError as exc:
        if task.token.is_cancelled():
            task.mark_cancelled()
            log("task %s cancelled (render)", task.task_id)
        else:
            pub = public_error(exc)
            task.mark_failed(f"{pub['message']}（{pub['code']}）")
            log("task %s render failed [%s] %s: %s", task.task_id, pub["code"],
                type(exc).__name__, exc)
    except Exception as exc:  # noqa: BLE001 — MediaError 等渲染层错误也转 failed
        if task.token.is_cancelled():
            task.mark_cancelled()
            log("task %s cancelled (render)", task.task_id)
        else:
            pub = public_error(exc)
            task.mark_failed(f"{pub['message']}（{pub['code']}）")
            log("task %s render failed [%s] %s: %s", task.task_id, pub["code"],
                type(exc).__name__, exc)
    except Exception as exc:  # noqa: BLE001 — worker 兜住一切，转为 failed
        pub = public_error(exc)
        task.mark_failed(f"{pub['message']}（{pub['code']}）")
        log("task %s render failed [%s] %s: %s", task.task_id, pub["code"],
            type(exc).__name__, exc)
    else:
        task.mark_completed({"kind": "render", **info})
        log("task %s render completed: %s", task.task_id, info.get("movie_path"))
