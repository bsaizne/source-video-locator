"""p36 细切分对照实验——「查询单元切得更细是否让正确位置成为 primary」取证（2026-09-04）。

对 ed 110-111.5(2fps, 3帧):
  A. 整段查询(现状 EvidenceLocalizer min_frames=2) -> 期望复现失败(2060);
  B. 逐帧单帧查询(min_frames=1 放宽, 模拟细切分后的单镜头查询) -> 2042-2043.4 是否成为命中;
  C. 单帧 argmax + finloc_window 直接定位(最宽松: 不依赖 scene 回退)。
输出: work/p36_fineseg_experiment.json
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
from engine.localization.finloc import finloc_window  # noqa: E402
from engine.candidates import produce_candidates  # noqa: E402

IDX = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
EDIT_VID = r"D:/video/1.mp4"
GT = (2042.0, 2043.4)
EDIT_RANGE = (110.0, 111.5)


def grab_frames(t0, t1, fps):
    W = H = 518
    n_expect = max(1, int((t1 - t0) * fps) + 1)
    proc = subprocess.run(
        [str(FFMPEG), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
         "-i", EDIT_VID, "-vf", f"fps={fps},scale={W}:{H}", "-f", "rawvideo",
         "-pix_fmt", "bgr24", "-frames:v", str(n_expect), "-"], capture_output=True)
    raw = proc.stdout
    if len(raw) == 0:
        return np.zeros((0, 384), np.float32), np.zeros((0,), np.float64)
    n = min(len(raw) // (H * W * 3), n_expect)
    buf = np.frombuffer(raw[:n * H * W * 3], dtype=np.uint8).reshape(n, H, W, 3)
    return buf, np.linspace(t0, t0 + n / fps, n)


def embed(sess, buf):
    outs = []
    for i in range(len(buf)):
        inp = preprocess_np([buf[i]])
        outs.append(sess.run(["embedding"], {"input": np.ascontiguousarray(inp)})[0])
    return l2norm(np.concatenate(outs, axis=0))


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

    # --- A. 整段查询(现状 min_frames=2) ---
    buf, qt = grab_frames(*EDIT_RANGE, fps=2.0)
    q = embed(sess, buf)
    loc2 = EvidenceLocalizer(min_frames=2)
    rA = loc2.localize(q, qt.astype(np.float32), bundle)
    report["cases"]["A_whole_minf2"] = {
        "n_query": len(q), "mode": rA.mode,
        "spans": [{"orig": list(s.original_span), "cover": round(s.cover or 0, 3),
                   "sim": round(s.best_sim or 0, 3)} for s in rA.spans],
        "primary": list(rA.primary.original_span) if rA.primary else None,
        "gt_hit": any(s.original_span and s.original_span[0] <= GT[1] and s.original_span[1] >= GT[0]
                    for s in rA.spans),
    }
    print("A:", json.dumps(report["cases"]["A_whole_minf2"], ensure_ascii=False), flush=True)

    # --- B. 单帧查询(min_frames=1 放宽, 模拟细切分单镜头) ---
    rB = []
    for i in range(len(q)):
        loc1 = EvidenceLocalizer(min_frames=1)
        rr = loc1.localize(q[i:i + 1], qt[i:i + 1].astype(np.float32), bundle)
        hit = bool(rr.primary and rr.primary.original_span
                   and rr.primary.original_span[0] <= GT[1]
                   and rr.primary.original_span[1] >= GT[0])
        rB.append({
            "ed_t": round(float(qt[i]), 2),
            "mode": rr.mode, "n_strong": rr.n_strong_clusters,
            "primary": list(rr.primary.original_span) if rr.primary else None,
            "primary_cover": round(rr.primary.cover or 0, 3) if rr.primary else None,
            "gt_hit": bool(hit),
            "spans": [{"orig": list(s.original_span), "cover": round(s.cover or 0, 3)}
                      for s in (rr.spans or [])],
        })
        print(f"B[{i}]:", json.dumps(rB[-1], ensure_ascii=False), flush=True)
    report["cases"]["B_single_minf1"] = rB
    report["cases"]["B_any_gt_hit"] = any(x["gt_hit"] for x in rB)

    # --- C. 单帧 argmax + finloc_window 直接定位(绕过 scene 回退) ---
    sim_all = q @ bundle.features.T
    rC = []
    for i in range(len(q)):
        # 以单帧 argmax 为中心构造窄候选(±8s)
        bt = float(bundle.times[int(np.argmax(sim_all[i]))])
        cand = type("Cand", (), {"start": bt - 8.0, "end": bt + 8.0, "width": 16.0})()
        fl = finloc_window(cand, q[i:i + 1], bundle.features, bundle.times)
        hit = fl.span is not None and fl.span[0] <= GT[1] and fl.span[1] >= GT[0]
        rC.append({
            "ed_t": round(float(qt[i]), 2),
            "argmax_orig": round(bt, 1),
            "finloc_span": list(fl.span) if fl.span else None,
            "best_cover": round(float(fl.best_cover), 3) if fl.best_cover is not None else None,
            "gt_hit": bool(hit),
        })
        print(f"C[{i}]:", json.dumps(rC[-1], ensure_ascii=False), flush=True)
    report["cases"]["C_argmax_finloc"] = rC
    report["cases"]["C_any_gt_hit"] = any(x["gt_hit"] for x in rC)

    out = BENCH / "work" / "p36_fineseg_experiment.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())