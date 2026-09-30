# -*- coding: utf-8 -*-
"""(E) 立项 · 形态2：段内分镜 × 逐镜 span（2026-09-30，无 GT 反标，零 runtime）。

形态1（`probe_inscene_refine.py`，主 span 中位数偏移平移）结论：严格 130 零回退 ✓、
导出实得 107→113、但口袋 1/8 未达门槛；诊断 = 口袋多住在**多镜头编辑段**里
（2mkv s0 一段盖 3 个 GT 行，帧间偏移散射一致率 0.29；test3 s3 = 0.11），
单 span 平移会 p01↔p02 拆东补西。⇒ 形态2 换粒度：

  1. 编辑窗内 4fps 采帧（≤40），生产 CLS（DML 硬断言）逐帧嵌入；
  2. 相邻帧余弦 < CUT_THR(0.55) 判切割 → 分镜（run <2 帧并入前镜）；
  3. 逐镜：各帧与索引 1fps 特征在主 span 中心 ±WIN(30s) 内 argmax，
     δ = median(argmax−et) − (cs−rs0)（形态1 教训：减掉隐含偏移）；
     一致率 ≥0.5 且镜内帧 ≥2 才产出该镜 span；
  4. 产出 span = 主 span 平移 δ 后裁到该镜编辑区间，**追加为子 span**
     （与既有 main/sub IoU≥0.8 的去重不追加）。

安全性（结构性）：主 span 不动 ⇒ 导出实得不变；只处理主 span 非空的段 ⇒
拒识负例（空 span）无新暴露面；子 span 只增不减 ⇒ 严格不可能回退。
门槛不变：8 条口袋 ≥3/8（此形态下严格门自动满足，仍复核）。

产物 `work/inscene_refine_pershot/`。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_inscene_refine_pershot.py
"""
from __future__ import annotations

import contextlib
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
from infrastructure.config import load_config          # noqa: E402
from media.ffmpeg import FFmpegIO                      # noqa: E402
from measure_shot_recall import evaluate               # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = BENCH / "work" / "inscene_refine_pershot"
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


def iou(a0, a1, b0, b1):
    inter = max(0.0, min(a1, b1) - max(a0, b0))
    uni = max(a1, b1) - min(a0, b0)
    return inter / uni if uni > 1e-9 else 0.0


def shots_of(ets, embs):
    """相邻余弦切分镜；返回 [(起,止)] 编辑时刻区间。"""
    cuts = [0]
    for i in range(1, len(ets)):
        c = float(embs[i - 1] @ embs[i])
        if c < CUT_THR:
            cuts.append(i)
    cuts.append(len(ets))
    out = []
    for a, b in zip(cuts[:-1], cuts[1:]):
        if b - a < 2 and out:            # 短 run 并入前镜
            out[-1] = (out[-1][0], ets[b - 1])
            continue
        if b - a < 2 and not out:
            continue
        out.append((ets[a], ets[b - 1]))
    if out:
        out[-1] = (out[-1][0], ets[-1])  # 末镜补齐到窗尾
    return out


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

    report = {"params": {"WIN": WIN, "CUT_THR": CUT_THR, "AGREE_MIN": AGREE_MIN,
                         "SHOT_FPS": SHOT_FPS}, "cases": []}
    for case, gt_rel, ours_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        b = svc.store.load_index(src)
        n_added = 0
        for r in raw["results"]:
            orig = r.get("original") or {}
            cs, ce = orig.get("candidate_start"), orig.get("candidate_end")
            edseg = r.get("edited_segment") or {}
            rs0, rs1 = edseg.get("start"), edseg.get("end")
            if cs is None or ce is None or ce - cs <= 0.01 or rs1 - rs0 <= 0.01:
                continue                                   # 含 not_in_source：不加 span
            dur = rs1 - rs0
            n = max(2, min(SHOT_MAX, int(dur * SHOT_FPS)))
            ets = [rs0 + dur * (i + 0.5) / n for i in range(n)]
            embs = []
            for et in ets:
                embs.append(embed(fio.grab_frame(ed, et)))
            lo, hi = (cs + ce) / 2 - WIN, (cs + ce) / 2 + WIN
            mask = (b.times >= lo) & (b.times <= hi)
            if not mask.any():
                continue
            sub_t, sub_f = b.times[mask], b.features[mask]
            implied = cs - rs0
            added = []
            for s0, s1 in shots_of(ets, embs):
                idx = [i for i, t in enumerate(ets) if s0 <= t <= s1]
                if len(idx) < 2:
                    continue
                offs = [float(sub_t[int(np.argmax(sub_f @ embs[i]))]) - ets[i]
                        for i in idx]
                med = statistics.median(offs)
                agree = sum(1 for o in offs if abs(o - med) <= 1.5) / len(offs)
                delta = med - implied
                if agree < AGREE_MIN or abs(delta) < 0.5:
                    r.setdefault("_pershot", []).append(
                        {"shot": [round(s0, 2), round(s1, 2)], "delta": round(delta, 2),
                         "agree": round(agree, 2), "applied": False})
                    continue
                a0 = cs + delta + (s0 - rs0)
                a1 = cs + delta + (s1 - rs0) + (1.0 / SHOT_FPS)
                if any(iou(a0, a1, x[0], x[1]) >= 0.8 for x in
                       [(cs, ce)] + [(s["candidate_start"], s["candidate_end"])
                                     for s in r.get("original_segments") or []]):
                    continue
                added.append({"candidate_start": round(a0, 3),
                              "candidate_end": round(a1, 3),
                              "source": "inscene_pershot"})
                r.setdefault("_pershot", []).append(
                    {"shot": [round(s0, 2), round(s1, 2)], "delta": round(delta, 2),
                     "agree": round(agree, 2), "applied": True,
                     "span": [round(a0, 2), round(a1, 2)]})
            if added:
                r.setdefault("original_segments", []).extend(added)
                n_added += len(added)
        with contextlib.redirect_stdout(io.StringIO()):
            m = evaluate(gt, raw["results"])
        per = {x["id"]: x["mark"] for x in m["per_pos"]}
        main_per = {x["id"]: x["main_hit"] for x in m["per_pos"]}
        pk = {pid: per.get(pid) for c, pid in PROD_MISS_POCKETS if c == case}
        rep = {"case": case, "added": n_added, "strict": m["strict_hit"],
               "n_pos": m["n_pos"], "fp": m["fp"],
               "main_hit": sum(main_per.values()), "pockets": pk}
        report["cases"].append(rep)
        print("[%-5s] +%d 子span | 严格 %d/%d | main_hit %d/%d | FP %d | 口袋 %s" % (
            case, n_added, m["strict_hit"], m["n_pos"], sum(main_per.values()),
            m["n_pos"], m["fp"], pk), flush=True)
        (BENCH / "work" / f"inscene_pershot_{case}.results.json").write_text(
            json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    tot_s = sum(c["strict"] for c in report["cases"])
    tot_m = sum(c["main_hit"] for c in report["cases"])
    tot_fp = sum(c["fp"] for c in report["cases"])
    pk_hits = sum(1 for c in report["cases"] for v in c["pockets"].values() if v == "HIT")
    print("\n=== 形态2汇总: 严格 %d/139 (基线130) | main_hit(导出实得) %d/139 (基线107) | "
          "FP %d (基线4) | 口袋 %d/8 (门=≥3) ===" % (tot_s, tot_m, tot_fp, pk_hits))
    report["totals"] = {"strict": tot_s, "main_hit": tot_m, "fp": tot_fp,
                        "pocket_hits": pk_hits}
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print("产物: %s" % (OUT / "report.json"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
