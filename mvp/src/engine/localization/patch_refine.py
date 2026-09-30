# -*- coding: utf-8 -*-
"""patch 局部精排（patch refine，2026-09-30 续32 形态6 runtime 化，默认关）。

离线验证：`benchmark/mvp/benchmark/user_case/semantic_signal/
FINDINGS_INSCENE_REFINE_PROBE_20260930.md` 形态6（`probe_patch_local_refine.py`）——
盲区行 4/5 patch 峰落 GT 窗（t3r02c CLS 全盲行 margin 0.115）、对照行 4/4 稳定、
9/9 全量读图确证。用户审计结论：patch「全局融合打分」判负维持，**局部精排形态未被
测过且信号真实**。

机制（top-K 候选各自局部精排再择优，竞品 TopK-DTW + local_refiner 组合形态）：
  1. 每段 5 查询帧（ED 窗）→ 双级特征（CLS + patch token）；
  2. CLS 全库均值检索 → 贪心聚簇（≥3s）取 top-K 候选 + 现主 span；
  3. **歧义门**：top1 簇距现主 ≤2s 且领先第二名 ≥CLS_CLEAR_MARGIN → 跳过
     （明确段不动，控 patch 成本）；
  4. 每候选 ±REFINE_WIN_S @1fps 稠密网格，逐帧
     score = W_GLOBAL·CLS + W_PATCH·patch top-100 均值（查询帧平均）；
  5. 全局最优峰若胜现主局部分 +SWITCH_MARGIN → 主 span 切到峰中心（编辑窗等长），
     老主降为首子 span（宽 span 保全 ⇒ 严格结构性零回退）。

拒识/手动/排除/空主 span 段不碰。开关：``pipeline.patch_refine_enabled``（默认 False）。
feature_version 零变更（不加索引，patch 特征按需现算）。
"""
from __future__ import annotations

import copy
import logging
from dataclasses import replace
from typing import Callable, Sequence

import numpy as np

from domain.models import OriginalSegment, Result, TimeSpan

W_GLOBAL, W_PATCH = 0.45, 0.55          # 竞品字节确证值
N_QUERY = 5                              # 竞品 frame_refine_query_count=5
TOPK_CAND = 4                            # CLS 聚簇候选数（含现主外）
CLUSTER_GAP_S = 3.0
CLS_CLEAR_MARGIN = 0.03                  # 歧义门：top1 领先第二名即视为明确
REFINE_WIN_S = 5.0                       # 候选局部半径（形态6 验证 ±10s 的减半档, 控成本）
REFINE_FPS = 1.0
SWITCH_MARGIN = 0.05                     # 形态4/6 已验证 margin
PATCH_TOPK = 100


def _patch_score(q_patch: np.ndarray, cand_patch: np.ndarray) -> float:
    m = (q_patch @ cand_patch.T).max(axis=1)
    k = min(PATCH_TOPK, len(m))
    return float(np.sort(m)[-k:].mean())


def _clusters(q_cls_mean: np.ndarray, lib_times: np.ndarray, lib_feats: np.ndarray,
              k: int) -> list[float]:
    sims = lib_feats @ q_cls_mean
    order = np.argsort(-sims)
    mids: list[float] = []
    for ti in order:
        t = float(lib_times[ti])
        if all(abs(t - m) >= CLUSTER_GAP_S for m in mids):
            mids.append(t)
            if len(mids) >= k:
                break
    return mids


def apply_patch_refine(results: Sequence[Result], *, edited_path, source_path,
                       grab_frame: Callable, embed_dual: Callable,
                       lib_times: np.ndarray, lib_feats: np.ndarray,
                       log: logging.Logger | None = None) -> list[Result]:
    """对歧义段做 patch 局部精排；其余原样返回。不修改入参对象。"""
    out: list[Result] = []
    n_refine = n_switch = 0
    for r in results:
        if (r.not_in_source or r.manual_override or r.excluded
                or r.original.width <= 0.01 or r.edited.width <= 0.01):
            out.append(r)
            continue
        rs0, rs1 = r.edited.start, r.edited.end
        w = rs1 - rs0
        q_ets = [rs0 + w * (i + 0.5) / N_QUERY for i in range(N_QUERY)]
        q_cls, q_patch = [], []
        for et in q_ets:
            c, pp = embed_dual(grab_frame(edited_path, et))
            q_cls.append(np.asarray(c, dtype=np.float64))
            q_patch.append(np.asarray(pp, dtype=np.float64))
        q_mean = np.mean(q_cls, axis=0)
        q_mean = q_mean / max(1e-8, float(np.linalg.norm(q_mean)))
        cand_mids = _clusters(q_mean, lib_times, lib_feats, TOPK_CAND + 1)
        main_mid = (r.original.start + r.original.end) / 2
        # 歧义门（控 patch 成本，不再整段跳过——t2r06c 型"门误判"防线）：
        # top1 近主且明显领先 → 只精排 [top1, top2, main] 三候选；否则全候选精排。
        gate_clear = False
        if cand_mids and abs(cand_mids[0] - main_mid) <= 2.0:
            s1 = float(np.max(lib_feats[np.argmin(np.abs(lib_times - cand_mids[0]))]
                              @ q_mean))
            s2 = 0.0
            if len(cand_mids) > 1:
                s2 = float(np.max(lib_feats[
                    np.argmin(np.abs(lib_times - cand_mids[1]))] @ q_mean))
            gate_clear = (s1 - s2) >= CLS_CLEAR_MARGIN
        if all(abs(m - main_mid) >= 0.5 for m in cand_mids):
            cand_mids = [main_mid] + cand_mids
        eval_mids = ([cand_mids[0], cand_mids[1] if len(cand_mids) > 1 else None,
                      main_mid] if gate_clear else cand_mids[:TOPK_CAND + 2])
        eval_mids = [m for m in dict.fromkeys(eval_mids) if m is not None]
        best_score, best_mid = -1.0, None
        main_score = None
        for mid in eval_mids:
            g0, g1 = max(0.0, mid - REFINE_WIN_S), mid + REFINE_WIN_S
            n = max(6, int((g1 - g0) * REFINE_FPS))
            grid = [g0 + (g1 - g0) * (i + 0.5) / n for i in range(n)]
            peak_s = -1.0
            for t in grid:
                frame = grab_frame(source_path, t)
                c, pp = embed_dual(frame)
                c = np.asarray(c, dtype=np.float64)
                pp = np.asarray(pp, dtype=np.float64)
                s = (W_GLOBAL * float(np.mean([c @ q for q in q_cls]))
                     + W_PATCH * float(np.mean([_patch_score(qp, pp)
                                                for qp in q_patch])))
                if s > peak_s:
                    peak_s = s
            if abs(mid - main_mid) <= 0.5:
                main_score = peak_s
            if peak_s > best_score:
                best_score, best_mid = peak_s, mid
        n_refine += 1
        if best_mid is None or main_score is None:
            out.append(r)
            continue
        patch_margin = best_score - main_score
        # 序列对位投票 margin（CLS, 独立第二信号；诊断/形态5 已验证形态）
        S_q = np.stack(q_cls) @ lib_feats.T

        def vote_score(mid: float) -> float:
            dm = mid - (rs0 + w / 2)
            vals = []
            for i, et in enumerate(q_ets):
                m = np.abs(lib_times - (et + dm)) <= 1.0
                if m.any():
                    vals.append(float(np.max(S_q[i][m])))
            return float(np.mean(vals)) if vals else 0.0

        seq_margin = vote_score(best_mid) - vote_score(main_mid)
        # 融合判据：patch 强信号单独切；patch 弱信号须序列投票同向互证
        # （形态5 教训：单项低阈值独裁会 churn；形态6：patch 判别力真实）
        switched = (patch_margin >= SWITCH_MARGIN
                    or (patch_margin >= SWITCH_MARGIN / 2 and seq_margin >= 0.05))
        if not switched or abs(best_mid - main_mid) <= 0.5:
            out.append(r)
            continue
        child = replace(
            r, original=TimeSpan(round(best_mid - w / 2, 3),
                                 round(best_mid + w / 2, 3)),
            original_segments=([OriginalSegment(r.original.start,
                                                r.original.end, 0.0)]
                               + copy.deepcopy(r.original_segments)))
        child.result_id = r.result_id + "-pr"
        out.append(child)
        n_switch += 1
    if log is not None and n_refine:
        log.info("patch_refine: refined %d segments, switched %d", n_refine, n_switch)
    return out
