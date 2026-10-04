# -*- coding: utf-8 -*-
"""ISC 第二意见局部重排（isc refine，2026-10-02 续44 立项 runtime 化，默认关）。

立项链：方案B 正交 backbone 探针（`FINDINGS_ORTHOGONAL_BACKBONE_PROBE_20261002.md`）
→ 20 案例 MISS6 5/6 gt>main、6/6 gt_is_peak 过门槛 → 全 139 正例扩验证（核心桶 44/63 vs
dino 37/63、配对 15:8）→ 独家增量 12 例多模态复核 11 干净 + 1 边界 → 用户拍板选项①立项。

机制（扩验证 §9.3 约束的保守形态——**第二意见 tiebreaker，不当主判据**）：
  1. 每段 3 查询帧（ED 窗）→ ISC 256-d（与探针同口径）+ CLS 均值（候选提案复用 patch_refine
     的 ``_clusters``，保证两模块候选同源可比）；
  2. **歧义门**（同 patch_refine 形态）：top1 簇距现主 ≤2s 且 CLS 领先第二名 ≥0.03 → 跳过
     （明确段零 churn——aligned 桶两臂同基线 71/76 的教训）；
  3. 每候选**自身 span±1.5s**（子镜头粒度容差，t2r07b 教训）窗内 1s 步长 ISC 重扫，
     候选分 = 窗内最高余弦（查询帧平均，探针 gt_sc 同口径）；
  4. 切换判据（保守）：最优它选候选领先现主 ≥``pipeline.isc_refine_margin``（默认 0.05）
     → 主 span 切到它选中点（编辑窗等长），老主降为首子 span（宽 span 保全 ⇒ 严格结构性零回退）；
     低于门一律不动（t1r30a/t2r04a「两臂一致错」教训：ISC 会自信地错，绝不能当主判据）。

不创建无中生有的答案（候选来自既有 CLS 簇 + 现主）；拒识/手动/排除/空主 span 段不碰。
开关：``pipeline.isc_refine_enabled``（默认 False——须四片 A/B + 三指标零回退 + MISS6 验收
后由用户拍板再翻）。快速档（``locate(refine=False)``）跳过本模块。feature_version 零变更
（ISC 不进索引，按需现算）。

工程注意（探针 §6 留痕）：ISC ONNX 的 DML 授权可行（gem 已重写 ReduceMean）；但**任何其它
模型 DML 授权失败会污染进程** ⇒ 本模块 session 构建只许成功或整体跳过，禁止先试 DML 再回退
的失败路径留在主进程。
"""
from __future__ import annotations

import copy
import logging
import os
from dataclasses import replace
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from domain.models import OriginalSegment, Result, TimeSpan
from engine.localization.patch_refine import CLS_CLEAR_MARGIN, _clusters

N_QUERY = 3                              # 探针同口径（patch_refine 用 5）
TOPK_CAND = 4                            # 候选簇数（含现主外），与 patch_refine 同
ISC_TOL_S = 1.5                          # 候选评分窗 = span±1.5s（子镜头粒度容差）
ISC_STEP = 1.0                           # 重扫步长（探针同）
ISC_INPUT_SIZE = 512                     # isc_ft_v107 训练输入
ISC_MEAN = (0.5, 0.5, 0.5)               # timm tf_efficientnetv2_m.in21k_ft_in1k default_cfg
ISC_STD = (0.5, 0.5, 0.5)
SWITCH_MARGIN_DEFAULT = 0.05             # 扩验证 §9.3：margin 绝对门
# —— v2 宽幅扫描（2026-10-03 续45：候选提案放宽；CLS 真盲 ⇒ 聚簇提案救不到 p20/p34 型）——
WIDE_COARSE_STEP = 2.0                   # 粗扫步长（2s：GT 窗 avg 2.7-8s ⇒ 至少 1 个采样点）
WIDE_TOPK = 3                            # 取 top-3 粗峰细化
WIDE_REFINE_S = 2.0                      # 每粗峰 ±2s @1s 细化
WIDE_EXCLUDE_S = 2.0                     # 距现主/已有候选 ≤2s 的粗峰不重复采纳


def resolve_isc_onnx(explicit: str | Path | None = None) -> str | None:
    """ISC ONNX 解析：显式 → env ``SVL_ISC_ONNX`` → repo work 研究资产（parents[4]，
    与 ``resolve_patch_onnx`` 同构；``.onnx.data`` 必须同目录）。找不到返回 None。"""
    if explicit and Path(explicit).exists():
        return str(explicit)
    env = os.environ.get("SVL_ISC_ONNX")
    if env and Path(env).exists():
        return env
    cand = (Path(__file__).resolve().parents[4] / "work" / "isc21_weights_ortho_probe"
            / "isc_ft_v107.onnx")
    if cand.exists():
        return str(cand)
    return None


class IscScorer:
    """ISC21 `isc_ft_v107` ONNX 推理封装（DirectML 优先）。

    ``ensure()`` False = 资产缺失/会话失败，调用方整体跳过（不回退、不重试——探针 §6①：
    DML 失败路径会污染进程）。CPU 回退仅当 ORT 显式只给出 CPU provider（GPU-first 留痕）。
    """

    def __init__(self, onnx_path: str | Path | None = None,
                 dml_device_id: int = 0):
        self._explicit = onnx_path
        self._device_id = dml_device_id
        self._session = None
        self.device = "uninitialized"

    def ensure(self) -> bool:
        if self._session is not None:
            return True
        path = resolve_isc_onnx(self._explicit)
        if not path:
            return False
        import onnxruntime as ort

        opts = [("DmlExecutionProvider", {"device_id": self._device_id}),
                "CPUExecutionProvider"]
        self._session = ort.InferenceSession(path, providers=opts)
        prov = self._session.get_providers()
        self.device = "dml" if prov[0] == "DmlExecutionProvider" else "cpu"
        return True

    def embed(self, frame_bgr) -> np.ndarray:
        import cv2

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        rgb = cv2.resize(rgb, (ISC_INPUT_SIZE, ISC_INPUT_SIZE),
                         interpolation=cv2.INTER_CUBIC)
        x = (rgb.astype(np.float32) / 255.0 - np.asarray(ISC_MEAN, np.float32)) \
            / np.asarray(ISC_STD, np.float32)
        inp = np.ascontiguousarray(x.transpose(2, 0, 1)[None])
        y = self._session.run(["emb"], {"input": inp})[0][0].astype(np.float32)
        n = float(np.linalg.norm(y))
        return y / n if n > 1e-8 else y


def apply_isc_refine(results: Sequence[Result], *, edited_path, source_path,
                     grab_frame: Callable, embed_isc: Callable,
                     embed_cls: Callable, lib_times: np.ndarray,
                     lib_feats: np.ndarray, margin: float = SWITCH_MARGIN_DEFAULT,
                     scan_radius_s: float = 0.0, ladder_s: float = 0.0,
                     log: logging.Logger | None = None,
                     grab_frames: Callable | None = None,
                     grab_grid: Callable | None = None,
                     l2_index: tuple[np.ndarray, np.ndarray] | None = None,
                     progress: Callable[[int, int], None] | None = None) -> list[Result]:
    """对歧义段做 ISC 第二意见局部重排；其余原样返回。不修改入参对象。

    ``grab_grid(path, times) -> {t: frame}``（可选，2026-10-03 续50 接线）：网格抽取抓帧
    （select 抽帧，管道量 ÷~30）。**只用在宽扫粗扫**（``coarse_ts`` 本就是 2s 均匀网格）；
    候选窗/细化窗的相位非网格对齐，继续走 ``grab_frames`` 以免选帧偏移。缺省 = 全走旧路径。


    ``embed_isc(frame) -> np.ndarray(256,)``（L2）；``embed_cls(frame) -> np.ndarray``
    （现役 CLS，用于候选提案与歧义门）。``grab_frames``/``progress`` 语义与
    ``apply_patch_refine`` 相同（批量抓帧先并行、embed 串行；逐段进度回调）。

    v2 宽幅扫描（``scan_radius_s`` > 0，2026-10-03 续45）：以现主为中心 ±radius 粗扫
    （``WIDE_COARSE_STEP``）→ top-3 粗峰各 ±``WIDE_REFINE_S`` 细化 → 峰作为虚拟候选进
    同一 margin 门。动机：聚簇提案来自 CLS，CLS 真盲案例（p20/p34，GT 区 rank 286+）
    的候选集里根本没有 GT ⇒ 第二意见视野被第一意见框死（续44 验收实证）。宽扫对
    **所有**合格段生效（歧义门只保护聚簇路径）——margin 门是唯一裁决，aligned 桶的
    churn 风险由「先粗后细 + margin>0.05 + 距主 ≥2s」三重约束控制。成本 ≈
    (2·radius/2 + 3×5 + 5×8) embeds/段，radius=90 时 ~150 embeds/段（DML ~8s）。
    """
    def _grab_many(path, times):
        times = list(times)
        if grab_frames is not None:
            return grab_frames(path, times)
        return [grab_frame(path, t) for t in times]

    out: list[Result] = []
    n_refine = n_switch = 0
    n_total = len(results)
    for i_r, r in enumerate(results, start=1):
        if progress is not None:
            progress(i_r, n_total)
        if (r.not_in_source or r.manual_override or r.excluded
                or r.original.width <= 0.01 or r.edited.width <= 0.01):
            out.append(r)
            continue
        rs0, rs1 = r.edited.start, r.edited.end
        w = rs1 - rs0
        q_ets = [rs0 + w * (i + 0.5) / N_QUERY for i in range(N_QUERY)]
        q_isc, q_cls = [], []
        for frame in _grab_many(edited_path, q_ets):
            q_isc.append(np.asarray(embed_isc(frame), dtype=np.float64))
            q_cls.append(np.asarray(embed_cls(frame), dtype=np.float64))
        q_mean = np.mean(q_cls, axis=0)
        q_mean = q_mean / max(1e-8, float(np.linalg.norm(q_mean)))
        main_mid = (r.original.start + r.original.end) / 2
        cand_mids = _clusters(q_mean, lib_times, lib_feats, TOPK_CAND + 1)
        # 歧义门（同 patch_refine 形态）：top1 近主且明显领先 → 明确段，零 churn 跳过。
        # v2：宽扫开启时门只保护聚簇路径（宽扫仍跑）——p20 型 gate_clear+CLS 真盲段。
        gate_clear = False
        if cand_mids and abs(cand_mids[0] - main_mid) <= 2.0:
            i1 = int(np.argmin(np.abs(lib_times - cand_mids[0])))
            s1 = float(np.max(lib_feats[i1] @ q_mean))
            s2 = 0.0
            if len(cand_mids) > 1:
                i2 = int(np.argmin(np.abs(lib_times - cand_mids[1])))
                s2 = float(np.max(lib_feats[i2] @ q_mean))
            gate_clear = (s1 - s2) >= CLS_CLEAR_MARGIN
        if gate_clear and scan_radius_s <= 0:
            out.append(r)
            continue
        if gate_clear:
            cand_mids = [main_mid]
        elif all(abs(m - main_mid) >= 0.5 for m in cand_mids):
            cand_mids = [main_mid] + cand_mids
        eval_mids = list(dict.fromkeys(cand_mids))[:TOPK_CAND + 2]
        if not any(abs(m - main_mid) <= 0.5 for m in eval_mids):
            eval_mids = [main_mid] + eval_mids[:TOPK_CAND + 1]

        # 逐候选：自身 span±tol 窗 1s 网格 ISC 重扫（跨候选共享帧缓存）
        cache: dict[float, np.ndarray] = {}

        def _embed_missing(ts):
            miss = [t for t in ts if t not in cache]
            if miss:
                for t, frame in zip(miss, _grab_many(source_path, miss)):
                    cache[t] = np.asarray(embed_isc(frame), dtype=np.float64)

        def _embed_missing_grid(ts):
            """粗扫专用：网格抽取抓帧（带洞安全——grab_grid_times 抽的是超集，仍按 first_ge 配对）。"""
            miss = [t for t in ts if t not in cache]
            if not miss:
                return
            if grab_grid is None:
                _embed_missing(miss)
                return
            got = grab_grid(source_path, miss)
            for t in miss:
                fr = got.get(float(t))
                if fr is None:                       # 超集未覆盖（超片尾/解码失败）→ 逐帧回退
                    fr = _grab_many(source_path, [t])[0]
                cache[t] = np.asarray(embed_isc(fr), dtype=np.float64)

        def _score_mid(mid: float) -> float:
            lo = max(0.0, mid - w / 2 - ISC_TOL_S)
            hi = mid + w / 2 + ISC_TOL_S
            n = max(2, int(np.ceil((hi - lo) / ISC_STEP)))
            ts = sorted({round(lo + (hi - lo) * (i + 0.5) / n, 3) for i in range(n)})
            _embed_missing(ts)
            return max(float(np.mean([cache[t] @ q for q in q_isc])) for t in ts)

        # v2 宽幅扫描（续45）：±radius 粗扫 → top-3 粗峰细化 → 虚拟候选。
        # v3 阶梯（2026-10-03 续48，``ladder_s`` > 0）：先 ±ladder_s 内圈，阶段内已有峰过
        # margin 门即收工，否则扩展到 ±scan_radius_s 外圈——p20 型（7s）一阶段命中、
        # p34 型（82s）内圈无过门峰必触发扩展 ⇒ radius90 能救的阶梯全救，多数段省外圈粗扫。
        # 注意：多峰过门时选峰与全域扫可能不同 ⇒ 行为变更，须四片回归（门槛同续45）。
        wide_mids: list[float] = []
        if scan_radius_s > 0:
            def _s(t: float) -> float:
                return float(np.mean([cache[t] @ q for q in q_isc]))

            def _refine_topk(coarse_ts, taken):
                picked = []
                coarse_sorted = sorted(coarse_ts, key=_s, reverse=True)
                for t0 in coarse_sorted:
                    if len(picked) >= WIDE_TOPK:
                        break
                    if any(abs(t0 - m) <= WIDE_EXCLUDE_S for m in taken):
                        continue
                    rlo, rhi = max(0.0, t0 - WIDE_REFINE_S), t0 + WIDE_REFINE_S
                    n_f = max(2, int(np.ceil((rhi - rlo) / ISC_STEP)))
                    fine_ts = sorted({round(rlo + (rhi - rlo) * (i + 0.5) / n_f, 3)
                                      for i in range(n_f)})
                    _embed_missing(fine_ts)
                    best_t = max(fine_ts, key=_s)
                    picked.append(best_t)
                    taken.append(best_t)
                return picked

            stages = [scan_radius_s]
            if 0 < ladder_s < scan_radius_s and l2_index is None:
                stages = [ladder_s, scan_radius_s]
            # L2 源片索引宽扫（2026-10-04 续52 接线，形态 B）：粗排 = 索引 matmul（1s 特征表
            # × q_isc 均值分，零抓帧零嵌入），top-WIDE_TOPK 峰仍走真帧 ±WIDE_REFINE_S 细化
            # （_embed_missing/_s 与现役完全同一路径）——行为变更面收在「粗排怎么排序」一处。
            # 索引取帧 = truepts first_ge（与扫描侧 grab_frame 同帧，续52-C 双时间系统对齐）。
            # ladder 与 L2 互斥（ladder 的「阶段门」依赖粗扫抓帧成本，L2 下粗排近零价无意义）。
            if l2_index is not None:
                idx_t, idx_f = l2_index
                m = np.abs(idx_t - main_mid) <= scan_radius_s
                it_, if_ = np.asarray(idx_t)[m], np.asarray(idx_f, dtype=np.float64)[m]
                if it_.size:
                    Q = np.stack([np.asarray(q, dtype=np.float64) for q in q_isc], axis=1)
                    s_idx = (if_ @ Q).mean(axis=1)
                    taken = [main_mid] + list(eval_mids) + list(wide_mids)
                    order = np.argsort(-s_idx)
                    picked = []
                    for k in order:
                        if len(picked) >= WIDE_TOPK:
                            break
                        t0 = float(it_[k])
                        if any(abs(t0 - mm) <= WIDE_EXCLUDE_S for mm in taken):
                            continue
                        rlo, rhi = max(0.0, t0 - WIDE_REFINE_S), t0 + WIDE_REFINE_S
                        n_f = max(2, int(np.ceil((rhi - rlo) / ISC_STEP)))
                        fine_ts = sorted({round(rlo + (rhi - rlo) * (i + 0.5) / n_f, 3)
                                          for i in range(n_f)})
                        _embed_missing(fine_ts)
                        best_t = max(fine_ts, key=_s)
                        picked.append(best_t)
                        taken.append(best_t)
                    wide_mids.extend(picked)
            else:
                # 主定位分提前算（阶梯阶段门要用；_score_mid 走缓存，最终 scores 复算同值）
                main_key = min(eval_mids, key=lambda m: abs(m - main_mid))
                main_score_early = _score_mid(main_key)
                scanned_r = 0.0
                for R in stages:
                    wlo = max(0.0, main_mid - R)
                    whi = main_mid + R
                    n_c = max(2, int(np.ceil((whi - wlo) / WIDE_COARSE_STEP)) + 1)
                    coarse_ts = [round(wlo + (whi - wlo) * i / (n_c - 1), 3) for i in range(n_c)]
                    coarse_ts = [t for t in coarse_ts if abs(t - main_mid) > scanned_r + 1e-6]
                    _embed_missing_grid(coarse_ts)
                    taken = [main_mid] + list(eval_mids) + list(wide_mids)
                    stage_picked = _refine_topk(coarse_ts, taken)
                    wide_mids.extend(stage_picked)
                    scanned_r = R
                    if (ladder_s > 0 and stage_picked
                            and any(_score_mid(m) - main_score_early >= margin
                                    for m in stage_picked)):
                        break  # 内圈已有过门峰 ⇒ 不扩展外圈
        eval_mids = eval_mids + [m for m in wide_mids if m not in eval_mids]

        scores = {m: _score_mid(m) for m in eval_mids}
        main_key = min(eval_mids, key=lambda m: abs(m - main_mid))
        main_score = scores[main_key]
        others = [(s, m) for m, s in scores.items() if abs(m - main_mid) > 0.5]
        n_refine += 1
        if not others or main_score is None:
            out.append(r)
            continue
        best_score, best_mid = max(others, key=lambda x: (x[0], -x[1]))
        if best_score - main_score < margin:
            out.append(r)
            continue
        child = replace(
            r, original=TimeSpan(round(best_mid - w / 2, 3),
                                 round(best_mid + w / 2, 3)),
            original_segments=([OriginalSegment(r.original.start,
                                                r.original.end, 0.0)]
                               + copy.deepcopy(r.original_segments)))
        child.result_id = r.result_id + ("-iscw" if best_mid in wide_mids else "-isc")
        out.append(child)
        n_switch += 1
    if log is not None and n_refine:
        log.info("isc_refine: refined %d segments, switched %d", n_refine, n_switch)
    return out
