# -*- coding: utf-8 -*-
"""段级拆分（shot split，2026-09-30 续32 形态4 runtime 化，默认关）。

离线验证：`benchmark/mvp/benchmark/user_case/semantic_signal/
FINDINGS_INSCENE_REFINE_PROBE_20260930.md` 形态4（`probe_inscene_split_v2.py`）——
四片导出实得 107→115（+8）、严格 130→131（结构性零回退）、FP 4→4 持平；
10 行翻转读图 8 真增益 + 1 真损失（t3r02a，严格由携带的父 span 保住）。

机制：多镜头结果段按编辑窗内切镜（硬切 cos<HARD_CUT + 谷值检测 VALLEY_DEPTH，
学竞品「镜头优先分割」粒度）重排为逐镜子结果；逐镜 span = 父主 span 的 1:1 投影，
当精化（median offset，agree 门）且 margin 门（精化帧均分胜投影 +MARGIN）通过时
采纳精化；**宽 span 保全**：每子段随身携带父主 span + 父子 span 作为子 span ⇒
严格口径（含宽 cov 记账）结构性零回退。单镜段不动；拒识/手动/排除段不碰。

设计约束：零新索引依赖（用既有 1fps IndexBundle 特征）；不改导出/渲染契约
（仍是"每条结果导主 span"，只是结果变多、变准）；feature_version 零变更。
开关：``pipeline.shot_split_enabled``（默认 False）。
"""
from __future__ import annotations

import copy
import logging
import statistics
import uuid
from dataclasses import replace
from typing import Callable, Sequence

import numpy as np

from domain.models import OriginalSegment, Result, TimeSpan

HARD_CUT = 0.55
VALLEY_DEPTH = 0.10
SHOT_FPS = 4.0
SHOT_MAX_FRAMES = 40
WIN_S = 30.0
AGREE_MIN = 0.5
AGREE_TOL_S = 1.5
ALIGN_TOL_S = 1.0
MARGIN = 0.05
MIN_DELTA_S = 0.5


def detect_shots(ets: Sequence[float], embs: Sequence[np.ndarray], *,
                 hard_cut: float = HARD_CUT,
                 valley_depth: float = VALLEY_DEPTH) -> list[tuple[float, float]]:
    """编辑窗采样帧序列按相邻余弦切镜；run<2 帧并入前镜，末镜补齐到窗尾。

    切点 = 相邻帧余弦 < hard_cut（硬切）或为局部极小且低于两侧邻域 valley_depth（软切，
    抓同景内切换）。
    """
    n = len(ets)
    if n < 2:
        return [(ets[0], ets[-1])] if n else []
    cos = [float(embs[i - 1] @ embs[i]) for i in range(1, n)]
    cuts = [0]
    for k, c in enumerate(cos):          # k: 切在第 k+1 帧前
        hard = c < hard_cut
        valley = (0 < k < len(cos) - 1
                  and c < min(cos[k - 1], cos[k + 1]) - valley_depth)
        if hard or valley:
            cuts.append(k + 1)
    cuts.append(n)
    out: list[tuple[float, float]] = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 2 and out:
            out[-1] = (out[-1][0], ets[b - 1])
        elif b - a >= 2:
            out.append((ets[a], ets[b - 1]))
    if out:
        out[-1] = (out[-1][0], ets[-1])
    return out


def _aligned_score(emb: np.ndarray, lib_times: np.ndarray, lib_feats: np.ndarray,
                   pos: float) -> float:
    m = (lib_times >= pos - ALIGN_TOL_S) & (lib_times <= pos + ALIGN_TOL_S)
    return float(np.max(lib_feats[m] @ emb)) if m.any() else 0.0


def split_results(results: Sequence[Result], *, edited_path, grab_frame: Callable,
                  embed: Callable[[np.ndarray], np.ndarray], lib_times: np.ndarray,
                  lib_feats: np.ndarray, log: logging.Logger | None = None
                  ) -> list[Result]:
    """对多镜头结果段做段级拆分；其余结果原样返回。不修改入参对象。"""
    out: list[Result] = []
    n_split = n_refined = 0
    for r in results:
        if (r.not_in_source or r.manual_override or r.excluded
                or r.original.width <= 0.01 or r.edited.width <= 0.01):
            out.append(r)
            continue
        rs0, rs1 = r.edited.start, r.edited.end
        dur = rs1 - rs0
        n = max(2, min(SHOT_MAX_FRAMES, int(dur * SHOT_FPS)))
        ets = [rs0 + dur * (i + 0.5) / n for i in range(n)]
        embs = []
        for et in ets:
            v = np.asarray(embed(grab_frame(edited_path, et)), dtype=np.float64)
            embs.append(v / max(1e-8, float(np.linalg.norm(v))))
        shots = detect_shots(ets, embs)
        if len(shots) < 2:
            out.append(r)
            continue
        cs, ce = r.original.start, r.original.end
        win = (lib_times >= (cs + ce) / 2 - WIN_S) & (lib_times <= (cs + ce) / 2 + WIN_S)
        if not win.any():
            out.append(r)
            continue
        lib_t, lib_f = lib_times[win], lib_feats[win]
        # 镜间边界 = 相邻镜末帧/首帧中点；首镜从 rs0 起、末镜到 rs1 止（无缝分割）
        bounds = [rs0]
        for k in range(len(shots) - 1):
            bounds.append((shots[k][1] + shots[k + 1][0]) / 2)
        bounds.append(rs1)
        # 宽 span 保全：父主 span + 父子 span 随每个子段（严格口径结构性零回退）
        carried = [OriginalSegment(r.original.start, r.original.end, 0.0)]
        carried += copy.deepcopy(r.original_segments)
        for k, (s0, s1) in enumerate(shots):
            shot_ets = [t for t in ets if bounds[k] <= t <= bounds[k + 1]]
            shot_embs = [embs[ets.index(t)] for t in shot_ets]
            proj0 = cs + (bounds[k] - rs0)
            proj1 = cs + (bounds[k + 1] - rs0)
            refined = False
            if len(shot_ets) >= 2:
                offs = []
                for et, emb in zip(shot_ets, shot_embs):
                    j = int(np.argmax(lib_f @ emb))
                    offs.append(float(lib_t[j]) - et)
                med = statistics.median(offs)
                agree = (sum(1 for o in offs if abs(o - med) <= AGREE_TOL_S)
                         / len(offs))
                delta = med - (cs - rs0)
                if agree >= AGREE_MIN and abs(delta) >= MIN_DELTA_S:
                    r0, r1 = proj0 + delta, proj1 + delta
                    s_ref = float(np.mean([
                        _aligned_score(e, lib_t, lib_f,
                                       r0 + (r1 - r0) * (et - s0) / max(1e-9, s1 - s0))
                        for et, e in zip(shot_ets, shot_embs)]))
                    s_proj = float(np.mean([
                        _aligned_score(e, lib_t, lib_f,
                                       proj0 + (proj1 - proj0) * (et - s0)
                                       / max(1e-9, s1 - s0))
                        for et, e in zip(shot_ets, shot_embs)]))
                    if s_ref > s_proj + MARGIN:
                        refined = True
                        proj0, proj1 = r0, r1
            child = replace(
                r, edited=TimeSpan(round(bounds[k], 3), round(bounds[k + 1], 3)),
                original=TimeSpan(round(proj0, 3), round(max(proj1, proj0 + 0.05), 3)),
                original_segments=copy.deepcopy(carried))
            child.result_id = uuid.uuid4().hex
            out.append(child)
            if refined:
                n_refined += 1
        n_split += 1
    if log is not None and n_split:
        log.info("shot_split: split %d segments (%d refined shots), results %d→%d",
                 n_split, n_refined, len(results), len(out))
    return out
