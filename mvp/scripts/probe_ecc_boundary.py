# -*- coding: utf-8 -*-
"""E3 判决探针: ECC 仿射运动校验能否分离"我方假切点 vs 已裁决真切点"(2026-09-28)。

背景: 竞品 commentary_scene ED 复核 = TN 双预测 + 48x27 描述子 + **ECC 仿射运动校验** + 白闪。
续8b 已证伪"TN 概率 + H-CM1 帧差"仲裁(交换比 1:1); 本探针测唯一未验证的信号腿 = ECC:
"切点前后帧若可被仿射运动对齐(残差小), 该 CLS 峰是运动伪峰(假切点); 对不齐 = 真切换"。

锚点 = work/proxy_blind_disputes/verdicts_44.csv 的 44 例已裁决集(逐张读图裁决, 2026-09-26):
  FALSE(6): 我方假切点 2mkv 113.17 / test1 2.53·44.73·73.93 / test3 49.14·27.79
  TRUE(36): theirs_only 判 cut 的 27 点(theirs_s) + ours_only 判 cut 的 9 点(ours_s)
  unsure 2 例剔除。

判据(不碰 GT、不调 runtime): 每特征给出 FALSE 分布 vs TRUE 分布的 Mann-Whitney AUC +
最优工作点交换比(假切点被拦数 / 真切换被误杀数)。CPU 纯 cv2, 秒级~分钟级。

运行: "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/probe_ecc_boundary.py
产物: work/ecc_boundary_probe.json
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
EDS = {
    "2mkv": r"D:\video\1.mp4",
    "test1": r"D:\ProjectXIXI\test1\test1-ed.mp4",
    "test2": r"D:\ProjectXIXI\test2\tset2-ed.mp4",
    "test3": r"D:\ProjectXIXI\test3\test3-ed.mp4",
}
SMALL = (48, 27)   # 竞品 SceneRuntime 低分辨率口径 (w,h)


def frames_at(path: str, t: float, k: int = 2):
    cap = cv2.VideoCapture(path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    idx = int(round(t * fps))
    out = {}
    for off in range(-k, k + 1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, idx + off))
        ok, fr = cap.read()
        if not ok:
            continue
        g = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY)
        out[off] = {"g_full": g,
                    "g_small": cv2.resize(g, SMALL),
                    "bgr": cv2.resize(fr, SMALL)}
    cap.release()
    return fps, out


def hist_corr(a: np.ndarray, b: np.ndarray) -> float:
    """LAB 均值 + Sobel 边缘 + HSV 直方图 的组合相关(竞品 _normalized_correlation 近似)。"""
    la = cv2.cvtColor(a, cv2.COLOR_BGR2LAB).reshape(-1, 3).mean(0)
    lb = cv2.cvtColor(b, cv2.COLOR_BGR2LAB).reshape(-1, 3).mean(0)
    struct_a = cv2.Sobel(cv2.cvtColor(a, cv2.COLOR_BGR2GRAY), cv2.CV_32F, 1, 1)
    struct_b = cv2.Sobel(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), cv2.CV_32F, 1, 1)
    sc = float(np.corrcoef(struct_a.ravel(), struct_b.ravel())[0, 1])
    ha = cv2.calcHist([a], [0, 1], None, [16, 16], [0, 256, 0, 256])
    hb = cv2.calcHist([b], [0, 1], None, [16, 16], [0, 256, 0, 256])
    hc = float(cv2.compareHist(ha, hb, cv2.HISTCMP_CORREL))
    return 0.5 * max(sc, 0) + 0.5 * max(hc, 0)


def ecc_features(fr: dict) -> dict:
    prev, nxt = fr.get(-1), fr.get(1)
    if prev is None or nxt is None:
        return {}
    gp, gn = prev["g_small"].astype(np.float32), nxt["g_small"].astype(np.float32)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        cc, warp = cv2.findTransformECC(gp, gn, warp, cv2.MOTION_AFFINE,
                                        (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 50, 1e-4))
        aligned = cv2.warpAffine(gn, warp, (SMALL[0], SMALL[1]))
        resid = float(np.abs(gp - aligned).mean() / 255.0)
        ecc_ok = 1
    except cv2.error:
        cc, resid, ecc_ok = float("nan"), float("nan"), 0
    raw = float(np.abs(gp - gn).mean() / 255.0)
    # 无对齐仿射失败时残差取"直接差"作上界
    if not np.isfinite(resid):
        resid = raw
    hcorr = hist_corr(prev["bgr"], nxt["bgr"])
    # 白闪旁证(竞品 _probable_flash_cut 输入): 切点帧亮度 vs 邻帧
    m_prev = float(prev["g_full"].mean())
    m_at = float(fr[0]["g_full"].mean()) if 0 in fr else m_prev
    m_next = float(nxt["g_full"].mean())
    return {"raw_diff": raw, "ecc_cc": float(cc), "ecc_resid": resid, "ecc_ok": ecc_ok,
            "hist_corr": hcorr, "bright_jump": abs(m_at - (m_prev + m_next) / 2) / 255.0}


def auc(pos: list[float], neg: list[float]) -> float:
    """P(random TRUE score  > random FALSE score) for a "bigger=more real" feature."""
    a, b = np.asarray(pos), np.asarray(neg)
    gt = (a[:, None] > b[None, :]).mean()
    eq = (a[:, None] == b[None, :]).mean()
    return float(gt + 0.5 * eq)


def main() -> None:
    rows = list(csv.DictReader(open(BENCH / "work/proxy_blind_disputes/verdicts_44.csv",
                                    encoding="utf-8-sig")))
    anchors = []
    for r in rows:
        case = r["case"]
        if r["kind"] == "ours_only":
            if r["ours_verdict"] in ("cut", "nocut"):
                anchors.append((case, float(r["ours_s"]), r["ours_verdict"] == "cut"))
        elif r["kind"] == "theirs_only" and r["theirs_verdict"] == "cut":
            anchors.append((case, float(r["theirs_s"]), True))
    feats = []
    for case, t, is_true in anchors:
        _, fr = None, None
        fps, fr = frames_at(EDS[case], t)
        f = ecc_features(fr)
        if not f:
            continue
        f.update({"case": case, "t": t, "label": "true" if is_true else "false"})
        feats.append(f)
        print("%s %8.2f %-5s raw=%.3f ecc_resid=%.3f cc=%.3f hist=%.3f jump=%.3f"
              % (case, t, f["label"], f["raw_diff"], f["ecc_resid"], f["ecc_cc"],
                 f["hist_corr"], f["bright_jump"]), flush=True)
    pos = [f for f in feats if f["label"] == "true"]
    neg = [f for f in feats if f["label"] == "false"]
    report = {"n_true": len(pos), "n_false": len(neg), "features": {}}
    for key, bigger_real in (("raw_diff", True), ("ecc_resid", True), ("hist_corr", False),
                             ("ecc_cc", False), ("bright_jump", False)):
        p = [f[key] for f in pos if np.isfinite(f[key])]
        n = [f[key] for f in neg if np.isfinite(f[key])]
        if not p or not n:
            continue
        a = auc(p, n)
        report["features"][key] = {
            "auc_true_gt_false": round(a, 3), "auc_flip": round(1 - a, 3),
            "true_min_med_max": [round(min(p), 3), round(float(np.median(p)), 3), round(max(p), 3)],
            "false_min_med_max": [round(min(n), 3), round(float(np.median(n)), 3), round(max(n), 3)],
        }
    (BENCH / "work/ecc_boundary_probe.json").write_text(
        json.dumps({"points": feats, "report": report}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
