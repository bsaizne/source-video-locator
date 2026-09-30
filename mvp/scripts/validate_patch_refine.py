# -*- coding: utf-8 -*-
"""patch_refine（形态6 runtime 模块）离线验证（2026-09-30）。

把 runtime 模块 `engine/localization/patch_refine.apply_patch_refine` 直接套在
四片生产结果批上（PatchReranker DML 双输出），与基线对照四口径 + 目标行 + 翻转行读图。

门槛（先立）：严格 ≥130（结构性）| FP ≤4 | 导出实得 ≥107（零回退）| 目标行 t1r14c 修复。
产物 `work/patch_refine_validate/`。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/validate_patch_refine.py
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

sys.stdout.reconfigure(encoding="utf-8")

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend   # noqa: E402
from diagnostics.contact_sheet import compose_sheet   # noqa: E402
from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts  # noqa: E402
from domain.models import Result  # noqa: E402
from engine.localization.patch_refine import apply_patch_refine  # noqa: E402
from infrastructure.config import load_config          # noqa: E402
from measure_shot_recall import evaluate               # noqa: E402

OUT = BENCH / "work" / "patch_refine_validate"
CASES = [("2mkv", "datasets/real/ground_truth_v4.json",
          "work/fastglobal_default_2mkv.results.json"),
         ("test1", "datasets/real/ground_truth_test1.json",
          "work/fastglobal_default_test1.results.json"),
         ("test2", "datasets/real/ground_truth_test2.json",
          "work/fastglobal_default_test2.results.json"),
         ("test3", "datasets/real/ground_truth_test3.json",
          "work/fastglobal_default_test3.results.json")]
TARGETS = [("test1", "t1r14c"), ("test2", "t2r06c"), ("test3", "t3r02c"),
           ("2mkv", "p30"), ("2mkv", "p34")]


def strip(res):
    res = copy.deepcopy(res)
    for x in res:
        x["original_segments"] = []
        x["alternatives"] = []
    return res


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(parents=True, exist_ok=True)
    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
    from engine.localization.patch_rerank import (PatchReranker, resolve_patch_onnx,
                                                  resolve_weights)
    cfg = svc.config.pipeline
    rr = PatchReranker(resolve_weights(cfg.patch_weights_path or None),
                       resolve_patch_onnx((cfg.patch_onnx_model or "").strip() or None),
                       dml_device_id=svc.config.device.dml_device_id)
    assert rr.ensure(), "patch backend 不可用"
    print("patch backend=%s" % rr.device, flush=True)

    flips, tot = [], {"sb": 0, "ss": 0, "eb": 0, "es": 0, "fb": 0, "fs": 0}
    for case, gt_rel, ours_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / ours_rel).read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        bundle = svc.store.load_index(src)
        post_objs = apply_patch_refine(
            [Result.from_dict(r) for r in copy.deepcopy(raw["results"])],
            edited_path=ed, source_path=src, grab_frame=svc.ffmpeg.grab_frame,
            embed_dual=rr.frame_dual,
            lib_times=np.asarray(bundle.times, dtype=np.float64),
            lib_feats=bundle.features, log=svc._log)
        post = [r.to_dict() for r in post_objs]
        with contextlib.redirect_stdout(io.StringIO()):
            mb_s = evaluate(gt, raw["results"])
            ms_s = evaluate(gt, post)
            mb_e = evaluate(gt, strip(raw["results"]))
            ms_e = evaluate(gt, strip(post))
        tot["sb"] += mb_s["strict_hit"]; tot["ss"] += ms_s["strict_hit"]
        tot["eb"] += mb_e["strict_hit"]; tot["es"] += ms_e["strict_hit"]
        tot["fb"] += mb_e["fp"]; tot["fs"] += ms_e["fp"]
        be = {x["id"]: x["mark"] for x in mb_e["per_pos"]}
        se = {x["id"]: x["mark"] for x in ms_e["per_pos"]}
        for pid in be:
            if be[pid] != se[pid]:
                flips.append({"case": case, "id": pid, "old": be[pid], "new": se[pid]})
        print("[%-5s] 严格 %d→%d | 导出 %d→%d | FP %d→%d" % (
            case, mb_s["strict_hit"], ms_s["strict_hit"],
            mb_e["strict_hit"], ms_e["strict_hit"], mb_e["fp"], ms_e["fp"]), flush=True)
        (BENCH / "work" / f"patchrefine_{case}.results.json").write_text(
            json.dumps(post, ensure_ascii=False), encoding="utf-8")
    print("\n=== 验证: 严格 %d→%d (门≥130) | 导出 %d→%d (门≥107) | FP %d→%d (门≤4) ===" % (
        tot["sb"], tot["ss"], tot["eb"], tot["es"], tot["fb"], tot["fs"]))
    for c, pid in TARGETS:
        m = [f for f in flips if f["case"] == c and f["id"] == pid]
        print("目标 %-5s/%-7s %s" % (c, pid, m[0] if m else "无翻转"))
    print("全部翻转:", flips)
    if flips:
        rows = []
        gts = {c: json.loads((BENCH / g).read_text(encoding="utf-8"))
               for c, g, _ in CASES}
        for f in flips:
            case = f["case"]
            raw0 = json.loads((BENCH / dict((c, o) for c, _, o in CASES)[case])
                              .read_text(encoding="utf-8"))
            src, ed = Path(raw0["original_video"]), Path(raw0["edited_video"])
            p = next(x for x in gts[case]["positives"] if x["id"] == f["id"])
            e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
            best, span = 0.0, None
            for r in json.loads((BENCH / f"work/patchrefine_{case}.results.json")
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
                                 "PR %s" % (span,))):
                pp = OUT / "frames" / f"{tag}_{cap.split()[0]}.png"
                try:
                    ffmpeg_frame(vid, max(0.0, float(t)), pp)
                    cells.append((str(pp), [cap, fmt_ts(t)]))
                except Exception:
                    cells.append(None)
            rows.append(cells)
        for i in range(0, len(rows), 4):
            compose_sheet(rows[i:i + 4], OUT / f"flips_{i // 4 + 1}.png",
                          "patch_refine flips %d-%d: GT_ED | GT_OG | PR"
                          % (i + 1, i + 4))
        print("翻转 %d 行 -> flips_*.png" % len(flips))
    ok = tot["ss"] >= 130 and tot["es"] >= 107 and tot["fs"] <= 4
    print("验收: %s" % ("PASS" if ok else "FAIL"))
    (OUT / "report.json").write_text(json.dumps(
        {"totals": tot, "flips": flips}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    import numpy as np  # noqa
    sys.exit(main())
