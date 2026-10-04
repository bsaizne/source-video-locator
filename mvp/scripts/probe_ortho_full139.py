# -*- coding: utf-8 -*-
"""方案 B 扩验证（续43 拍板选项②）：全 139 正例复算 ISC/dino 峰位命中分布，排除 MISS6 小样本运气。

与 probe_orthogonal_backbone.py 同协议（同扫描窗/判据/主定位来源），区别：
  - 覆盖四份 GT 全部 139 条 positives（2mkv 39 / test1 43 / test2 20 / test3 37）；
  - 只跑两臂：ISC21（信号臂）+ dino CLS（sanity 对照臂）——判据有效性必须看两臂差；
    CLIP 臂砍掉（续43 弱信号 + CPU 慢）；ens 砍掉；
  - 不出 139 张曲线/拼图（按需对分歧案例补图），只落 index.json + stdout 汇总。

读数口径：
  - gt_is_peak：全局峰（±1.5s）落在 GT 窗（与探针同判据）；
  - margin：GT窗内最高 − 主定位处（主定位出窗/占位时为 None，只参与 gt_is_peak）；
  - 桶：aligned（off≤2s，main≈GT，峰命中≈同义反复基线）/ drift（2<off≤15s）/ far（off>15s）/
    nowin（主定位占位或出窗，t2r03b/p30 型）。
  关键读出 = drift+far+nowin 桶（我方定位错）上 ISC 峰命中率 vs dino 峰命中率之差。

跑法：D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_ortho_full139.py
产物：work/orthogonal_backbone_full139/{index.json}；stdout 汇总。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", r"D:\claudework\benchmark\tools\ffmpeg.exe")
os.environ.setdefault("MEDIA_FFPROBE", r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
os.environ.setdefault("SVL_DML_MODEL", r"C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
sys.path.insert(0, str(BENCH / "engines" / "isc21"))

import numpy as np  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from probe_orthogonal_backbone import (  # noqa: E402
    FILM_META, GT_FILE, OURS_BATCH, N_QUERY, MARGIN_GATE, PEAK_TOL,
    IscEmbedder, DinoEmbedder, rep_times,
)

SCAN_STEP = 1.0
SCAN_PAD = 10.0
WIN_CLAMP = 150.0
GT_CLAMP_PAD = 15.0
OUT = BENCH / "work" / "orthogonal_backbone_full139"


def bucket_of(off: float, main_in_window: bool) -> str:
    if not main_in_window:
        return "nowin"
    if off <= 2.0:
        return "aligned"
    if off <= 15.0:
        return "drift"
    return "far"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    from app.locator_service import SourceLocatorService
    from device.directml_backend import DirectMLBackend
    from infrastructure.config import load_config
    from engine.localization.patch_rerank import PatchReranker, resolve_patch_onnx, resolve_weights

    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend)
    print("BACKEND_SELECTED type=%s" % type(srv.backend).__name__, flush=True)
    rr = PatchReranker(resolve_weights(cfg.pipeline.patch_weights_path or None),
                       resolve_patch_onnx((cfg.pipeline.patch_onnx_model or "").strip() or None),
                       dml_device_id=cfg.device.dml_device_id)
    assert rr.ensure() and rr.device == "dml"
    print("building isc (DML) + dino (DML) ...", flush=True)
    isc = IscEmbedder()
    dino = DinoEmbedder(rr)
    arms = {"isc": isc, "dino": dino}

    def gt_case(film, gid):
        gt = json.loads((BENCH / "datasets/real" / GT_FILE[film]).read_text(encoding="utf-8"))
        for p in gt["positives"]:
            if p["id"] == gid:
                return p
        raise KeyError(f"{film}/{gid}")

    def ours_main_mid(film, p):
        res = json.loads((BENCH / OURS_BATCH.format(film=film)).read_text(encoding="utf-8"))["results"]
        e0, e1 = p["edited"]
        cands = [r for r in res
                 if min(e1, r["edited_segment"]["end"]) - max(e0, r["edited_segment"]["start"]) > 0]
        if not cands:
            return None
        cands.sort(key=lambda r: -(min(e1, r["edited_segment"]["end"])
                                  - max(e0, r["edited_segment"]["start"])))
        o = cands[0]["original"]
        return (o["candidate_start"] + o["candidate_end"]) / 2.0

    plan = []
    for film in FILM_META:
        gt = json.loads((BENCH / "datasets/real" / GT_FILE[film]).read_text(encoding="utf-8"))
        for p in gt["positives"]:
            plan.append((film, p["id"]))
    total = len(plan)
    print(f"total positives = {total}", flush=True)

    index = []
    t_start = time.time()
    for k, (film, gid) in enumerate(plan):
        p = gt_case(film, gid)
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        gt_mid = (o0 + o1) / 2.0
        ed_vid, og_vid = FILM_META[film]
        main_mid = ours_main_mid(film, p)
        if main_mid is None:
            main_in_window = False
            lo, hi = max(0.0, o0 - GT_CLAMP_PAD), o1 + GT_CLAMP_PAD
            off = None
        else:
            off = abs(main_mid - gt_mid)
            lo = max(0.0, min(o0, main_mid) - SCAN_PAD)
            hi = max(o1, main_mid) + SCAN_PAD
            if hi - lo > WIN_CLAMP:
                lo, hi = max(0.0, o0 - GT_CLAMP_PAD), o1 + GT_CLAMP_PAD
                main_in_window = False
            else:
                main_in_window = lo <= main_mid <= hi
        scan_t = [round(float(t), 2) for t in np.arange(lo, hi, SCAN_STEP)]

        q_times = rep_times(e0, e1)
        q_frames = [srv.ffmpeg.grab_frame(ed_vid, t) for t in q_times]
        qembs = {a: [arms[a].embed(q) for q in q_frames] for a in arms}
        raw = {a: [] for a in arms}
        for t in scan_t:
            f = srv.ffmpeg.grab_frame(og_vid, t)
            for a in arms:
                se = arms[a].embed(f)
                raw[a].append((t, round(float(np.mean([qe @ se for qe in qembs[a]])), 4)))

        row = {"id": gid, "film": film,
               "gt_win": [round(o0, 2), round(o1, 2)], "gt_mid": round(gt_mid, 2),
               "main_mid": None if main_mid is None else round(main_mid, 2),
               "offset": None if off is None else round(off, 2),
               "bucket": bucket_of(off if off is not None else 1e9, main_in_window),
               "main_in_window": bool(main_in_window), "n_scan": len(scan_t)}
        for a in arms:
            curve = raw[a]
            gt_sc = max((c for c in curve if o0 - 1.0 <= c[0] <= o1 + 1.0),
                        key=lambda c: c[1], default=None)
            main_sc = (min(curve, key=lambda c: abs(c[0] - main_mid))
                       if curve and main_in_window else None)
            peak = max(curve, key=lambda c: c[1]) if curve else None
            margin = (round(gt_sc[1] - main_sc[1], 4) if gt_sc and main_sc else None)
            row[a] = {
                "gt_score": gt_sc[1] if gt_sc else None,
                "main_score": main_sc[1] if main_sc else None,
                "peak_t": peak[0] if peak else None,
                "peak_score": peak[1] if peak else None,
                "margin_gt_minus_main": margin,
                "gt_is_peak": bool(gt_sc and peak and abs(gt_sc[0] - peak[0]) <= PEAK_TOL),
                "gt_gt_main": bool(margin is not None and margin > MARGIN_GATE),
            }
        index.append(row)
        print(f"[{k+1}/{total}] {row['bucket']:7s} {gid:9s} off={row['offset']} "
              f"isc_peak={int(row['isc']['gt_is_peak'])} dino_peak={int(row['dino']['gt_is_peak'])} "
              f"isc_m={row['isc']['margin_gt_minus_main']}", flush=True)
        if (k + 1) % 20 == 0:
            el = time.time() - t_start
            print(f"  ... {k+1}/{total} elapsed {el/60:.1f}min eta {el/(k+1)*(total-k-1)/60:.1f}min",
                  flush=True)

    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2),
                                    encoding="utf-8")

    print("\n==== 汇总：gt_is_peak（全局峰落 GT±1.5s）====", flush=True)
    for b in ("aligned", "drift", "far", "nowin", "ALL"):
        sub = [r for r in index if b == "ALL" or r["bucket"] == b]
        if not sub:
            continue
        line = f"{b:8s} n={len(sub):3d} "
        for a in arms:
            hit = sum(1 for r in sub if r[a]["gt_is_peak"])
            line += f"| {a} {hit}/{len(sub)} "
        # 两臂配对分歧
        both = sum(1 for r in sub if r["isc"]["gt_is_peak"] and r["dino"]["gt_is_peak"])
        isc_only = sum(1 for r in sub if r["isc"]["gt_is_peak"] and not r["dino"]["gt_is_peak"])
        dino_only = sum(1 for r in sub if r["dino"]["gt_is_peak"] and not r["isc"]["gt_is_peak"])
        neither = sum(1 for r in sub if not r["isc"]["gt_is_peak"] and not r["dino"]["gt_is_peak"])
        line += f"| 配对: 双中{both} 仅ISC{isc_only} 仅dino{dino_only} 双缺{neither}"
        print(line, flush=True)
    print("\n==== margin>0.02（gt>main，仅主定位在窗内案例）====", flush=True)
    for b in ("aligned", "drift", "far", "ALL"):
        sub = [r for r in index if (b == "ALL" or r["bucket"] == b) and r["main_in_window"]]
        if not sub:
            continue
        line = f"{b:8s} n={len(sub):3d} "
        for a in arms:
            hit = sum(1 for r in sub if r[a]["gt_gt_main"])
            line += f"| {a} {hit}/{len(sub)} "
        print(line, flush=True)
    print("\n==== 我方定位错（drift+far+nowin，核心判别桶）====", flush=True)
    sub = [r for r in index if r["bucket"] in ("drift", "far", "nowin")]
    for a in arms:
        hit = sum(1 for r in sub if r[a]["gt_is_peak"])
        print(f"{a}: {hit}/{len(sub)} gt_is_peak", flush=True)
    isc_miss = [f"{r['film']}:{r['id']}(off={r['offset']})"
                for r in sub if not r["isc"]["gt_is_peak"]]
    print("ISC 未中名单:", ", ".join(isc_miss) if isc_miss else "（无）", flush=True)
    print("DONE elapsed=%.1fmin" % ((time.time() - t_start) / 60), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
