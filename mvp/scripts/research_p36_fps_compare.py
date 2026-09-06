"""p36 采样率三档对照——2fps vs 4fps vs 8fps（C 项验证补充, 2026-09-05）。

对 ed 110-111.5 分别以 2/4/8fps 整段查询(EvidenceLocalizer 生产参数 min_frames=2),
对照 primary 是否命中 GT 2042-2043.4; 同时记录段内 argmax 分布(哪个子镜头帧数过门)。
输出: work/p36_fps_compare.json
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

IDX = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
EDIT_VID = r"D:/video/1.mp4"
GT = (2042.0, 2043.4)
EDIT_RANGE = (110.0, 111.5)

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
    for fps in (2.0, 4.0, 6.0, 8.0):
        buf, t = grab_frames(*EDIT_RANGE, fps=fps)
        q = embed(sess, buf)
        r = EvidenceLocalizer(**LOC).localize(q, t.astype(np.float32), bundle)
        # argmax 分布（诊断: 各帧 argmax 指向哪、2042 簇几帧）
        sim = q @ bundle.features.T
        best = np.argmax(sim, axis=1)
        bt = bundle.times[best]
        n_2042 = int(np.sum((bt >= 2034) & (bt <= 2053)))
        report["cases"][f"fps{fps:g}"] = {
            "n_query": len(q), "mode": r.mode,
            "primary": [float(s) for s in r.primary.original_span] if r.primary else None,
            "primary_cover": round(r.primary.cover or 0, 3) if r.primary else None,
            "spans": [[float(s.original_span[0]), float(s.original_span[1]),
                       round(s.cover or 0, 3)] for s in r.spans],
            "argmax_times": [round(float(x), 2) for x in bt],
            "n_argmax_in_2034_2053": int(n_2042),
            "gt_hit": hit(r.primary.original_span if r.primary else None)}
        print(f"fps{fps:g}: nq={len(q)} mode={r.mode} primary={report['cases'][f'fps{fps:g}']['primary']} "
              f"cover={report['cases'][f'fps{fps:g}']['primary_cover']} "
              f"hit={report['cases'][f'fps{fps:g}']['gt_hit']} argmax={[round(float(x),1) for x in bt]}", flush=True)
    out = BENCH / "work" / "p36_fps_compare.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
