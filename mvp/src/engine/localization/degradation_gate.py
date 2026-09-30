# -*- coding: utf-8 -*-
"""engine.localization.degradation_gate — 退化拒绝门 + 场景覆盖门槛 + 碎片告警。

竞品语义来源（静态逆向，字节确证）：``cutmatch.results.validation`` 的三条硬停条件
「候选为空 / 覆盖不足(``min_scene_coverage=0.2``) / 重复率退化(``max_duplicate_scene_ratio=0.8``)」，
以及 ``exporting.segments.builder`` 的「N 个单帧片段 → 会生成闪烁视频」导出前告警。

我方口径映射（与竞品非同一实现，只借判据形态）：
  - **重复率退化**：本段主 span 被**更强的其它结论**已认领区间的覆盖比例。> 阈值 ⇒ 同一源位置被
    反复交给多个查询 = 退化，本段拒识（不进导出，结果页仍可见并降 LOW）。按置信分降序处理，
    最强认领者存活；被拒者不再认领，避免一处误配级联拉黑全部重叠段。
    ⚠️ 已知误伤面：解说片刻意复用同一源镜头（回闪/ recap/ 前后呼应）会被此门误拒，故默认关。
  - **覆盖不足**：候选子 span（场景/事件扩池产物）的 ``cover`` 低于门槛 ⇒ 丢弃该子 span
    （不给它兜底主定位）。
  - **碎片告警**：导出计划里宽度小于 ``min_clip_s`` 的 clip 计数，只告警不改数据。
  - **重复认领告警**（``duplicate_claim_warnings``，2026-09-29 续31）：同一原片区被多个导出
    clip 指到时提示用户可合并。这是退化判据的**同构安全形态** —— 不做「唯一认领者存活」
    式删答案（该语义在我方架构实测砍正确段），只指出冗余。

全部为纯函数，输入 ``Result`` 列表 / ``ExportClip`` 列表，返回统计字典，便于离线重放 A/B。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from domain import Confidence, ConfidenceLevel


def _union_length(intervals) -> float:
    """区间并集长度（去重）。"""
    total = 0.0
    cur = None
    for s, e in sorted(intervals):
        if e <= s:
            continue
        if cur is None:
            cur = [s, e]
        elif s <= cur[1]:
            cur[1] = max(cur[1], e)
        else:
            total += cur[1] - cur[0]
            cur = [s, e]
    if cur is not None:
        total += cur[1] - cur[0]
    return total


def duplicate_ratio(span: tuple[float, float], others: list[tuple[float, float]]) -> float:
    """``span`` 被 ``others`` 的**并集**覆盖的比例（上限 1.0）。零宽 → 0.0。

    2026-09-29 续31 修正：此前把各段重叠长度**直接相加**，多个邻居彼此又互相重叠时同一片区间
    被重复计数。实测危害落在 2.mkv/test3 的宽 span 上：test3 seg17（源 425-437.6 的 12.6s 场景池
    宽 span，独力承重 t3r04c/t3r05/t3r06a 三条 GT）累加算得 0.92 被误拒，按并集算 <0.8 得以保留
    （分腿复测因此回收 严格 +2 / 场景 +1）。竞品的 ``duplicate_scene_ratio`` 是「比例」语义，
    分子不该重复计数，故并集才是该判据的本意。
    """
    s, e = span
    width = e - s
    if width <= 0:
        return 0.0
    covered = _union_length([(max(s, o_s), min(e, o_e)) for o_s, o_e in others
                             if min(e, o_e) - max(s, o_s) > 0])
    return min(1.0, covered / width)


def duplicate_claim_groups(items, *, min_ratio: float = 0.8,
                           min_width_ratio: float = 0.5) -> list[list[int]]:
    """把「指向原片同一区间」的条目分组成团（并查集传递闭包），只返回 ≥2 成员的团。

    ``items`` 元素需有 ``orig_start``/``orig_end``（导出 clip）或为 ``(start, end)`` 元组。
    判据 = ① 两者重叠 ÷ **较窄**一方宽度 ≥ ``min_ratio``，且 ② 窄/宽 宽度比 ≥
    ``min_width_ratio``。②是 2026-09-29 续31 读图复核后加的：我方输出是「帧级窄 span +
    场景/事件池宽 span」分层并存，宽 span 整个包住窄 span 是常态而非冗余（实测 test3
    第 30/31 段：8s 宽 span 含住 2s 窄 span，读图确认两条各自对应**不同角色不同镜头**、
    都定位正确）。只比宽度相近的认领，才是用户在工程里真能感知的重复素材。
    纯分组、不改数据 —— 与 ``apply_degradation_gate`` 的「唯一认领者存活」语义不同，
    这里不删任何答案，只负责把重复指出来（每查询独立作答口径，见 DECISIONS 续21-E1 纪律）。
    """
    spans = []
    for it in items:
        if isinstance(it, tuple):
            spans.append((float(it[0]), float(it[1])))
        else:
            spans.append((float(it.orig_start), float(it.orig_end)))
    n = len(spans)
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i in range(n):
        a0, a1 = spans[i]
        if a1 - a0 <= 0:
            continue
        for j in range(i + 1, n):
            b0, b1 = spans[j]
            if b1 - b0 <= 0:
                continue
            wa, wb = a1 - a0, b1 - b0
            if min(wa, wb) / max(wa, wb) < min_width_ratio:
                continue
            inter = max(0.0, min(a1, b1) - max(a0, b0))
            if inter / max(1e-6, min(wa, wb)) < min_ratio:
                continue
            ri, rj = find(i), find(j)
            if ri != rj:
                parent[rj] = ri
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return sorted([g for g in groups.values() if len(g) > 1])


def duplicate_claim_warnings(clips, *, min_ratio: float = 0.8,
                             min_width_ratio: float = 0.5,
                             seg_index_attr: str = "seg_index") -> list[str]:
    """导出前「重复认领」告警（竞品 results.validation 退化判据的同构安全形态）。

    退化门按唯一认领**删答案**，在我方镜头级细切分 + 宽窄 span 混排的架构下实测砍掉正确段
    （续19 两腿同开 −14；续31 分腿复测：并集修正后的拒识腿单独 = 严格 −2 / 场景 −1，
    且负例误报一点没降）；本函数只做提示、零数据改动：同一原片区被多个宽度相近的导出
    clip 指到时，告知用户工程里会出现重复素材、可自行合并。
    """
    groups = duplicate_claim_groups(clips, min_ratio=min_ratio,
                                    min_width_ratio=min_width_ratio)
    out = []
    for g in groups:
        segs = sorted({getattr(clips[i], seg_index_attr, i) + 1 for i in g})
        lo = min(clips[i].orig_start for i in g)
        hi = max(clips[i].orig_end for i in g)
        out.append(
            f"LOC-2002 第 {'、'.join(str(s) for s in segs)} 段都指向原片同一区间 "
            f"{lo:.1f}-{hi:.1f}s，导出工程里会出现重复素材；"
            f"若是刻意的画面复用可忽略，否则建议在剪辑软件中合并为一条。")
    return out



def _answerable(r) -> bool:
    """有主 span 且非用户结论的段才受此门管辖。"""
    if r.not_in_source or r.failure_reason or r.excluded or r.manual_override:
        return False
    return r.original.end - r.original.start > 0


@dataclass
class GateStats:
    rejected: list[int] = field(default_factory=list)      # 结果下标（0 基）
    dup_ratios: dict[int, float] = field(default_factory=dict)
    subs_dropped: int = 0
    subs_kept: int = 0

    def as_dict(self) -> dict:
        return {"rejected": list(self.rejected),
                "dup_ratios": {str(k): round(v, 4) for k, v in self.dup_ratios.items()},
                "subs_dropped": self.subs_dropped, "subs_kept": self.subs_kept}


def apply_degradation_gate(results: list, *, enabled: bool,
                           max_duplicate_scene_ratio: float,
                           min_scene_coverage: float,
                           log=None) -> GateStats:
    """就地修改 ``results``：退化段标 ``failure_reason="degenerate_duplicate"`` 并降 LOW，
    低覆盖子 span 丢弃。``enabled=False`` 时零改动（只回空统计）。
    """
    stats = GateStats()
    if not enabled:
        return stats
    spans = [(r.original.start, r.original.end) if _answerable(r) else None for r in results]

    # 1) 覆盖不足：丢弃 cover 低于门槛的子 span
    for r in results:
        if not r.original_segments:
            continue
        keep = []
        for s in r.original_segments:
            if s.cover < min_scene_coverage:
                stats.subs_dropped += 1
            else:
                keep.append(s)
                stats.subs_kept += 1
        if len(keep) != len(r.original_segments):
            r.original_segments = keep

    # 2) 重复率退化：主 span 已被**更强的其它结论**大面积认领 → 本段拒识。
    #    按置信分降序处理（同分按编辑序），最强认领者存活并计入已认领集合，
    #    被拒者不再认领（避免一处误配级联拉黑所有重叠段）。
    order = sorted((i for i, sp in enumerate(spans) if sp is not None),
                   key=lambda i: (-(results[i].confidence.score if results[i].confidence else 0.0),
                                  results[i].edited.start, results[i].edited.end))
    kept: list[tuple[float, float]] = []
    for i in order:
        r = results[i]
        mine = (r.original.start, r.original.end)
        ratio = duplicate_ratio(mine, kept)
        stats.dup_ratios[i] = round(ratio, 4)
        if ratio <= max_duplicate_scene_ratio:
            kept.append(mine)
            continue
        r.failure_reason = "degenerate_duplicate"
        r.confidence = Confidence(ConfidenceLevel.LOW, 0.0,
                                  tuple(r.confidence.reasons) + ("degenerate_duplicate_rejected",))
        stats.rejected.append(i)
        if log is not None:
            log.warning("degradation gate seg=%d ed=%.1f-%.1f dup=%.2f span=%.0f-%.0f -> rejected",
                        i + 1, r.edited.start, r.edited.end, ratio,
                        r.original.start, r.original.end)
    stats.rejected.sort()
    return stats


def fragment_warnings(clips: list, *, min_clip_s: float = 0.15) -> list[str]:
    """导出前碎片告警（竞品 ``segments.builder`` 语义：单帧片段 = 闪烁视频）。

    ``clips`` 元素需有 ``orig_start``/``orig_end``。只告警，不裁剪、不丢弃。
    """
    tiny = [c for c in clips if (c.orig_end - c.orig_start) < min_clip_s]
    if not tiny:
        return []
    return [f"LOC-2001 导出清单中有 {len(tiny)} 个不足 {min_clip_s:.2f} 秒的极短片段，"
            f"导入剪辑软件后可能表现为闪烁或无效素材；建议在这些位置改用完整镜头边界。"]
