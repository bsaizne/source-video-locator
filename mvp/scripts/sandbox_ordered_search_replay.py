# -*- coding: utf-8 -*-
"""ordered_search M0 离线复现沙盒（2026-09-29 续27, E 层 ordered_search 单独立项令）。

竞品机制（blob D#173 docstring 八句 + options#68 十四键**字节确证**）：
  「按已确认原片位置增量向后检索，并只回退到未搜索区间」/「从上一段结尾向后增量扫描,
  每个候选起点只归属一个区间」/「只扫描指定的候选起点区间, 同时读取到片段末尾所需的
  上下文」/「合并多区间候选并按原片起点去重」/「粗分数近似排序, 分块合并稳定顺序」/
  「只补搜顺序搜索未覆盖的后段和前段」/「只在局部证据、采样支持和候选间隔都可靠时
  接受顺序结果」/「从可靠递增匹配中自动识别主线, 并在重排时解除锁定」。

参数（cutmatch.matching.fast_timeline.options#68, 全 14 键确证值）：
  enabled=True window=300 max=1800 chunk=315 expand=900 backtrack=15 context=2
  candidate_count=3 candidate_margin=0.03 coarse_min_score=0.55
  coarse_min_support_ratio=0.35 refined_min_score=0.62 consistency_min_score=0.55
  lock_segments=3

**推断级口径**（复现=我方已存特征矩阵上的重建, 非竞品实测; 已知近似）：
  - 竞品源索引 1fps, 我方 0.5fps（2s 网格）——候选起点只能在 2s 网格上取。
  - ED 密帧 8fps 缓存降采样 3fps（与 fast_global 同款近似）。
  - chunk/expand/window 的 I/O 分块语义在整矩阵离线复现下只保留**搜索区间**含义。
  - refined = top-1 起点上做 ±2s 路径对齐重算均值；consistency = 锁定期望起点单调
    增量（重叠由 backtrack 15s 容忍）——两者为 docstring 语义的工程重建。
  - 全局兜底 = 全片 coarse/refined 双门（竞品「只补搜未覆盖前/后段」的近似）。

章程门（对照 fast_global M0 先例）：arm_full 的 **main-span 截等长口径 ≥ 基线截等长 +8**
且逐 ID 净改善为正 ⇒ 申请 M1 进 runtime 双臂；否则负结果归档、通道关闭。

臂：full（全门+主线锁）/ nolock（全门无锁）/ raw（窗内 argmax, 无接受门）——
raw 用于判「门的贡献」，nolock 判「锁的贡献」。

产物: work/ordered_search_{case}.results.json + work/ordered_search_replay.json

运行（须 venv python; GPU 任务不在此脚本内——纯 numpy 秒级探针允许 CPU）：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/sandbox_ordered_search_replay.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
for p in (BENCH / "mvp" / "src", BENCH / "mvp" / "scripts", BENCH / "mvp"):
    sys.path.insert(0, str(p))

import numpy as np  # noqa: E402

from infrastructure.config import load_config  # noqa: E402
from measure_shot_recall import evaluate  # noqa: E402
from measure_mainspan_caliber import truncate_main  # noqa: E402
from rerun_fast_global import CASES  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402

# ---- 竞品确证参数（options#68） ------------------------------------------------ #
P = dict(window=300.0, max=1800.0, backtrack=15.0, context=2.0,
         cand_k=3, margin=0.03, coarse_min=0.55, support_min=0.35,
         refined_min=0.62, consistency_min=0.55, lock_segs=3)

GT = {"2mkv": "datasets/real/ground_truth_v4.json",
      "test1": "datasets/real/ground_truth_test1.json",
      "test2": "datasets/real/ground_truth_test2.json",
      "test3": "datasets/real/ground_truth_test3.json"}
BASE_PATTERN = "work/fastglobal_default_{case}.results.json"


def best_matrix(ed_f, src_f):
    return np.maximum(ed_f @ src_f.T, 0.0)  # [M, N] 逐帧最佳相似度


def row_window_max(S, lo, hi):
    """每行在列区间 [lo,hi) 的最大值与 argmax。lo/hi 为标量列号。"""
    sub = S[:, lo:hi]
    if sub.shape[1] == 0:
        return np.full(sub.shape[0], -1.0), np.zeros(sub.shape[0], dtype=int)
    return sub.max(axis=1), sub.argmax(axis=1)


def score_starts(S, cols, grid_lo, grid_hi, span_cols):
    """候选起点（列号数组）→ coarse/support/refined。"""
    out = []
    for c in cols:
        lo = max(0, int(c))
        hi = min(S.shape[1], int(c) + span_cols + 1)
        if hi - lo < max(2, span_cols // 3):
            out.append((-1.0, -1.0, -1.0))
            continue
        bv, _ = row_window_max(S, lo, hi)
        coarse = float(bv.mean())
        support = float((bv >= P["coarse_min"]).mean())
        # refined：每行 argmax 收敛到 top-1 路径 ±2s（源 0.5fps → ±1 列）后再均值
        sub = S[:, lo:hi]
        am = sub.argmax(axis=1)
        med = int(np.median(am))
        r_lo, r_hi = lo + max(0, med - 1), lo + min(sub.shape[1], med + 2)
        rv, _ = row_window_max(S, r_lo, r_hi)
        refined = float(rv.mean())
        out.append((coarse, support, refined))
    return np.array(out)


def parabola_offset(a, b, c, step_s):
    """三点抛物线顶点偏移（修 2s 网格量化）；退化/非凸 → 0。"""
    den = a - 2 * b + c
    if abs(den) < 1e-9:
        return 0.0
    off = 0.5 * (a - c) / den
    return float(np.clip(off, -1.0, 1.0)) * step_s


def ordered_search(S, src_times, ed_segs, *, arm: str):
    """返回 placements: list[(start, end, trace)]，None=未定位。ed_segs:
    [(row_lo, row_hi, seg_dur)] 按 ED 时间序，行区间索引进 S。"""
    n = len(src_times)
    step_s = float(src_times[1] - src_times[0]) if n > 1 else 2.0
    src_dur = float(src_times[-1]) + step_s
    prev_start = None
    prev_len = 0.0
    consec = 0
    locked = False
    placements, traces = [], []

    for i, (rlo, rhi, dur, _ed_lo, _ed_hi) in enumerate(ed_segs):
        Si = S[rlo:rhi]
        span_cols = max(1, int(round(dur / step_s)))
        all_cols = np.arange(max(0, 0), max(0, n - span_cols))
        if all_cols.size == 0:
            placements.append(None); traces.append({"i": i, "why": "src_too_short"}); continue

        def search(cols):
            sc = score_starts(Si, cols, 0, n, span_cols)
            rows = np.argsort(-sc[:, 0])[:min(P["cand_k"], cols.size)]
            best = sc[:, 0].max()
            outside = sc[:, 0][sc[:, 0] < best - P["margin"]]
            margin = float(best - outside.max()) if outside.size else 1.0
            # 选择=coarse argmax（第二判读轮）。第一轮「簇内最早」带 +0.03 平带左偏
            # 系统性 −2~4s 起点（回退 11 ID 全部同向, 09-29 根因分解），弃用。
            return [(int(cols[r]), sc[r]) for r in rows], margin

        accepted = None
        trace = {"i": i, "dur": round(dur, 2)}

        # ---- 轮4/5 臂：全片搜索 + （可选）亚网格细化；rr=+主线连续性带内重排 ----
        if arm in ("interp", "rr", "argmax_g", "rrnop"):
            sc_all = score_starts(Si, all_cols, 0, n, span_cols)
            best = float(sc_all[:, 0].max())
            sel = int(np.argmax(sc_all[:, 0]))
            chose = "argmax"
            if arm in ("rr", "rrnop") and prev_start is not None:
                band = np.where(sc_all[:, 0] >= best - P["margin"])[0]
                mono = band[src_times[band] >= prev_start - 1e-6]
                if mono.size:
                    target = prev_start + prev_len  # 增量续接点
                    sel = int(mono[int(np.argmin(np.abs(src_times[mono] - target)))])
                    chose = "band_cont"
            sco = sc_all[sel]
            if not (sco[0] >= P["coarse_min"] and sco[1] >= P["support_min"]
                    and sco[2] >= P["refined_min"]):
                placements.append(None)
                trace["why"] = "gates_rejected"
                traces.append(trace)
                prev_start = None
                continue
            off = 0.0
            if arm in ("interp", "rr"):  # 亚网格抛物线细化（仅这两个臂开启）
                a_l = float(sc_all[sel - 1, 0]) if sel > 0 else -1.0
                a_r = float(sc_all[sel + 1, 0]) if sel + 1 < sc_all.shape[0] else -1.0
                off = parabola_offset(a_l, float(sco[0]), a_r, step_s)
            s_t = max(0.0, float(src_times[sel]) + off)
            e_t = min(src_dur, s_t + dur)
            placements.append((s_t, e_t))
            prev_start, prev_len = s_t, dur
            trace.update(start=round(s_t, 2), coarse=round(float(sco[0]), 3),
                         offset=round(off, 2), chose=chose)
            traces.append(trace)
            continue
        regions = []
        if prev_start is None or arm == "raw":
            regions.append(("global", all_cols))
        else:
            pe = prev_start + prev_len  # 上一段结尾（竞品：从上一段结尾向后增量）
            for r in (P["window"], 900.0, P["max"]):
                lo = max(0.0, pe - P["backtrack"])
                hi = min(src_dur, pe + r)
                cols = all_cols[(src_times[all_cols] >= lo) & (src_times[all_cols] <= hi - dur)]
                if cols.size:
                    regions.append((f"w{int(r)}", cols))
            # 竞品：顺序失败后「只补搜未覆盖前段」= 全片兜底
            regions.append(("fallback", all_cols))

        for tag, cols in regions:
            cands, margin = search(cols)
            if not cands:
                continue
            c, sco = cands[0]
            if arm == "raw":
                accepted = (c, float(sco[0]), tag)
                break
            gates_ok = (sco[0] >= P["coarse_min"] and sco[1] >= P["support_min"]
                        and sco[2] >= P["refined_min"])
            s_t = float(src_times[c])
            if gates_ok and prev_start is not None and locked and arm != "nolock":
                if s_t < prev_start - P["backtrack"] + 1e-6:
                    gates_ok = False
                    trace.setdefault("rejected_monotonic", []).append(s_t)
            if gates_ok:
                accepted = (c, float(sco[0]), tag)
                break
        if accepted is None:
            placements.append(None)
            trace["why"] = "all_regions_rejected"
            traces.append(trace)
            prev_start = None; consec = 0; locked = False
            continue
        c, sco, tag = accepted
        s_t = float(src_times[c])
        e_t = min(src_dur, s_t + dur)
        if prev_start is not None and s_t >= prev_start - 1e-6:
            consec += 1
        else:
            consec = 1 if prev_start is None else 0
        if arm != "nolock" and consec >= P["lock_segs"]:
            locked = True
        trace.update(start=round(s_t, 1), coarse=round(float(sco), 3), region=tag,
                     consec=consec, locked=locked)
        placements.append((s_t, e_t))
        prev_start = s_t
        prev_len = dur
        traces.append(trace)
    return placements, traces


def build_results(placements, ed_segs, src_times):
    n = len(src_times)
    step_s = float(src_times[1] - src_times[0])
    src_dur = float(src_times[-1]) + step_s
    res = []
    for (rlo, rhi, dur_ed, ed_lo, ed_hi), pl in zip(ed_segs, placements):
        if pl is None:
            span = {"candidate_start": src_dur / 2, "candidate_end": src_dur / 2 + 0.01}
            nis = True
        else:
            span = {"candidate_start": pl[0], "candidate_end": pl[1]}
            nis = False
        res.append({
            "edited_segment": {"start": ed_lo, "end": ed_hi},
            "original": dict(span),
            "original_segments": [],
            "alternatives": [],
            "confidence": "LOW" if nis else "MEDIUM",
            "not_in_source": bool(nis),
        })
    return {"schema_version": 1, "results": res}


def main() -> int:
    srv = SourceLocatorService(config=load_config())
    report = {"params": P, "cases": {}}
    for name in ("2mkv", "test1", "test2", "test3"):
        t0 = time.monotonic()
        paths = CASES[name]
        bundle = srv.store.load_index(paths["original"])
        shots = srv.analyze_edited_video(paths["edited"])
        src_times = np.asarray(bundle.times, dtype=np.float64)
        # ED 全片 3fps 密帧拼接（行区间记录每段起止行）
        ed_rows, ed_meta = [], []
        dense_fps = float(srv.config.pipeline.seq_align.edit_fps)
        step = max(1, int(round(dense_fps / 3.0)))
        for sh in sorted(shots, key=lambda x: x.span.start):
            d = srv._embed_dense_query(sh, Path(paths["edited"]))
            if d is None:
                continue
            f = np.asarray(d[0])[::step]
            if f.shape[0] == 0:
                continue
            ed_rows.append(f)
            ed_meta.append((sh.span.start, sh.span.end))
        ED = np.vstack(ed_rows)
        S = np.maximum(ED @ bundle.features.T, 0.0)
        cursor = 0
        segs = []
        for (ed_lo, ed_hi), f in zip(ed_meta, ed_rows):
            segs.append((cursor, cursor + f.shape[0], ed_hi - ed_lo, ed_lo, ed_hi))
            cursor += f.shape[0]
        case_out = {"segments": len(segs), "arms": {}}
        gt = json.loads((BENCH / GT[name]).read_text(encoding="utf-8"))
        # 基线截等长（同 arm 形态对照：main-span only）
        base_full = json.loads((BENCH / BASE_PATTERN.format(case=name)).read_text(encoding="utf-8"))
        base_tr = truncate_main(base_full)
        r_base = evaluate(gt, base_tr["results"], label=f"{name}_baseline_trunc")
        case_out["baseline_trunc"] = {"strict": r_base["strict_hit"], "n": r_base["n_pos"],
                                      "scene": r_base["scene_hit"], "fp": r_base["fp"]}
        base_marks = {row["id"]: row["mark"] for row in r_base["per_pos"]}
        for arm in ("raw", "argmax_g", "rrnop", "rr"):
            pls, traces = ordered_search(S, src_times, segs, arm=arm)
            res = build_results(pls, segs, src_times)
            out = BENCH / "work" / f"ordered_search_{name}_{arm}.results.json"
            out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
            r = evaluate(gt, res["results"], label=f"{name}_ordered_{arm}")
            flips = {row["id"]: [base_marks.get(row["id"]), row["mark"]]
                     for row in r["per_pos"] if base_marks.get(row["id"]) != row["mark"]}
            up = sum(1 for a, b in flips.values() if a != "HIT" and b == "HIT")
            dn = sum(1 for a, b in flips.values() if a == "HIT" and b != "HIT")
            case_out["arms"][arm] = {
                "strict": r["strict_hit"], "n": r["n_pos"], "scene": r["scene_hit"],
                "fp": r["fp"], "placed": sum(p is not None for p in pls),
                "up": up, "down": dn, "flips": flips,
            }
            if arm == "rrnop":
                (BENCH / "work" / f"ordered_search_{name}_trace.json").write_text(
                    json.dumps(traces, ensure_ascii=False, indent=1), encoding="utf-8")
        # rrnop 相对 argmax_g 天花板的独家翻转（修复版归因：重排 alone）：
        rr_f = case_out["arms"]["rrnop"]["flips"]
        ip_f = case_out["arms"]["argmax_g"]["flips"]
        case_out["rr_vs_interp"] = {
            "rr_only_up": sorted(k for k, v in rr_f.items()
                                  if k not in ip_f and v[1] == "HIT"),
            "rr_only_down": sorted(k for k, v in rr_f.items()
                                   if k not in ip_f and v[0] == "HIT"),
        }
        report["cases"][name] = case_out
        print(f"[{name}] {time.monotonic()-t0:.1f}s base_trunc={case_out['baseline_trunc']} "
              + " ".join(f"{a}:{v['strict']}/{v['n']} up={v['up']} dn={v['down']}"
                         for a, v in case_out["arms"].items()), flush=True)
    (BENCH / "work" / "ordered_search_replay.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = {a: sum(c["arms"][a]["strict"] for c in report["cases"].values())
           for a in ("raw", "argmax_g", "rrnop", "rr")}
    base_tot = sum(c["baseline_trunc"]["strict"] for c in report["cases"].values())
    print(f"SUMMARY baseline_trunc={base_tot}/139 " + " ".join(
        f"{a}={tot[a]}" for a in tot), flush=True)
    print("ALL_DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
