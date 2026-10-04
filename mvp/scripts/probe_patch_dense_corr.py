# -*- coding: utf-8 -*-
"""方案 A 可行性探针：DINOv2 patch 级「稠密几何对应」位置判别信号（研究侧，零 runtime）。

动机（FINDINGS_DUAL_STACK / REDIG_20261001）：同场景内 2–7s 偏移与兄弟机位族的天花板 =
DINOv2 CLS/patch 余弦的「语义不变性」——同场景不同时刻在余弦空间本就相近。现有 patch_score
(patch_rerank.py:133) 是「每 query patch 对 source patch 的最大余弦 top-100 均值」= 袋式匹配，
**丢掉了 argmax 落点**，因此只回答「有没有相似 patch」，不回答「相似 patch 的空间排列是否一致」。

本探针利用被丢掉的落点：query patch i 的最近邻落在 source patch j → 位移向量 (dx,dy)。
- 同一瞬间画面（剪辑只做裁剪/缩放/平移）→ 位移场被一个全局仿射解释 → RANSAC 内点率高；
- 同场景偏几秒（前景人物/物体已移动）→ 位移场无法被单一仿射解释 → 内点率崩。
这是语义 CLS 与袋式 patch_score 都看不到的**正交信号**，且我方 518/1369-token 表示强于竞品 224/256。

与已证伪路线的区别：phase24_1/M7 用 AKAZE/ALIKED **稀疏手工关键点** + 单应（证伪理由「同刚性
场景不同机位仍满足单应」）；本探针用 **DINOv2 稠密学习 patch 特征** + mutual-NN + 仿射内点率，
是不同形态（稠密 vs 稀疏、学习 vs 手工、位移场一致性 vs 单应内点）。按「改形态重试」纪律值得一试。

判据（先看信号存在性，再谈采纳门控——与 patch_v2 立项同路径）：
  对每条案例在 source 时间轴上扫描，画 dense_corr 分数曲线，看
  ① GT 正确窗内分数是否显著高于我方当前主定位处（margin>0）；② GT 处是否局部峰；
  ③ 对照组（当前已正确段）分数是否也在正确位置成峰（判据本身有效性）。
门槛：MISS+POCKET 命中 ≥1/3 且对照组零反噬 ⇒ 进采纳门控设计；否则如实关闭转方案 B。

跑法（GPU/DirectML，硬断言后端）：
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_patch_dense_corr.py
产物：work/patch_dense_corr/{index.json, curves/*.png, sheets/*.png}
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", r"D:\claudework\benchmark\tools\ffmpeg.exe")
os.environ.setdefault("MEDIA_FFPROBE", r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
os.environ.setdefault("SVL_DML_MODEL", r"C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")

BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

import numpy as np  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台保护
except Exception:
    pass

try:
    import cv2  # noqa: E402
except Exception:  # pragma: no cover
    cv2 = None

GRID = 37              # 518/14 patch 网格边长
NN_THRESH = 0.45       # patch 最近邻余弦下限（弱匹配=噪声，丢弃）
RANSAC_TOL = 2.0       # 仿射 RANSAC 重投影阈值（patch 单位；1 patch≈14px）
SCAN_STEP = 1.0        # source 时间轴扫描步长（秒）
SCAN_PAD = 10.0        # 扫描窗在 [GT,主定位] 包络外的扩张（秒）
N_QUERY = 3            # 每案例 edited 段查询帧数

FILM_META = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
GT_FILE = {"2mkv": "ground_truth_v4.json", "test1": "ground_truth_test1.json",
           "test2": "ground_truth_test2.json", "test3": "ground_truth_test3.json"}
# 现役结果批（续33/39 两旋钮 ON 臂 = r7 对应批，基线严格 133）
OURS_BATCH = "work/spl_patch_arms/on_{film}.results.json"

# 案例集：6 条严格未命中（续39）+ 8 条真口袋（重锚定后，probe_pocket_retest_gt130），去重
MISS6 = [("2mkv", "p14"), ("2mkv", "p20"), ("2mkv", "p34"),
         ("test1", "t1r08c"), ("test1", "t1r12a"), ("test2", "t2r03b")]
POCKET8 = [("2mkv", "p02"), ("2mkv", "p03"), ("2mkv", "p20"), ("2mkv", "p30"),
           ("2mkv", "p34"), ("test1", "t1r14c"), ("test2", "t2r06c"), ("test3", "t3r02c")]
# 对照组：当前严格命中的段（判据有效性 + 零反噬预检）
CONTROLS = [("2mkv", "p04"), ("2mkv", "p10"), ("2mkv", "p32"),
            ("test1", "t1r00"), ("test1", "t1r27"),
            ("test2", "t2r00"), ("test3", "t3r07"), ("test3", "t3r12")]

OUT = BENCH / "work" / "patch_dense_corr"


def _dedup(cases):
    seen, out = set(), []
    for c in cases:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def dense_corr(q_patches: np.ndarray, s_patches: np.ndarray) -> dict:
    """query↔source 单帧稠密对应一致性分数。

    返回 inlier_ratio（仿射 RANSAC 内点率，主判据）、n_strong（mutual-NN 强匹配数）、
    mean_nn（强匹配平均余弦）、combined（inlier_ratio×mean_nn）。
    """
    sim = q_patches @ s_patches.T                      # [1369,1369] 余弦（均已 L2）
    nn_idx = sim.argmax(axis=1)                        # Q→S 最近邻
    nn_val = sim.max(axis=1)
    nn_rev = sim.argmax(axis=0)                        # S→Q 最近邻（mutual 用）
    strong = np.where(nn_val >= NN_THRESH)[0]
    # mutual-NN 过滤：i 的最近邻是 j，且 j 的最近邻回到 i
    mutual = np.array([i for i in strong if nn_rev[nn_idx[i]] == i], dtype=np.int64)
    use = mutual if len(mutual) >= 12 else strong
    if len(use) < 12 or cv2 is None:
        return {"inlier_ratio": 0.0, "n_strong": int(len(use)), "mean_nn": 0.0, "combined": 0.0}
    si = nn_idx[use]
    qp = np.stack([use % GRID, use // GRID], axis=1).astype(np.float32)
    sp = np.stack([si % GRID, si // GRID], axis=1).astype(np.float32)
    M, inl = cv2.estimateAffinePartial2D(qp, sp, method=cv2.RANSAC,
                                         ransacReprojThreshold=RANSAC_TOL)
    if M is None or inl is None:
        return {"inlier_ratio": 0.0, "n_strong": int(len(use)), "mean_nn": 0.0, "combined": 0.0}
    inlier_ratio = float(inl.sum()) / float(len(use))
    mean_nn = float(nn_val[use].mean())
    return {"inlier_ratio": round(inlier_ratio, 4), "n_strong": int(len(use)),
            "mean_nn": round(mean_nn, 4), "combined": round(inlier_ratio * mean_nn, 4)}


def rep_times(a, b, n=N_QUERY):
    return [round(a + (b - a) * (i + 0.5) / n, 2) for i in range(n)]


def main() -> int:
    (OUT / "curves").mkdir(parents=True, exist_ok=True)
    (OUT / "sheets").mkdir(parents=True, exist_ok=True)
    (OUT / "frames").mkdir(parents=True, exist_ok=True)

    from app.locator_service import SourceLocatorService
    from device.directml_backend import DirectMLBackend
    from infrastructure.config import load_config
    from engine.localization.patch_rerank import PatchReranker, resolve_patch_onnx, resolve_weights

    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), \
        f"必须 DirectMLBackend, 实际 {type(srv.backend).__name__}"
    print("BACKEND_SELECTED type=%s" % type(srv.backend).__name__, flush=True)
    rr = PatchReranker(resolve_weights(cfg.pipeline.patch_weights_path or None),
                       resolve_patch_onnx((cfg.pipeline.patch_onnx_model or "").strip() or None),
                       dml_device_id=cfg.device.dml_device_id)
    assert rr.ensure(), "PatchReranker 不可用（缺 DML ONNX 资产 / 权重）"
    print("patch device:", rr.device, flush=True)
    assert rr.device == "dml", f"patch 特征必须走 DML, 实际 {rr.device}"

    def gt_case(film, gid):
        gt = json.loads((BENCH / "datasets/real" / GT_FILE[film]).read_text(encoding="utf-8"))
        for p in gt["positives"]:
            if p["id"] == gid:
                return p
        raise KeyError(f"{film}/{gid} 不在 GT positives")

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

    index = []
    all_cases = _dedup(MISS6 + POCKET8)
    roles = {}
    for c in MISS6:
        roles[c] = "miss"
    for c in POCKET8:
        roles.setdefault(c, "pocket")
    for c in CONTROLS:
        roles[c] = "control"

    plan = [(f, g, roles[(f, g)]) for (f, g) in _dedup(all_cases + CONTROLS)]
    total = len(plan)
    for k, (film, gid, role) in enumerate(plan):
        p = gt_case(film, gid)
        e0, e1 = p["edited"]
        o0, o1 = p["original"]
        gt_mid = (o0 + o1) / 2.0
        ed_vid, og_vid = FILM_META[film]
        main_mid = ours_main_mid(film, p)
        if main_mid is None:
            print(f"[{k+1}/{total}] {gid} 无我方主定位，跳过", flush=True)
            continue
        # query：edited 段 3 帧的 patch（逐帧缓存）
        q_frames = [srv.ffmpeg.grab_frame(ed_vid, t) for t in rep_times(e0, e1)]
        q_patches = [rr.frame_patches(f) for f in q_frames]
        # source 扫描窗：覆盖 [GT窗, 主定位] 包络 + 外扩
        lo = min(o0, main_mid) - SCAN_PAD
        hi = max(o1, main_mid) + SCAN_PAD
        lo = max(0.0, lo)
        scan_t = np.arange(lo, hi, SCAN_STEP)
        # 逐候选位置：抓 1 帧 source，算 N_QUERY 帧 query 的 dense_corr，取均值
        curve = []
        s_cache = {}
        for t in scan_t:
            t = round(float(t), 2)
            f = srv.ffmpeg.grab_frame(og_vid, t)
            sp = rr.frame_patches(f)
            s_cache[t] = f          # 缓存原始帧(uint8)供 _sheet 出图；patch 张量用完即弃
            ds = [dense_corr(qp, sp) for qp in q_patches]
            curve.append({
                "t": t,
                "inlier_ratio": round(float(np.mean([d["inlier_ratio"] for d in ds])), 4),
                "combined": round(float(np.mean([d["combined"] for d in ds])), 4),
                "n_strong": int(np.mean([d["n_strong"] for d in ds])),
            })
        # 关键位置分数
        def score_at(target):
            if not curve:
                return None
            best = min(curve, key=lambda c: abs(c["t"] - target))
            return best
        gt_sc = max((c for c in curve if o0 - 1.0 <= c["t"] <= o1 + 1.0),
                    key=lambda c: c["inlier_ratio"], default=None)
        main_sc = score_at(main_mid)
        peak = max(curve, key=lambda c: c["inlier_ratio"]) if curve else None
        margin = (round(gt_sc["inlier_ratio"] - main_sc["inlier_ratio"], 4)
                  if gt_sc and main_sc else None)
        gt_is_peak = bool(gt_sc and peak and abs(gt_sc["t"] - peak["t"]) <= 1.5)
        gt_gt_main = bool(margin is not None and margin > 0.02)
        row = {
            "id": gid, "film": film, "role": role,
            "gt_win": [round(o0, 2), round(o1, 2)], "gt_mid": round(gt_mid, 2),
            "main_mid": round(main_mid, 2), "offset": round(abs(main_mid - gt_mid), 2),
            "gt_inlier": gt_sc["inlier_ratio"] if gt_sc else None,
            "main_inlier": main_sc["inlier_ratio"] if main_sc else None,
            "peak_inlier": peak["inlier_ratio"] if peak else None,
            "peak_t": peak["t"] if peak else None,
            "margin_gt_minus_main": margin,
            "gt_is_peak": gt_is_peak, "gt_gt_main": gt_gt_main,
            "n_scan": len(curve),
        }
        index.append(row)
        # 曲线图
        _plot_curve(row, curve, o0, o1, main_mid)
        # 帧拼图：query中帧 | GT帧 | 主定位帧
        _sheet(film, gid, role, q_frames[len(q_frames)//2], ed_vid,
               rep_times(e0, e1)[len(q_frames)//2], gt_sc, main_sc, og_vid, s_cache)
        print(f"[{k+1}/{total}] {role:8s} {gid:8s} off={row['offset']:6.1f} "
              f"gt_inl={row['gt_inlier']} main_inl={row['main_inlier']} "
              f"margin={margin} gt_is_peak={gt_is_peak} gt>main={gt_gt_main}", flush=True)

    (OUT / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    # 汇总
    def rate(role):
        sub = [r for r in index if r["role"] == role]
        if not sub:
            return "n/a"
        hit = sum(1 for r in sub if r["gt_gt_main"])
        peak = sum(1 for r in sub if r["gt_is_peak"])
        return f"{hit}/{len(sub)} gt>main, {peak}/{len(sub)} gt_is_peak"
    print("\n==== 汇总 ====", flush=True)
    print("MISS+POCKET :", rate("miss"), "|", rate("pocket"), flush=True)
    print("CONTROL     :", rate("control"), flush=True)
    print("DONE", flush=True)
    return 0


def _plot_curve(row, curve, o0, o1, main_mid):
    """cv2 画 dense_corr inlier_ratio 位置扫描曲线（无 matplotlib 依赖，图注全 ASCII）。"""
    if cv2 is None or not curve:
        return
    W, H = 900, 320
    L, R, T, B = 55, 20, 40, 34
    pw, ph = W - L - R, H - T - B
    ts = [c["t"] for c in curve]
    ys = [c["inlier_ratio"] for c in curve]
    lo, hi = min(ts), max(ts)
    span = max(hi - lo, 1e-6)
    canvas = np.full((H, W, 3), 255, np.uint8)

    def X(t):
        return int(L + (t - lo) / span * pw)

    def Y(v):
        return int(T + (1.0 - max(0.0, min(1.0, v))) * ph)

    overlay = canvas.copy()
    cv2.rectangle(overlay, (X(o0), T), (X(o1), T + ph), (200, 235, 200), -1)
    cv2.addWeighted(overlay, 0.55, canvas, 0.45, 0, canvas)
    for v in (0.0, 0.25, 0.5, 0.75, 1.0):
        cv2.line(canvas, (L, Y(v)), (L + pw, Y(v)), (235, 235, 235), 1)
        cv2.putText(canvas, f"{v:.2f}", (10, Y(v) + 4), cv2.FONT_HERSHEY_SIMPLEX,
                    0.35, (120, 120, 120), 1)
    cv2.line(canvas, (X(main_mid), T), (X(main_mid), T + ph), (40, 40, 200), 1, cv2.LINE_AA)
    pts = np.array([[X(t), Y(y)] for t, y in zip(ts, ys)], np.int32)
    cv2.polylines(canvas, [pts], False, (60, 60, 60), 1, cv2.LINE_AA)
    for px, py in pts:
        cv2.circle(canvas, (int(px), int(py)), 2, (60, 60, 60), -1)
    if row.get("peak_t") is not None and row.get("peak_inlier") is not None:
        cv2.circle(canvas, (X(row["peak_t"]), Y(row["peak_inlier"])), 5, (200, 120, 0), 2)
    title = (f"{row['role']} {row['id']}  dense-corr inlier_ratio  "
             f"margin={row['margin_gt_minus_main']}  gt_is_peak={row['gt_is_peak']}")
    cv2.putText(canvas, title, (L, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"x: source time {lo:.0f}-{hi:.0f}s   y: inlier_ratio",
                (L, H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
    cv2.rectangle(canvas, (L + pw - 158, T + 4), (L + pw - 148, T + 12), (200, 235, 200), -1)
    cv2.putText(canvas, "GT win", (L + pw - 144, T + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (80, 80, 80), 1)
    cv2.line(canvas, (L + pw - 86, T + 8), (L + pw - 76, T + 8), (40, 40, 200), 1)
    cv2.putText(canvas, "ours main", (L + pw - 72, T + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (80, 80, 80), 1)
    cv2.imwrite(str(OUT / "curves" / f"{row['film']}_{row['id']}.png"), canvas)


def _sheet(film, gid, role, q_frame, ed_vid, q_t, gt_sc, main_sc, og_vid, s_cache):
    if cv2 is None:
        return
    def cap(frame, text):
        if frame is None:
            return None
        f = frame.copy()
        cv2.putText(f, text, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        return cv2.resize(f, (360, 202))
    cells = [cap(q_frame, f"ED q @{q_t:.1f}s")]
    if gt_sc and gt_sc["t"] in s_cache:
        cells.append(cap(s_cache[gt_sc["t"]],
                         f"GT @{gt_sc['t']:.1f} inl={gt_sc['inlier_ratio']:.2f}"))
    if main_sc and main_sc["t"] in s_cache:
        cells.append(cap(s_cache[main_sc["t"]],
                         f"OURS @{main_sc['t']:.1f} inl={main_sc['inlier_ratio']:.2f}"))
    cells = [c for c in cells if c is not None]
    if not cells:
        return
    while len(cells) < 3:
        cells.append(np.zeros_like(cells[0]))
    sheet = np.hstack(cells)
    cv2.imwrite(str(OUT / "sheets" / f"{film}_{gid}_{role}.png"), sheet)


if __name__ == "__main__":
    raise SystemExit(main())
