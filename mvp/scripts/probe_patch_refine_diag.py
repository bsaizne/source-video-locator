# -*- coding: utf-8 -*-
"""诊断：4 行未翻转的精确卡点（歧义门 or margin 不足，2026-09-30）。

对每行父段打印：top1 簇距现主、s1/s2（CLS 门输入）、patch margin、seq margin。
产物 work/patch_refine_diag.json。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_patch_refine_diag.py
"""
from __future__ import annotations

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
from infrastructure.config import load_config          # noqa: E402
from domain.models import Result                       # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

ROWS = [("test2", "t2r06c"), ("test3", "t3r02c"), ("2mkv", "p30"), ("2mkv", "p34")]
SRC_OF = {"2mkv": "work/fastglobal_default_2mkv.results.json",
          "test1": "work/fastglobal_default_test1.results.json",
          "test2": "work/fastglobal_default_test2.results.json",
          "test3": "work/fastglobal_default_test3.results.json"}
W_GLOBAL, W_PATCH, N_QUERY = 0.45, 0.55, 5


def patch_score(qp, pp):
    m = (qp @ pp.T).max(axis=1)
    return float(np.sort(m)[-min(100, len(m)):].mean())


def main() -> int:
    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend)
    from engine.localization.patch_rerank import (PatchReranker, resolve_patch_onnx,
                                                  resolve_weights)
    cfg = svc.config.pipeline
    rr = PatchReranker(resolve_weights(cfg.patch_weights_path or None),
                       resolve_patch_onnx((cfg.patch_onnx_model or "").strip() or None),
                       dml_device_id=svc.config.device.dml_device_id)
    assert rr.ensure()
    gts = {c: json.loads((BENCH / g).read_text(encoding="utf-8"))
           for c, g in [("test2", "datasets/real/ground_truth_test2.json"),
                        ("test3", "datasets/real/ground_truth_test3.json"),
                        ("2mkv", "datasets/real/ground_truth_v4.json")]}
    out = []
    for case, pid in ROWS:
        gt = gts[case]
        raw = json.loads((BENCH / SRC_OF[case]).read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        bundle = svc.store.load_index(src)
        lib_t = np.asarray(bundle.times, dtype=np.float64)
        lib_f = bundle.features
        p = next(x for x in gt["positives"] if x["id"] == pid)
        e0, e1, o0, o1 = p["edited"][0], p["edited"][1], p["original"][0], p["original"][1]
        w = e1 - e0
        # 生产现主 span（按编辑窗最大重叠映射）——不是 GT 窗（这几行正是二者不同的行）
        best_ov, main_span = 0.0, None
        for r in raw["results"]:
            re0, re1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            ov = min(e1, re1) - max(e0, re0)
            if ov > best_ov:
                best_ov = ov
                org = r.get("original") or {}
                if "candidate_start" in org:
                    main_span = (org["candidate_start"], org["candidate_end"])
        assert main_span, (case, pid)
        q_ets = [e0 + w * (i + 0.5) / N_QUERY for i in range(N_QUERY)]
        q_cls, q_patch = [], []
        for et in q_ets:
            c, pp = rr.frame_dual(svc.ffmpeg.grab_frame(ed, float(et)))
            q_cls.append(np.asarray(c, dtype=np.float64))
            q_patch.append(np.asarray(pp, dtype=np.float64))
        q_mean = np.mean(q_cls, axis=0)
        q_mean = q_mean / max(1e-8, float(np.linalg.norm(q_mean)))
        sims = lib_f @ q_mean
        order = np.argsort(-sims)
        mids = []
        for ti in order:
            t = float(lib_t[ti])
            if all(abs(t - m) >= 3.0 for m in mids):
                mids.append(t)
                if len(mids) >= 5:
                    break
        main_mid = (main_span[0] + main_span[1]) / 2
        near_top1 = min(abs(m - main_mid) for m in mids[:2])
        s1 = float(np.max(lib_f[np.argmin(np.abs(lib_t - mids[0]))] @ q_mean))
        s2 = float(np.max(lib_f[np.argmin(np.abs(lib_t - mids[1]))] @ q_mean)) \
            if len(mids) > 1 else 0.0
        gate_skipped = abs(mids[0] - main_mid) <= 2.0 and (s1 - s2) >= 0.03

        def local_peak(mid):
            best = -1.0
            g0, g1 = max(0.0, mid - 5.0), mid + 5.0
            for k in range(11):
                t = g0 + (g1 - g0) * (k + 0.5) / 11
                c, pp = rr.frame_dual(svc.ffmpeg.grab_frame(src, float(t)))
                c = np.asarray(c, dtype=np.float64)
                pp = np.asarray(pp, dtype=np.float64)
                s = (W_GLOBAL * float(np.mean([c @ q for q in q_cls]))
                     + W_PATCH * float(np.mean([patch_score(qp, pp) for qp in q_patch])))
                best = max(best, s)
            return best

        main_peak = local_peak(main_mid)
        gt_peak = local_peak((o0 + o1) / 2)
        patch_margin = gt_peak - main_peak
        S_q = np.stack(q_cls) @ lib_f.T

        def vote(mid):
            dm = mid - (e0 + e1) / 2
            vals = []
            for i, et in enumerate(q_ets):
                m = np.abs(lib_t - (et + dm)) <= 1.0
                if m.any():
                    vals.append(float(np.max(S_q[i][m])))
            return float(np.mean(vals)) if vals else 0.0

        seq_margin = vote(main_mid) - vote(main_mid)  # GT 窗已=锚, 记门输入即可
        rec = {"case": case, "id": pid, "main_mid": round(main_mid, 1),
               "clusters": [round(m, 1) for m in mids],
               "near_top1": round(near_top1, 2), "s1": round(s1, 4),
               "s2": round(s2, 4), "gate_skipped": gate_skipped,
               "main_patch_peak": round(main_peak, 4),
               "gt_patch_peak": round(gt_peak, 4),
               "patch_margin_gt_vs_main": round(patch_margin, 4),
               "prod_main": [round(main_span[0],1), round(main_span[1],1)]}
        out.append(rec)
        print("[%-5s %-7s] 门跳过=%s (top1距主=%.1f s1-s2=%.3f) | patch峰: 主区=%.3f "
              "GT区=%.3f margin=%+.3f" % (case, pid, gate_skipped, near_top1,
                                          s1 - s2, main_peak, gt_peak,
                                          patch_margin), flush=True)
    (BENCH / "work" / "patch_refine_diag.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
