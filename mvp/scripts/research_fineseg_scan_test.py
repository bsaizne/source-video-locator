"""test1-3 同类段扫描——细切分(单帧查询)可救回上限取证（2026-09-04, 用户拍板第 2 步）。

对 test1/2/3 每片 GT 正例中「严格未命中」的段: 从编辑视频抽 2fps 帧嵌入,
对照 ①整段查询(现状 min_frames=2) ②单帧查询(细切分模拟 min_frames=1) 是否命中 GT original;
统计「整段未命中但单帧可命中」的段数 = 方案 A(单帧强证据保留) 的收益上限。
只读评估, 零 runtime 改动。输出: work/fineseg_scan_test.json
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
              "gt": BENCH / "datasets/real/ground_truth_test1.json",
              "res": BENCH / "work/rerun_test1_timelineprior.results.json"},
    "test2": {"ed": r"D:/ProjectXIXI/test2/tset2-ed.mp4", "orig_idx": "test2-om__35b9a58f.idx",
              "gt": BENCH / "datasets/real/ground_truth_test2.json",
              "res": BENCH / "work/rerun_test2_timelineprior.results.json"},
    "test3": {"ed": r"D:/ProjectXIXI/test3/test3-ed.mp4", "orig_idx": "test3-om__074e2dcc.idx",
              "gt": BENCH / "datasets/real/ground_truth_test3.json",
              "res": BENCH / "work/rerun_test3_timelineprior.results.json"},
}
QUERY_FPS = 2.0
MAX_QUERY_FRAMES = 12   # 超长段截断(取中段), 控成本


def grab_embed(sess, video, t0, t1):
    W = H = 518
    n_expect = max(1, int((t1 - t0) * QUERY_FPS) + 1)
    if n_expect > MAX_QUERY_FRAMES:
        mid = (t0 + t1) / 2; t0 = mid - MAX_QUERY_FRAMES / QUERY_FPS / 2
        t1 = mid + MAX_QUERY_FRAMES / QUERY_FPS / 2
        n_expect = MAX_QUERY_FRAMES
    proc = subprocess.run(
        [str(FFMPEG), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}",
         "-i", video, "-vf", f"fps={QUERY_FPS},scale={W}:{H}", "-f", "rawvideo",
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
    times = np.linspace(t0, t0 + n / QUERY_FPS, n)
    return feats, times


def span_hits_gt(span, g0, g1):
    """span 与 GT original 有交集 或 中点落内(宽松命中, 对应救回判定)。"""
    if span is None:
        return False
    a, b = span
    inter = max(0.0, min(b, g1) - max(a, g0))
    mid = (g0 + g1) / 2
    return inter > 0.0 or (a <= mid <= b)


def main() -> int:
    sess = ort.InferenceSession(str(MODEL_PATH),
                                providers=[("DmlExecutionProvider", {"device_id": 0}),
                                           "CPUExecutionProvider"])
    report = {"pairs": {}, "total": {"strict_miss": 0, "rescuable": 0, "miss_frames": 0}}
    for name, cfg in PAIRS.items():
        gt = json.loads(Path(cfg["gt"]).read_text(encoding="utf-8"))
        bundle = IndexBundle(
            IndexMeta.from_dict(json.loads((IDX_DIR / cfg["orig_idx"] / "index.json").read_text(encoding="utf-8"))),
            np.load(IDX_DIR / cfg["orig_idx"] / "features.npy").astype(np.float32),
            np.load(IDX_DIR / cfg["orig_idx"] / "times.npy").astype(np.float64),
            np.load(IDX_DIR / cfg["orig_idx"] / "scenes.npy").astype(np.float64),
            np.load(IDX_DIR / cfg["orig_idx"] / "scene_feats.npy").astype(np.float32),
        )
        loc2 = EvidenceLocalizer(min_frames=2)
        loc1 = EvidenceLocalizer(min_frames=1)
        cases = []
        n_miss = n_rescue = n_noframe = 0
        for p in gt["positives"]:
            e0, e1 = p["edited"]; g0, g1 = p["original"]
            q, qt = grab_embed(sess, cfg["ed"], e0, e1)
            if len(q) == 0:
                n_noframe += 1; continue
            r2 = loc2.localize(q, qt.astype(np.float32), bundle)
            whole_hit = any(s.original_span and span_hits_gt(s.original_span, g0, g1) for s in r2.spans)
            if whole_hit:
                continue   # 已命中, 不在扫描范围
            n_miss += 1
            # 单帧查询(细切分模拟)
            frame_hits = []
            for i in range(len(q)):
                r1 = loc1.localize(q[i:i + 1], qt[i:i + 1].astype(np.float32), bundle)
                ok = r1.primary and r1.primary.original_span and span_hits_gt(r1.primary.original_span, g0, g1)
                frame_hits.append({"ed_t": round(float(qt[i]), 2), "hit": bool(ok),
                                  "primary": list(r1.primary.original_span) if r1.primary else None})
            any_frame_hit = any(f["hit"] for f in frame_hits)
            n_rescue += any_frame_hit
            cases.append({"id": p["id"], "edited": list(p["edited"]), "original": list(p["original"]),
                          "whole_primary": list(r2.primary.original_span) if r2.primary else None,
                          "whole_mode": r2.mode, "frame_hits": frame_hits,
                          "rescuable_by_frameseg": any_frame_hit})
            print(f"[{name}] {p['id']}: whole_miss, frame-rescue={any_frame_hit}", flush=True)
        report["pairs"][name] = {"cases": cases, "strict_miss": n_miss,
                                 "rescuable": n_rescue, "no_frames": n_noframe}
        report["total"]["strict_miss"] += n_miss; report["total"]["rescuable"] += n_rescue
        report["total"]["miss_frames"] += n_noframe
        print(f"[{name}] strict_miss={n_miss} rescuable={n_rescue} no_frames={n_noframe}", flush=True)
    out = BENCH / "work" / "fineseg_scan_test.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())