"""GT v3 全量 41 条审核对照图生成——校准阶段数据层(用户拍板 A+B, 先从 GT 修正开始)。

每张对照图 3 行:
  行1 = 编辑段 3 帧(待定位内容)
  行2 = 当前 GT original 窗 3 帧(TRUE, 现标注的正确位置)
  行3 = CLS 检索 top-1 候选窗 3 帧(CAND, 算法认为的位置, 标注 sim)
目的: 人工审核「编辑行 ↔ GT 行」是否真的对应; 若算法 top-1 与 GT 不同, 往往是 GT 标错线索
(如 p26: GT=2809 望远镜/举牌, 算法 top-1=1766 坐椅看书=才是编辑内容)。

复用 build_gt_v3_candidates.py 检索流程(DirectML), 不改算法。输出 mvp/benchmark/user_case/gt_review/。
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "src"))

from diagnostics.frame_sampler import ffmpeg_frame, fmt_ts, pick_reps  # noqa: E402
from diagnostics.contact_sheet import compose_sheet  # noqa: E402
from media.ffmpeg import FFmpegIO  # noqa: E402

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
IDX = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index/2__4c6d4ab2.idx")
APP_MODEL = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                 "dinov2_cls_384/dinov2_cls_384.onnx")
GT = BENCH / "datasets" / "real" / "ground_truth_v3.json"
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "gt_review"
EDIT = "D:/video/1.mp4"
ORIG = "D:/video/2.mkv"
TOP_K = 20
WINDOW_GAP_S = 8.0


def cluster_top1(top_idx, times, sims):
    hits = sorted((float(times[i]), float(sims[i])) for i in top_idx)
    groups = []
    for t, s in hits:
        if groups and t - groups[-1][-1][0] <= WINDOW_GAP_S:
            groups[-1].append((t, s))
        else:
            groups.append([(t, s)])
    scored = []
    for g in groups:
        ts = [x[0] for x in g]
        ss = [x[1] for x in g]
        scored.append((round(min(ts), 1), round(max(ts) + 1.0, 1),
                       round(float(np.mean(ss)), 3), len(g)))
    scored.sort(key=lambda w: (-w[2], -w[3]))
    return scored[0] if scored else None


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_frames").mkdir(exist_ok=True)
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    from device import resolve_backend
    backend = resolve_backend(preferred="auto")
    ff = FFmpegIO(FFMPEG, FFPROBE)
    print("backend:", type(backend).__name__, flush=True)

    feats = np.load(IDX / "features.npy").astype(np.float32)
    times = np.load(IDX / "times.npy").astype(np.float64)
    gt = json.loads(Path(GT).read_text(encoding="utf-8"))
    positives = gt["positives"]
    print(f"GT positives: {len(positives)}", flush=True)

    manifest = {"cases": []}
    for p in positives:
        pid = p["id"]
        (e0, e1) = p["edited"]
        (o0, o1) = p["original"]
        e_mid = (e0 + e1) / 2.0

        # 编辑行 3 帧
        ereps = [e_mid - 0.4, e_mid, e_mid + 0.4]
        ed_frames = [ff.grab_frame(EDIT, t) for t in ereps]
        ef = backend.embed_frames(ed_frames)
        q = ef.mean(axis=0)
        q /= max(np.linalg.norm(q), 1e-8)
        sims = feats @ q
        top = np.argsort(-sims)[:TOP_K]
        c1 = cluster_top1(top, times, sims)

        rows = [[(str(ffmpeg_frame(EDIT, t, OUT / "_frames" / f"{pid}_e{j}.png")),
                  [fmt_ts(t), "ED"]) for j, t in enumerate(ereps)]]
        # GT 窗 3 帧
        greps = pick_reps(o0, o1, 3)
        rows.append([(str(ffmpeg_frame(ORIG, t, OUT / "_frames" / f"{pid}_g{j}.png")),
                      [fmt_ts(t), "GT"]) for j, t in enumerate(greps)])
        # top-1 候选 3 帧
        if c1:
            a, b, ms, _ = c1
            creps = pick_reps(a, b, 3)
            rows.append([(str(ffmpeg_frame(ORIG, t, OUT / "_frames" / f"{pid}_c{j}.png")),
                          [fmt_ts(t), f"C1 sim={ms}"]) for j, t in enumerate(creps)])
        else:
            rows.append([(None, ["C1 none"])])

        title = (f"{pid} [{p['tier']}] ed {fmt_ts(e0)}..{fmt_ts(e1)} "
                 f"| GT {o0:.0f}-{o1:.0f} " + (f"| C1 {c1[0]:.0f}-{c1[1]:.0f} sim{c1[2]}" if c1 else ""))
        compose_sheet(rows, OUT / f"{pid}_sheet.jpg", title)
        manifest["cases"].append({
            "id": pid, "tier": p["tier"], "edited": list(p["edited"]),
            "gt": list(p["original"]), "note": p["note"],
            "c1": (list(c1[:2]) + [c1[2]]) if c1 else None,
            "gt_vs_c1_diff": (c1 and abs((c1[0] + c1[1]) / 2 - (o0 + o1) / 2) > 10.0),
        })
        print(f"{pid}: GT {o0:.0f}-{o1:.0f} | C1 {c1[0]:.0f}-{c1[1]:.0f} sim{c1[2]} "
              f"| diff>10s: {manifest['cases'][-1]['gt_vs_c1_diff']}", flush=True)

    (OUT / "gt_review_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONE ->", OUT, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
