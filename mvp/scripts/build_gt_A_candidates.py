"""校准阶段 A 段:失败族 GT 候选对照图生成(供人工逐帧裁决补 GT)。

范围(用户拍板 A+B, 先 A): 2.mkv 失败族(p08/p38/p26) + test3(t3r12) + test4(t4r01)
周边与 Ambiguous 候选段。每个案例生成:
  row1 = 编辑段 3 帧(edit_mid ±0.4s)
  row2 = 真值窗帧(原片, true_win 内取 3)
  row3 = 干扰窗帧(原片, dist_win 内取 3)
  row4-6 = CLS 检索 top-3 候选窗各 2 帧(mean_sim 标注)
供人工裁决:哪条原片区间真正对应编辑段 / 是否 Ambiguous -> 补入 GT。

复用 build_gt_v3_candidates.py 的检索聚簇流程(不改算法, 只做标注辅助)。

输出: mvp/benchmark/user_case/gt_A/<pid>_sheet.jpg + gt_A_candidates.json
"""
import json
import os
import subprocess
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
IDX_DIR = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")
APP_MODEL = Path(r"C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/models/"
                 "dinov2_cls_384/dinov2_cls_384.onnx")
OUT = BENCH / "mvp" / "benchmark" / "user_case" / "gt_A"

EDIT_VIDEO = {"2mkv": "D:/video/1.mp4", "test3": "D:/ProjectXIXI/test3/test3-ed.mp4",
              "test4": "D:/ProjectXIXI/test4/test4-ed.mp4"}
ORIG_VIDEO = {"2mkv": "D:/video/2.mkv", "test3": "D:/ProjectXIXI/test3/test3-om.mp4",
              "test4": "D:/ProjectXIXI/test4/test4-om.mkv"}
ORIG_IDX = {"2mkv": IDX_DIR / "2__4c6d4ab2.idx",
            "test3": IDX_DIR / "test3-om__074e2dcc.idx",
            "test4": IDX_DIR / "test4-om__eb686e0c.idx"}

# (pair, pid, 编辑中心, 正确窗(v4), 干扰窗|None, 说明)
# 2.mkv 失败族(数据层 A 段, GT v4 修正后): p08(兄弟机位真漏) + part(p05/p20/p34/p35/p41) + 真漏(p28/p36)
CASES = [
    ("2mkv", "p08", 13.5, (1108, 1110), (1048, 1050), "兄弟机位: 瞭望塔(真值) vs 士兵特写(兄弟); v4 MISS"),
    ("2mkv", "p05", 6.75, (978, 984), (996, 998), "塔上远距特写; v4 修正 978-984, 旧GT/算法 996-998(part)"),
    ("2mkv", "p20", 42.3, (1551, 1564), (1568, 1580), "卡其男岩壁行走; v4 修正 1551-1564, 旧GT 1568-1580(part)"),
    ("2mkv", "p34", 116.25, (2058, 2060), (2064, 2066), "女吧台抬手; v4 修正 2058-2060, 算法 main 2064-2066(part)"),
    ("2mkv", "p35", 121.75, (2101.2, 2103.0), (2112, 2114), "铁丝网围栏; v4 修正 2101.2-2103, 旧GT/算法 2112-2114(part)"),
    ("2mkv", "p41", 79.5, (1786, 1787), (1772, 1780), "夜阳台女走位; v4 修正 1786-1787, 旧GT/算法 1772-1780(part)"),
    ("2mkv", "p28", 87.8, (2810, 2812), (1877, 1883), "举牌We Are Not Allowed; v4 修正 2810-2812, 旧GT 1877-1883(MISS)"),
    ("2mkv", "p36", 110.75, (2042, 2043.4), (2828, 2830), "女演员张臂+举牌; v4 修正 2042-2043.4, 旧GT 2828-2830(MISS)"),
    ("test3", "t3r12", 64.75, (454, 480), (481, 488), "精灵王重复镜头(真值) vs 另一实例(干扰)"),
    ("test4", "t4r01", 1.8, (3329, 3355), (3355, 3398), "同质滑梯(真值) vs 紧邻同质干扰"),
]
TOP_WINDOWS = 3
WINDOW_GAP_S = 8.0


def cluster_windows(top_idx, times, sims):
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
        scored.append({"a": round(min(ts), 1), "b": round(max(ts) + 1.0, 1),
                       "mean_sim": round(float(np.mean(ss)), 3),
                       "max_sim": round(float(np.max(ss)), 3), "n": len(g)})
    scored.sort(key=lambda w: (-w["mean_sim"], -w["n"]))
    return scored[:TOP_WINDOWS]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "_frames").mkdir(exist_ok=True)
    os.environ["SVL_DML_MODEL"] = str(APP_MODEL)
    from device import resolve_backend
    backend = resolve_backend(preferred="auto")
    ff = FFmpegIO(FFMPEG, FFPROBE)
    print("backend:", type(backend).__name__)

    report = {"cases": []}
    for pair, pid, e_mid, true_win, dist_win, note in CASES:
        feats = np.load(ORIG_IDX[pair] / "features.npy").astype(np.float32)
        times = np.load(ORIG_IDX[pair] / "times.npy").astype(np.float64)
        # 编辑段 3 帧 embed
        reps = [e_mid - 0.4, e_mid, e_mid + 0.4]
        frames = [ff.grab_frame(EDIT_VIDEO[pair], t) for t in reps]
        ef = backend.embed_frames(frames)
        q = ef.mean(axis=0)
        q /= max(np.linalg.norm(q), 1e-8)
        sims = feats @ q
        top = np.argsort(-sims)[:24]
        cands = cluster_windows(top, times, sims)

        rows = [[(str(ffmpeg_frame(EDIT_VIDEO[pair], t,
                                   OUT / "_frames" / f"{pid}_e{j}.png")), [fmt_ts(t)])
                 for j, t in enumerate(reps)]]
        # 真值窗
        tr = pick_reps(true_win[0], true_win[1], 3)
        rows.append([(str(ffmpeg_frame(ORIG_VIDEO[pair], t,
                                       OUT / "_frames" / f"{pid}_t{j}.png")),
                      [fmt_ts(t), "TRUE"]) for j, t in enumerate(tr)])
        # 干扰窗
        if dist_win:
            dr = pick_reps(dist_win[0], dist_win[1], 3)
            rows.append([(str(ffmpeg_frame(ORIG_VIDEO[pair], t,
                                           OUT / "_frames" / f"{pid}_d{j}.png")),
                          [fmt_ts(t), "DIST"]) for j, t in enumerate(dr)])
        # top 候选窗各 2 帧
        for wi, w in enumerate(cands):
            cells = []
            for j, t in enumerate(pick_reps(w["a"], w["b"], 2)):
                try:
                    p = OUT / "_frames" / f"{pid}_c{wi}_{j}.png"
                    ffmpeg_frame(ORIG_VIDEO[pair], t, p)
                    cells.append((str(p), [fmt_ts(t), f"sim={w['mean_sim']}"]))
                except Exception as exc:
                    print(f"  [skip {p.name}: {exc}]")
                    cells.append(None)
            rows.append(cells)
        title = (f"{pid} ed({fmt_ts(e_mid)}) TRUE {true_win[0]:.0f}-{true_win[1]:.0f} "
                 + (f"DIST {dist_win[0]:.0f}-{dist_win[1]:.0f} " if dist_win else "")
                 + " | ".join(f"c{wi}:{w['a']:.0f}-{w['b']:.0f} sim{w['mean_sim']}"
                              for wi, w in enumerate(cands)))
        compose_sheet(rows, OUT / f"{pid}_sheet.jpg", title)
        report["cases"].append({"id": pid, "note": note, "true_win": list(true_win),
                                "dist_win": (list(dist_win) if dist_win else None),
                                "cands": cands})
        print(f"{pid}: TRUE {true_win} DIST {dist_win} cands: "
              + "; ".join(f"{w['a']:.0f}-{w['b']:.0f}({w['mean_sim']})" for w in cands))

    (OUT / "gt_A_candidates.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("DONE ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())