"""test1-3 严格未命中段 8fps 整段查询扫描——C 项验证第 2 步(2026-09-05)。

对 2026-09-04 fineseg_scan_test.json 里 24 个「2fps 整段查询未命中」段:
  用 8fps 整段查询(EvidenceLocalizer min_frames=2, 生产参数)重查, 对照 2fps;
  判定用 measure_shot_recall 严格口径(within±2s / mid_in / cov≥0.4);
  重点: t2r02b(假阳性风险段) 8fps 下是否被救回(若救回=假阳性风险需警惕)。
零 runtime 改动。输出: work/fineseg_scan_test_8fps.json
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp" / "poc" / "amdgpu_onnx"))
from common import MODEL_PATH, preprocess_np, l2norm  # noqa: E402
import onnxruntime as ort  # noqa: E402
from domain import IndexMeta  # noqa: E402
from engine.feature_store import IndexBundle  # noqa: E402
from engine.localization.evidence_localize import EvidenceLocalizer  # noqa: E402

IDX_DIR = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"

PAIRS = {
    "test1": {"ed": r"D:/ProjectXIXI/test1/test1-ed.mp4", "orig_idx": "test1-om__5d4fdc2b.idx",
              "gt": BENCH / "datasets/real/ground_truth_test1.json"},
    "test2": {"ed": r"D:/ProjectXIXI/test2/tset2-ed.mp4", "orig_idx": "test2-om__35b9a58f.idx",
              "gt": BENCH / "datasets/real/ground_truth_test2.json"},
    "test3": {"ed": r"D:/ProjectXIXI/test3/test3-ed.mp4", "orig_idx": "test3-om__074e2dcc.idx",
              "gt": BENCH / "datasets/real/ground_truth_test3.json"},
}
MAX_QUERY_FRAMES = 96   # 8fps 下 12s 段上限; 超长取中段(与 09-04 扫描一致的截断策略)

LOC = dict(min_frames=2, min_sim=0.40, cluster_gap_s=15.0,
           weak_cover=0.30, weak_sim=0.45, max_span_s=15.0,
           subspan_min_cover=0.45, subspan_min_sim=0.50,
           subspan_iou_merge=0.60, subspan_max_keep=4,
           scene_recall_enabled=True, scene_top_k=5, scene_max_expand_frames=120)


def grab_embed(sess, video, t0, t1, fps):
    W = H = 518
    n_expect = max(1, int((t1 - t0) * fps) + 1)
    if n_expect > MAX_QUERY_FRAMES:
        mid = (t0 + t1) / 2
        t0 = mid - MAX_QUERY_FRAMES / fps / 2
        t1 = mid + MAX_QUERY_FRAMES / fps / 2
        n_expect = MAX_QUERY_FRAMES
    proc = subprocess.run(
        [str(FFMPEG), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
         "-i", video, "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo",
         "-pix_fmt", "bgr24", "-frames:v", str(n_expect), "-"], capture_output=True)
    raw = proc.stdout
    n = min(len(raw) // (H * W * 3), n_expect)
    if n <= 0:
        return np.zeros((0, 384), np.float32), np.zeros((0,), np.float64)
    buf = np.frombuffer(raw[:n * H * W * 3], dtype=np.uint8).reshape(n, H, W, 3)
    outs = []
    for i in range(n):
        outs.append(sess.run(["embedding"], {"input": np.ascontiguousarray(preprocess_np([buf[i]]))})[0])
    feats = l2norm(np.concatenate(outs, axis=0))
    times = np.linspace(t0, t0 + n / fps, n)
    return feats, times


def strict_hit(span, g0, g1):
    """measure_shot_recall 严格口径: within±2s / mid_in / cov≥0.4 之一。"""
    if span is None:
        return False
    a, b = span
    within = (a >= g0 - 2.0) and (b <= g1 + 2.0)
    mid_in = a <= (g0 + g1) / 2 <= b
    inter = max(0.0, min(b, g1) - max(a, g0))
    cov = inter / max(1e-6, g1 - g0) >= 0.4
    return within or mid_in or cov


def main() -> int:
    scan = json.loads((BENCH / "work" / "fineseg_scan_test.json").read_text(encoding="utf-8"))
    sess = ort.InferenceSession(str(MODEL_PATH),
                                providers=[("DmlExecutionProvider", {"device_id": 0}),
                                           "CPUExecutionProvider"])
    report = {"pairs": {}}
    for name, cfg in PAIRS.items():
        gt = json.loads(Path(cfg["gt"]).read_text(encoding="utf-8"))
        gt_map = {p["id"]: p for p in gt["positives"]}
        bundle = IndexBundle(
            IndexMeta.from_dict(json.loads((IDX_DIR / cfg["orig_idx"] / "index.json").read_text(encoding="utf-8"))),
            np.load(IDX_DIR / cfg["orig_idx"] / "features.npy").astype(np.float32),
            np.load(IDX_DIR / cfg["orig_idx"] / "times.npy").astype(np.float64),
            np.load(IDX_DIR / cfg["orig_idx"] / "scenes.npy").astype(np.float64),
            np.load(IDX_DIR / cfg["orig_idx"] / "scene_feats.npy").astype(np.float32),
        )
        cases = []
        n_hit2 = n_hit8 = n_new = n_fp_risk = 0
        # 只扫 09-04 扫描中的严格未命中段
        for c in scan["pairs"].get(name, {}).get("cases", []):
            pid = c["id"]
            p = gt_map[pid]
            e0, e1 = p["edited"]; g0, g1 = p["original"]
            # 2fps 整段查询(对照)
            q2, t2 = grab_embed(sess, cfg["ed"], e0, e1, 2.0)
            r2 = EvidenceLocalizer(**LOC).localize(q2, t2.astype(np.float32), bundle)
            hit2 = strict_hit(r2.primary.original_span if r2.primary else None, g0, g1)
            # 8fps 整段查询
            q8, t8 = grab_embed(sess, cfg["ed"], e0, e1, 8.0)
            r8 = EvidenceLocalizer(**LOC).localize(q8, t8.astype(np.float32), bundle)
            hit8 = strict_hit(r8.primary.original_span if r8.primary else None, g0, g1)
            n_hit2 += hit2; n_hit8 += hit8
            new = (not hit2) and hit8
            n_new += new
            # 假阳性风险: 8fps 下 primary 是否指向「已知误配区」(t2r02b 2921-2934 型)
            fp_risk = False
            if hit8 and not hit2:
                # 8fps 新增命中且原 2fps primary 远离 GT(>±30s) = 可能是「另一处相似区」而非修正
                old_p = r2.primary.original_span if r2.primary else None
                if old_p:
                    d = abs((old_p[0] + old_p[1]) / 2 - (g0 + g1) / 2)
                    fp_risk = d > 30.0
                n_fp_risk += fp_risk
            cases.append({
                "id": pid, "edited": [e0, e1], "original": [g0, g1],
                "fps2_primary": list(r2.primary.original_span) if r2.primary else None,
                "fps2_mode": r2.mode, "fps2_hit": hit2,
                "fps8_primary": list(r8.primary.original_span) if r8.primary else None,
                "fps8_mode": r8.mode, "fps8_hit": hit8,
                "new_hit": new, "fp_risk_flag": fp_risk})
            print(f"[{name}] {pid}: 2fps_hit={hit2} 8fps_hit={hit8} new={new}"
                  f" 8fps_primary={cases[-1]['fps8_primary']}", flush=True)
        report["pairs"][name] = {"cases": cases, "hit2": n_hit2, "hit8": n_hit8,
                                 "new_hit": n_new, "fp_risk": n_fp_risk}
        print(f"[{name}] hit2={n_hit2} hit8={n_hit8} new={n_new} fp_risk={n_fp_risk}", flush=True)
    out = BENCH / "work" / "fineseg_scan_test_8fps.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
