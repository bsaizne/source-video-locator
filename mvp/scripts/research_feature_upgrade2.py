"""Phase 23 特征升级预研(二):patch 级匹配探针(ViT-S vs ViT-B patch tokens)。

背景:预研(一)`research_feature_upgrade.py` 实锤 ViT-B/14 CLS 不解决
同场景/同质混淆(p08b 反而恶化),CLS 全局特征族在该失败模式上饱和。
本实验测交接单另一方向 = patch 级检索:V3 patch-max 得分(query patch 对
候选帧 patch 最大余弦,取 top100 均值,research_phase21 V3 定义),
在硬探针窗口上比较 ViT-S(384d)与 ViT-B(768d)patch token 的判别分离度。

窗口定义与预研(一)完全一致(干扰窗由 ViT-S CLS 全索引选出)。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" \
      mvp/scripts/research_feature_upgrade2.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

BENCH = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BENCH / "mvp" / "src"))

from device.dinov2_model import DinoV2Small, _imagenet_preprocess
from media.ffmpeg import FFmpegIO

FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
W_S = BENCH / "work" / "dinov2_weights" / "dinov2_vits14_pretrain.pth"
W_B = BENCH / "work" / "dinov2_weights" / "dinov2_vitb14_pretrain.pth"
IDX_DIR = Path("C:/Users/Bsaizne/AppData/Roaming/Video Locator AI/data/index")

PAIRS = {
    "2mkv":  dict(orig="D:/video/2.mkv",  edit="D:/video/1.mp4",
                  idx="2__4c6d4ab2"),
    "test3": dict(orig="D:/ProjectXIXI/test3/test3-om.mp4",
                  edit="D:/ProjectXIXI/test3/test3-ed.mp4",
                  idx="test3-om__074e2dcc"),
    "test4": dict(orig="D:/ProjectXIXI/test4/test4-om.mkv",
                  edit="D:/ProjectXIXI/test4/test4-ed.mp4",
                  idx="test4-om__eb686e0c"),
}

# 与 research_feature_upgrade.py 相同探针/窗口(结论可比)
QUERIES = [
    ("2mkv", "p26_hard", 76.8, (2808, 2811), "夜读书+手(CLS 硬混淆)"),
    ("2mkv", "p08_brother", 13.5, (1108, 1110), "瞭望塔机位:兄弟 1048-1050"),
    ("2mkv", "p08b_brother", 13.9, (1048, 1050), "士兵特写:兄弟 1108-1110"),
    ("2mkv", "p27_sign", 85.5, (1808, 1815), "WHAT字牌(回归观察)"),
    ("2mkv", "p01_easy", 0.8, (2417, 2428), "金属球(sanity 易例)"),
    ("test3", "t3r10_adj", 56.25, (441.5, 446.9), "逃亡奔跑:真值≈444.5(内缩避开447边界)"),
    ("test4", "t4r01_obs", 1.25, (3335, 3350), "同质滑梯(仅观察)"),
]
BROTHER = {"p08_brother": (1048, 1050), "p08b_brother": (1108, 1110)}
HALF_WIN = 20.0
HALF_DIST = 10.0
TOPK_DISTRACT = 40
PATCH_TOPK = 100  # V3: 每候选帧 query-patch 最大余弦的 top100 均值


def load_models():
    ms = DinoV2Small()
    ms.load_state_dict(torch.load(str(W_S), map_location="cpu", weights_only=True),
                       strict=False)
    ms.eval()
    mb = DinoV2Small(embed_dim=768, num_heads=12)
    mb.load_state_dict(
        torch.load(str(W_B), map_location="cpu", weights_only=True), strict=False)
    mb.eval()
    return ms, mb


@torch.no_grad()
def embed_patches(model, ff, video, ts, batch=4):
    """时刻列表 -> patch tokens L2 [N,P,D](CPU)。"""
    out = []
    for i in range(0, len(ts), batch):
        chunk = ts[i:i + batch]
        x = torch.cat([_imagenet_preprocess(ff.grab_frame(video, float(t)))
                       for t in chunk], dim=0)
        _, patches = model.forward_features(x)
        p = patches.numpy().astype(np.float32)
        p = p / np.maximum(np.linalg.norm(p, axis=2, keepdims=True), 1e-8)
        out.append(p)
    return np.concatenate(out, axis=0) if out else np.zeros((0, 1, 1), np.float32)


def runs_from_frames(ts_sorted, gap=5.0):
    if not len(ts_sorted):
        return []
    out = [[ts_sorted[0], ts_sorted[0]]]
    for t in ts_sorted[1:]:
        if t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


def patch_max_score(q_patches, cand_patches):
    """V3: query 各 patch 对候选帧 patch 最大余弦 -> top100 均值。"""
    m = np.asarray(q_patches @ cand_patches.T).max(axis=0)
    k = min(PATCH_TOPK, m.shape[0])
    return float(np.sort(np.asarray(m).ravel())[-k:].mean())


def main() -> int:
    t0 = time.time()
    ff = FFmpegIO(FFMPEG, FFPROBE)
    ms, mb = load_models()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"),
              "method": "patch-max top100 (research_phase21 V3)",
              "probes": []}

    for pair, pid, qt, true_win, note in QUERIES:
        cfg = PAIRS[pair]
        feats = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "features.npy")
        times = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "times.npy")

        q_ts = [qt - 0.4, qt, qt + 0.4]
        q_cls_s = None
        # 干扰窗仍由 ViT-S CLS 全索引选出(与预研一同口径)
        x_q = torch.cat([_imagenet_preprocess(ff.grab_frame(cfg["edit"], float(t)))
                         for t in q_ts], dim=0)
        with torch.no_grad():
            cls_q, pat_q_s = ms.forward_features(x_q)
            _, pat_q_b = mb.forward_features(x_q)
        cls_s = cls_q.mean(dim=0).numpy().astype(np.float32)
        cls_s /= max(np.linalg.norm(cls_s), 1e-8)
        q_pat_s = pat_q_s.numpy().astype(np.float32)   # [3,P,384]
        q_pat_b = pat_q_b.numpy().astype(np.float32)   # [3,P,768]
        q_pat_s = q_pat_s / np.maximum(
            np.linalg.norm(q_pat_s, axis=2, keepdims=True), 1e-8)
        q_pat_b = q_pat_b / np.maximum(
            np.linalg.norm(q_pat_b, axis=2, keepdims=True), 1e-8)

        sims_s = feats @ cls_s
        confusable = [int(i) for i in np.argsort(-sims_s)[:TOPK_DISTRACT]
                      if not (true_win[0] - HALF_DIST <= times[i]
                              <= true_win[1] + HALF_DIST)]
        distract_runs = runs_from_frames(
            sorted(float(times[i]) for i in confusable))
        distract_wins = [(max(0, a - HALF_DIST), b + HALF_DIST)
                         for a, b in distract_runs[:2]]
        if pid in BROTHER:
            distract_wins.insert(0, BROTHER[pid])
        if pair == "test3":
            distract_wins.insert(0, (447.0, 450.0))

        true_ts = [float(t) for t in times
                   if true_win[0] <= t <= true_win[1]]
        dist_ts = sorted({float(t) for a, b in distract_wins
                          for t in times if a <= t <= b})
        # 每窗候选帧上限 12(均匀抽),控制 patch 计算量
        def thin(ts_list, cap=12):
            if len(ts_list) <= cap:
                return ts_list
            idx = np.linspace(0, len(ts_list) - 1, cap).round().astype(int)
            return [ts_list[i] for i in idx]
        true_ts_t, dist_ts_t = thin(true_ts), thin(dist_ts)
        all_ts = sorted(set(true_ts_t + dist_ts_t))

        pat_s = embed_patches(ms, ff, cfg["orig"], all_ts)
        pat_b = embed_patches(mb, ff, cfg["orig"], all_ts)
        t2r = {t: k for k, t in enumerate(all_ts)}
        q_s_flat = np.concatenate(q_pat_s, axis=0)
        q_b_flat = np.concatenate(q_pat_b, axis=0)

        def margins(pat, q_flat):
            s_true = {t: patch_max_score(q_flat, pat[t2r[t]]) for t in true_ts_t}
            s_dist = {t: patch_max_score(q_flat, pat[t2r[t]]) for t in dist_ts_t}
            tm, dm = max(s_true.values()), max(s_dist.values())
            arg = max({**s_true, **s_dist}, key={**s_true, **s_dist}.get)
            return tm, dm, tm - dm, arg

        tms, dms, mgs, ams = margins(pat_s, q_s_flat)
        tmb, dmb, mgb, amb = margins(pat_b, q_b_flat)
        entry = {
            "id": pid, "pair": pair, "query_t": qt,
            "true_win": list(true_win), "note": note,
            "distract_wins": [[round(a, 1), round(b, 1)] for a, b in distract_wins],
            "patch_vits": {"true_max": round(tms, 4), "wrong_max": round(dms, 4),
                           "margin": round(mgs, 4), "argmax_t": round(ams, 1)},
            "patch_vitb": {"true_max": round(tmb, 4), "wrong_max": round(dmb, 4),
                           "margin": round(mgb, 4), "argmax_t": round(amb, 1)},
            "frames_embedded": len(all_ts) * 2,
        }
        report["probes"].append(entry)
        print(f"[{pid}] true={true_win} distract={entry['distract_wins']}\n"
              f"  patch ViT-S margin={mgs:+.4f} (true {tms:.4f} / wrong {dms:.4f})"
              f" argmax@{ams:.1f}\n"
              f"  patch ViT-B margin={mgb:+.4f} (true {tmb:.4f} / wrong {dmb:.4f})"
              f" argmax@{amb:.1f}", flush=True)

    out = BENCH / "work" / "feature_upgrade_probe2_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
