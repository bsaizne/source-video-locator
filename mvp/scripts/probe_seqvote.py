# -*- coding: utf-8 -*-
"""(E) 形态5：序列对位分接入决策层（2026-09-30，用户拍板「按你的计划来」）。

机制（`probe_competitor_gap_diag.py` 证实）：t1r14c / p30 的 GT 锚不在管线候选集
（p30 候选全在 1600-1800 区）或被宽 sub 糊住 ⇒ 需要 ①序列投票峰作为**新增候选**，
②用**序列对位分**在候选间重选主 span。老主 span 降级为子 span ⇒ 严格结构性零回退
（形态4 已验证该结构）。拒识段（主 span 空）不碰 ⇒ 负例无新暴露面。

参数（先立后跑一次）：
  - ED 帧 ≤15 @3fps；对位取 ±TOL(1.0s) 内最大相似度（治 1fps 粒度尖峰）
  - 投票峰 δ 网格 = 全片 1s 步长；峰 span = [rs0+δ*, rs1+δ*]（编辑窗等长）
  - 切换 margin = 0.015（对位分须胜当前主 span 才切换）
评估门槛：导出实得 ≥+2（t1r14c/p30）且 严格 ≥130（结构性）且 FP ≤4；翻转行读图。
产物 `work/seqvote_probe/`。零 runtime / 零 GT / feature_version 零变更。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_seqvote.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

import numpy as np  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend   # noqa: E402
from diagnostics.contact_sheet import compose_sheet   # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402
from infrastructure.config import load_config          # noqa: E402
from media.ffmpeg import FFmpegIO                      # noqa: E402
from measure_shot_recall import evaluate               # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "seqvote_probe"
CASES = [("2mkv", "datasets/real/ground_truth_v4.json",
          "work/fastglobal_default_2mkv.results.json"),
         ("test1", "datasets/real/ground_truth_test1.json",
          "work/fastglobal_default_test1.results.json"),
         ("test2", "datasets/real/ground_truth_test2.json",
          "work/fastglobal_default_test2.results.json"),
         ("test3", "datasets/real/ground_truth_test3.json",
          "work/fastglobal_default_test3.results.json")]
TARGET_POCKETS = [("2mkv", "p20"), ("2mkv", "p30"), ("2mkv", "p34"),
                  ("test1", "t1r14c"), ("test2", "t2r06c"), ("test3", "t3r02c")]
WIN_TOL, MARGIN, ED_FPS, ED_MAX = 1.0, 0.05, 3.0, 15  # margin 统一到形态4已验证值 0.05（0.015 churn 判负）


def aligned_scores(embs, b, ets, c0, c1, rs0, rs1):
    """各 ED 帧在候选 [c0,c1] 1:1 对位处的 ±TOL 最大相似度。"""
    vals = []
    for i, et in enumerate(ets):
        p = c0 + (et - rs0)
        lo, hi = p - WIN_TOL, p + WIN_TOL
        m = (b.times >= lo) & (b.times <= hi)
        if m.any():
            vals.append(float(np.max(b.features[m] @ embs[i])))
    return float(np.mean(vals)) if vals else 0.0


def vote_peak(embs, b, ets, rs0, rs1):
    """全片 1s 网格投票：score(δ)=mean_i ±TOL 对位分；返回 (δ*, score)。"""
    T = float(b.times[-1])
    best_d, best_s = 0.0, -1.0
    for d in np.arange(0.0, T, 1.0):
        s = aligned_scores(embs, b, ets, rs0 + d, rs1 + d, rs0, rs1)
        if s > best_s:
            best_d, best_s = float(d), s
    return best_d, best_s


def process(fio, ed, b, r, embed):
    """返回 (delta_applied, old_main, new_main, vote_score, n_cand) 或 None。"""
    orig = r.get("original") or {}
    cs, ce = orig.get("candidate_start"), orig.get("candidate_end")
    edseg = r.get("edited_segment") or {}
    rs0, rs1 = edseg.get("start"), edseg.get("end")
    if cs is None or ce is None or ce - cs <= 0.01 or rs1 - rs0 <= 0.01:
        return None
    dur = rs1 - rs0
    n = max(3, min(ED_MAX, int(dur * ED_FPS)))
    ets = [rs0 + dur * (i + 0.5) / n for i in range(n)]
    embs = [embed(fio.grab_frame(ed, et)) for et in ets]
    cands = [("main", cs, ce)]
    for s in r.get("original_segments") or []:
        cands.append(("sub", s["candidate_start"], s["candidate_end"]))
    for a in r.get("alternatives") or []:
        if a.get("candidate_start") is not None:
            cands.append(("alt", a["candidate_start"], a["candidate_end"]))
    d_star, s_star = vote_peak(embs, b, ets, rs0, rs1)
    peak = (rs0 + d_star, rs1 + d_star)
    if all(abs(peak[0] - c0) > 1.0 or abs(peak[1] - c1) > 1.0 for _, c0, c1 in cands):
        cands.append(("votepeak", peak[0], peak[1]))
    scored = [(k, c0, c1, aligned_scores(embs, b, ets, c0, c1, rs0, rs1))
              for k, c0, c1 in cands]
    scored.sort(key=lambda x: -x[3])
    best = scored[0]
    cur = next((x for x in scored if x[0] == "main"), None)
    if cur is None or best[0] == "main" or best[3] - cur[3] < MARGIN:
        return (0.0, (cs, ce), (cs, ce), cur[3] if cur else 0.0, len(cands))
    return (1, (cs, ce), (best[1], best[2]), best[3], len(cands))


def strip_subs(raw):
    b = copy.deepcopy(raw)
    for x in b["results"]:
        x["original_segments"] = []
        x["alternatives"] = []
    return b


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
    print("BACKEND_SELECTED type=%s" % type(svc.backend).__name__, flush=True)
    fio = FFmpegIO(Path(os.environ["MEDIA_FFMPEG"]), Path(os.environ["MEDIA_FFPROBE"]))

    def embed(frame):
        v = svc.backend.embed_frames([frame])[0]
        return v / max(1e-8, float(np.linalg.norm(v)))

    report = {"params": {"WIN_TOL": WIN_TOL, "MARGIN": MARGIN}, "cases": []}
    flips = []
    for case, gt_rel, ours_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        b = svc.store.load_index(src)
        n_sw = 0
        new_results = []
        for r in raw["results"]:
            res = process(fio, ed, b, r, embed)
            if res is None:
                new_results.append(r)
                continue
            applied, old, new, sc, nc = res
            r.setdefault("_seqvote", {"switched": bool(applied),
                                      "new_main": [round(new[0], 2), round(new[1], 2)],
                                      "score": round(sc, 4), "n_cand": nc})
            if applied:
                r["original_segments"] = (r.get("original_segments") or [])
                r["original_segments"].insert(0, {
                    "candidate_start": old[0], "candidate_end": old[1]})
                r["original"]["candidate_start"] = round(new[0], 3)
                r["original"]["candidate_end"] = round(new[1], 3)
                n_sw += 1
            new_results.append(r)
        with contextlib.redirect_stdout(io.StringIO()):
            m_bs = evaluate(gt, raw["results"])
            m_ss = evaluate(gt, new_results)
            m_be = evaluate(gt, strip_subs(raw)["results"])
            m_se = evaluate(gt, strip_subs({"results": new_results})["results"])
        base_e = {x["id"]: x["mark"] for x in m_be["per_pos"]}
        split_e = {x["id"]: x["mark"] for x in m_se["per_pos"]}
        pk = {pid: split_e.get(pid) for c, pid in TARGET_POCKETS if c == case}
        for pid in base_e:
            if base_e[pid] != split_e[pid]:
                flips.append({"case": case, "id": pid,
                              "old": base_e[pid], "new": split_e[pid]})
        rep = {"case": case, "switched": n_sw,
               "strict_base": m_bs["strict_hit"], "strict_split": m_ss["strict_hit"],
               "export_base": m_be["strict_hit"], "export_split": m_se["strict_hit"],
               "fp_base": m_be["fp"], "fp_split": m_se["fp"], "pockets": pk}
        report["cases"].append(rep)
        print("[%-5s] 切换 %d 段 | 严格 %d→%d | 导出 %d→%d | FP %d→%d | 目标行 %s" % (
            case, n_sw, m_bs["strict_hit"], m_ss["strict_hit"],
            m_be["strict_hit"], m_se["strict_hit"], m_be["fp"], m_se["fp"], pk),
            flush=True)
        (BENCH / "work" / f"seqvote_{case}.results.json").write_text(
            json.dumps(new_results, ensure_ascii=False), encoding="utf-8")
    tb = sum(c["export_base"] for c in report["cases"])
    ts = sum(c["export_split"] for c in report["cases"])
    sb = sum(c["strict_base"] for c in report["cases"])
    ss = sum(c["strict_split"] for c in report["cases"])
    fb = sum(c["fp_base"] for c in report["cases"])
    fs = sum(c["fp_split"] for c in report["cases"])
    pkh = sum(1 for c in report["cases"] for v in c["pockets"].values() if v == "HIT")
    print("\n=== 形态5汇总: 导出 %d→%d (门≥+2) | 严格 %d→%d (结构性≥130) | FP %d→%d | "
          "目标行命中 %d/6 ===" % (tb, ts, sb, ss, fb, fs, pkh))
    report["totals"] = {"export_base": tb, "export_split": ts,
                        "strict_base": sb, "strict_split": ss,
                        "fp_base": fb, "fp_split": fs, "pocket_hits": pkh}
    if flips:
        rows = []
        for f in flips:
            case = f["case"]
            gtf = next(g for c, g, _ in CASES if c == case)
            gt = json.loads((BENCH / gtf).read_text(encoding="utf-8"))
            raw0 = json.loads((BENCH / dict((c, o) for c, _, o in CASES)[case])
                              .read_text(encoding="utf-8"))
            src, ed = Path(raw0["original_video"]), Path(raw0["edited_video"])
            p = next(x for x in gt["positives"] if x["id"] == f["id"])
            e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
            best, span = 0.0, None
            for r in json.loads((BENCH / f"work/seqvote_{case}.results.json")
                                .read_text(encoding="utf-8")):
                re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
                ov = min(e1, re1) - max(e0, re0)
                if ov > best:
                    best = ov
                    orig = r.get("original") or {}
                    if "candidate_start" in orig:
                        span = (orig["candidate_start"], orig["candidate_end"])
            tag = f"{case}_{f['id']}"
            cells = []
            for vid, t, cap in ((ed, (e0 + e1) / 2, "GT ED"),
                                (src, (o0 + o1) / 2, "GT OG"),
                                (src, (span[0] + span[1]) / 2 if span else None,
                                 "V5 %s" % (span,))):
                pp = OUT / "frames" / f"{tag}_{cap.split()[0]}.png"
                try:
                    ffmpeg_frame(vid, max(0.0, float(t)), pp)
                    cells.append((str(pp), [cap, fmt_ts(t)]))
                except Exception:
                    cells.append(None)
            rows.append(cells)
        for i in range(0, len(rows), 4):
            compose_sheet(rows[i:i + 4], OUT / f"flips_{i // 4 + 1}.png",
                          "seqvote flips %d-%d: GT_ED | GT_OG | V5" % (i + 1, i + 4))
        print("导出口径翻转 %d 行 -> %s/flips_*.png" % (len(flips), OUT))
    report["flips"] = flips
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print("产物: %s" % (OUT / "report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
