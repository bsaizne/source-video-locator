"""两级分层切分原型 v2——生产 detect_shots 粗网格 + 局部密帧精修（2026-09-05）。

用户方案:
  1. 全局粗采样(较大间隔 5-8帧)跑完整视频 → 候选切点(用生产 detect_shots 语义);
  2. 局部稠密回扫(切点 ±20帧, 1-2帧间隔) → 精修真实切点时间戳;
  约束: 最短镜头保护 0.5s + fps 换算间隔。

v1 失败原因: 自写粗检测边界不准(110.21/111.86); 改用生产 detect_shots(粗网格 step=6)
→ p36 区段 [110.07,111.52] 与 GT 编辑窗吻合。本版验证该段是否命中 GT 2042-2043.4。
零 runtime 改动。输出: work/twopass_prototype_v2.json
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
from engine.segment.segment import detect_shots, adjacent_distances  # noqa: E402

IDX = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
EDIT_VID = r"D:/video/1.mp4"
GT = (2042.0, 2043.4)
EDIT_FPS = 29.0
EDIT_DUR = 126.79

COARSE_STEP = 6          # 粗采样步长(帧) -> ~4.8fps @29
FINE_WINDOW_FRAMES = 20  # 精修窗 ±20 帧
FINE_STEP = 1            # 精修采样步长(帧) -> ~29fps
MIN_SHOT_S = 0.5

LOC = dict(min_frames=2, min_sim=0.40, cluster_gap_s=15.0,
           weak_cover=0.30, weak_sim=0.45, max_span_s=15.0,
           subspan_min_cover=0.45, subspan_min_sim=0.50,
           subspan_iou_merge=0.60, subspan_max_keep=4,
           scene_recall_enabled=True, scene_top_k=5, scene_max_expand_frames=120)
W = H = 518


def grab_range(t0, t1, step):
    f0 = int(round(t0 * EDIT_FPS)); f1 = int(round(t1 * EDIT_FPS))
    n = max(0, (f1 - f0) // step)
    if n == 0:
        return np.zeros((0, H, W, 3), np.uint8), np.zeros((0,), np.float64)
    eff = EDIT_FPS / step
    proc = subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1-t0:.3f}",
        "-i", EDIT_VID, "-vf", f"fps={eff:.4f},scale={W}:{H}", "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-frames:v", str(n), "-"], capture_output=True)
    raw = proc.stdout
    n_ok = min(len(raw) // (H * W * 3), n)
    if n_ok <= 0:
        return np.zeros((0, H, W, 3), np.uint8), np.zeros((0,), np.float64)
    buf = np.frombuffer(raw[:n_ok * H * W * 3], dtype=np.uint8).reshape(n_ok, H, W, 3)
    times = np.array([t0 + i * step / EDIT_FPS for i in range(n_ok)])
    return buf, times


def embed(sess, buf):
    if len(buf) == 0:
        return np.zeros((0, 384), np.float32)
    outs = []
    for i in range(len(buf)):
        outs.append(sess.run(["embedding"], {"input": np.ascontiguousarray(preprocess_np([buf[i]]))})[0])
    return l2norm(np.concatenate(outs, axis=0))


def refine_boundary(sess, cut_t):
    """局部密帧精修: 切点 ±FINE_WINDOW 帧窗内 FINE_STEP 步长, 找相邻距离峰 → 精确切点时间。"""
    f = cut_t * EDIT_FPS
    t0 = max(0.0, (f - FINE_WINDOW_FRAMES) / EDIT_FPS)
    t1 = min(EDIT_DUR, (f + FINE_WINDOW_FRAMES) / EDIT_FPS)
    buf, ts = grab_range(t0, t1, FINE_STEP)
    if len(buf) < 3:
        return cut_t
    q = embed(sess, buf)
    d = adjacent_distances(q)
    i = int(np.argmax(d))
    return float(ts[i + 1])


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

    # --- 1) 粗采样全片 + 生产 detect_shots ---
    buf, ts = grab_range(0.0, EDIT_DUR, COARSE_STEP)
    q = embed(sess, buf)
    shots = detect_shots(q, ts.astype(np.float32), cut_abs=0.26, z_thresh=1.7,
                         min_shot_s=0.8, fps=EDIT_FPS / COARSE_STEP)
    print(f"coarse: {len(q)} 帧, detect_shots -> {len(shots)} 段", flush=True)

    # --- 2) 切点 = 段边界; 局部精修每个内部边界 ---
    bounds = [0.0] + [s.span.start for s in shots[1:]] + [EDIT_DUR]
    # 用段起点做候选切点(生产 detect_shots 已含 NMS/merge; 精修边界时间)
    cuts_coarse = [s.span.start for s in shots[1:]]
    refined = sorted(set(round(refine_boundary(sess, t), 3) for t in cuts_coarse))
    print(f"粗切点 {len(cuts_coarse)} -> 精修后 {len(refined)}", flush=True)

    # --- 3) 最短镜头保护 ---
    pts = [0.0] + refined + [EDIT_DUR]
    changed = True
    while changed:
        changed = False
        i = 1
        while i < len(pts) - 1:
            gl = pts[i] - pts[i - 1]; gr = pts[i + 1] - pts[i]
            if gl < MIN_SHOT_S or gr < MIN_SHOT_S:
                del pts[i if gl <= gr else i + 1]
                changed = True
            else:
                i += 1
    segs = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1) if pts[j + 1] - pts[j] >= MIN_SHOT_S]
    print(f"最短镜头保护后: {len(segs)} 段", flush=True)

    # --- 4) p36 查询单元: 编辑窗与 GT 110-111.5 重叠 >=50% 的段 ---
    p36_segs = [s for s in segs if min(s[1], 111.5) - max(s[0], 110.0) >= 0.5 * (111.5 - 110.0)]
    print(f"p36 编辑窗覆盖段: {[tuple(round(x,2) for x in s) for s in p36_segs]}", flush=True)

    report = {"params": {"coarse_step": COARSE_STEP, "fine_window_frames": FINE_WINDOW_FRAMES,
                         "fine_step": FINE_STEP, "min_shot_s": MIN_SHOT_S, "fps": EDIT_FPS},
              "n_coarse_shots": len(shots), "n_refined_cuts": len(refined), "n_segments": len(segs),
              "p36_cover_segments": [tuple(round(x, 2) for x in s) for s in p36_segs], "cases": {}}
    for (a, b) in p36_segs:
        buf2, ts2 = grab_range(a, b, COARSE_STEP)
        if len(buf2) == 0:
            continue
        q2 = embed(sess, buf2)
        r = EvidenceLocalizer(**LOC).localize(q2, ts2.astype(np.float32), bundle)
        hit = bool(r.primary and r.primary.original_span
                   and r.primary.original_span[0] <= GT[1] and r.primary.original_span[1] >= GT[0])
        report["cases"][f"{a:.2f}-{b:.2f}"] = {
            "n_query": len(q2), "mode": r.mode,
            "primary": list(r.primary.original_span) if r.primary else None,
            "cover": round(r.primary.cover or 0, 3) if r.primary else None,
            "gt_hit": hit}
        print(f"  seg {a:.2f}-{b:.2f}: nq={len(q2)} mode={r.mode} "
              f"primary={list(r.primary.original_span) if r.primary else None} hit={hit}", flush=True)
    out = BENCH / "work" / "twopass_prototype_v2.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("saved", out, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
