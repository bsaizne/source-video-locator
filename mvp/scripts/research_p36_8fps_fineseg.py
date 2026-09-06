"""p36 8fps 细切分收益验证——C 项(编辑侧 2fps→8fps + 细切分)第一步(2026-09-05)。

对 ed 110-111.5:
  A. 整段 2fps 查询(现状, 期望复现失败 primary=1869-1884 / 2060);
  B. 整段 8fps 查询(不切分, min_frames=2): 水瓶女子帧数足够 -> 2042 簇是否过门;
  C. 8fps + detect_shots_two_level 细切分: 子镜头独立查询单元 -> 命中 GT 2042-2043.4?
  D. 8fps + 段内硬切分对照(每 0.25s 一个查询单元, 模拟更细粒度)。
输出: work/p36_8fps_fineseg.json
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
from engine.segment.segment import detect_shots_two_level  # noqa: E402

IDX = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
EDIT_VID = r"D:/video/1.mp4"
GT = (2042.0, 2043.4)
EDIT_RANGE = (110.0, 111.5)

# 生产 PipelineConfig 切分参数(与 config.py 一致)
SEG = dict(cut_abs=0.26, z_thresh=1.7, min_shot_s=0.8, smooth=1,
           max_shot_s=8.0, fine_cut_factor=0.75, fine_z_factor=0.85, fine_min_shot_s=0.6)
# EvidenceLocalizer 生产参数
LOC = dict(min_frames=2, min_sim=0.40, cluster_gap_s=15.0,
           weak_cover=0.30, weak_sim=0.45, max_span_s=15.0,
           subspan_min_cover=0.45, subspan_min_sim=0.50,
           subspan_iou_merge=0.60, subspan_max_keep=4,
           scene_recall_enabled=True, scene_top_k=5, scene_max_expand_frames=120)


def grab_frames(t0, t1, fps):
    W = H = 518
    n_expect = max(1, int((t1 - t0) * fps) + 1)
    proc = subprocess.run(
        [str(FFMPEG), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
         "-i", EDIT_VID, "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo",
         "-pix_fmt", "bgr24", "-frames:v", str(n_expect), "-"], capture_output=True)
    raw = proc.stdout
    if len(raw) == 0:
        return np.zeros((0, H, W, 3), np.uint8), np.zeros((0,), np.float64)
    n = min(len(raw) // (H * W * 3), n_expect)
    buf = np.frombuffer(raw[:n * H * W * 3], dtype=np.uint8).reshape(n, H, W, 3)
    return buf, np.linspace(t0, t0 + n / fps, n)


def embed(sess, buf):
    outs = []
    for i in range(len(buf)):
        inp = preprocess_np([buf[i]])
        outs.append(sess.run(["embedding"], {"input": np.ascontiguousarray(inp)})[0])
    return l2norm(np.concatenate(outs, axis=0))


def hit(span, g0=GT[0], g1=GT[1]):
    if span is None:
        return False
    a, b = span
    return a <= g1 and b >= g0


def span_summary(s):
    if s is None:
        return None
    return {"orig": list(s.original_span), "cover": round(s.cover or 0, 3),
            "sim": round(s.best_sim or 0, 3)}


def main() -> int:
    bundle = IndexBundle(
        IndexMeta.from_dict(json.loads((IDX / "index.json").read_text(encoding="utf-8"))),
        np.load(IDX / "features.npy").astype(np.float32),
        np.load(IDX / "times.npy").astype(np.float64),
        np.load(IDX / "scenes.npy").astype(np.float64),
        np.load(IDX / "scene_feats.npy").astype(np.float32),
    )
    sess = ort.InferenceSession(str(MODEL_PATH),
                                providers=[("DmlExecutionProvider", {"device_id": 0}),
                                           "CPUExecutionProvider"])
    report = {"edited_range": list(EDIT_RANGE), "gt": list(GT), "cases": {}}

    # --- A. 整段 2fps(现状) ---
    buf2, t2 = grab_frames(*EDIT_RANGE, fps=2.0)
    q2 = embed(sess, buf2)
    locA = EvidenceLocalizer(**LOC)
    rA = locA.localize(q2, t2.astype(np.float32), bundle)
    report["cases"]["A_2fps_whole"] = {
        "n_query": len(q2), "mode": rA.mode,
        "spans": [span_summary(s) for s in rA.spans],
        "primary": span_summary(rA.primary), "gt_hit": hit(rA.primary.original_span)}
    print("A:", json.dumps(report["cases"]["A_2fps_whole"], ensure_ascii=False), flush=True)

    # --- B. 整段 8fps(不切分) ---
    buf8, t8 = grab_frames(*EDIT_RANGE, fps=8.0)
    q8 = embed(sess, buf8)
    locB = EvidenceLocalizer(**LOC)
    rB = locB.localize(q8, t8.astype(np.float32), bundle)
    report["cases"]["B_8fps_whole"] = {
        "n_query": len(q8), "mode": rB.mode,
        "spans": [span_summary(s) for s in rB.spans],
        "primary": span_summary(rB.primary), "gt_hit": hit(rB.primary.original_span)}
    print("B:", json.dumps(report["cases"]["B_8fps_whole"], ensure_ascii=False), flush=True)

    # --- C. 8fps + 两级切分 ---
    shots = detect_shots_two_level(q8, t8.astype(np.float32), fps=8.0, **SEG)
    c_cases = []
    for i, sh in enumerate(shots):
        locC = EvidenceLocalizer(**LOC)
        rC = locC.localize(sh.feats, sh.times.astype(np.float32), bundle)
        c_cases.append({
            "shot_idx": i, "span": [sh.span.start, sh.span.end], "nq": sh.nq,
            "mode": rC.mode, "primary": span_summary(rC.primary),
            "spans": [span_summary(s) for s in rC.spans],
            "gt_hit": hit(rC.primary.original_span)})
        print(f"C[{i}]: span={[sh.span.start, sh.span.end]} nq={sh.nq} primary={span_summary(rC.primary)} hit={c_cases[-1]['gt_hit']}", flush=True)
    report["cases"]["C_8fps_fineseg"] = {
        "n_shots": len(shots), "shots": c_cases,
        "any_hit": any(x["gt_hit"] for x in c_cases)}

    # --- D. 8fps + 0.25s 硬切分对照(查询单元更细) ---
    d_cases = []
    step = 0.25
    t0 = EDIT_RANGE[0]
    while t0 < EDIT_RANGE[1] - 1e-6:
        t1 = min(t0 + step, EDIT_RANGE[1])
        m = (t8 >= t0 - 1e-6) & (t8 < t1 + 1e-6)
        if m.sum() == 0:
            t0 = t1; continue
        locD = EvidenceLocalizer(**LOC)
        rD = locD.localize(q8[m], t8[m].astype(np.float32), bundle)
        d_cases.append({"ed_win": [round(float(t0), 2), round(float(t1), 2)],
                        "nq": int(m.sum()), "primary": span_summary(rD.primary),
                        "mode": rD.mode, "gt_hit": hit(rD.primary.original_span)})
        t0 = t1
    report["cases"]["D_8fps_hard025"] = {
        "cases": d_cases, "any_hit": any(x["gt_hit"] for x in d_cases)}

    out = BENCH / "work" / "p36_8fps_fineseg.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    print("summary: A_hit={} B_hit={} C_any_hit={} D_any_hit={}".format(
        report["cases"]["A_2fps_whole"]["gt_hit"],
        report["cases"]["B_8fps_whole"]["gt_hit"],
        report["cases"]["C_8fps_fineseg"]["any_hit"],
        report["cases"]["D_8fps_hard025"]["any_hit"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
