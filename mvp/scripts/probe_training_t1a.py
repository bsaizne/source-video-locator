# -*- coding: utf-8 -*-
"""T1a: 最优线性判别投影可行性探针（LDA 闭式解, 分钟级, 零 runtime）。

问题: 在「场景标签监督的最优线性判别投影」空间里, 当前 22 条失败案例的 GT 排名
能否进入 top-20（池内）? 易例是否保持?
方法: 四片 1fps 索引特征 → 按场景表打场景标签 → 类间/类内散度 → LDA 投影(384→k)
→ 投影空间重算 查询(GT 覆盖段均值) vs 全索引 的 GT 排名。
判读: 显著救回 → 线性可分信号存在, 进 T1b 对比微调; 救不动 → 线性不可分,
训练需要非线性/更大容量或换监督, 重新评估。
"""
import json
import os
import sys
from pathlib import Path

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
os.environ.setdefault("SVL_DML_MODEL", r"C:/Users/Bsaizne/AppData/Local/SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

import numpy as np  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

FRAME_N = {"2mkv": 7668, "test1": 8221, "test2": 5051, "test3": 10177}
FILM_META = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
GT_FILE = {"2mkv": "ground_truth_v4.json", "test1": "ground_truth_test1.json",
           "test2": "ground_truth_test2.json", "test3": "ground_truth_test3.json"}

# 22 条当前非严格命中（id, film, 状态）——从 2026-09-06 池覆盖/指标复核
CASES = [
    ("p14", "2mkv", "池外"), ("p20", "2mkv", "part"), ("p30", "2mkv", "part"), ("p35", "2mkv", "part"),
    ("t1r02", "test1", "池外"), ("t1r08b", "test1", "part"), ("t1r10b", "test1", "part"),
    ("t1r12a", "test1", "part"), ("t1r14d", "test1", "池外"), ("t1r14b", "test1", "part"),
    ("t1r26", "test1", "part"), ("t1r07a", "test1", "part"),
    ("t2r02a", "test2", "part"), ("t2r03b", "test2", "池外"), ("t2r03c", "test2", "part"),
    ("t2r04a", "test2", "part"), ("t2r05a", "test2", "池外"), ("t2r05b", "test2", "part"),
    ("t2r06a", "test2", "part"), ("t2r07c", "test2", "池外"),
    ("t3r03a", "test3", "part"), ("t3r06b", "test3", "part"), ("t3r29", "test3", "part"),
]


def scene_labels(times: np.ndarray, scenes: np.ndarray) -> np.ndarray:
    """scenes[S,2] 时间区间 → 每帧场景 id（区间外 = -1）。"""
    labels = np.full(len(times), -1, dtype=np.int64)
    for si, (a, b) in enumerate(scenes):
        m = (times >= a - 1e-6) & (times <= b + 1e-6)
        labels[m] = si
    return labels


def lda_projection(X: np.ndarray, y: np.ndarray, k: int = 64) -> np.ndarray:
    """经典 LDA: S_b/S_w 广义特征问题 → 投影矩阵 [384, k]。类内散度加正则。"""
    classes = np.unique(y[y >= 0])
    mu_all = X[y >= 0].mean(axis=0)
    S_w = np.zeros((X.shape[1], X.shape[1]), dtype=np.float64)
    S_b = np.zeros_like(S_w)
    for c in classes:
        Xc = X[y == c]
        mu_c = Xc.mean(axis=0)
        d = (Xc - mu_c).astype(np.float64)
        S_w += d.T @ d
        sb = (mu_c - mu_all).astype(np.float64)
        S_b += len(Xc) * np.outer(sb, sb)
    # 正则化类内散度(帧级特征类内散度可能奇异)
    S_w += 1e-3 * np.trace(S_w) / S_w.shape[0] * np.eye(S_w.shape[0])
    from scipy.linalg import eigh
    eigvals, eigvecs = eigh(np.linalg.solve(S_w, S_b))
    order = np.argsort(-eigvals)[:k]
    return eigvecs[:, order].astype(np.float32)   # [384, k]


def main():
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    IDX = Path(os.environ["SVL_DATA_DIR"]) / "index"
    data = {}
    for d in IDX.glob("*.idx"):
        try:
            f = np.load(d / "features.npy")
            n = f.shape[0]
            if n in FRAME_N.values():
                film = [k for k, v in FRAME_N.items() if v == n][0]
                scenes_p = d / "scenes.npy"
                scenes = np.load(scenes_p) if scenes_p.exists() else None
                data[film] = (f, np.load(d / "times.npy"), scenes)
        except Exception:
            continue
    print("索引:", {k: v[0].shape[0] for k, v in data.items()}, flush=True)

    # 1) 场景标签(逐片)
    labels = {film: scene_labels(t, sc) if sc is not None else None
              for film, (f, t, sc) in data.items()}
    for film, lb in labels.items():
        n_sc = len(np.unique(lb[lb >= 0]))
        print(f"  {film}: 场景 {n_sc}, 未覆盖帧 {(lb < 0).sum()}", flush=True)

    # 2) 全局 LDA(四片联合, 场景标签=类)
    Xs, ys = [], []
    for film, (f, t, sc) in data.items():
        lb = labels[film]
        m = lb >= 0
        Xs.append(f[m].astype(np.float64)); ys.append(lb[m])
    X = np.concatenate(Xs); y = np.concatenate(ys)
    print(f"LDA 输入: {X.shape}, 类数 {len(np.unique(y))}", flush=True)

    results = {}
    for k in (16, 64, 128):
        W = lda_projection(X, y, k=k)
        proj = {}
        for film, (f, t, sc) in data.items():
            proj[film] = (f @ W, t)
        results[k] = (proj, W)
        print(f"  LDA k={k} 完成", flush=True)

    # 3) 失败案例: 原空间 vs 各 LDA 空间的 GT 最优排名
    def gt_rank(f_t, q, o0, o1):
        f, t = f_t
        win = np.where((t >= o0 - 2.0) & (t <= o1 + 2.0))[0]
        if not len(win):
            return None
        s = f @ q
        best = 99999
        for i in win:
            best = min(best, int((s > s[i]).sum()) + 1)
        return best

    print(f"\n{'case':10s}{'状态':6s}{'原rank':>8}" + "".join(f"{f'k={k}':>8}" for k in (16, 64, 128)), flush=True)
    fixed = {k: 0 for k in (16, 64, 128)}
    total = 0
    for gid, film, status in CASES:
        gt = json.loads(Path("datasets/real", GT_FILE[film]).read_text(encoding="utf-8"))
        p = next(x for x in gt["positives"] if x["id"] == gid)
        e0, e1 = p["edited"]; o0, o1 = p["original"]
        ed_vid, _ = FILM_META[film]
        res = json.loads(Path(f"work/rerun_{film}_perfopt.results.json").read_text(encoding="utf-8"))["results"]
        cov = [r for r in res if min(e1, r["edited_segment"]["end"]) - max(e0, r["edited_segment"]["start"]) > 0]
        if not cov:
            continue
        r0 = cov[0]
        frames = [f for _, f in srv.ffmpeg.iter_frames(ed_vid, 2.0,
                  start=r0["edited_segment"]["start"], end=r0["edited_segment"]["end"])]
        if not frames:
            continue
        q0 = srv.backend.embed_frames(frames).mean(axis=0)
        q0 /= max(float(np.linalg.norm(q0)), 1e-8)
        ranks = [gt_rank(data[film][:2], q0, o0, o1) or 99999]
        for j, k in enumerate((16, 64, 128)):
            proj_k, W_k = results[k]
            f, t = proj_k[film]
            qk = q0 @ W_k   # 投影空间查询 = q0 @ W_k（与索引同一投影）
            ranks.append(gt_rank((f, t), qk, o0, o1) or 99999)
        total += 1
        for j, k in enumerate((16, 64, 128)):
            if ranks[0] > 20 and ranks[j + 1] <= 20:
                fixed[k] += 1
        cells = "".join((f"{r:>8}" if r < 99999 else "     池外") for r in ranks)
        print(f"{gid:10s}{status:6s}{cells}", flush=True)
    print(f"\n池外→池内: k=16 {fixed[16]} | k=64 {fixed[64]} | k=128 {fixed[128]}  (共 {total} 失败案例)", flush=True)


if __name__ == "__main__":
    main()
