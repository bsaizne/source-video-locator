# -*- coding: utf-8 -*-
"""输入尺寸探针: 224 vs 518 —— 竞品 feature_image_size=224(常量流确证) vs 我方冻结的 518.

动机: FINDINGS/09 给出 feature_image_size = 224(零间隔相邻, 语义自洽), 而我方
device/dinov2_model._imagenet_preprocess 硬编码 resize 到 518x518。两者 patch 数不同
(224/14=16 -> 256 patch; 518/14=37 -> 1369 patch), 特征粒度与判别力可能不同。
这是 A1/A2 之后**唯一尚未测过的、且直接来自竞品配方**的维度。

做法(局部窗口口径, 与 research_feature_upgrade_v4.py 一致):
  * 查询帧 = 编辑片 qt 及 ±0.4s 三帧;
  * 真值窗 = GT(v4 / test3) 的 original 区间 ±1s @1fps;
  * 干扰窗 = 手工指定的兄弟机位/夜阳台窗 ±1s @1fps(与既有失败族定义一致);
  * 指标: margin = max(cos(q, 真值窗)) - max(cos(q, 干扰窗)), 对查询帧取均值; hit = margin>0 比例。
  * 224 侧需对 pos_embed 做双线性插值(DINOv2 官方 interpolate_pos_encoding 做法);
    模型本体与权重(work/dinov2_weights/dinov2_vits14_pretrain.pth)不变, 不改 mvp/src。

运行: python mvp/scripts/research_input_size_probe.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

BENCH = Path(r"D:\claudework\benchmark")
FFPROBE = (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", FFPROBE)
sys.path.insert(0, str(BENCH / "mvp" / "src"))

import cv2                                              # noqa: E402
from device.dinov2_model import DinoV2Small              # noqa: E402
from media.ffmpeg import FFmpegIO                        # noqa: E402

W_S = BENCH / "work" / "dinov2_weights" / "dinov2_vits14_pretrain.pth"
OUT = BENCH / "work" / "input_size_probe_results.json"

PAIRS = {
    "2mkv": dict(orig=r"D:\video\2.mkv", edit=r"D:\video\1.mp4"),
    "test3": dict(orig=r"D:\ProjectXIXI\test3\test3-om.mp4", edit=r"D:\ProjectXIXI\test3\test3-ed.mp4"),
}
# (id, pair, 查询秒, 真值窗, 干扰窗, 说明)
PROBES = [
    ("p08_brother",  "2mkv", 13.5,  (1108.15, 1109.1), (1048.0, 1050.0), "瞭望塔机位: 兄弟机位为干扰"),
    ("p08b_brother", "2mkv", 13.9,  (1108.15, 1109.1), (1048.0, 1050.0), "士兵特写: 同上"),
    ("p26_nightbal", "2mkv", 76.8,  (1768.2, 1770.05), (1692.0, 1694.0), "夜读 vs 夜阳台"),
    ("p01_easy",     "2mkv", 0.8,   (2417.5, 2418.1),  (2421.2, 2422.1), "易例对照(同场景相邻镜头)"),
    ("t3r12_dup",    "test3", 64.75, (466.0, 478.0),   (481.0, 488.0),   "重复镜头(失败族)"),
]
SIZES = [224, 518]
WIN_PAD = 1.0
WIN_FPS = 1.0


def preprocess(frame_bgr, size):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (size, size), interpolation=cv2.INTER_LINEAR)
    t = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1)
    mean = torch.tensor([0.485, 0.456, 0.406]).view(3, 1, 1)
    std = torch.tensor([0.229, 0.224, 0.225]).view(3, 1, 1)
    return ((t - mean) / std)


class AnySize(torch.nn.Module):
    """包一层: 输入任意尺寸时对 pos_embed 的 patch 部分做双线性插值(DINOv2 官方做法)."""

    def __init__(self, base, size):
        super().__init__()
        self.m = base
        self.size = size
        self.grid0 = int(round((base.pos_embed.shape[1] - 1) ** 0.5))

    def forward(self, x):
        B = x.shape[0]
        x = self.m.patch_embed(x)
        x = torch.cat((self.m.cls_token.expand(B, -1, -1), x), dim=1)
        pos = self.m.pos_embed
        n = x.shape[1] - 1
        if n != pos.shape[1] - 1:
            g = int(round(n ** 0.5))
            cls_pos = pos[:, :1]
            pp = pos[:, 1:].reshape(1, self.grid0, self.grid0, -1).permute(0, 3, 1, 2)
            pp = F.interpolate(pp, size=(g, g), mode="bicubic", align_corners=False)
            pp = pp.permute(0, 2, 3, 1).reshape(1, g * g, -1)
            pos = torch.cat([cls_pos, pp], dim=1)
        x = x + pos
        for blk in self.m.blocks:
            x = blk(x)
        return self.m.norm(x)[:, 0]


def embed(model, frames, size):
    if not frames:
        return np.zeros((0, 384), np.float32)
    outs = []
    with torch.no_grad():
        for i in range(0, len(frames), 8):
            batch = torch.stack([preprocess(f, size) for f in frames[i:i + 8]], dim=0)
            v = model(batch).numpy().astype(np.float32)
            outs.append(v)
    v = np.concatenate(outs, axis=0)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-8)


def window_frames(ff, path, a, b):
    a2, b2 = max(0.0, a - WIN_PAD), b + WIN_PAD
    return [f for _, f in ff.iter_frames(path, WIN_FPS, start=a2, end=b2)]


def main() -> int:
    ff = FFmpegIO()
    base = DinoV2Small()
    missing, unexpected = base.load_state_dict(
        torch.load(str(W_S), map_location="cpu", weights_only=True), strict=False)
    print("weights loaded | missing=%d unexpected=%d" % (len(missing), len(unexpected)), flush=True)
    base.eval()
    models = {s: AnySize(base, s).eval() for s in SIZES}

    out = {}
    for pid, pair, qt, truth, wrong, note in PROBES:
        p = PAIRS[pair]
        t0 = time.monotonic()
        q_frames = [ff.grab_frame(Path(p["edit"]), max(0.0, qt + d)) for d in (-0.4, 0.0, 0.4)]
        tr_frames = window_frames(ff, Path(p["orig"]), truth[0], truth[1])
        wr_frames = window_frames(ff, Path(p["orig"]), wrong[0], wrong[1])
        row = {"pair": pair, "note": note, "n_truth": len(tr_frames), "n_wrong": len(wr_frames)}
        for s in SIZES:
            m = models[s]
            q = embed(m, q_frames, s)
            tr = embed(m, tr_frames, s)
            wr = embed(m, wr_frames, s)
            tm = (q @ tr.T).max(axis=1)
            wm = (q @ wr.T).max(axis=1)
            margin = tm - wm
            row["size_%d" % s] = {"margin_mean": round(float(margin.mean()), 4),
                                  "margin_min": round(float(margin.min()), 4),
                                  "hit_rate": round(float((margin > 0).mean()), 3),
                                  "truth_max_mean": round(float(tm.mean()), 4),
                                  "wrong_max_mean": round(float(wm.mean()), 4)}
            print("  %-1s %-13s size=%d margin=%+.4f (min %+.4f, hit %.2f) truth=%.4f wrong=%.4f" % (
                pair[0], pid, s, margin.mean(), margin.min(), (margin > 0).mean(), tm.mean(), wm.mean()), flush=True)
        out[pid] = row
        print("     (%s, %.1fs)" % (note, time.monotonic() - t0), flush=True)

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n=== 汇总 (margin_mean / hit_rate) ===", flush=True)
    print("  %-14s %-18s %-18s %s" % ("probe", "224", "518", "Δmargin"), flush=True)
    for pid, r in out.items():
        a, b = r["size_224"], r["size_518"]
        print("  %-14s %+.4f / %.2f    %+.4f / %.2f    %+.4f" % (
            pid, a["margin_mean"], a["hit_rate"], b["margin_mean"], b["hit_rate"],
            a["margin_mean"] - b["margin_mean"]), flush=True)
    print("\nsaved work/input_size_probe_results.json", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
