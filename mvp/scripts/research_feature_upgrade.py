"""Phase 23 特征升级预研:ViT-S/14 CLS(现役冻结基线) vs ViT-B/14 CLS 对照。

问题(STATE 交接单 A 项,2026-08-30 用户拍板立项):CLS 特征在
"同场景重复镜头 / 同质外观场景"上无分辨率(p26 真值 0.31 vs 错误 0.87;
test3-r10 相邻镜头错位;test4 全片同质滑梯最强 sim 0.53-0.60 互混)。
实验:三类实锤失败探针 + 易例回归,比较两个 backbone 的判别分离度。

口径:
- ViT-S = 现成全片索引缓存(Roaming Video Locator AI/data/index,1fps L2)。
- ViT-B = 对「真值窗口 + 干扰窗口」局部嵌入(窗口由 ViT-S 全索引干扰区选出,
  若 ViT-B 在该保守干扰集内把真值排第一,则全索引意义下方向性成立;
  结论边界 = 干扰覆盖不全,预研证据非产品验收)。
- 指标:sim_true_max / sim_wrong_max / margin = true_max - wrong_max /
  argmax 是否落真值窗。

运行:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" \
      mvp/scripts/research_feature_upgrade.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
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

# (pair, probe_id, query_t, true_win, note)  true_win=原片真值窗(秒)
QUERIES = [
    ("2mkv", "p26_hard", 76.8, (2808, 2811), "夜读书+手:CLS 硬混淆(ViT-S 0.31真/0.87错)"),
    ("2mkv", "p08_brother", 13.5, (1108, 1110), "瞭望塔机位:兄弟 1048-1050"),
    ("2mkv", "p08b_brother", 13.9, (1048, 1050), "士兵特写:兄弟 1108-1110"),
    ("2mkv", "p27_sign", 85.5, (1808, 1815), "WHAT字牌:同场景相似绿牌"),
    ("2mkv", "p01_easy", 0.8, (2417, 2428), "金属球准备(sanity 易例)"),
    ("2mkv", "p04_easy", 4.6, (833, 845), "峡谷航拍(sanity 易例)"),
    ("2mkv", "p17_easy", 36.0, (1397, 1419), "铁丝网山脊(sanity 易例)"),
    ("test3", "t3r10_adj", 56.25, (441.5, 447.0), "逃亡奔跑:真值≈444.5,错位447-449"),
    ("test4", "t4r01_obs", 1.25, (3335, 3350), "同质滑梯(仅观察,定位区即窗口)"),
    ("test4", "t4r13_obs", 66.0, (3335, 3350), "同质滑梯(仅观察,定位区即窗口)"),
]

BROTHER = {"p08_brother": (1048, 1050), "p08b_brother": (1108, 1110)}
HALF_WIN = 20.0     # 真值窗向两侧各扩的秒数(嵌入窗口)
HALF_DIST = 10.0    # 干扰窗半径
TOPK_DISTRACT = 40  # ViT-S 全索引取前 K 帧聚干扰区


def load_models():
    ms = DinoV2Small()
    ms.load_state_dict(torch.load(str(W_S), map_location="cpu", weights_only=True),
                       strict=False)
    ms.eval()
    mb = DinoV2Small(embed_dim=768, num_heads=12)
    ckpt = torch.load(str(W_B), map_location="cpu", weights_only=True)
    missing, unexpected = mb.load_state_dict(ckpt, strict=False)
    print(f"ViT-B load: missing={list(missing)} unexpected={list(unexpected)}",
          flush=True)
    mb.eval()
    return ms, mb


@torch.no_grad()
def embed_batch(model, ff, video, ts, batch=8):
    """时刻列表 -> CLS L2 特征 [N,D](CPU)。"""
    out = []
    for i in range(0, len(ts), batch):
        chunk = ts[i:i + batch]
        x = torch.cat([_imagenet_preprocess(ff.grab_frame(video, float(t)))
                       for t in chunk], dim=0)
        c = model(x)
        c = c.numpy().astype(np.float32)
        c = c / np.maximum(np.linalg.norm(c, axis=1, keepdims=True), 1e-8)
        out.append(c)
    return np.concatenate(out, axis=0) if out else np.zeros((0, 1), np.float32)


def runs_from_frames(ts_sorted, gap=5.0):
    """有序秒列表 -> 连续区 [(a,b)](gap 秒内算同区)。"""
    if not len(ts_sorted):
        return []
    out = [[ts_sorted[0], ts_sorted[0]]]
    for t in ts_sorted[1:]:
        if t - out[-1][1] <= gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return out


def main() -> int:
    t0 = time.time()
    ff = FFmpegIO(FFMPEG, FFPROBE)
    ms, mb = load_models()
    report = {"started": time.strftime("%Y-%m-%d %H:%M:%S"), "probes": []}

    for pair, pid, qt, true_win, note in QUERIES:
        cfg = PAIRS[pair]
        feats = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "features.npy")
        times = np.load(IDX_DIR / (cfg["idx"] + ".idx") / "times.npy")

        # --- 查询帧(ViT-S 与 ViT-B 各自嵌入) ---
        q_ts = [qt - 0.4, qt, qt + 0.4]
        q_s = embed_batch(ms, ff, cfg["edit"], q_ts).mean(axis=0)
        q_b = embed_batch(mb, ff, cfg["edit"], q_ts).mean(axis=0)
        q_s /= max(np.linalg.norm(q_s), 1e-8)
        q_b /= max(np.linalg.norm(q_b), 1e-8)

        # --- 真值窗 / 干扰窗 ---
        true_ts = [float(t) for t in times
                   if true_win[0] - 1 <= t <= true_win[1] + 1]
        sims_s = feats @ q_s
        confusable = [int(i) for i in np.argsort(-sims_s)[:TOPK_DISTRACT]
                      if not (true_win[0] - HALF_DIST <= times[i]
                              <= true_win[1] + HALF_DIST)]
        distract_runs = [r for r in runs_from_frames(
            sorted(float(times[i]) for i in confusable))]
        distract_wins = [(max(0, a - HALF_DIST), b + HALF_DIST)
                         for a, b in distract_runs[:2]]
        if pid in BROTHER:
            distract_wins.insert(0, BROTHER[pid])
        if pair == "test3":
            distract_wins.insert(0, (447.0, 450.0))  # 已知错位区

        # --- ViT-S 指标(全片缓存) ---
        true_s = max(sims_s[int(i)] for i in
                     np.where((times >= true_win[0]) & (times <= true_win[1]))[0])
        d_sims_s = [max(sims_s[int(i)] for i in
                        np.where((times >= a) & (times <= b))[0])
                    for a, b in distract_wins if
                    np.any((times >= a) & (times <= b))]
        argmax_s = float(times[int(np.argmax(sims_s))])

        # --- ViT-B 指标(局部窗口嵌入,同帧集合) ---
        all_ts = sorted(set(true_ts + [float(t) for a, b in distract_wins
                                       for t in times
                                       if a <= t <= b]))
        f_b = embed_batch(mb, ff, cfg["orig"], all_ts)
        t2r = {t: k for k, t in enumerate(all_ts)}
        sims_b = f_b @ q_b
        true_b = max(sims_b[t2r[t]] for t in true_ts) if true_ts else 0.0
        d_sims_b = [max(sims_b[t2r[float(t)]] for t in all_ts
                        if a <= t <= b) for a, b in distract_wins
                    if any(a <= t <= b for t in all_ts)]
        argmax_b = all_ts[int(np.argmax(sims_b))]

        # ViT-S 同帧集合口径(公平对照)
        sims_s_local = np.array([sims_s[int(np.argmin(np.abs(times - t)))]
                                 for t in all_ts])
        true_s_local = max(sims_s_local[t2r[t]] for t in true_ts) if true_ts else 0.0
        d_sims_s_local = [max(sims_s_local[t2r[float(t)]] for t in all_ts
                              if a <= t <= b) for a, b in distract_wins
                          if any(a <= t <= b for t in all_ts)]

        wrong_max_s = max(d_sims_s_local) if d_sims_s_local else float("nan")
        wrong_max_b = max(d_sims_b) if d_sims_b else float("nan")
        entry = {
            "id": pid, "pair": pair, "query_t": qt, "true_win": list(true_win),
            "note": note,
            "distract_wins": [[round(a, 1), round(b, 1)] for a, b in distract_wins],
            "argmax": {"s_full": round(argmax_s, 1), "s_local": None,
                       "b": round(argmax_b, 1)},
            "vit_s": {"true_max": round(float(true_s), 4),
                      "wrong_max": round(float(max(d_sims_s)), 4) if d_sims_s else None,
                      "wrong_max_local": round(float(wrong_max_s), 4),
                      "margin": round(float(true_s - wrong_max_s), 4)},
            "vit_b": {"true_max": round(float(true_b), 4),
                      "wrong_max": round(float(wrong_max_b), 4),
                      "margin": round(float(true_b - wrong_max_b), 4)},
            "frames_embedded": len(all_ts) + len(q_ts) * 2,
        }
        report["probes"].append(entry)
        print(f"[{pid}] true_win={true_win} distract={entry['distract_wins']}\n"
              f"  ViT-S margin={entry['vit_s']['margin']:+.4f} "
              f"(true {entry['vit_s']['true_max']:.4f} / wrong {entry['vit_s']['wrong_max_local']:.4f})"
              f"  argmax@{argmax_s:.1f}s\n"
              f"  ViT-B margin={entry['vit_b']['margin']:+.4f} "
              f"(true {entry['vit_b']['true_max']:.4f} / wrong {entry['vit_b']['wrong_max']:.4f})"
              f"  argmax@{argmax_b:.1f}s", flush=True)

    out = BENCH / "work" / "feature_upgrade_probe_results.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\nsaved {out}  total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
