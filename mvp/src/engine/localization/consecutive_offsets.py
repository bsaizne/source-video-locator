"""consecutive_offsets — 连续重复起点修正（竞品 ``resolve_consecutive_scene_offsets`` 语义重建）。

**竞品语义（docstring 确证, FINDINGS_DOCSTRING_BREAKTHROUGH §1b）**：「时间线连续偏移：修正
连续命中同一源镜头时重复使用起始帧的问题」；重复容差 1.0s = 字节确证常量；``_fits_source_range``
= 修正后的起点+时长不得超过源范围；修正留痕字段 ``source_offset_resolved_shift``。

**我方形态（推断级 = 语义重建，非其代码流复刻）**：按编辑序遍历结果，相邻已定位对 (a, b) 若
``|b.start - a.start| <= dup_tol_s``（同一起点被两段复用）⇒ 把 b 主 span 后移 ``b.start = a.end``
（宽度保持）。b 为手动段则跳过（不动用户数据）；平移后超出源时长则放弃（宁不动不越界）。
a 可为手动段（视为已确认锚点）。只移主 span，不碰 confidence/子 span/alternatives。

**影响面预统计（2026-09-28 E1 实施前, work/voteprior_*.results.json）**：四片仅 7 对相邻重复起点
（2mkv/test1=0），其中多对疑似合法「同素材复用/相邻切片」⇒ 本模块价值须由双臂实测+逐图裁决定，
不得凭机制存在而默认开。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Sequence

_EPS = 1e-6


@dataclass
class ConsecutiveResolveStats:
    shifted: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)


def _span_of(r: Any):
    return getattr(r, "original", None)


def _is_manual(r: Any) -> bool:
    return bool(getattr(r, "manual_override", False)) or \
        getattr(r, "source", "auto") == "manual"


def resolve_consecutive_offsets(
    results: Sequence[Any],
    *,
    dup_tol_s: float = 1.0,
    source_duration_s: float | None = None,
) -> ConsecutiveResolveStats:
    """就地修正 results（域对象需 ``original.start/end`` 可写）；返回移位数与跳过留痕。"""
    stats = ConsecutiveResolveStats()
    prev: Any = None
    for idx, r in enumerate(results):
        if getattr(r, "failure_reason", None) or getattr(r, "not_in_source", False):
            continue  # 未定位/非源片段不认领起点，也不打断"连续"判定
        span = _span_of(r)
        if span is None or span.end - span.start <= _EPS:
            continue
        pspan = _span_of(prev) if prev is not None else None
        if pspan is not None and abs(span.start - pspan.start) <= dup_tol_s:
            new_start = pspan.end
            new_end = new_start + (span.end - span.start)
            if _is_manual(r):
                stats.skipped.append({"index": idx, "reason": "manual",
                                      "start": span.start})
            elif new_start <= span.start + _EPS:
                # a 的终点不晚于 b 的起点：b 本就在 a 之后，非"重复使用起点"形态
                pass
            elif source_duration_s is not None and new_end > source_duration_s + _EPS:
                stats.skipped.append({"index": idx, "reason": "exceeds_source_range",
                                      "start": span.start, "to_end": new_end})
            else:
                stats.shifted.append({"index": idx,
                                      "from": [span.start, span.end],
                                      "to": [new_start, new_end]})
                r.original = type(span)(new_start, new_end)
        prev = r
    return stats
