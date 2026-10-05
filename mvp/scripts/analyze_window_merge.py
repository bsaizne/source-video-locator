# -*- coding: utf-8 -*-
"""窗抓帧账单分析（2026-10-05 续54 补）：把 probe_locate_stage_timing 的逐次抓帧清单
按「段」分组，离线复算两种合并形态能省多少 spawn / 解码秒 / 管道帧数。

分组口径：patch_refine / isc_refine 每段开头都对**编辑片**取一次查询帧 ⇒ 以「编辑片
grab_frames 调用」作为段边界，其间的源片调用归为同一段。

合并形态：
  current = 现役（每候选窗一次调用，调用内按 gap≤4s/span≤40s 聚簇）
  union   = 同一段所有候选目标并成一次调用（续54 `_preembed_mids` 同原语）
  grid    = 并集后再走网格抽取（select 只吐网格帧 ⇒ 管道帧数 = 目标数，解码秒数不变）

成本模型（本仓实测口径，只用于估算排序，不当验收数字）：
  spawn 固定开销 1.0s/簇（续54：spawn+seek+解码 0.6 + Python 读帧 0.4）
  解码 21× 实时 ⇒ 0.048s/解码秒（续50）
  管道 1920x1080 bgr24 = 6.22MB/帧，676MB/s ⇒ 0.0092s/帧（续50 同量级）
用法: python mvp/scripts/analyze_window_merge.py <windows.jsonl> --edited <编辑片文件名>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

MAX_GAP_S = 4.0
MAX_SPAN_S = 40.0
S_PER_SPAWN = 1.0
S_PER_DECODE_S = 1.0 / 21.0
SRC_FPS = 25.0
S_PER_PIPE_FRAME = 6.22 / 676.0


def clusters(uniq):
    """与 FFmpegIO.grab_frames 同口径的聚簇划分。"""
    if not uniq:
        return []
    out, c = [], [uniq[0]]
    for t in uniq[1:]:
        if t - c[-1] <= MAX_GAP_S and t - c[0] <= MAX_SPAN_S:
            c.append(t)
        else:
            out.append(c)
            c = [t]
    out.append(c)
    return out


def cluster_cost(cl):
    """一簇的解码秒数 + 管道帧数（现役窗解码 = 解码整段，逐帧搬运）。"""
    span = cl[-1] - cl[0] if len(cl) > 1 else 0.0
    decode_s = span + 0.04            # 末帧之后无额外搬运（terminate 后收尾）
    return decode_s, decode_s * SRC_FPS


def cost(groups):
    """groups: list[list[float]]（每段一次调用的目标并集）→ 聚合成本。"""
    n_spawn = dec = pipe = 0.0
    for g in groups:
        for cl in clusters(sorted(set(g))):
            d, p = cluster_cost(cl)
            n_spawn += 1
            dec += d
            pipe += p
    return {"spawns": int(n_spawn), "decode_s": round(dec, 1),
            "pipe_frames": int(pipe),
            "est_s": round(n_spawn * S_PER_SPAWN + dec * S_PER_DECODE_S
                           + pipe * S_PER_PIPE_FRAME, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--edited", required=True, help="编辑片文件名（段边界标记）")
    args = ap.parse_args()
    recs = [json.loads(line) for line in
            Path(args.jsonl).read_text(encoding="utf-8").splitlines() if line.strip()]

    per_stage = {}
    for stage in sorted({r["stage"] for r in recs}):
        cur_groups, union_groups, grid_groups = [], [], []
        seg_src = None
        for r in recs:
            if r["stage"] != stage:
                continue
            if r["file"] == args.edited:
                if seg_src is not None and seg_src:
                    union_groups.append(seg_src)
                seg_src = []
                continue
            if seg_src is None:
                seg_src = []
            seg_src.extend(r["targets"])
            cur_groups.append(r["targets"])
        if seg_src:
            union_groups.append(seg_src)
        # grid 形态：并集簇 + select（管道帧 = 目标数，解码秒不变）
        g_dec = g_pipe = g_spawn = 0.0
        for g in union_groups:
            for cl in clusters(sorted(set(g))):
                d, _ = cluster_cost(cl)
                g_spawn += 1
                g_dec += d
                g_pipe += len(cl)
        per_stage[stage] = {
            "segments": len(union_groups),
            "calls": sum(len(r["targets"]) > 0 for r in recs if r["stage"] == stage),
            "current": cost(cur_groups),
            "union": cost(union_groups),
            "union_grid": {"spawns": int(g_spawn), "decode_s": round(g_dec, 1),
                           "pipe_frames": int(g_pipe),
                           "est_s": round(g_spawn * S_PER_SPAWN + g_dec * S_PER_DECODE_S
                                          + g_pipe * S_PER_PIPE_FRAME, 1)},
        }

    print(json.dumps(per_stage, ensure_ascii=False, indent=1))
    for stage, d in per_stage.items():
        if not d["segments"]:
            continue
        print("\n== %s（%d 段 / %d 次调用）==" % (stage, d["segments"], d["calls"]))
        base = d["current"]["est_s"]
        for form in ("current", "union", "union_grid"):
            est = d[form]["est_s"]
            print("  %-11s est %7.1fs  spawns=%-5d decode=%6.1fs pipe_frames=%7d  %s"
                  % (form, est, d[form]["spawns"], d[form]["decode_s"], d[form]["pipe_frames"],
                     ("参照" if form == "current" else "%.2f×" % (base / max(est, 1e-9)))),
                  flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
