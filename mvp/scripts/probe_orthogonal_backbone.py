# -*- coding: utf-8 -*-
"""方案 B 可行性探针：正交预训练 backbone（ISC21 / CLIP）能否在 MISS6 上挑出 GT（研究侧，零 runtime）。

动机（FINDINGS_PATCH_DENSE_CORR_20261002 §7）：方案 A（patch 稠密几何对应）判负后，该族
（同场景 2–7s 偏移 + 兄弟机位）的根因 = DINOv2 CLS/patch 余弦的「语义不变性」= 特征判别力上限。
ViT-B 同族换大已证无增益（−1）⇒ 剩余候选 = **非 DINOv2 同族的正交预训练 backbone 集成**。

三臂（全 GPU/DirectML，硬断言；DML 不可用才显式回退 CPU 留痕）：
  - isc  : ISC21 官方 `isc_ft_v107`（EfficientNetV2-M @512, 256-d, copy-detection 专用，与 DINOv2 完全异族；
           权重本地恢复自 tier2 trash，Phase 12 只在旧 GT v1/解说片场景用过，从未对当前 MISS 族做过判别探针）
  - clip : OpenAI CLIP ViT-B/32 @224（语义监督家族；权重 openaipublic，HF 不可达已绕开）
  - dino : 现役 DINOv2 CLS-384（PatchReranker.frame_dual，sanity 基线——已知该信号在 MISS 上无判别力）
  - ens  : 三臂逐位置 z-score 均值（方案 B 的 runtime 集成形态）

判据（与方案 A 同口径）：对每案例在 source 时间轴扫描，
  ① GT 窗内分数 > 我方主定位处（margin>0.02）；② GT 处是全局峰（±1.5s）。
门槛（patch_v2/方案 A 同规格）：MISS+POCKET 命中 ≥1/3 且对照组零反噬 ⇒ 进采纳门控设计；否则关闭。

⚠️ 口径警示（同方案 A §3）：POCKET8 基于旧基线 127 时代，其中 p02/p03/t1r14c 在现役两旋钮 ON 批
已接近正确，gt>main 无判别意义；干净目标集 = MISS6（t2r03b 主定位=0s 占位，主定位≈扫描窗下界）。

跑法：D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_orthogonal_backbone.py
产物：work/orthogonal_backbone/{index.json, curves/*.png, sheets/*.png}
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
sys.path.insert(0, str(BENCH / "engines" / "isc21"))

import numpy as np  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")  # Windows GBK 控制台保护
except Exception:
    pass

try:
    import cv2  # noqa: E402
except Exception:  # pragma: no cover
    cv2 = None

import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402
import onnxruntime as ort  # noqa: E402

SCAN_STEP = 1.0        # source 时间轴扫描步长（秒）
SCAN_PAD = 10.0        # 扫描窗在 [GT,主定位] 包络外的扩张（秒）
N_QUERY = 3            # 每案例 edited 段查询帧数
MARGIN_GATE = 0.02     # gt>main 判据门（与方案 A 一致）
PEAK_TOL = 1.5         # gt_is_peak 容差（秒）

FILM_META = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
GT_FILE = {"2mkv": "ground_truth_v4.json", "test1": "ground_truth_test1.json",
           "test2": "ground_truth_test2.json", "test3": "ground_truth_test3.json"}
# 现役结果批（续33/39 两旋钮 ON 臂 = r7 对应批，基线严格 133）——与方案 A 同一批
OURS_BATCH = "work/spl_patch_arms/on_{film}.results.json"

MISS6 = [("2mkv", "p14"), ("2mkv", "p20"), ("2mkv", "p34"),
         ("test1", "t1r08c"), ("test1", "t1r12a"), ("test2", "t2r03b")]
POCKET8 = [("2mkv", "p02"), ("2mkv", "p03"), ("2mkv", "p20"), ("2mkv", "p30"),
           ("2mkv", "p34"), ("test1", "t1r14c"), ("test2", "t2r06c"), ("test3", "t3r02c")]
CONTROLS = [("2mkv", "p04"), ("2mkv", "p10"), ("2mkv", "p32"),
            ("test1", "t1r00"), ("test1", "t1r27"),
            ("test2", "t2r00"), ("test3", "t3r07"), ("test3", "t3r12")]

OUT = BENCH / "work" / "orthogonal_backbone"
ISC_DIR = BENCH / "work" / "isc21_weights_ortho_probe"
ARMS = ("isc", "clip", "dino", "ens")

# CLIP 归一化常量（OpenAI 官方）
CLIP_NPX = 224
CLIP_MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
CLIP_STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)


def _dml_session(onnx_path: Path) -> tuple:
    """DML 优先（GPU-first 硬断言级别）；失败显式回退 CPU 并留痕。"""
    opts = [("DmlExecutionProvider", {"device_id": 0}), "CPUExecutionProvider"]
    sess = ort.InferenceSession(str(onnx_path), providers=opts)
    prov = sess.get_providers()
    print(f"  session providers = {prov}", flush=True)
    return sess, ("dml" if prov[0] == "DmlExecutionProvider" else "cpu")


def _frame_to_tensor(frame_bgr: np.ndarray, size: int, mean: np.ndarray, std: np.ndarray,
                     center_crop: bool) -> np.ndarray:
    """BGR uint8 → RGB float32 CHW [0,1] 归一化。center_crop=True 走 CLIP 短边缩放+中心裁剪，
    否则（ISC）直接方形 Resize 到 size。"""
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    if center_crop:
        h, w = rgb.shape[:2]
        scale = size / min(h, w)
        rgb = cv2.resize(rgb, (int(round(w * scale)), int(round(h * scale))),
                         interpolation=cv2.INTER_CUBIC)
        h, w = rgb.shape[:2]
        y0, x0 = max(0, (h - size) // 2), max(0, (w - size) // 2)
        rgb = rgb[y0:y0 + size, x0:x0 + size]
        if rgb.shape[0] != size or rgb.shape[1] != size:  # 极端窄边兜底
            rgb = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_CUBIC)
    else:
        rgb = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_CUBIC)
    x = rgb.astype(np.float32) / 255.0
    x = (x - mean) / std
    return np.ascontiguousarray(x.transpose(2, 0, 1)[None])


class IscEmbedder:
    """ISC21 isc_ft_v107：torch 构建一次 → ONNX（gem(p=1)=ReduceMean，DML 可授权）→ DirectML。"""

    name = "isc"

    def __init__(self):
        import timm
        from isc_feature_extractor.model import ISCNet
        ckpt = torch.load(str(ISC_DIR / "isc_ft_v107.pth.tar"), map_location="cpu",
                          weights_only=False)
        size = int(ckpt["args"].input_size)
        bb = timm.create_model("timm/tf_efficientnetv2_m.in21k_ft_in1k", features_only=True)
        net = ISCNet(backbone=bb, fc_dim=256, p=1.0, eval_p=1.0)
        sd = {s.replace("module.", ""): v for s, v in ckpt["state_dict"].items()}
        net.load_state_dict(sd)
        net.eval()

        class Wrap(torch.nn.Module):
            def __init__(self, n):
                super().__init__()
                self.n = n

            def forward(self, x):
                f = self.n.backbone(x)[-1]
                return F.normalize(self.n.bn(self.n.fc(f.mean(dim=(2, 3)))))  # eval_p=1.0

        onnx_path = ISC_DIR / "isc_ft_v107.onnx"
        if not onnx_path.exists():
            ex = torch.randn(1, 3, size, size)
            torch.onnx.export(Wrap(net), ex, str(onnx_path), opset_version=17,
                              input_names=["input"], output_names=["emb"])
        self.sess, self.device = _dml_session(onnx_path)
        mean = np.asarray(bb.default_cfg["mean"], np.float32)
        std = np.asarray(bb.default_cfg["std"], np.float32)
        self._prep = lambda f: _frame_to_tensor(f, size, mean, std, center_crop=False)
        print(f"  isc ready size={size}", flush=True)

    def embed(self, frame_bgr: np.ndarray) -> np.ndarray:
        y = self.sess.run(["emb"], {"input": self._prep(frame_bgr)})[0][0]
        return y.astype(np.float32)


class ClipEmbedder:
    """OpenAI CLIP ViT-B/32 视觉塔：clip.load 一次 → ONNX → CPU。

    ⚠️ 本机实测（2026-10-02）：该图的 DML 授权会失败（E_INVALIDARG 80070057），且失败路径会
    污染进程状态——之后任何 DML session Run 都段错误（EXIT=139，已用双臂无 CLIP 对照复现归因）。
    故此处直接 CPU-only 构建，不做 DML 尝试；ViT-B/32@224 极小，CPU 代价可忽略。GPU-first 留痕。"""

    name = "clip"

    def __init__(self):
        import clip
        model, _ = clip.load("ViT-B/32", device="cpu")
        model.eval()

        class Wrap(torch.nn.Module):
            def __init__(self, v):
                super().__init__()
                self.v = v

            def forward(self, x):
                return F.normalize(self.v(x), dim=-1)

        onnx_path = ISC_DIR / "clip_vitb32_visual.onnx"
        if not onnx_path.exists():
            ex = torch.randn(1, 3, CLIP_NPX, CLIP_NPX)
            torch.onnx.export(Wrap(model.visual), ex, str(onnx_path), opset_version=14,
                              input_names=["input"], output_names=["emb"])
        sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        self.sess = sess
        self.device = "cpu-fallback(clip-dml-author-fail)"
        print("  clip session providers = CPU（DML 授权失败使进程不稳，见类注释）", flush=True)
        self._prep = lambda f: _frame_to_tensor(f, CLIP_NPX, CLIP_MEAN, CLIP_STD,
                                                center_crop=True)
        print("  clip ready", flush=True)

    def embed(self, frame_bgr: np.ndarray) -> np.ndarray:
        y = self.sess.run(["emb"], {"input": self._prep(frame_bgr)})[0][0]
        return y.astype(np.float32)


class DinoEmbedder:
    """现役 DINOv2 CLS-384（PatchReranker.frame_dual 第一输出），sanity 基线臂。"""

    name = "dino"

    def __init__(self, rr):
        self.rr = rr
        self.device = rr.device

    def embed(self, frame_bgr: np.ndarray) -> np.ndarray:
        return self.rr.frame_dual(frame_bgr)[0]


def rep_times(a, b, n=N_QUERY):
    return [round(a + (b - a) * (i + 0.5) / n, 2) for i in range(n)]


def main() -> int:
    (OUT / "curves").mkdir(parents=True, exist_ok=True)
    (OUT / "sheets").mkdir(parents=True, exist_ok=True)

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
    assert rr.device == "dml", f"dino 臂必须走 DML, 实际 {rr.device}"

    embedders = {"dino": DinoEmbedder(rr)}
    print("building isc ...", flush=True)
    embedders["isc"] = IscEmbedder()
    try:
        print("building clip ...", flush=True)
        embedders["clip"] = ClipEmbedder()
    except Exception as exc:  # 网络阻断如实标记，不伪造
        print(f"  clip 不可用（{type(exc).__name__}: {exc}）⇒ 该臂 NETWORK_BLOCKED", flush=True)
        embedders.pop("clip", None)
    active_arms = [a for a in ARMS if a != "ens" and a in embedders]
    assert embedders["isc"].device == "dml", "isc 臂必须 DML（GPU-first 硬断言）"
    print("active arms:", active_arms, flush=True)

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

    seen, plan = set(), []
    roles = {}
    for c in MISS6:
        roles[c] = "miss"
    for c in POCKET8:
        roles.setdefault(c, "pocket")
    for c in CONTROLS:
        roles[c] = "control"
    for c in _all_cases():
        if c not in seen:
            seen.add(c)
            plan.append((c[0], c[1], roles[c]))

    index = []
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
        q_times = rep_times(e0, e1)
        q_frames = [srv.ffmpeg.grab_frame(ed_vid, t) for t in q_times]
        lo = max(0.0, min(o0, main_mid) - SCAN_PAD)
        hi = max(o1, main_mid) + SCAN_PAD
        if hi - lo > 150.0:
            # 主定位占位（t2r03b main=0s）会把窗口炸到全片；钳到 GT 邻域，主定位视为出窗
            lo = max(0.0, o0 - 15.0)
            hi = o1 + 15.0
            main_in_window = False
        else:
            main_in_window = lo <= main_mid <= hi
        scan_t = [round(float(t), 2) for t in np.arange(lo, hi, SCAN_STEP)]

        # 逐位置抓 1 帧，所有臂各算一次 embedding 余弦（query embedding 每案例只算一次）
        raw = {a: [] for a in active_arms}
        s_cache = {}
        qembs = {a: [embedders[a].embed(q) for q in q_frames] for a in active_arms}
        for t in scan_t:
            f = srv.ffmpeg.grab_frame(og_vid, t)
            s_cache[t] = f
            sembs = {a: embedders[a].embed(f) for a in active_arms}
            for a in active_arms:
                sims = [float(qe @ sembs[a]) for qe in qembs[a]]
                raw[a].append((t, round(float(np.mean(sims)), 4)))

        # 集成臂 = 各臂逐位置 z-score 均值（方案 B 的 runtime 集成形态）
        z = {}
        for a in active_arms:
            vals = np.array([v for _, v in raw[a]], np.float64)
            sd = vals.std()
            z[a] = (vals - vals.mean()) / (sd if sd > 1e-9 else 1e-9)
        ens_vals = np.mean([z[a] for a in active_arms], axis=0)
        curves = {a: list(raw[a]) for a in active_arms}
        curves["ens"] = [(t, round(float(v), 4)) for (t, _), v in zip(raw[active_arms[0]], ens_vals)]

        row = {"id": gid, "film": film, "role": role,
               "gt_win": [round(o0, 2), round(o1, 2)], "gt_mid": round(gt_mid, 2),
               "main_mid": round(main_mid, 2), "offset": round(abs(main_mid - gt_mid), 2),
               "main_in_window": bool(main_in_window),
               "n_scan": len(scan_t)}
        for a in ARMS:
            if a != "ens" and a not in embedders:
                row[a] = "NETWORK_BLOCKED"
                continue
            curve = curves[a]
            gt_sc = max((c for c in curve if o0 - 1.0 <= c[0] <= o1 + 1.0),
                        key=lambda c: c[1], default=None)
            main_sc = (min(curve, key=lambda c: abs(c[0] - main_mid))
                       if curve and main_in_window else None)
            peak = max(curve, key=lambda c: c[1]) if curve else None
            margin = (round(gt_sc[1] - main_sc[1], 4) if gt_sc and main_sc else None)
            row[a] = {
                "gt_score": gt_sc[1] if gt_sc else None,
                "main_score": main_sc[1] if main_sc else None,
                "peak_score": peak[1] if peak else None,
                "peak_t": peak[0] if peak else None,
                "margin_gt_minus_main": margin,
                "gt_is_peak": bool(gt_sc and peak and abs(gt_sc[0] - peak[0]) <= PEAK_TOL),
                "gt_gt_main": bool(margin is not None and margin > MARGIN_GATE),
            }
        index.append(row)
        _plot_curve(row, curves, active_arms, o0, o1, main_mid)
        _sheet(film, gid, role, q_times[len(q_times) // 2],
               q_frames[len(q_frames) // 2], row, og_vid, s_cache, active_arms)
        brief = " ".join(
            f"{a}:m={row[a]['margin_gt_minus_main']},peak={int(row[a]['gt_is_peak'])}"
            for a in ARMS if isinstance(row[a], dict))
        print(f"[{k+1}/{total}] {role:7s} {gid:8s} off={row['offset']:6.1f} {brief}", flush=True)

    (OUT / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
    print("\n==== 汇总（判据: margin>%.2f 记 gt>main；gt_is_peak ±%.1fs）====" % (MARGIN_GATE, PEAK_TOL),
          flush=True)
    for a in ARMS:
        sub_ok = [r for r in index if isinstance(r.get(a), dict)]
        if not sub_ok:
            print(f"{a:5s}: n/a", flush=True)
            continue
        parts = []
        for role in ("miss", "pocket", "control"):
            sub = [r for r in sub_ok if r["role"] == role]
            if sub:
                hit = sum(1 for r in sub if r[a]["gt_gt_main"])
                pk = sum(1 for r in sub if r[a]["gt_is_peak"])
                parts.append(f"{role} {hit}/{len(sub)} gt>main, {pk}/{len(sub)} peak")
        print(f"{a:5s}: " + " | ".join(parts), flush=True)
    print("DONE", flush=True)
    return 0


def _all_cases():
    seen, out = set(), []
    for c in MISS6 + POCKET8 + CONTROLS:
        if c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _plot_curve(row, curves, active_arms, o0, o1, main_mid):
    if cv2 is None:
        return
    W, H = 960, 340
    L, R, T, B = 55, 20, 40, 34
    pw, ph = W - L - R, H - T - B
    ts = [t for t, _ in curves[active_arms[0]]]
    allv = [v for a in ARMS if isinstance(row.get(a), dict) for _, v in curves[a]]
    lo, hi = min(ts), max(ts)
    vmin, vmax = min(allv), max(allv)
    span_t = max(hi - lo, 1e-6)
    span_v = max(vmax - vmin, 1e-9)
    canvas = np.full((H, W, 3), 255, np.uint8)

    def X(t):
        return int(L + (t - lo) / span_t * pw)

    def Y(v):
        return int(T + (1.0 - (v - vmin) / span_v) * ph)

    ov = canvas.copy()
    cv2.rectangle(ov, (X(o0), T), (X(o1), T + ph), (200, 235, 200), -1)
    cv2.addWeighted(ov, 0.55, canvas, 0.45, 0, canvas)
    cv2.line(canvas, (X(main_mid), T), (X(main_mid), T + ph), (40, 40, 200), 1, cv2.LINE_AA)
    colors = {"isc": (200, 120, 0), "clip": (180, 60, 160), "dino": (150, 150, 150),
              "ens": (60, 60, 60)}
    for a in ARMS:
        if not isinstance(row.get(a), dict):
            continue
        pts = np.array([[X(t), Y(v)] for t, v in curves[a]], np.int32)
        thick = 2 if a == "ens" else 1
        cv2.polylines(canvas, [pts], False, colors[a], thick, cv2.LINE_AA)
    title = (f"{row['role']} {row['id']}  off={row['offset']}s  "
             + " ".join(f"{a}={'peak' if row[a]['gt_is_peak'] else '-'}"
                        f"/m={row[a]['margin_gt_minus_main']}"
                        for a in ARMS if isinstance(row[a], dict)))
    cv2.putText(canvas, title[:150], (L, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"x: source time {lo:.0f}-{hi:.0f}s  (normalized per-arm)",
                (L, H - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (100, 100, 100), 1)
    cv2.rectangle(canvas, (L + pw - 158, T + 4), (L + pw - 148, T + 12), (200, 235, 200), -1)
    cv2.putText(canvas, "GT win", (L + pw - 144, T + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (80, 80, 80), 1)
    cv2.line(canvas, (L + pw - 86, T + 8), (L + pw - 76, T + 8), (40, 40, 200), 1)
    cv2.putText(canvas, "ours main", (L + pw - 72, T + 12), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (80, 80, 80), 1)
    cv2.imwrite(str(OUT / "curves" / f"{row['film']}_{row['id']}.png"), canvas)


def _sheet(film, gid, role, q_t, q_frame, row, og_vid, s_cache, active_arms):
    if cv2 is None:
        return
    def cap(frame, text):
        if frame is None:
            return None
        f = frame.copy()
        cv2.putText(f, text, (6, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 0), 2)
        return cv2.resize(f, (360, 202))

    cells = [cap(q_frame, f"ED q @{q_t:.1f}s")]
    # GT 位置帧与主定位帧直接从扫描缓存里取最近位置
    g0, g1 = row["gt_win"]
    gt_t = min(s_cache.keys(), key=lambda t: abs(t - (g0 + g1) / 2.0))
    main_t = min(s_cache.keys(), key=lambda t: abs(t - row["main_mid"]))
    cells.append(cap(s_cache.get(gt_t), f"GT @{gt_t:.1f}s"))
    cells.append(cap(s_cache.get(main_t), f"OURS @{main_t:.1f}s"))
    cells = [c for c in cells if c is not None]
    while len(cells) < 3:
        cells.append(np.zeros_like(cells[0]))
    cv2.imwrite(str(OUT / "sheets" / f"{film}_{gid}_{role}.png"), np.hstack(cells))


if __name__ == "__main__":
    raise SystemExit(main())
