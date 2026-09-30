# -*- coding: utf-8 -*-
"""(E) 形态4：段级拆分 v2 —— 谷值切镜 + margin 门 + 宽 span 保全（2026-09-30）。

用户指令：「数据只是标准、说不定数据是错的；怎么改能用就改，参考竞品学习」。
对形态3 的三处修正（参数先立后跑，一次定 verdict，不再调参）：

  1. 切镜 = **谷值检测**（学竞品「镜头优先分割」）：c[i] 为局部极小且低于邻域 VALLEY_DEPTH
     （0.1）判软切；保留绝对硬切阈 0.55。⇒ 能抓同景内软切换（形态3 漏掉 t2r06c 等的根因）。
  2. 逐镜 span 采纳 = **margin 门**（patch v2 同款纪律）：精化 span 帧均匹配分须胜过投影
     span 帧均分 +0.05 才采纳，否则用投影 ⇒ 防 t3r01 式「精化挪错」。
  3. **宽 span 保全**：每子段随身携带父主 span + 父子 span 作为子 span
     ⇒ 严格口径（含宽 cov 记账）结构性零回退；导出口径 = 逐镜精准主 span。

评估：严格 / 导出实得（全长主 span）/ 截等长 / FP / 8 口袋 / 导出口径翻转行读图。
产物 `work/inscene_split_v2/`。零 runtime / 零 GT / feature_version 零变更。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_inscene_split_v2.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import statistics
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
from measure_mainspan_caliber import truncate_main     # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "inscene_split_v2"
CASES = [("2mkv", "datasets/real/ground_truth_v4.json",
          "work/fastglobal_default_2mkv.results.json"),
         ("test1", "datasets/real/ground_truth_test1.json",
          "work/fastglobal_default_test1.results.json"),
         ("test2", "datasets/real/ground_truth_test2.json",
          "work/fastglobal_default_test2.results.json"),
         ("test3", "datasets/real/ground_truth_test3.json",
          "work/fastglobal_default_test3.results.json")]
PROD_MISS_POCKETS = [("2mkv", "p02"), ("2mkv", "p03"), ("2mkv", "p20"), ("2mkv", "p30"),
                     ("2mkv", "p34"), ("test1", "t1r14c"), ("test2", "t2r06c"),
                     ("test3", "t3r02c")]
WIN, HARD_CUT, VALLEY_DEPTH, MARGIN, SHOT_FPS, SHOT_MAX = 30.0, 0.55, 0.10, 0.05, 4.0, 40


def shots_of(ets, embs):
    n = len(ets)
    cos = [float(embs[i - 1] @ embs[i]) for i in range(1, n)]
    cuts = [0]
    for i, c in enumerate(cos):                     # i: cut 在第 i+1 帧前
        hard = c < HARD_CUT
        valley = (0 < i < len(cos) - 1
                  and c < min(cos[i - 1], cos[i + 1]) - VALLEY_DEPTH)
        if hard or valley:
            cuts.append(i + 1)
    cuts.append(n)
    cuts = sorted(set(cuts))
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 2 and out:
            out[-1] = (out[-1][0], ets[b - 1])
        elif b - a >= 2:
            out.append((ets[a], ets[b - 1]))
    if out:
        out[-1] = (out[-1][0], ets[-1])
    return out


def split_result(fio, ed, b, r, embed):
    orig = r.get("original") or {}
    cs, ce = orig.get("candidate_start"), orig.get("candidate_end")
    edseg = r.get("edited_segment") or {}
    rs0, rs1 = edseg.get("start"), edseg.get("end")
    if cs is None or ce is None or ce - cs <= 0.01 or rs1 - rs0 <= 0.01:
        return [], 0, 0
    dur = rs1 - rs0
    n = max(2, min(SHOT_MAX, int(dur * SHOT_FPS)))
    ets = [rs0 + dur * (i + 0.5) / n for i in range(n)]
    embs = [embed(fio.grab_frame(ed, et)) for et in ets]
    shots = shots_of(ets, embs)
    if len(shots) < 2:
        return [], 0, 0
    lo, hi = (cs + ce) / 2 - WIN, (cs + ce) / 2 + WIN
    mask = (b.times >= lo) & (b.times <= hi)
    if not mask.any():
        return [], 0, 0
    sub_t, sub_f = b.times[mask], b.features[mask]
    children, n_ref, n_margin = [], 0, 0
    for s0, s1 in shots:
        child = copy.deepcopy(r)
        child["edited_segment"] = {"start": round(s0, 3), "end": round(s1, 3)}
        proj0, proj1 = cs + s0 - rs0, cs + s1 - rs0
        idx = [i for i, t in enumerate(ets) if s0 <= t <= s1]
        refined = None
        if len(idx) >= 2:
            offs = [float(sub_t[int(np.argmax(sub_f @ embs[i]))]) - ets[i] for i in idx]
            med = statistics.median(offs)
            agree = sum(1 for o in offs if abs(o - med) <= 1.5) / len(offs)
            delta = med - (cs - rs0)
            if agree >= 0.5 and abs(delta) >= 0.5:
                r0, r1 = proj0 + delta, proj1 + delta
                # margin 门：精化 span 采样帧与 argmax 源帧的相似度均值
                # vs 投影 span 同法（自一致性，无 GT）
                def score(a0, a1):
                    vals = []
                    for i in idx:
                        et = ets[i]
                        st = a0 + (a1 - a0) * (et - s0) / max(1e-9, s1 - s0)
                        m2 = (b.times >= st - 0.5) & (b.times <= st + 0.5)
                        if m2.any():
                            vals.append(float(np.max(b.features[m2] @ embs[i])))
                    return statistics.mean(vals) if vals else 0.0
                if score(r0, r1) > score(proj0, proj1) + MARGIN:
                    refined = (r0, r1, round(delta, 2), round(agree, 2))
                    n_ref += 1
                else:
                    n_margin += 1
        a0, a1 = refined[:2] if refined else (proj0, proj1)
        child["original"]["candidate_start"] = round(a0, 3)
        child["original"]["candidate_end"] = round(max(a1, a0 + 0.05), 3)
        # 宽 span 保全：父主 span + 父子 span 全部作为本子段的子 span
        subs = [{"candidate_start": cs, "candidate_end": ce}]
        subs += [{"candidate_start": s["candidate_start"],
                  "candidate_end": s["candidate_end"]}
                 for s in r.get("original_segments") or []]
        child["original_segments"] = subs
        child["_split"] = {"shot_ed": [round(s0, 2), round(s1, 2)],
                           "refined": bool(refined),
                           "delta": refined[2] if refined else 0.0,
                           "agree": refined[3] if refined else 0.0}
        children.append(child)
    return children, n_ref, n_margin


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

    report = {"params": {"WIN": WIN, "HARD_CUT": HARD_CUT,
                         "VALLEY_DEPTH": VALLEY_DEPTH, "MARGIN": MARGIN},
              "cases": []}
    flips = []
    for case, gt_rel, ours_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        b = svc.store.load_index(src)
        children_all, n_ref, n_mg, n_split = [], 0, 0, 0
        for r in raw["results"]:
            children, nr, nm = split_result(fio, ed, b, r, embed)
            if children:
                children_all.extend(children)
                n_ref += nr
                n_mg += nm
                n_split += 1
            else:
                children_all.append(r)
        with contextlib.redirect_stdout(io.StringIO()):
            m_bs = evaluate(gt, raw["results"])
            m_ss = evaluate(gt, children_all)
            m_be = evaluate(gt, strip_subs(raw)["results"])
            m_se = evaluate(gt, strip_subs({"results": children_all})["results"])
            m_bt = evaluate(gt, truncate_main(raw)["results"])
            m_st = evaluate(gt, truncate_main({"results": children_all})["results"])
        split_pk = {x["id"]: x["mark"] for x in m_st["per_pos"]}
        pk = {pid: split_pk.get(pid) for c, pid in PROD_MISS_POCKETS if c == case}
        base_e = {x["id"]: x["mark"] for x in m_be["per_pos"]}
        split_e = {x["id"]: x["mark"] for x in m_se["per_pos"]}
        for pid in base_e:
            if base_e[pid] != split_e[pid]:
                flips.append({"case": case, "id": pid,
                              "old": base_e[pid], "new": split_e[pid]})
        rep = {"case": case, "split_segments": n_split, "refined_shots": n_ref,
               "margin_blocked": n_mg, "n_results": len(children_all),
               "strict_base": m_bs["strict_hit"], "strict_split": m_ss["strict_hit"],
               "export_base": m_be["strict_hit"], "export_split": m_se["strict_hit"],
               "trunc_base": m_bt["strict_hit"], "trunc_split": m_st["strict_hit"],
               "fp_base": m_be["fp"], "fp_split": m_se["fp"], "pockets": pk}
        report["cases"].append(rep)
        print("[%-5s] 拆 %d(精化 %d margin拦 %d) | 严格 %d→%d | 导出 %d→%d | "
              "截等长 %d→%d | FP %d→%d | 口袋 %s" % (
                  case, n_split, n_ref, n_mg,
                  m_bs["strict_hit"], m_ss["strict_hit"],
                  m_be["strict_hit"], m_se["strict_hit"],
                  m_bt["strict_hit"], m_st["strict_hit"],
                  m_be["fp"], m_se["fp"], pk), flush=True)
        (BENCH / "work" / f"inscene_splitv2_{case}.results.json").write_text(
            json.dumps(children_all, ensure_ascii=False), encoding="utf-8")
    tb = sum(c["export_base"] for c in report["cases"])
    ts = sum(c["export_split"] for c in report["cases"])
    sb = sum(c["strict_base"] for c in report["cases"])
    ss = sum(c["strict_split"] for c in report["cases"])
    fb = sum(c["fp_base"] for c in report["cases"])
    fs = sum(c["fp_split"] for c in report["cases"])
    pkh = sum(1 for c in report["cases"] for v in c["pockets"].values() if v == "HIT")
    print("\n=== 形态4汇总: 导出实得 %d→%d | 严格 %d→%d (结构性≥) | FP %d→%d | "
          "口袋 %d/8 ===" % (tb, ts, sb, ss, fb, fs, pkh))
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
            for r in json.loads((BENCH / f"work/inscene_splitv2_{case}.results.json")
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
                                 "V2 %s" % (span,))):
                pp = OUT / "frames" / f"{tag}_{cap.split()[0]}.png"
                try:
                    ffmpeg_frame(vid, max(0.0, float(t)), pp)
                    cells.append((str(pp), [cap, fmt_ts(t)]))
                except Exception:
                    cells.append(None)
            rows.append(cells)
        for i in range(0, len(rows), 4):
            compose_sheet(rows[i:i + 4], OUT / f"flips_{i // 4 + 1}.png",
                          "split v2 flips %d-%d: GT_ED | GT_OG | V2" % (i + 1, i + 4))
        print("导出口径翻转 %d 行 -> %s/flips_*.png" % (len(flips), OUT))
    report["flips"] = flips
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print("产物: %s" % (OUT / "report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
