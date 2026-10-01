"""probe_inwindow_peak — 主 span「窗内峰位移」探针（2026-10-01 续37，零 runtime 改动）。

假设：`patch_refine.apply_patch_refine` 对每个候选算 ±5s 网格峰分 ``peak_s`` 但**丢弃峰位置**，
只能在相距 ≥3s 的 CLS 聚簇中心之间切换；竞品 `fast_timeline.local_refiner` 语义是「局部窗口
**移动起点** + 多帧 patch 精排」。13 行「严格 HIT / 主 span 未中」中 9 行是同场景主 span 偏 2.5~8.5s
⇒ 若 GT 峰就在现主自己的窗内，修法 = 记录窗内峰位置并平移主 span，**零新增推理形态**。

两形态（同一网格帧、同一 0.45/0.55 融合分、同一 SWITCH_MARGIN=0.05，不扫参）：
  A peak  : 窗内各网格帧对 5 查询帧的平均分，取 argmax 时刻；
  B align : 偏移 δ 下查询帧 i 对位原片 m+δ+dq_i（保持编辑侧时序），取 argmax δ。
均为「多查询聚合分」的窗内峰，非 per-query 单帧 argmax。移动后老主降为首子 span（与
patch_refine 同构 ⇒ 严格口径结构性零回退）。

输入 = 现役基线结果批 `work/spl_patch_arms/on_{case}.results.json`（两旋钮开）。
产物 `work/inwindow_peak_probe/`（report.json + 翻转行读图 flips_*.png）。
Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_inwindow_peak.py
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

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
from engine.localization.patch_refine import (N_QUERY, PATCH_TOPK, REFINE_WIN_S,  # noqa: E402
                                              SWITCH_MARGIN, W_GLOBAL, W_PATCH)
from infrastructure.config import load_config          # noqa: E402
from measure_shot_recall import evaluate               # noqa: E402

OUT = BENCH / "work" / "inwindow_peak_probe"
CASES = [("2mkv", "datasets/real/ground_truth_v4.json"),
         ("test1", "datasets/real/ground_truth_test1.json"),
         ("test2", "datasets/real/ground_truth_test2.json"),
         ("test3", "datasets/real/ground_truth_test3.json")]
GRID_FPS = 2.0
POOL = {"p08", "p34", "p40", "t1r13a", "t1r14a", "t1r22", "t1r25",
        "t2r02b", "t2r06c", "t2r07c", "t3r02a", "t3r02c", "t3r10"}


def _fused(q_cls, q_patch, c, pp):
    """查询帧 i × 一网格帧 → (N_QUERY,) 融合分（与 patch_refine 同式，单帧不再求均）。"""
    g = q_cls @ c                                           # (N,)
    m = (q_patch.reshape(-1, q_patch.shape[-1]) @ pp.T).max(axis=1)
    m = m.reshape(q_patch.shape[0], -1)                     # (N, 1369)
    k = min(PATCH_TOPK, m.shape[1])
    p = np.sort(m, axis=1)[:, -k:].mean(axis=1)
    return W_GLOBAL * g + W_PATCH * p


def _shift(r: dict, dt: float) -> dict:
    """主 span 平移 dt（等宽），老主降为首子 span（与 patch_refine 同构）。"""
    r = copy.deepcopy(r)
    a, b = r["original"]["candidate_start"], r["original"]["candidate_end"]
    r["original_segments"] = ([{"candidate_start": a, "candidate_end": b, "cover": 0.0}]
                              + list(r.get("original_segments") or []))
    r["original"]["candidate_start"] = round(a + dt, 3)
    r["original"]["candidate_end"] = round(b + dt, 3)
    return r


def _eval(gt, res):
    with contextlib.redirect_stdout(io.StringIO()):
        return evaluate(gt, res)


def _main_marks(m):
    return {x["id"]: ("HIT" if x["main_hit"] else x["mark"]) for x in m["per_pos"]}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(exist_ok=True)
    svc = SourceLocatorService(config=load_config())
    assert isinstance(svc.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(svc.backend).__name__}"
    from engine.localization.patch_rerank import (PatchReranker, resolve_patch_onnx,
                                                  resolve_weights)
    cfg = svc.config.pipeline
    rr = PatchReranker(resolve_weights(cfg.patch_weights_path or None),
                       resolve_patch_onnx((cfg.patch_onnx_model or "").strip() or None),
                       dml_device_id=svc.config.device.dml_device_id)
    assert rr.ensure() and rr.device == "dml", f"patch backend={rr.device}"
    print("BACKEND_SELECTED=%s patch=%s" % (type(svc.backend).__name__, rr.device), flush=True)

    report = {"cases": {}, "tot": {}}
    tot = {k: 0 for k in ("base_s", "base_e", "A_s", "A_e", "B_s", "B_e",
                          "base_fp", "A_fp", "B_fp", "A_moved", "B_moved", "n_seg")}
    flips_all = []
    t_start = time.perf_counter()
    for case, gt_rel in CASES:
        gt = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
        raw = json.loads((BENCH / f"work/spl_patch_arms/on_{case}.results.json")
                         .read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        base = raw["results"]
        resA, resB, segs = [], [], []
        for r in base:
            e0, e1 = r["edited_segment"]["start"], r["edited_segment"]["end"]
            a, b = r["original"]["candidate_start"], r["original"]["candidate_end"]
            w = e1 - e0
            if (r.get("not_in_source") or r.get("manual_override") or r.get("excluded")
                    or b - a <= 0.01 or w <= 0.01):
                resA.append(r); resB.append(r)
                continue
            tot["n_seg"] += 1
            q_ets = [e0 + w * (i + 0.5) / N_QUERY for i in range(N_QUERY)]
            dq = np.array(q_ets) - (e0 + w / 2)
            qc, qp = zip(*[rr.frame_dual(f) for f in svc._grab_frames_parallel(ed, q_ets)])
            q_cls, q_patch = np.stack(qc), np.stack(qp)
            m = (a + b) / 2
            g0 = max(0.0, m - REFINE_WIN_S - w / 2)
            g1 = m + REFINE_WIN_S + w / 2
            grid = np.arange(g0, g1 + 1e-6, 1.0 / GRID_FPS)
            S = np.stack([_fused(q_cls, q_patch, *rr.frame_dual(f))
                          for f in svc._grab_frames_parallel(src, list(grid))], axis=1)

            def at(t):
                return int(np.argmin(np.abs(grid - t)))
            # A：窗内多查询均值分峰
            sA = S.mean(axis=0)
            inwin = np.where(np.abs(grid - m) <= REFINE_WIN_S)[0]
            jA = int(inwin[np.argmax(sA[inwin])])
            cA = float(sA[at(m)])
            dA = float(grid[jA] - m)
            moveA = (sA[jA] - cA) >= SWITCH_MARGIN and abs(dA) > 0.5
            # B：保持编辑侧时序的对位偏移
            deltas = np.arange(-REFINE_WIN_S, REFINE_WIN_S + 1e-6, 0.5)
            sB = np.array([np.mean([S[i, at(m + d + dq[i])] for i in range(N_QUERY)])
                           for d in deltas])
            cB = float(sB[np.argmin(np.abs(deltas))])
            kB = int(np.argmax(sB))
            dB = float(deltas[kB])
            moveB = (sB[kB] - cB) >= SWITCH_MARGIN and abs(dB) > 0.5
            moveA, moveB = bool(moveA), bool(moveB)
            tot["A_moved"] += moveA
            tot["B_moved"] += moveB
            resA.append(_shift(r, dA) if moveA else r)
            resB.append(_shift(r, dB) if moveB else r)
            segs.append({"ed": [e0, e1], "main": [a, b], "dA": dA, "gainA": float(sA[jA] - cA),
                         "moveA": bool(moveA), "dB": dB, "gainB": float(sB[kB] - cB),
                         "moveB": bool(moveB)})
        mb, ma, mB = _eval(gt, base), _eval(gt, resA), _eval(gt, resB)
        for k, mm in (("base", mb), ("A", ma), ("B", mB)):
            tot[k + "_s"] += mm["strict_hit"]
            tot[k + "_e"] += mm["main_hit"]
            tot[k + "_fp"] += mm["fp"]
        bm, am, Bm = _main_marks(mb), _main_marks(ma), _main_marks(mB)
        flips = [{"case": case, "id": pid, "base": bm[pid], "A": am[pid], "B": Bm[pid],
                  "pool": pid in POOL}
                 for pid in bm if not (bm[pid] == am[pid] == Bm[pid])]
        flips_all += flips
        for v, res in (("A", resA), ("B", resB)):
            (OUT / f"{v}_{case}.results.json").write_text(
                json.dumps({**raw, "results": res}, ensure_ascii=False), encoding="utf-8")
        report["cases"][case] = {"base": [mb["strict_hit"], mb["main_hit"], mb["fp"]],
                                 "A": [ma["strict_hit"], ma["main_hit"], ma["fp"]],
                                 "B": [mB["strict_hit"], mB["main_hit"], mB["fp"]],
                                 "segs": segs, "flips": flips}
        print("[%-5s] 严格/导出/FP  base %d/%d/%d | A %d/%d/%d | B %d/%d/%d  (%.0fs)" % (
            case, *report["cases"][case]["base"], *report["cases"][case]["A"],
            *report["cases"][case]["B"], time.perf_counter() - t_start), flush=True)
    report["tot"] = tot
    report["flips"] = flips_all
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    print("\n=== 四片: 严格 base %(base_s)d A %(A_s)d B %(B_s)d | 导出 base %(base_e)d "
          "A %(A_e)d B %(B_e)d | FP base %(base_fp)d A %(A_fp)d B %(B_fp)d | "
          "移动 A %(A_moved)d B %(B_moved)d / %(n_seg)d 段 ===" % tot)
    for f in flips_all:
        print("  flip", f)
    _sheets(flips_all)
    return 0


def _main_mid_for(res, e0, e1):
    best, mid = 0.0, None
    for r in res:
        ov = min(e1, r["edited_segment"]["end"]) - max(e0, r["edited_segment"]["start"])
        o = r["original"]
        if ov > best and o["candidate_end"] - o["candidate_start"] > 0.01:
            best, mid = ov, (o["candidate_start"] + o["candidate_end"]) / 2
    return mid


def _sheets(flips):
    """翻转行读图：GT_ED | GT_OG | base 主 | A 主 | B 主（与 GT 重叠最大的那段）。"""
    if not flips:
        return
    gts = {c: json.loads((BENCH / g).read_text(encoding="utf-8")) for c, g in CASES}
    rows = []
    for f in flips:
        case = f["case"]
        p = next(x for x in gts[case]["positives"] if x["id"] == f["id"])
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        raw = json.loads((BENCH / f"work/spl_patch_arms/on_{case}.results.json")
                         .read_text(encoding="utf-8"))
        src, ed = Path(raw["original_video"]), Path(raw["edited_video"])
        cells_spec = [(ed, (e0 + e1) / 2, "GT_ED"), (src, (o0 + o1) / 2, "GT_OG"),
                      (src, _main_mid_for(raw["results"], e0, e1), "base " + f["base"])]
        for v in ("A", "B"):
            res = json.loads((OUT / f"{v}_{case}.results.json").read_text(
                encoding="utf-8"))["results"]
            cells_spec.append((src, _main_mid_for(res, e0, e1), f"{v} {f[v]}"))
        cells = []
        for vid, t, cap in cells_spec:
            if t is None:
                cells.append(None)
                continue
            pp = OUT / "frames" / f"{case}_{f['id']}_{cap.split()[0]}.png"
            try:
                ffmpeg_frame(vid, max(0.0, float(t)), pp)
                cells.append((str(pp), [f"{case}/{f['id']} {cap}", fmt_ts(t)]))
            except Exception:
                cells.append(None)
        rows.append(cells)
    for i in range(0, len(rows), 4):
        compose_sheet(rows[i:i + 4], OUT / f"flips_{i // 4 + 1}.png",
                      "in-window peak flips %d-%d: GT_ED | GT_OG | base | A | B" % (i + 1, i + 4))
    print("读图 %d 行 -> %s/flips_*.png" % (len(rows), OUT))


if __name__ == "__main__":
    sys.exit(main())
