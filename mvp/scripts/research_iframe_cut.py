# -*- coding: utf-8 -*-
"""I帧锚定 + 动态步长 + 三特征抑制 切分研究探针（2026-09-05 用户方案）。

用户方案:
  第一层: I帧锚定粗筛 —— ffprobe 取所有 I 帧时间戳(比特流级,零解码成本),
           I 帧作为"免费锚点"(I 帧本身大概率=编码器场景切换点);
  第二层: 动态步长细扫 —— 慢节奏镜头(帧间差异小)步长 8-12 帧, 快节奏(差异大)
           步长 3-5 帧; 全程不做 1 帧全量遍历;
  精修:   候选切点 ±10 帧范围 1fps 精度回扫;
  通用假阳性抑制: 镜头切换判定须同时满足 ≥2 个核心特征:
           ① 颜色直方图差异超阈值  ② 边缘轮廓特征差异超阈值  ③ 帧差/运动突变(SSD);
           单一特征波动(仅亮度/仅抖动)直接抑制不生成候选切点。

Stage 0 前提(ffprobe 实测, 见 FINDINGS): 2mkv/test3 = 固定 10s GOP(仅 13/15 个
I 帧), 生产切点仅 10%/7% 落在 I 帧 ±0.5s 内 → 纯 I 帧粗筛不可行, 必须配动态步长;
test2 = 密 GOP(1.15s), 83% 切点落 I 帧 ±0.5s → I 帧锚定有效。本探针把 I 帧锚点
(零成本) + 一遍动态步长粗扫(慢 10 帧/快 4 帧自适应) 合并成网格, 验证整体三指标。

成本目标: 切分阶段零 embed(纯像素特征); embed 仅用于最终段特征(检索必需)。
诊断输出: work/diag_<case>_iframecut.json(各阶段帧数/耗时)。

实现: 子类化 SourceLocatorService, 仅覆盖 analyze_edited_video 的切分步骤;
其余管线(_locate_features/时序/冲突/ambiguity/card_guard/text_anchor)零改动。
结果批保存到 work/rerun_<case>_iframecut.results.json。零 runtime 改动。
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from app.locator_service import SourceLocatorService  # noqa: E402
from app.models import ProgressStage  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from domain import TimeSpan  # noqa: E402
from engine.segment import ShotSegment  # noqa: E402
from flash_guard import (is_flash_frame, drop_flash_cuts, dynamic_min_shot,
                         merge_flash_segments, FLASH_DYN_MIN_SHOT_S,
                         frame_mean_brightness, brightness_spike_regions,
                         drop_brightness_spike_cuts)  # noqa: E402

CASES = {
    "2mkv":  {"edited": r"D:\video\1.mp4",            "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",  "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",  "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",  "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
}

# ---- 切分参数(一次定死, 不 sweep) ----
COARSE_STEP_SLOW_FRAMES = 10   # 慢节奏步长(帧): 8-12 区间取 10
COARSE_STEP_FAST_FRAMES = 4    # 快节奏步长(帧): 3-5 区间取 4
FINE_WINDOW_FRAMES = 10        # 精修窗: 候选切点 ±10 帧
FINE_STEP_FRAMES = 1           # 精修步长(帧): 1fps 精度回扫
MIN_SHOT_S = 0.5               # 最短镜头保护
FLASH_MARGIN_S = 0.25          # 白闪邻域
NEED_FEATURES = 2              # ≥2 特征同时超阈值才判切点
DENSE_MARGIN_S = 0.25          # I 帧锚点去重: 距网格帧 < 此值不重复抽

# ---- 三特征阈值(Bhattacharyya 距离 0-1 量纲; 初值 = 1.mp4 生产切点统计 p10, 见 FINDINGS) ----
HIST_TH = 0.22     # 颜色直方图(3ch×16bin)
EDGE_TH = 0.18     # 边缘 Sobel 幅值直方图
SSD_TH = 0.16      # 帧差(下采样灰度绝对差均值/255)


def probe_iframe_times(vid):
    """ffprobe 取所有 I 帧时间戳(零解码成本)。"""
    out = subprocess.run([os.environ["MEDIA_FFPROBE"], "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "frame=pict_type,pts_time", "-of", "csv=p=0", str(vid)],
                         capture_output=True, text=True, encoding="utf-8", errors="replace",
                         timeout=120)
    times = []
    for ln in out.stdout.strip().split("\n"):
        parts = ln.strip().split(",")
        if len(parts) < 2:
            continue
        try:
            t = float(parts[0])
        except ValueError:
            continue
        if parts[1].strip() == "I":
            times.append(t)
    return sorted(times)


def _gray_small(frame, side=64):
    h, w = frame.shape[:2]
    ys = np.linspace(0, h - 1, side).astype(int)
    xs = np.linspace(0, w - 1, side).astype(int)
    return frame[np.ix_(ys, xs, [0])][..., 0].astype(np.float32)


def color_hist_dist(a, b, bins=16):
    d = 0.0
    for c in range(3):
        ha, _ = np.histogram(a[..., c].ravel(), bins=bins, range=(0, 256))
        hb, _ = np.histogram(b[..., c].ravel(), bins=bins, range=(0, 256))
        ha = ha / max(1e-6, ha.sum()); hb = hb / max(1e-6, hb.sum())
        d += 1.0 - np.sum(np.sqrt(ha * hb))
    return d / 3.0


def edge_hist_dist(a, b, bins=16):
    def sobel_hist(f):
        g = _gray_small(f, 128)
        gx = np.abs(np.diff(g, axis=1)); gy = np.abs(np.diff(g, axis=0))
        mag = gx[:-1, :] + gy[:, :-1]
        h, _ = np.histogram(mag.ravel(), bins=bins, range=(0, 510))
        return h / max(1e-6, h.sum())
    ha, hb = sobel_hist(a), sobel_hist(b)
    return 1.0 - np.sum(np.sqrt(ha * hb))


def frame_ssd(a, b):
    ga, gb = _gray_small(a), _gray_small(b)
    return float(np.mean(np.abs(ga - gb)) / 255.0)


def features_diff(a, b):
    return {"hist": color_hist_dist(a, b), "edge": edge_hist_dist(a, b),
            "ssd": frame_ssd(a, b)}


def n_over(fd):
    return int(fd["hist"] >= HIST_TH) + int(fd["edge"] >= EDGE_TH) + int(fd["ssd"] >= SSD_TH)


class IframeCutService(SourceLocatorService):
    """I帧锚定 + 动态步长 + 三特征抑制版: 仅替换 analyze_edited_video 的切分步骤。"""

    def analyze_edited_video(self, edited, *, on_progress=None, cancel_token=None):
        edited = Path(edited)
        self._check_cancel(cancel_token)
        cfg = self.config.pipeline
        self._ensure_session()
        self._log.info("analysis started edited=%s (iframecut)", edited.name)
        diag = {"case": edited.stem}
        try:
            meta = self.ffmpeg.metadata(edited)
            vfps = float(meta.fps) if meta.fps else 29.0
            dur = float(meta.duration) if meta.duration else 0.0
            if vfps <= 0:
                vfps = 29.0
            diag.update(fps=vfps, dur=dur)
            self._log.info("iframecut fps=%s dur=%.1f", vfps, dur)

            # --- ① 一遍粗扫(慢步长 vfps/10 ≈ 2.9fps): 主网格 ---
            t0 = time.monotonic()
            base_fps = vfps / COARSE_STEP_SLOW_FRAMES
            base = list(self.ffmpeg.iter_frames(edited, base_fps))
            diag["coarse_frames"] = len(base)
            diag["coarse_s"] = round(time.monotonic() - t0, 2)
            self._check_cancel(cancel_token)
            if not base:
                raise Exception(f"edited video has no frames extracted: {edited.name}")

            # --- ② I 帧锚点(零成本 ffprobe + 距网格帧远的 I 帧才 grab) ---
            t0 = time.monotonic()
            iframe_t = probe_iframe_times(edited)
            anchors = []
            for t in iframe_t:
                if any(abs(t - bt) < DENSE_MARGIN_S for bt, _ in base):
                    continue
                try:
                    anchors.append((t, self.ffmpeg.grab_frame(edited, t)))
                except Exception:
                    continue
            diag["iframes"] = len(iframe_t)
            diag["anchor_grabbed"] = len(anchors)
            diag["anchor_s"] = round(time.monotonic() - t0, 2)
            self._check_cancel(cancel_token)

            # --- ③ 动态步长加密: 高差异区段(≥1 特征超阈)内 iter_frames 一次细扫 ---
            # (避免逐点 grab_frame 子进程风暴; 每高差异区间一次 ffmpeg 调用, vfps/4 ≈ 7.25fps)
            t0 = time.monotonic()
            densified = []
            dense_fps = vfps / COARSE_STEP_FAST_FRAMES
            for j in range(1, len(base)):
                ta, fa = base[j - 1]
                tb, fb = base[j]
                fd = features_diff(fa, fb)
                if fd["hist"] >= HIST_TH or fd["edge"] >= EDGE_TH or fd["ssd"] >= SSD_TH:
                    try:
                        seg = list(self.ffmpeg.iter_frames(edited, dense_fps,
                                                           start=max(0.0, ta), end=tb))
                        densified.extend(seg)
                    except Exception:
                        continue
            diag["dense_frames"] = len(densified)
            diag["dense_s"] = round(time.monotonic() - t0, 2)
            self._check_cancel(cancel_token)

            # --- ④ 合并网格 + 去重 ---
            grid = sorted(base + anchors + densified, key=lambda x: x[0])
            dedup = []
            last_t = -1e9
            for t, fr in grid:
                if t - last_t > 2.0 / vfps:
                    dedup.append((t, fr))
                    last_t = t
            grid = dedup
            grid_t = np.array([t for t, _ in grid], dtype=np.float64)
            diag["grid_frames"] = len(grid)
            self._log.info("iframecut grid=%d (coarse=%d anchor=%d dense=%d)",
                           len(grid), len(base), len(anchors), len(densified))

            # --- ⑤ 候选切点: 相邻网格帧 ≥2 特征超阈值 ---
            cands = []
            for j in range(1, len(grid)):
                ta, fa = grid[j - 1]
                tb, fb = grid[j]
                fd = features_diff(fa, fb)
                if n_over(fd) >= NEED_FEATURES:
                    cands.append({"t": tb, "hist": round(fd["hist"], 3),
                                  "edge": round(fd["edge"], 3), "ssd": round(fd["ssd"], 3),
                                  "n": n_over(fd)})
            diag["candidates"] = len(cands)
            self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                         message=f"iframecut candidates: {len(cands)}")

            # --- ⑥ 白闪前置过滤 + 亮度尖峰: 邻域切点删除 ---
            flash_times = [t for t, fr in grid if is_flash_frame(fr)[0]]
            cut_times = [c["t"] for c in cands]
            cuts_kept = drop_flash_cuts(cut_times, flash_times, FLASH_MARGIN_S)
            means = np.array([frame_mean_brightness(fr) for _, fr in grid], dtype=np.float64)
            spikes = brightness_spike_regions(means, grid_t)
            cuts_kept = drop_brightness_spike_cuts(cuts_kept, spikes, FLASH_MARGIN_S)
            diag["flash_frames"] = len(flash_times)
            diag["cuts_after_flash"] = len(cuts_kept)
            self._log.info("iframecut cuts %d -> %d (flash=%d spikes=%d)",
                           len(cut_times), len(cuts_kept), len(flash_times), len(spikes))

            # --- ⑦ 局部 1fps 精修: 候选切点 ±10 帧(像素特征, 零 embed) ---
            t0 = time.monotonic()
            refined = []
            n_fine = 0
            for ct in cuts_kept:
                t0w = max(0.0, ct - FINE_WINDOW_FRAMES / vfps)
                t1w = min(dur, ct + FINE_WINDOW_FRAMES / vfps)
                try:
                    frames = list(self.ffmpeg.iter_frames(edited, vfps, start=t0w, end=t1w))
                except Exception:
                    refined.append(ct)
                    continue
                n_fine += len(frames)
                if len(frames) < 3:
                    refined.append(ct)
                    continue
                best_t, best_score = ct, -1.0
                for k in range(1, len(frames)):
                    ta, fa = frames[k - 1]
                    tb, fb = frames[k]
                    fd = features_diff(fa, fb)
                    score = fd["hist"] / HIST_TH + fd["edge"] / EDGE_TH + fd["ssd"] / SSD_TH
                    if score > best_score:
                        best_score = score
                        best_t = tb
                refined.append(round(best_t, 4))
            refined = sorted(set(x for x in refined if x > 0.05))
            diag["fine_frames"] = n_fine
            diag["fine_s"] = round(time.monotonic() - t0, 2)
            self._check_cancel(cancel_token)

            # --- ⑧ 最短镜头保护(0.5s) + 白闪动态阈值 + 业务兜底 ---
            pts = [0.0] + refined + ([dur] if dur > 0 else [])
            pts = sorted(set(round(x, 4) for x in pts))
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
            seg_bounds = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)
                          if pts[j + 1] - pts[j] >= MIN_SHOT_S]
            if flash_times:
                seg_bounds = merge_flash_segments(seg_bounds, flash_times)
            diag["segments_before_feats"] = len(seg_bounds)

            # --- ⑨ 每段特征: 优先复用网格帧; 段内网格帧 <2 或网格太稀 → 2fps 抽帧 embed ---
            t0 = time.monotonic()
            out_shots = []
            n_embed = 0
            for (a, b) in seg_bounds:
                m = (grid_t >= a - 1e-4) & (grid_t <= b + 1e-4)
                idx = np.flatnonzero(m)
                if idx.size >= 2 and (b - a) <= 2.0 * idx.size / max(1e-6, vfps):
                    st = grid_t[idx].astype(np.float32)
                    fe = self._embed_batch([fr for _, fr in grid][int(idx[0]):int(idx[-1]) + 1],
                                           cancel_token)
                else:
                    try:
                        sf = list(self.ffmpeg.iter_frames(edited, 2.0, start=a, end=b))
                    except Exception:
                        continue
                    if not sf:
                        continue
                    st = np.array([t for t, _ in sf], dtype=np.float32)
                    fe = self._embed_batch([f for _, f in sf], cancel_token)
                n_embed += len(st)
                out_shots.append(ShotSegment(span=TimeSpan(float(a), float(b)),
                                             feats=fe, times=st))
            diag["embed_frames"] = n_embed
            diag["embed_s"] = round(time.monotonic() - t0, 2)

            # card_guard: 用网格帧逐帧像素判别(复用原逻辑)
            card_flags = np.array([self._card_frame_flag(fr, cfg) for _, fr in grid],
                                  dtype=np.float32)
            for s in out_shots:
                m = (grid_t >= s.span.start - 1e-6) & (grid_t <= s.span.end + 1e-6)
                s.card_ratio = float(card_flags[m].mean()) if bool(m.any()) else 0.0
            self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                         message=f"iframecut final: {len(out_shots)} seg")
            self._log.info("iframecut final segments=%d", len(out_shots))
            diag["segments"] = len(out_shots)
            out = BENCH / "work" / f"diag_{diag['case']}_iframecut.json"
            out.write_text(json.dumps(diag, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as exc:
            self._log.exception("analysis failed edited=%s", edited.name)
            raise
        self._current_edited = edited
        return out_shots

    def _embed_batch(self, bgr_list, cancel_token):
        embs = []
        _BS = 16
        n = len(bgr_list)
        for i in range(0, n, _BS):
            self._check_cancel(cancel_token)
            embs.append(self.backend.embed_frames(bgr_list[i:i + _BS]))
        return np.concatenate(embs, axis=0)

    def _card_frame_flag(self, frame, cfg):
        from engine.segment.card_guard import is_card_frame
        return is_card_frame(frame, black_ratio=cfg.card_black_ratio,
                             bright_lo=cfg.card_bright_lo, bright_hi=cfg.card_bright_hi,
                             bright_max_spread=cfg.card_bright_max_spread,
                             bright_min_area_frac=cfg.card_bright_min_area_frac)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config()
    cfg.pipeline.edited_segment_fps = 2.0
    srv = IframeCutService(config=cfg)
    try:
        b = srv.backend
        print(f"BACKEND_SELECTED type={type(b).__name__} "
              f"device={getattr(b, 'device_name', lambda: '?')()} "
              f"dtype={getattr(b, 'device_type', lambda: '?')()}", flush=True)
    except Exception as bexc:
        print(f"BACKEND_SELECTED ERROR: {bexc}", flush=True)
    for name, paths in CASES.items():
        if only and name != only:
            continue
        out = BENCH / "work" / f"rerun_{name}_iframecut.results.json"
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print(f"  {name}: skip (result exists: {out.name})", flush=True)
            continue
        print(f"\n=== {name} rerun (iframecut) ===", flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"])
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            print(f"  {name}: {len(batch.results)} 段 HIGH={n_high} elapsed={time.monotonic()-t0:.1f}s -> {out.name}", flush=True)
        except Exception as exc:
            print(f"  {name} FAILED: {type(exc).__name__}: {exc}", flush=True)
    print("\nALL DONE", flush=True)


if __name__ == "__main__":
    main()
