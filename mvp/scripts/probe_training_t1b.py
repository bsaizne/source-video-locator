# -*- coding: utf-8 -*-
"""T1b: 对比微调可行性探针（残差 MLP 头 + 时间对比监督, CPU 分钟级, 零 runtime）。

监督: 时间对比——同片 ±1.5s 内为正样本, 批内其他帧为负（含 4~30s 同片难负的天然混合）。
模型: 残差头 out = normalize(f + MLP_θ(f)), 冻结 backbone 特征不动 → 原空间是特例。
训练: 3 片(2mkv/test1/test2), hold-out = test3（泛化验证）。
评估: 22 条失败案例 GT 排名 before/after + 易例抽查 + hold-out 分辨。
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
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import load_config  # noqa: E402

FRAME_N = {"2mkv": 7668, "test1": 8221, "test2": 5051, "test3": 10177}
TRAIN_FILMS = ["2mkv", "test1", "test2"]
HOLDOUT = "test3"
FILM_META = {
    "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
    "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
    "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
    "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
}
GT_FILE = {"2mkv": "ground_truth_v4.json", "test1": "ground_truth_test1.json",
           "test2": "ground_truth_test2.json", "test3": "ground_truth_test3.json"}

# 失败案例 22 条（id, film, 状态）
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
# 易例对照（当前严格 HIT 的代表，验证投影后不破坏）
CONTROLS = [("2mkv", "p04"), ("2mkv", "p27"), ("test1", "t1r00"), ("test1", "t1r27"),
            ("test2", "t2r00"), ("test2", "t2r06b"), ("test3", "t3r07"), ("test3", "t3r12")]


class ResidualHead(nn.Module):
    def __init__(self, dim=384):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(dim, dim), nn.GELU(), nn.Linear(dim, dim))

    def forward(self, x):
        return torch.nn.functional.normalize(x + self.net(x), dim=-1)


def main():
    torch.manual_seed(7)
    np.random.seed(7)
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    IDX = Path(os.environ["SVL_DATA_DIR"]) / "index"
    feats, times, films = {}, {}, {}
    for d in IDX.glob("*.idx"):
        try:
            f = np.load(d / "features.npy")
            n = f.shape[0]
            if n in FRAME_N.values():
                film = [k for k, v in FRAME_N.items() if v == n][0]
                feats[film] = torch.from_numpy(f.astype(np.float32))
                times[film] = np.load(d / "times.npy").astype(np.float64)
                films[film] = film
        except Exception:
            continue

    # ---------- 训练 ----------
    model = ResidualHead()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    rng = np.random.RandomState(7)
    train_films = TRAIN_FILMS
    ft = {f: (feats[f], times[f]) for f in train_films}
    STEPS, BATCH, POS_WIN, HARD_LO, HARD_HI = 3000, 256, 1.5, 4.0, 30.0
    model.train()
    for step in range(STEPS):
        anchors, poss = [], []
        for _ in range(BATCH):
            f = train_films[rng.randint(len(train_films))]
            F, T = ft[f]
            i = rng.randint(len(T))
            dt = T - T[i]
            pos_cands = np.where((np.abs(dt) <= POS_WIN) & (np.arange(len(T)) != i))[0]
            if len(pos_cands) == 0:
                continue
            j = pos_cands[rng.randint(len(pos_cands))]
            anchors.append(F[i]); poss.append(F[j])
        if len(anchors) < 8:
            continue
        a = torch.stack(anchors); pj = torch.stack(poss)
        ea = model(a); ep = model(pj)
        logits = ea @ ep.T / 0.1
        labels = torch.arange(len(ea))
        loss = torch.nn.functional.cross_entropy(logits, labels)
        opt.zero_grad(); loss.backward(); opt.step()
        if step % 500 == 0:
            acc = float((logits.argmax(1) == labels).float().mean())
            print(f"  step {step}: loss {loss.item():.4f} batch-acc {acc:.3f}", flush=True)
    model.eval()

    def project(film):
        with torch.no_grad():
            return model(feats[film]).numpy().astype(np.float32)

    # ---------- 评估 ----------
    def gt_rank(space, film, q, o0, o1):
        f, t = space[film]
        win = np.where((t >= o0 - 2.0) & (t <= o1 + 2.0))[0]
        if not len(win):
            return None
        s = f @ q
        return min(int((s > s[i]).sum()) + 1 for i in win)

    orig_space = {f: (feats[f].numpy(), times[f]) for f in feats}
    proj_space = {f: (project(f), times[f]) for f in feats}

    print(f"\n{'case':10s}{'film':6s}{'原rank':>8}{'新rank':>8}  判定", flush=True)
    fixed = fixed_holdout = n = n_holdout = 0
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
        with torch.no_grad():
            q1 = model(torch.from_numpy(q0[None, :])).numpy()[0].astype(np.float32)
        r_orig = gt_rank(orig_space, film, q0, o0, o1) or 99999
        r_proj = gt_rank(proj_space, film, q1, o0, o1) or 99999
        n += 1
        if film == HOLDOUT:
            n_holdout += 1
        improved = (r_orig > 20 and r_proj <= 20)
        if improved:
            fixed += 1
            if film == HOLDOUT:
                fixed_holdout += 1
        tag = "✅ 拉回" if improved else ("↗ 改善" if r_proj < r_orig - 5 else ("↘ 恶化" if r_proj > r_orig + 5 else "— 持平"))
        print(f"{gid:10s}{film:6s}{r_orig:>8}{r_proj:>8}  {tag}{' (hold-out)' if film == HOLDOUT else ''}", flush=True)

    print(f"\n失败案例: 池外→池内 {fixed}/{n}（其中 hold-out {fixed_holdout}/{n_holdout}）", flush=True)
    print("易例对照:", flush=True)
    reg = 0
    for film, gid in CONTROLS:
        gt = json.loads(Path("datasets/real", GT_FILE[film]).read_text(encoding="utf-8"))
        p = next(x for x in gt["positives"] if x["id"] == gid)
        e0, e1 = p["edited"]; o0, o1 = p["original"]
        ed_vid, _ = FILM_META[film]
        frames = [f for _, f in srv.ffmpeg.iter_frames(ed_vid, 2.0, start=e0, end=e1)]
        q0 = srv.backend.embed_frames(frames).mean(axis=0)
        q0 /= max(float(np.linalg.norm(q0)), 1e-8)
        with torch.no_grad():
            q1 = model(torch.from_numpy(q0[None, :])).numpy()[0].astype(np.float32)
        r0 = gt_rank(orig_space, film, q0, o0, o1) or 99999
        r1 = gt_rank(proj_space, film, q1, o0, o1) or 99999
        flag = "" if (r0 <= 20 and r1 <= 20) else " ⚠️ 回退!"
        if flag:
            reg += 1
        print(f"  {gid:10s} {film:6s} 原{r0:>5} 新{r1:>5}{flag}", flush=True)
    print(f"易例回退: {reg}/{len(CONTROLS)}", flush=True)


if __name__ == "__main__":
    main()
