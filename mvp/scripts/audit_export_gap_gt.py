"""20 行导出缺口 GT 逐帧复核（2026-10-01 续38，零 runtime / 零 GT 改动）。

对象 = 现役基线（两旋钮开 `work/spl_patch_arms/on_*.results.json`）导出实得（仅主 span）未中的 20 行。
两路证据（同 2026-09-30 GT 工单裁决链）：
  1. **检索判别**：ED 窗内 3 帧（25/50/75%）→ 生产 CLS（DML 硬断言）→ 原片 1fps 索引 top-20，
     记 GT 窗 / 我方主 span 窗的最佳名次（窗两侧各 1s 容差）；三帧多数决出 verdict：
       OURS 在 & GT 不在 ⇒ GT 疑错；都在 ⇒ 同源重复/同场景；只 GT 在 ⇒ 我方错；都不在 ⇒ 特征盲/插入镜头。
  2. **读图**：每行 7 格 = ED×3 | GT 窗×2（首/尾）| 我方主 span×2（首/尾），`work/gap_gt_audit/sheet_*.png`。
裁决只出工单，**不改 GT**（改需用户逐条确认，另建文件）。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/audit_export_gap_gt.py
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.stdout.reconfigure(encoding="utf-8")

import numpy as np  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend   # noqa: E402
from diagnostics.contact_sheet import compose_sheet   # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402
from infrastructure.config import load_config          # noqa: E402

OUT = BENCH / "work" / "gap_gt_audit"
METRICS = BENCH / "work" / "spl_patch_arms" / "metrics_on.json"
CASES = {"2mkv": "datasets/real/ground_truth_v4.json",
         "test1": "datasets/real/ground_truth_test1.json",
         "test2": "datasets/real/ground_truth_test2.json",
         "test3": "datasets/real/ground_truth_test3.json"}
TOPK, PAD, ROWS_PER_SHEET = 20, 1.0, 3


def _rank(times, order, w0, w1):
    for k, row in enumerate(order[:TOPK]):
        if w0 - PAD <= float(times[row]) <= w1 + PAD:
            return k + 1
    return None


def _verdict(gr, orank):
    if orank is not None and gr is None:
        return "GT疑错"
    if orank is not None and gr is not None:
        return "同源/同场景"
    if gr is not None:
        return "我方错"
    return "特征盲"


def _main_span(res, e0, e1):
    best, span = 0.0, None
    for r in res:
        ov = min(e1, r["edited_segment"]["end"]) - max(e0, r["edited_segment"]["start"])
        o = r["original"]
        if ov > best and o["candidate_end"] - o["candidate_start"] > 0.01:
            best, span = ov, (o["candidate_start"], o["candidate_end"], r["confidence"])
    return span


def _cell(video, t, cap, tag):
    p = OUT / "frames" / f"{tag}.png"
    try:
        ffmpeg_frame(video, max(0.0, float(t)), p)
        return (str(p), [cap, fmt_ts(t)])
    except Exception as exc:  # noqa: BLE001
        return (None, [f"{cap} 取帧失败 {exc}", ""])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(exist_ok=True)
    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
    print("BACKEND_SELECTED=%s" % type(svc.backend).__name__, flush=True)
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    gap = {c["label"]: [p["id"] for p in c["per_pos"] if not p["main_hit"]]
           for c in metrics["rows"]}

    out_rows, sheet_rows = [], []
    for case, gt_rel in CASES.items():
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / f"work/spl_patch_arms/on_{case}.results.json")
                         .read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        b = svc.store.load_index(src)
        times = np.asarray(b.times, dtype=np.float64)
        mark = {p["id"]: p["mark"] for c in metrics["rows"] if c["label"] == case
                for p in c["per_pos"]}
        for p in gt["positives"]:
            if p["id"] not in gap[case]:
                continue
            e0, e1 = p["edited"]
            o0, o1 = p["original"]
            ms = _main_span(raw["results"], e0, e1)
            a0, a1, conf = ms if ms else (None, None, None)
            ets = [e0 + (e1 - e0) * f for f in (0.25, 0.5, 0.75)]
            frames = svc._grab_frames_parallel(ed, ets)
            embs = svc.backend.embed_frames(frames)
            per = []
            for emb in embs:
                emb = emb / max(1e-8, float(np.linalg.norm(emb)))
                order = np.argsort(-(b.features @ emb))
                gr = _rank(times, order, o0, o1)
                orank = _rank(times, order, a0, a1) if ms else None
                per.append({"gt_rank": gr, "ours_rank": orank,
                            "top1": round(float(times[order[0]]), 1),
                            "verdict": _verdict(gr, orank)})
            v = Counter(x["verdict"] for x in per).most_common(1)[0][0]
            row = {"case": case, "id": p["id"], "tier": p["tier"], "strict_mark": mark[p["id"]],
                   "ed": [e0, e1], "gt_og": [o0, o1],
                   "ours_main": [a0, a1] if ms else None, "conf": conf,
                   "offset_s": round(((a0 + a1) - (o0 + o1)) / 2, 1) if ms else None,
                   "per_frame": per, "verdict": v, "note": p.get("note", "")}
            out_rows.append(row)
            print("%-5s %-7s %-4s off=%-7s GTrank=%-12s OURSrank=%-12s => %s" % (
                case, p["id"], mark[p["id"]], row["offset_s"],
                [x["gt_rank"] for x in per], [x["ours_rank"] for x in per], v), flush=True)
            tag = f"{case}_{p['id']}"
            cells = [_cell(ed, t, f"{p['id']} ED {i + 1}/3", f"{tag}_ed{i}")
                     for i, t in enumerate(ets)]
            cells += [_cell(src, o0 + 0.1, f"GT {o0:.1f}-{o1:.1f} 首", f"{tag}_g0"),
                      _cell(src, max(o0, o1 - 0.1), "GT 尾", f"{tag}_g1")]
            if ms:
                cells += [_cell(src, a0 + 0.1, f"OURS {a0:.1f}-{a1:.1f} {conf} 首", f"{tag}_o0"),
                          _cell(src, max(a0, a1 - 0.1), "OURS 尾", f"{tag}_o1")]
            sheet_rows.append(cells)
    for i in range(0, len(sheet_rows), ROWS_PER_SHEET):
        sub = out_rows[i:i + ROWS_PER_SHEET]
        compose_sheet(sheet_rows[i:i + ROWS_PER_SHEET], OUT / f"sheet_{i // ROWS_PER_SHEET + 1:02d}.png",
                      "export-gap GT audit: ED x3 | GT first/last | OURS first/last   " +
                      ", ".join(f"{r['case']}/{r['id']}" for r in sub))
    (OUT / "audit.json").write_text(json.dumps(out_rows, ensure_ascii=False, indent=1),
                                    encoding="utf-8")
    print("\n分布: %s" % dict(Counter(r["verdict"] for r in out_rows)))
    print("产物 -> %s (%d 行, %d 张拼图)" % (OUT, len(out_rows),
                                        (len(sheet_rows) + ROWS_PER_SHEET - 1) // ROWS_PER_SHEET))
    return 0


if __name__ == "__main__":
    sys.exit(main())
