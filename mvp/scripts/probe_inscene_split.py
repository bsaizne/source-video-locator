# -*- coding: utf-8 -*-
"""(E) 形态3：段级拆分离线探针（2026-09-30，用户拍板「按你的计划来」第一步）。

假设：病灶 = 粗段盖多镜只带一个主 span（形态1 判负、形态2 信号精准的合流结论）。
方案：多镜头结果段按分镜重排为逐镜结果——
  - 单镜段（未检出切割）**原样不动**（已是逐镜粒度，少动少错）；
  - 多镜段 → 每镜一个子结果：过门镜（agree≥0.5）主 span = 精化逐镜 span；
    未过门镜主 span = 父主 span 的 1:1 投影兜底 [cs+s0−rs0, cs+s1−rs0]；
  - 置信度继承父段；子段 original_segments/alternatives = 空（干净模拟
    「管线天然逐镜」，父宽子 span 不随身携带——严格是否站得住由门槛检验）；
  - 拒识段（主 span 空）不拆（负例无新暴露面）。

门槛（2026-09-30 用户批）：**导出实得（全长主 span）≥ +10 且 严格 ≥130 且 FP ≤4**。
评估口径：严格（全 span）/ 导出实得（全长主 span）/ 截等长主 span（口袋口径）/
FP；8 条口袋逐条；导出口径翻转行出图复核。

产物 `work/inscene_split_probe/`。零 runtime / 零 GT / feature_version 零变更。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_inscene_split.py
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

OUT = BENCH / "work" / "inscene_split_probe"
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
WIN, CUT_THR, AGREE_MIN, SHOT_FPS, SHOT_MAX = 30.0, 0.55, 0.5, 4.0, 40


def shots_of(ets, embs):
    cuts = [0]
    for i in range(1, len(ets)):
        if float(embs[i - 1] @ embs[i]) < CUT_THR:
            cuts.append(i)
    cuts.append(len(ets))
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
    """返回 (children, n_refined)。children=[] 表示不拆。"""
    orig = r.get("original") or {}
    cs, ce = orig.get("candidate_start"), orig.get("candidate_end")
    edseg = r.get("edited_segment") or {}
    rs0, rs1 = edseg.get("start"), edseg.get("end")
    if cs is None or ce is None or ce - cs <= 0.01 or rs1 - rs0 <= 0.01:
        return [], 0
    dur = rs1 - rs0
    n = max(2, min(SHOT_MAX, int(dur * SHOT_FPS)))
    ets = [rs0 + dur * (i + 0.5) / n for i in range(n)]
    embs = [embed(fio.grab_frame(ed, et)) for et in ets]
    shots = shots_of(ets, embs)
    if len(shots) < 2:
        return [], 0                                  # 单镜段不动
    lo, hi = (cs + ce) / 2 - WIN, (cs + ce) / 2 + WIN
    mask = (b.times >= lo) & (b.times <= hi)
    if not mask.any():
        return [], 0
    sub_t, sub_f = b.times[mask], b.features[mask]
    children, n_ref = [], 0
    for s0, s1 in shots:
        child = copy.deepcopy(r)
        child["edited_segment"] = {"start": round(s0, 3), "end": round(s1, 3)}
        child["original_segments"] = []
        child["alternatives"] = []
        proj0, proj1 = cs + s0 - rs0, cs + s1 - rs0
        idx = [i for i, t in enumerate(ets) if s0 <= t <= s1]
        refined = None
        if len(idx) >= 2:
            offs = [float(sub_t[int(np.argmax(sub_f @ embs[i]))]) - ets[i] for i in idx]
            med = statistics.median(offs)
            agree = sum(1 for o in offs if abs(o - med) <= 1.5) / len(offs)
            delta = med - (cs - rs0)
            if agree >= AGREE_MIN and abs(delta) >= 0.5:
                refined = (proj0 + delta, proj1 + delta, round(delta, 2), round(agree, 2))
                n_ref += 1
        a0, a1 = refined[:2] if refined else (proj0, proj1)
        child["original"]["candidate_start"] = round(a0, 3)
        child["original"]["candidate_end"] = round(max(a1, a0 + 0.05), 3)
        child["_split"] = {"shot_ed": [round(s0, 2), round(s1, 2)],
                           "refined": bool(refined),
                           "delta": refined[2] if refined else 0.0,
                           "agree": refined[3] if refined else 0.0}
        children.append(child)
    return children, n_ref


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

    report = {"params": {"WIN": WIN, "CUT_THR": CUT_THR, "AGREE_MIN": AGREE_MIN},
              "cases": []}
    flips = []
    for case, gt_rel, ours_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        b = svc.store.load_index(src)
        split_children, n_ref, n_split = [], 0, 0
        for r in raw["results"]:
            children, nr = split_result(fio, ed, b, r, embed)
            if children:
                split_children.extend(children)
                n_ref += nr
                n_split += 1
            else:
                split_children.append(r)
        with contextlib.redirect_stdout(io.StringIO()):
            m_base_strict = evaluate(gt, raw["results"])
            m_split_strict = evaluate(gt, split_children)
            m_base_exp = evaluate(gt, strip_subs(raw)["results"])
            m_split_exp = evaluate(gt, strip_subs({"results": split_children})["results"])
            m_base_tr = evaluate(gt, truncate_main(raw)["results"])
            m_split_tr = evaluate(gt, truncate_main({"results": split_children})["results"])
        base_pk = {x["id"]: x["mark"] for x in m_base_tr["per_pos"]}
        split_pk = {x["id"]: x["mark"] for x in m_split_tr["per_pos"]}
        pk = {pid: split_pk.get(pid) for c, pid in PROD_MISS_POCKETS if c == case}
        base_exp_per = {x["id"]: x["mark"] for x in m_base_exp["per_pos"]}
        split_exp_per = {x["id"]: x["mark"] for x in m_split_exp["per_pos"]}
        for pid in base_exp_per:
            if base_exp_per[pid] != split_exp_per[pid]:
                flips.append({"case": case, "id": pid,
                              "old": base_exp_per[pid], "new": split_exp_per[pid]})
        rep = {"case": case, "split_segments": n_split, "refined_shots": n_ref,
               "n_results": len(split_children),
               "strict_base": m_base_strict["strict_hit"],
               "strict_split": m_split_strict["strict_hit"],
               "export_base": m_base_exp["strict_hit"],
               "export_split": m_split_exp["strict_hit"],
               "trunc_base": m_base_tr["strict_hit"],
               "trunc_split": m_split_tr["strict_hit"],
               "fp_base": m_base_exp["fp"], "fp_split": m_split_exp["fp"],
               "pockets": pk}
        report["cases"].append(rep)
        print("[%-5s] 拆 %d 段(精化 %d 镜) 结果 %d | 严格 %d→%d | 导出 %d→%d | "
              "截等长 %d→%d | FP %d→%d | 口袋 %s" % (
                  case, n_split, n_ref, len(split_children),
                  m_base_strict["strict_hit"], m_split_strict["strict_hit"],
                  m_base_exp["strict_hit"], m_split_exp["strict_hit"],
                  m_base_tr["strict_hit"], m_split_tr["strict_hit"],
                  m_base_exp["fp"], m_split_exp["fp"], pk), flush=True)
        (BENCH / "work" / f"inscene_split_{case}.results.json").write_text(
            json.dumps(split_children, ensure_ascii=False), encoding="utf-8")
    tb = sum(c["export_base"] for c in report["cases"])
    ts = sum(c["export_split"] for c in report["cases"])
    sb = sum(c["strict_base"] for c in report["cases"])
    ss = sum(c["strict_split"] for c in report["cases"])
    fb = sum(c["fp_base"] for c in report["cases"])
    fs = sum(c["fp_split"] for c in report["cases"])
    pkh = sum(1 for c in report["cases"] for v in c["pockets"].values() if v == "HIT")
    print("\n=== 形态3汇总: 导出实得 %d→%d (门≥+10) | 严格 %d→%d (门零回退 vs130) | "
          "FP %d→%d (门不增) | 口袋 %d/8 ===" % (tb, ts, sb, ss, fb, fs, pkh))
    report["totals"] = {"export_base": tb, "export_split": ts,
                        "strict_base": sb, "strict_split": ss,
                        "fp_base": fb, "fp_split": fs, "pocket_hits": pkh}
    # 导出口径翻转行读图
    if flips:
        rows = []
        for f in flips:
            case = f["case"]
            sc = json.loads((BENCH / f"work/inscene_split_{case}.results.json")
                            .read_text(encoding="utf-8"))
            gtf = next(g for c, g, _ in CASES if c == case)
            gt = json.loads((BENCH / gtf).read_text(encoding="utf-8"))
            raw0 = json.loads((BENCH / dict((c, o) for c, _, o in CASES)[case])
                              .read_text(encoding="utf-8"))
            src, ed = Path(raw0["original_video"]), Path(raw0["edited_video"])
            p = next(x for x in gt["positives"] if x["id"] == f["id"])
            e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
            best, span = 0.0, None
            for r in sc:
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
                                 "SPLIT %s" % (span,))):
                pp = OUT / "frames" / f"{tag}_{cap.split()[0]}.png"
                try:
                    ffmpeg_frame(vid, max(0.0, float(t)), pp)
                    cells.append((str(pp), [cap, fmt_ts(t)]))
                except Exception:
                    cells.append(None)
            rows.append(cells)
        for i in range(0, len(rows), 4):
            compose_sheet(rows[i:i + 4], OUT / f"flips_{i // 4 + 1}.png",
                          "split flips %d-%d: GT_ED | GT_OG | SPLIT" % (i + 1, i + 4))
        print("导出口径翻转 %d 行 -> %s/flips_*.png" % (len(flips), OUT))
    report["flips"] = flips
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print("产物: %s" % (OUT / "report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
