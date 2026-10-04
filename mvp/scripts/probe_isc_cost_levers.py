# -*- coding: utf-8 -*-
"""ISC 成本杠杆探针（2026-10-03 续50，用户问「性能侧还能怎么优化，先把成本打下来」）。

两个子命令（都不改 runtime、不写生产索引、不写 work/ 既有产物）：

  main-score   —— 决定「宽扫 main-agreement 门」能不能成立：
                  对四片 ON 臂（radius 0）每个合格段算 **ISC 在现主 span 上的分**（与
                  isc_refine._score_mid 同口径：3 查询帧 ISC 均值，窗 = span ±1.5s @1s 网格取 max），
                  并用 ON vs V2 的逐段落点差判「这段是否被宽扫切换过」。
                  若「被切换段」的 main_score 明显低于未被切换段 ⇒ 可以在宽扫前用 1 次廉价打分
                  跳过多数段（跳过段 = 回落到 ON 臂行为 = 已验证的 134/128/138/4 基线）。

  index-pilot  —— 量「ISC 源片索引化」的一次性成本：
                  对 test1-om 前 N 秒按 1s 网格建 ISC 特征（抓帧用窗解码批量），
                  测 wall / fps / 每帧字节，外推到整片。目标：把每段的 ±90s 现扫
                  换成「源片 ISC 表上的一次 matmul」。

用法:
  python mvp/scripts/probe_isc_cost_levers.py main-score
  python mvp/scripts/probe_isc_cost_levers.py index-pilot --seconds 300
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import time
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402

from media.ffmpeg import FFmpegIO                                    # noqa: E402
from infrastructure.config import load_config                        # noqa: E402
from engine.localization.isc_refine import (                         # noqa: E402
    IscScorer, N_QUERY, ISC_TOL_S, ISC_STEP)

OUT = BENCH / "work" / "isc_cost_levers"
ARMS = BENCH / "work" / "isc_refine_arms"

CASES = [
    ("2mkv", r"D:\video\1.mp4", r"D:\video\2.mkv",
     "datasets/real/ground_truth_v4.json"),
    ("test1", r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv",
     "datasets/real/ground_truth_test1.json"),
    ("test2", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4",
     "datasets/real/ground_truth_test2.json"),
    ("test3", r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4",
     "datasets/real/ground_truth_test3.json"),
]
# 续45 V2 验收里三指标真正获益的行（门必须保住的「不可跳」集合）
MUST_KEEP = {"2mkv": {"p20", "p34"}, "test2": {"t2r06c"}}


def eligible(r: dict) -> bool:
    if r.get("not_in_source") or r.get("manual_override") or r.get("excluded"):
        return False
    o, e = r["original"], r["edited_segment"]
    return (o["candidate_end"] - o["candidate_start"]) > 0.01 and \
           (e["end"] - e["start"]) > 0.01


def load_arm(case: str, arm: str) -> list:
    return json.loads((ARMS / ("%s_%s.results.json" % (arm, case)))
                      .read_text(encoding="utf-8"))["results"]


def grab_many(ff: FFmpegIO, path: str, ts: list):
    """窗解码批量抓帧（返回 list）；grab_frames 的真实返回是 {t: frame} dict，
    逐帧回退补齐缺失项（与生产 _grab_frames_window 同语义）。"""
    ts = [float(t) for t in ts]
    fn = getattr(ff, "grab_frames", None)
    if fn is not None:
        try:
            got = fn(Path(path), ts)
            if isinstance(got, dict) and got:
                out = []
                for t in ts:
                    fr = got.get(round(t, 6))
                    out.append(fr if fr is not None else ff.grab_frame(Path(path), t))
                return out
        except Exception as exc:                      # 回退逐帧（与生产同语义）
            print("  grab_frames fallback: %s" % exc, flush=True)
    return [ff.grab_frame(Path(path), t) for t in ts]


def score_isc(scorer: IscScorer, ff: FFmpegIO, path: str, main_mid: float,
              width: float, q_isc: np.ndarray) -> float:
    lo = max(0.0, main_mid - width / 2 - ISC_TOL_S)
    hi = main_mid + width / 2 + ISC_TOL_S
    n = max(2, int(np.ceil((hi - lo) / ISC_STEP)))
    ts = sorted({round(lo + (hi - lo) * (i + 0.5) / n, 3) for i in range(n)})
    frames = grab_many(ff, path, ts)
    best = -1.0
    for fr in frames:
        v = np.asarray(scorer.embed(fr), dtype=np.float64)
        best = max(best, float(np.mean(q_isc @ v)))
    return best


def cmd_main_score(_args) -> int:
    cfg = load_config()
    ff = FFmpegIO()
    scorer = IscScorer()
    if not scorer.ensure():
        print("ISC 资产缺失，无法继续", flush=True)
        return 2
    print("ISC device=%s" % scorer.device, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"device": scorer.device, "cases": {}, "rows": [], "caliber": (
        "main_score = 3 查询帧 ISC 均值在「现主 span ±1.5s @1s 网格」上的 max"
        "（与 isc_refine._score_mid 同口径）；switched = ON/V2 逐段主 span 中点或宽度差 > 0.5s")}
    t_all = time.time()
    for case, edited, source, gt_rel in CASES:
        rows_on = load_arm(case, "on")
        rows_v2 = load_arm(case, "v2")
        by_key = {}
        for i, r in enumerate(rows_v2):
            by_key[(round(r["edited_segment"]["start"], 3),
                    round(r["edited_segment"]["end"], 3))] = (i, r)
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        # GT id -> 编辑侧最大重叠行
        id_of = {}
        for p in gt["positives"]:
            e0, e1 = p["edited"]
            best_i, best_ov = None, 0.0
            for i, r in enumerate(rows_on):
                s = r["edited_segment"]
                ov = min(e1, s["end"]) - max(e0, s["start"])
                if ov > best_ov:
                    best_i, best_ov = i, ov
            if best_i is not None and best_ov > 0:
                id_of[best_i] = p["id"]
        n_ok = n_skip = n_sw = 0
        t0 = time.time()
        for i, r_on in enumerate(rows_on):
            if not eligible(r_on):
                continue
            key = (round(r_on["edited_segment"]["start"], 3),
                   round(r_on["edited_segment"]["end"], 3))
            hit = by_key.get(key)
            r_v2 = hit[1] if hit else None
            e0, e1 = r_on["edited_segment"]["start"], r_on["edited_segment"]["end"]
            w = e1 - e0
            q_ets = [e0 + w * (k + 0.5) / N_QUERY for k in range(N_QUERY)]
            q_frames = grab_many(ff, edited, q_ets)
            q_isc = np.mean([np.asarray(scorer.embed(f), dtype=np.float64)
                             for f in q_frames], axis=0)
            o_on = r_on["original"]
            main_mid = (o_on["candidate_start"] + o_on["candidate_end"]) / 2
            ms = score_isc(scorer, ff, source, main_mid, w, q_isc)
            switched, d_mid, d_w = False, None, None
            if r_v2 is not None:
                o_v2 = r_v2["original"]
                mid_v2 = (o_v2["candidate_start"] + o_v2["candidate_end"]) / 2
                d_mid = mid_v2 - main_mid
                d_w = (o_v2["candidate_end"] - o_v2["candidate_start"]) - \
                      (o_on["candidate_end"] - o_on["candidate_start"])
                switched = abs(d_mid) > 0.5 or abs(d_w) > 0.5
            n_ok += 1
            n_sw += int(switched)
            n_skip += int(ms >= 0.60)
            report["rows"].append(dict(case=case, idx=i, id=id_of.get(i),
                                       main_score=round(float(ms), 4),
                                       main_mid=round(main_mid, 2), switched=switched,
                                       d_mid=None if d_mid is None else round(d_mid, 2),
                                       d_w=None if d_w is None else round(d_w, 2)))
            if n_ok % 25 == 0:
                print("  %s %d 段 (%.0fs)" % (case, n_ok, time.time() - t0), flush=True)
        report["cases"][case] = {"eligible": n_ok, "switched": n_sw,
                                 "skip_at_0.60": n_skip, "sec": round(time.time() - t0, 1)}
        print("[%s] eligible=%d switched=%d (%.0fs)" % (case, n_ok, n_sw, time.time() - t0),
              flush=True)

    rows = report["rows"]
    ms_sw = [r["main_score"] for r in rows if r["switched"]]
    ms_no = [r["main_score"] for r in rows if not r["switched"]]
    report["summary"] = {
        "n": len(rows), "n_switched": len(ms_sw),
        "switched": {} if not ms_sw else {
            "min": min(ms_sw), "p25": float(np.percentile(ms_sw, 25)),
            "median": float(np.median(ms_sw)), "p75": float(np.percentile(ms_sw, 75)),
            "max": max(ms_sw)},
        "not_switched": {} if not ms_no else {
            "min": min(ms_no), "p25": float(np.percentile(ms_no, 25)),
            "median": float(np.median(ms_no)), "p75": float(np.percentile(ms_no, 75)),
            "max": max(ms_no)},
    }
    # 阈值扫：跳过的段数与「被跳过里含多少切换段 / 是否含 MUST_KEEP」
    scan = []
    for th in [0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
        skipped = [r for r in rows if r["main_score"] >= th]
        lost_sw = [r for r in skipped if r["switched"]]
        keep_lost = [r for r in skipped
                     if r["id"] in MUST_KEEP.get(r["case"], set())]
        scan.append({"theta": th, "skipped": len(skipped),
                     "skip_pct": round(100.0 * len(skipped) / max(1, len(rows)), 1),
                     "lost_switches": len(lost_sw),
                     "lost_switch_ids": ["%s/%s" % (r["case"], r["id"]) for r in lost_sw],
                     "must_keep_lost": ["%s/%s" % (r["case"], r["id"]) for r in keep_lost]})
    report["threshold_scan"] = scan

    print("\n=== main_score 分布 ===")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=1))
    print("\n=== 阈值扫（跳过 = main_score >= theta）===")
    for s in scan:
        print("  theta=%.2f 跳过 %3d/%d (%4.1f%%) 误跳切换段 %2d  丢失 MUST_KEEP %s"
              % (s["theta"], s["skipped"], len(rows), s["skip_pct"],
                 s["lost_switches"], s["must_keep_lost"] or "-"))
    print("\n=== MUST_KEEP 行明细 ===")
    for r in rows:
        if r["id"] in MUST_KEEP.get(r["case"], set()):
            print("  %s/%-8s main_score=%.3f switched=%s d_mid=%s"
                  % (r["case"], r["id"], r["main_score"], r["switched"], r["d_mid"]))
    (OUT / "main_score.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print("\nsaved %s" % (OUT / "main_score.json"))
    print("elapsed %.0fs" % (time.time() - t_all))
    print("ALL_DONE", flush=True)
    return 0


def cmd_index_pilot(args) -> int:
    ff = FFmpegIO()
    scorer = IscScorer()
    if not scorer.ensure():
        print("ISC 资产缺失", flush=True)
        return 2
    print("ISC device=%s" % scorer.device, flush=True)
    case, edited, source, gt_rel = CASES[1]           # test1-om，全长 8229s
    times = [float(t) for t in range(0, int(args.seconds), 1)]
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    frames = grab_many(ff, source, times)
    t_grab = time.time() - t0
    t1 = time.time()
    feats = np.zeros((len(times), 256), dtype=np.float32)
    for i, fr in enumerate(frames):
        feats[i] = np.asarray(scorer.embed(fr), dtype=np.float32)
        if (i + 1) % 100 == 0:
            print("  embed %d/%d (%.0fs)" % (i + 1, len(times), time.time() - t1), flush=True)
    t_emb = time.time() - t1
    np.save(OUT / ("isc_pilot_test1_%ds.npy" % int(args.seconds)), feats)
    per_frame = (t_grab + t_emb) / max(1, len(times))
    dur = 8229.28
    rep = {"case": case, "source": source, "seconds": int(args.seconds),
           "n": len(times), "grab_s": round(t_grab, 1), "embed_s": round(t_emb, 1),
           "grab_per_frame_s": round(t_grab / max(1, len(times)), 4),
           "embed_per_frame_s": round(t_emb / max(1, len(times)), 4),
           "embed_fps": round(len(times) / max(1e-6, t_emb), 1),
           "bytes_per_frame": int(feats[0].nbytes),
           "full_source_frames_1s": int(dur),
           "est_full_source_min": round(per_frame * dur / 60.0, 1),
           "est_full_index_mb": round(feats[0].nbytes * dur / 1e6, 1),
           "workdir": str(OUT)}
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    (OUT / "index_pilot.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print("ALL_DONE", flush=True)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("main-score")
    p2 = sub.add_parser("index-pilot")
    p2.add_argument("--seconds", type=int, default=300)
    args = ap.parse_args()
    if args.cmd == "main-score":
        return cmd_main_score(args)
    return cmd_index_pilot(args)


if __name__ == "__main__":
    sys.exit(main())
