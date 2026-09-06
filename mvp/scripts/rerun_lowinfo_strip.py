# -*- coding: utf-8 -*-
"""低信息帧降权 + 段首尾边界帧剥离 探针（2026-09-05 用户方案 1）。

背景: 4 个负例中 n01/n02 是「前段模糊/未确定内容」→ 低信息帧泛化特征偶然命中源片。
数据摸底(scan_lowinfo_frames.py): n01/n02 contrast/edge 在全片低位(16-20%分位),
n02 50% 帧为低信息; n03/t3r15 为正常内容帧(低信息判据 0%)——预期只对 n01/n02 有效。

实现(研究探针, 零 runtime 改动): 子类化 SourceLocatorService, 覆盖 _segment_twopass_flash
(生产方法名, 分派自动走子类), 完整复用生产两级切分+白闪守卫逻辑, 仅在构造 ShotSegment
时叠加:
  ① 低信息帧降权: 粗网格帧算 (contrast, edge), 双低位(<=全片 pct 分位) → 从段特征剔除
     (不参与检索/定位; 段内剩帧 <MIN_KEEP_FRAMES 则保留原段防退化);
  ② 段首尾边界帧剥离: 段内首/尾各剥 STRIP_EDGE 帧(段帧数足够才剥)。
对照: 基线(四片 112/139 · 136/139 · 4/9) vs 探针(三指标 + 负例误报)。
产物: work/rerun_*_lowinfostrip.results.json。
"""
import json
import os
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
from engine.segment import (ShotSegment, detect_shots, adjacent_distances,  # noqa: E402
                            is_card_frame, max_card_run_ratio,
                            brightness_spike_regions, drop_brightness_spike_cuts,
                            drop_flash_cuts, dynamic_min_shot, frame_mean_brightness,
                            is_flash_frame, merge_flash_segments)

CASES = {
    "2mkv":  {"edited": r"D:\video\1.mp4",            "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",  "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",  "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",  "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
}

LOW_PCT = 25          # contrast/edge 双低位分位阈值(摸底: n01/n02 在 16-20%)
STRIP_EDGE = 1        # 段首尾各剥帧数
MIN_KEEP_FRAMES = 2   # 段内最少保留帧数(低于则回退原段)


def _gray_small(frame, side=96):
    h, w = frame.shape[:2]
    ys = np.linspace(0, h - 1, side).astype(int)
    xs = np.linspace(0, w - 1, side).astype(int)
    return frame[np.ix_(ys, xs, [0])][..., 0].astype(np.float32)


def _contrast_edge(frames):
    """粗网格帧列表 -> (contrast[], edge[])。"""
    contrast = []
    edges = []
    for _, f in frames:
        g = _gray_small(f)
        contrast.append(float(np.std(g)))
        gx = np.abs(np.diff(g, axis=1)); gy = np.abs(np.diff(g, axis=0))
        mag = gx[:-1, :] + gy[:, :-1]
        edges.append(float(np.mean(mag > 60)))
    return np.array(contrast), np.array(edges)


class LowInfoStripService(SourceLocatorService):
    """低信息帧降权 + 段首尾边界帧剥离版: 覆盖生产 _segment_twopass_flash。"""

    def _segment_twopass_flash(self, edited, cfg, on_progress, cancel_token):
        meta = getattr(self.ffmpeg, "metadata", None)
        meta = meta(edited) if callable(meta) else None
        vfps = float(meta.fps) if meta and meta.fps else 29.0
        dur = float(meta.duration) if meta and meta.duration else 0.0
        if vfps <= 0:
            vfps = 29.0
        coarse_fps = vfps / max(1, int(cfg.seg_twopass_coarse_step_frames))
        fine_fps = vfps / max(1, int(cfg.seg_twopass_fine_step_frames))
        self._log.info("lowinfo+strip fps=%s coarse_fps=%.2f fine_fps=%.2f dur=%.1f",
                       vfps, coarse_fps, fine_fps, dur)

        # --- ① 粗采样全片（一次 ffmpeg 遍历）---
        self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                     message="lowinfo coarse sampling")
        frames = list(self.ffmpeg.iter_frames(edited, coarse_fps))
        self._check_cancel(cancel_token)
        if not frames:
            raise Exception(f"edited video has no frames extracted: {edited.name}")
        ed_times = np.array([t for t, _ in frames], dtype=np.float32)
        if dur <= 0 and ed_times.size:
            dur = float(ed_times[-1])
        ed_feats = self._embed_batch([f for _, f in frames], cancel_token)
        # 低信息帧判据(像素): contrast+edge 双低位
        low_flags = np.zeros(len(frames), dtype=bool)
        if len(frames) >= 8:
            contrast, edges = _contrast_edge(frames)
            c_th = np.percentile(contrast, LOW_PCT)
            e_th = np.percentile(edges, LOW_PCT)
            low_flags = (contrast <= c_th) & (edges <= e_th)
            self._log.info("lowinfo frames=%d low=%d (c_th=%.1f e_th=%.3f)",
                           len(frames), int(low_flags.sum()), c_th, e_th)
        coarse_flash = np.array([is_flash_frame(f, cfg.flash_mean_th,
                                                cfg.flash_frac_th)[0] for _, f in frames])
        flash_times = [float(t) for t, fl in zip(ed_times, coarse_flash) if fl]
        self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                     current=len(frames), total=max(len(frames), 1),
                     message=f"特征提取 {len(frames)}/{len(frames)} 帧")

        # --- ② 粗切分（语义 detect_shots, fps=coarse_fps 换算帧间隔）---
        self._check_cancel(cancel_token)
        self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                     message="lowinfo coarse segmentation")
        shots = detect_shots(ed_feats, ed_times,
                             cut_abs=cfg.seg_cut_abs, z_thresh=cfg.seg_z_thresh,
                             min_shot_s=cfg.seg_min_shot_s, smooth=cfg.seg_smooth,
                             fps=coarse_fps)

        # --- ③ 切点后处理: 白闪/亮度尖峰邻域切点删除 ---
        cuts = [float(s.span.start) for s in shots[1:]]
        cuts_kept = drop_flash_cuts(cuts, flash_times, cfg.flash_margin_s)
        means = np.array([frame_mean_brightness(f) for _, f in frames], dtype=np.float64)
        spikes = brightness_spike_regions(means, ed_times,
                                          delta=cfg.bright_spike_delta,
                                          peak_th=cfg.bright_spike_peak_th)
        cuts_kept = drop_brightness_spike_cuts(cuts_kept, spikes, cfg.flash_margin_s)

        # --- ④ 局部密帧精修每个内部边界 ---
        refined_bounds = [0.0]
        for ct in cuts_kept:
            t = self._refine_cut_twopass(edited, ct, vfps, fine_fps,
                                         int(cfg.seg_twopass_fine_window_frames),
                                         cancel_token, cfg)
            refined_bounds.append(t)
        if dur > 0:
            refined_bounds.append(float(dur))
        refined_bounds = sorted(set(round(x, 4) for x in refined_bounds))

        # --- ⑤ 最短镜头保护 + 动态阈值 ---
        pts = list(refined_bounds)
        if flash_times:
            seg_tmp = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)]
            ths = dynamic_min_shot(seg_tmp, flash_times,
                                   min_shot_s=cfg.seg_twopass_min_shot_s,
                                   dyn_s=cfg.flash_dyn_min_shot_s,
                                   flash_margin_s=cfg.flash_margin_s)
            changed = True
            while changed:
                changed = False
                i = 1
                while i < len(pts) - 1:
                    gl = pts[i] - pts[i - 1]; gr = pts[i + 1] - pts[i]
                    tl = ths[i - 1]; tr = ths[i]
                    if gl < tl or gr < tr:
                        drop = i if (gl - tl) <= (gr - tr) else i + 1
                        del pts[drop]
                        seg_tmp = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)]
                        ths = dynamic_min_shot(seg_tmp, flash_times,
                                               min_shot_s=cfg.seg_twopass_min_shot_s,
                                               dyn_s=cfg.flash_dyn_min_shot_s,
                                               flash_margin_s=cfg.flash_margin_s)
                        changed = True
                    else:
                        i += 1
        else:
            changed = True
            while changed:
                changed = False
                i = 1
                while i < len(pts) - 1:
                    gl = pts[i] - pts[i - 1]; gr = pts[i + 1] - pts[i]
                    if gl < cfg.seg_twopass_min_shot_s or gr < cfg.seg_twopass_min_shot_s:
                        del pts[i if gl <= gr else i + 1]
                        changed = True
                    else:
                        i += 1
        seg_bounds = [(pts[j], pts[j + 1]) for j in range(len(pts) - 1)
                      if pts[j + 1] - pts[j] >= cfg.seg_twopass_min_shot_s]

        # --- ⑥ 业务兜底: 段内白闪占比高 -> 合并 ---
        if flash_times:
            seg_bounds = merge_flash_segments(seg_bounds, flash_times,
                                              merge_frac=cfg.flash_merge_frac)

        # --- ⑦ 构造 ShotSegment + 低信息降权 + 边界剥离 ---
        out_shots = []
        n_stripped = n_dropped = 0
        for (a, b) in seg_bounds:
            m = (ed_times >= a - 1e-4) & (ed_times <= b + 1e-4)
            idx = np.flatnonzero(m)
            if idx.size == 0:
                continue
            keep = np.ones(idx.size, dtype=bool)
            # 低信息帧剔除(段内)
            if low_flags.any():
                in_low = low_flags[idx]
                n_drop = int(in_low.sum())
                # 保留帧数 >= MIN_KEEP_FRAMES 才剔除, 否则保留原段
                if int(idx.size) - n_drop >= MIN_KEEP_FRAMES:
                    keep &= ~in_low
                    n_dropped += n_drop
            # 首尾边界帧剥离(段内帧数足够才剥)
            nk = int(keep.sum())
            if nk > 2 * STRIP_EDGE + MIN_KEEP_FRAMES:
                # 在保留集上剥首尾 STRIP_EDGE 个
                pos = np.flatnonzero(keep)
                drop_edges = set(pos[:STRIP_EDGE].tolist()) | set(pos[-STRIP_EDGE:].tolist())
                keep[[i for i in range(idx.size) if idx[i] in drop_edges]] = False
                n_stripped += 2 * STRIP_EDGE
            fi = idx[keep]
            if fi.size == 0:
                fi = idx
            times = ed_times[fi]
            feats = ed_feats[fi]
            out_shots.append(ShotSegment(span=TimeSpan(float(a), float(b)),
                                         feats=feats, times=times))
        self._log.info("lowinfo+strip final segments=%d (dropped=%d stripped=%d)",
                       len(out_shots), n_dropped, n_stripped)

        # card_guard: 用粗网格帧逐帧像素判别（复用原逻辑）
        card_flags = np.array([is_card_frame(f, black_ratio=cfg.card_black_ratio,
                                             bright_lo=cfg.card_bright_lo,
                                             bright_hi=cfg.card_bright_hi,
                                             bright_max_spread=cfg.card_bright_max_spread,
                                             bright_min_area_frac=cfg.card_bright_min_area_frac)
                               for _, f in frames], dtype=np.float32)
        for s in out_shots:
            m = (ed_times >= s.span.start - 1e-6) & (ed_times <= s.span.end + 1e-6)
            s.card_ratio = float(card_flags[m].mean()) if bool(m.any()) else 0.0
        for s in out_shots:
            seg_flags = [bool(card_flags[int(round((tt - ed_times[0]) * coarse_fps))])
                         for tt in ed_times
                         if s.span.start - 1e-6 <= tt <= s.span.end + 1e-6]
            s.card_run_ratio = float(max_card_run_ratio(seg_flags))
        self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                     current=len(out_shots), total=max(len(out_shots), 1),
                     message=f"{len(out_shots)} segments")
        return out_shots


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config()
    srv = LowInfoStripService(config=cfg)
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
        out = BENCH / "work" / f"rerun_{name}_lowinfostrip.results.json"
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print(f"  {name}: skip (result exists)", flush=True)
            continue
        print(f"\n=== {name} lowinfo+strip ===", flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"])
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1),
                           encoding="utf-8")
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            print(f"  {name}: {len(batch.results)} 段 HIGH={n_high} "
                  f"elapsed={time.monotonic()-t0:.1f}s -> {out.name}", flush=True)
        except Exception as exc:
            print(f"  {name} FAILED: {type(exc).__name__}: {exc}", flush=True)
    print("\nALL DONE", flush=True)


if __name__ == "__main__":
    main()
