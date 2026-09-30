# -*- coding: utf-8 -*-
"""(E) 立项 · 场景内稠密局部位置信号探针（2026-09-30，无 GT 反标，零 runtime）。

信号（复现链「表示粒度」的我方口径重造，不接受其判据）：
  对每条结果段（edited 窗 [rs0,rs1]，主 span [cs,ce]）：
    1. 编辑窗内采 ≤10 帧（2fps 均匀），生产 CLS（DML 硬断言，batch=1）逐帧嵌入；
    2. 每帧与原片索引 1fps 特征在 **落位中心 ±WIN 秒邻域**内做余弦，取 argmax 行；
    3. δ = median(最佳匹配源时刻 − 编辑帧时刻)  （编辑↔原片 1:1 直切语义）；
    4. 一致率 = 与 δ 相差 ≤AGREE_S 的帧占比。
  安全门（防回退，先立后跑）：一致率 ≥AGREE_MIN 且 |δ| ≥MIN_MOVE 才平移主 span，
  否则原样保留。参数：WIN=30, AGREE_MIN=0.5, AGREE_S=1.5, MIN_MOVE=1.0。

评估门槛（续32 立项章程）：
  - 8 条真口袋（`work/combo_pocket_retest_gt130/index.json` 中生产未命中的 8 条）
    截等长主 span 严格命中 ≥3/8；
  - 全量严格 130 **零回退**；导出实得 107 读数对照；负例误报不增。

产物 `work/inscene_refine_probe/`（report.json + 翻转行读图拼图）。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_inscene_refine.py
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

OUT = BENCH / "work" / "inscene_refine_probe"
POCKETS = BENCH / "work" / "combo_pocket_retest_gt130" / "index.json"
CASES = [("2mkv", "datasets/real/ground_truth_v4.json",
          "work/fastglobal_default_2mkv.results.json"),
         ("test1", "datasets/real/ground_truth_test1.json",
          "work/fastglobal_default_test1.results.json"),
         ("test2", "datasets/real/ground_truth_test2.json",
          "work/fastglobal_default_test2.results.json"),
         ("test3", "datasets/real/ground_truth_test3.json",
          "work/fastglobal_default_test3.results.json")]
WIN, AGREE_MIN, AGREE_S, MIN_MOVE = 30.0, 0.5, 1.5, 1.0
ED_MAX_FRAMES, ED_FPS = 10, 2.0
PROD_MISS_POCKETS = [("2mkv", "p02"), ("2mkv", "p03"), ("2mkv", "p20"), ("2mkv", "p30"),
                     ("2mkv", "p34"), ("test1", "t1r14c"), ("test2", "t2r06c"),
                     ("test3", "t3r02c")]


def ed_times(rs0: float, rs1: float) -> list[float]:
    dur = rs1 - rs0
    n = max(2, min(ED_MAX_FRAMES, int(dur * ED_FPS)))
    return [rs0 + dur * (i + 0.5) / n for i in range(n)]


def refine_result(fio, ed_path, b, r, embed):
    """返回 (delta, agree, n_frames) 或 None(未动)。"""
    orig = r.get("original") or {}
    if "candidate_start" not in orig:
        return None
    edseg = r.get("edited_segment") or {}
    rs0, rs1 = edseg.get("start"), edseg.get("end")
    cs, ce = orig["candidate_start"], orig["candidate_end"]
    if rs1 is None or rs1 <= rs0 or ce <= cs:
        return None
    center = (cs + ce) / 2
    lo, hi = center - WIN, center + WIN
    mask = (b.times >= lo) & (b.times <= hi)
    if not mask.any():
        return None
    sub_t = b.times[mask]
    sub_f = b.features[mask]
    offs = []
    for et in ed_times(rs0, rs1):
        frame = fio.grab_frame(ed_path, et)
        emb = embed(frame)
        sims = sub_f @ emb
        k = int(np.argmax(sims))
        offs.append(float(sub_t[k]) - et)
    med = statistics.median(offs)
    agree = sum(1 for o in offs if abs(o - med) <= AGREE_S) / len(offs)
    # 修正量 = 实测绝对偏移 − 主 span 隐含偏移（cs−rs0）。首跑教训：med 本身是绝对映射
    # 常数（正确行上 ≈ cs−rs0，可达数千秒），直接当平移量会把整段打飞。
    delta = med - (cs - rs0)
    if agree < AGREE_MIN or abs(delta) < MIN_MOVE:
        return (med, agree, len(offs), 0.0)
    return (med, agree, len(offs), round(delta, 2))


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

    pocket_set = set(PROD_MISS_POCKETS)
    report = {"params": {"WIN": WIN, "AGREE_MIN": AGREE_MIN,
                         "AGREE_S": AGREE_S, "MIN_MOVE": MIN_MOVE},
              "cases": []}
    flips = []
    for case, gt_rel, ours_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        b = svc.store.load_index(src)
        moved = 0
        for r in raw["results"]:
            res = refine_result(fio, ed, b, r, embed)
            if res is None:
                continue
            med, agree, n, delta = res
            orig = r["original"]
            r.setdefault("_probe", {})
            r["_probe"] = {"median_off": round(med, 2), "agree": round(agree, 2),
                           "n_frames": n, "applied": delta}
            if delta:
                orig["candidate_start"] = round(orig["candidate_start"] + delta, 3)
                orig["candidate_end"] = round(orig["candidate_end"] + delta, 3)
                moved += 1
        # 评估：严格（全 span）+ 导出实得（仅主 span）+ 截等长
        with contextlib.redirect_stdout(io.StringIO()):
            m_new = evaluate(gt, raw["results"])
            m_new_export = evaluate(gt, truncate_main(raw)["results"])
        # 每口袋截等长命中
        with contextlib.redirect_stdout(io.StringIO()):
            per = {x["id"]: x["mark"] for x in m_new_export["per_pos"]}
        pk = {pid: per.get(pid) for c, pid in PROD_MISS_POCKETS if c == case}
        rep = {"case": case, "moved": moved, "n_results": len(raw["results"]),
               "strict": m_new["strict_hit"], "n_pos": m_new["n_pos"],
               "export": m_new_export["strict_hit"],
               "fp": m_new["fp"],
               "pockets": pk}
        report["cases"].append(rep)
        print("[%-5s] moved %d/%d | 严格 %d/%d | 导出实得 %d/%d | 口袋 %s" % (
            case, moved, len(raw["results"]), m_new["strict_hit"], m_new["n_pos"],
            m_new_export["strict_hit"], m_new["n_pos"], pk), flush=True)
        raw_out = BENCH / "work" / f"inscene_refine_{case}.results.json"
        raw_out.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        # 收集截等长翻转行供读图（新 HIT 且旧非 HIT / 反之）
        old_raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        with contextlib.redirect_stdout(io.StringIO()):
            old_export = {x["id"]: x["mark"]
                          for x in evaluate(gt, truncate_main(old_raw)["results"])["per_pos"]}
        for pid, mk in pk.items():
            old_mk = old_export.get(pid)
            if mk != old_mk:
                p = next(x for x in gt["positives"] if x["id"] == pid)
                flips.append({"case": case, "id": pid, "old": old_mk, "new": mk,
                              "gt_ed": p["edited"], "gt_og": p["original"]})
        # 翻转行读图行构造
    tot_s = sum(c["strict"] for c in report["cases"])
    tot_n = sum(c["n_pos"] for c in report["cases"])
    tot_e = sum(c["export"] for c in report["cases"])
    tot_fp = sum(c["fp"] for c in report["cases"])
    pk_hits = sum(1 for c in report["cases"] for v in c["pockets"].values() if v == "HIT")
    print("\n=== 汇总: 严格 %d/139 (门=零回退 vs130) | 导出实得 %d/139 (旧107) | "
          "负例 FP %d (旧4) | 口袋 %d/8 (门=≥3) ===" % (tot_s, tot_e, tot_fp, pk_hits))
    report["totals"] = {"strict": tot_s, "export": tot_e, "fp": tot_fp,
                        "pocket_hits": pk_hits}
    # 翻转行读图（多模态铁律）
    if flips:
        rows = []
        for f in flips:
            case = f["case"]
            raw_new = json.loads((BENCH / "work" / f"inscene_refine_{case}.results.json")
                                 .read_text(encoding="utf-8"))
            src = Path(raw_new["original_video"])
            ed = Path(raw_new["edited_video"])
            e0, e1 = f["gt_ed"]
            o0, o1 = f["gt_og"]
            best, span = 0.0, None
            for r in raw_new["results"]:
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
                                 "REFINED %s" % (span,))):
                p = OUT / "frames" / f"{tag}_{cap.split()[0]}.png"
                try:
                    ffmpeg_frame(vid, max(0.0, float(t)), p)
                    cells.append((str(p), [cap, fmt_ts(t)]))
                except Exception:
                    cells.append(None)
            rows.append(cells)
        for i in range(0, len(rows), 4):
            compose_sheet(rows[i:i + 4],
                          OUT / f"flips_{i // 4 + 1}.png",
                          "flips %d-%d: GT_ED | GT_OG | REFINED" % (i + 1, i + 4))
        print("翻转 %d 行 -> %s/flips_*.png" % (len(flips), OUT))
    report["flips"] = flips
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print("产物: %s" % (OUT / "report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
