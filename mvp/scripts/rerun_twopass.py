# -*- coding: utf-8 -*-
"""两级分层切分全量验证——C 项架构修正（2026-09-05）。

用户方案: ① 全局粗采样(5-8帧间隔)跑完整视频标记候选切点;
          ② 局部稠密回扫(切点±20帧, 1-2帧间隔)精修真实切点时间戳;
          约束: 最短镜头保护 0.5s + fps 换算间隔(不写死帧数)。

实现: 子类化 SourceLocatorService, 仅覆盖 analyze_edited_video 的切分步骤
(粗网格 embed → 生产 detect_shots → 逐边界密帧精修时间戳 → 最短镜头保护),
其余管线(_locate_features/时序/冲突/ambiguity/card_guard/text_anchor)零改动。
结果批保存到 work/rerun_<case>_twopass.results.json。零 runtime 改动。
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

from app.locator_service import SourceLocatorService  # noqa: E402
from app.models import ProgressStage  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from engine.segment import ShotSegment, detect_shots, adjacent_distances  # noqa: E402
from domain import TimeSpan  # noqa: E402

sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from flash_guard import (is_flash_frame, drop_flash_cuts, dynamic_min_shot,
                         merge_flash_segments, FLASH_DYN_MIN_SHOT_S)  # noqa: E402

sys.path.insert(0, str(BENCH / "mvp" / "scripts"))
from flash_guard import (is_flash_frame, drop_flash_cuts, dynamic_min_shot,
                         merge_flash_segments, FLASH_DYN_MIN_SHOT_S)  # noqa: E402

CASES = {
    "2mkv":  {"edited": r"D:\video\1.mp4",            "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4",  "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4",  "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4",  "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
}

# 用户方案参数(帧间隔, 运行时按视频 fps 换算成秒)
COARSE_STEP_FRAMES = 6      # 粗采样步长(帧): 5-8 帧区间取 6
FINE_WINDOW_FRAMES = 20     # 精修窗: 切点 ±20 帧
FINE_STEP_FRAMES = 2        # 精修采样步长(帧): 1-2 帧区间取 2
MIN_SHOT_S = 0.5            # 最短镜头保护(秒)


class TwoPassService(SourceLocatorService):
    """两级切分版: 仅替换 analyze_edited_video 的切分步骤。"""

    def analyze_edited_video(self, edited, *, on_progress=None, cancel_token=None):
        edited = Path(edited)
        self._check_cancel(cancel_token)
        cfg = self.config.pipeline
        self._ensure_session()
        self._log.info("analysis started edited=%s (twopass)", edited.name)
        try:
            meta = self.ffmpeg.metadata(edited)
            vfps = float(meta.fps) if meta.fps else 29.0
            dur = float(meta.duration) if meta.duration else 0.0
            if vfps <= 0:
                vfps = 29.0
            coarse_fps = vfps / COARSE_STEP_FRAMES      # ~4.8fps @29
            fine_fps = vfps / FINE_STEP_FRAMES          # ~14.5fps @29
            self._log.info("twopass fps=%s coarse_fps=%.2f fine_fps=%.2f dur=%.1f",
                           vfps, coarse_fps, fine_fps, dur)

            # --- ① 粗采样全片 ---
            self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION,
                         message="twopass coarse sampling")
            frames = list(self.ffmpeg.iter_frames(edited, coarse_fps))
            self._check_cancel(cancel_token)
            if not frames:
                raise Exception(f"edited video has no frames extracted: {edited.name}")
            ed_times = np.array([t for t, _ in frames], dtype=np.float32)
            ed_feats = self._embed_batch([f for _, f in frames], cancel_token)

            # --- 生产 detect_shots 粗切分(帧间隔已按 fps 换算) ---
            shots = detect_shots(ed_feats, ed_times, cut_abs=cfg.seg_cut_abs,
                                 z_thresh=cfg.seg_z_thresh, min_shot_s=cfg.seg_min_shot_s,
                                 smooth=cfg.seg_smooth, fps=coarse_fps)
            self._log.info("twopass coarse segments=%d", len(shots))
            self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                         message=f"twopass coarse: {len(shots)} seg")

            # --- ② 局部密帧精修每个内部边界时间戳 ---
            refined_bounds = [0.0]
            for s in shots[1:]:
                t = refine_cut(self, edited, float(s.span.start), vfps, fine_fps,
                               FINE_WINDOW_FRAMES, cancel_token)
                refined_bounds.append(t)
            if dur > 0:
                refined_bounds.append(float(dur))
            refined_bounds = sorted(set(round(x, 4) for x in refined_bounds))

            # --- ③ 最短镜头保护(0.5s): 反复合并 <MIN_SHOT_S 的切点(删较弱: 间距小的一侧) ---
            pts = list(refined_bounds)
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

            # --- 用粗网格帧构造 ShotSegment(边界用精修时间戳) ---
            out_shots = []
            for (a, b) in seg_bounds:
                m = (ed_times >= a - 1e-4) & (ed_times <= b + 1e-4)
                idx = np.flatnonzero(m)
                if idx.size == 0:
                    continue
                times = ed_times[idx]
                feats = ed_feats[idx]
                out_shots.append(ShotSegment(span=TimeSpan(float(a), float(b)),
                                             feats=feats, times=times))
            # card_guard: 用粗网格帧逐帧像素判别(复用原逻辑)
            card_flags = np.array([self._card_frame_flag(f, cfg) for _, f in frames],
                                  dtype=np.float32)
            for s in out_shots:
                m = (ed_times >= s.span.start - 1e-6) & (ed_times <= s.span.end + 1e-6)
                s.card_ratio = float(card_flags[m].mean()) if bool(m.any()) else 0.0
            self._notify(on_progress, ProgressStage.SEGMENT_DETECTION,
                         message=f"twopass final: {len(out_shots)} seg")
            self._log.info("twopass final segments=%d", len(out_shots))
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


def refine_cut(svc, edited, cut_t, vfps, fine_fps, window_frames, cancel_token):
    """局部密帧精修: 切点 ±window 帧窗内 fine_fps 采样, 相邻距离峰 → 精确切点时间。"""
    f = cut_t * vfps
    t0 = max(0.0, (f - window_frames) / vfps)
    t1 = (f + window_frames) / vfps
    frames = list(svc.ffmpeg.iter_frames(edited, fine_fps, start=t0, end=t1))
    if len(frames) < 3:
        return cut_t
    svc._check_cancel(cancel_token)
    feats = svc._embed_batch([fr for _, fr in frames], cancel_token)
    times = np.array([t for t, _ in frames], dtype=np.float32)
    d = adjacent_distances(feats)
    i = int(np.argmax(d))
    return float(times[i + 1])


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    cfg = load_config()
    cfg.pipeline.edited_segment_fps = 2.0   # 保持查询侧其他行为一致; 切分已被两级替换
    srv = TwoPassService(config=cfg)
    # 打印实际选中的推理后端（确认 DML/GPU 生效）
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
        out = BENCH / "work" / f"rerun_{name}_twopass.results.json"
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print(f"  {name}: skip (result exists: {out.name})", flush=True)
            continue
        print(f"\n=== {name} rerun (twopass) ===", flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"])
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            print(f"  {name}: {len(batch.results)} 段 HIGH={n_high} elapsed={time.monotonic()-t0:.1f}s -> {out.name}", flush=True)
        except Exception as exc:
            print(f"  {name} FAILED: {type(exc).__name__}: {exc}", flush=True)
    print("\nALL DONE", flush=True)


if __name__ == "__main__":
    main()
