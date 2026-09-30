# -*- coding: utf-8 -*-
"""A1-locate — TransNetV2 场景切分 替换 编辑侧两级切分 = 四片生产管线单点实验.

对标依据(竞品 CutMatch V7.1.0 静态逆向, 项目 D:/claudework/cutmatch-analysis):
  * 137 模块图 cutmatch.matching.scene_detection.* 对应 a01 = TransNetV2(确证);
  * 我方现状 = detect_shots 两级像素切分 + 白闪守卫, 从未使用学习式切分器。

做法(与 rerun_vitb_runtime.py 同款 harness 纪律, 零 mvp/src 改动):
  * monkey-patch SourceLocatorService._segment_twopass_flash -> _segment_transnet
    (TransNetV2 边界 -> 最短镜头保护 -> 2fps 特征切片 -> card_guard);
  * 其余生产管线不变(索引/检索/事件扩池/patch v2/置信等); 编辑缓存关闭(避免命中旧 shots);
  * 结果写 work/tn_<case>.results.json(不覆盖历史批), 用 measure_four_results.py 同口径评估。

边界先行结果(probe_transnet_bounds.py, work/tn_bounds_summary.json):
  TransNetV2 与我方两级切分边界高度重合(双向 recall 0.76-0.98, 中位距离 <0.1s)。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

BENCH = Path(r"D:\claudework\benchmark")

os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE",
                      r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")

sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from domain import TimeSpan                           # noqa: E402
from app.models import ProgressStage                  # noqa: E402
from engine.segment.segment import ShotSegment        # noqa: E402
from infrastructure.config import load_config         # noqa: E402
from infrastructure.logging import configure_logging  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
import tn_transnetv2 as tn                            # noqa: E402

CASES = {
    "2mkv":  {"edited": r"D:\video\1.mp4", "original": r"D:\video\2.mkv"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4", "original": r"D:\ProjectXIXI\test1\test1-om.mkv"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4", "original": r"D:\ProjectXIXI\test2\test2-om.mp4"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4", "original": r"D:\ProjectXIXI\test3\test3-om.mp4"},
}
TN_PROVIDER = os.environ.get("TN_PROVIDER", "DmlExecutionProvider")


def _merge_short_bounds(bounds: list[float], min_shot_s: float, total: float) -> list[float]:
    """最短镜头保护: 反复去掉造成过短段的边界(与 twopass 的 min_shot 同义)."""
    b = sorted(set(float(x) for x in bounds if 0.0 < float(x) < total))
    changed = True
    while changed and b:
        changed = False
        pts = [0.0] + b + [total]
        for i in range(1, len(pts) - 1):
            if min(pts[i] - pts[i - 1], pts[i + 1] - pts[i]) < min_shot_s:
                b.pop(i - 1)
                changed = True
                break
    return b


def _segment_transnet(self, edited, cfg, on_progress, cancel_token) -> list[ShotSegment]:
    """TransNetV2 版编辑侧切分(替换 _segment_twopass_flash; 其余生产逻辑不变)."""
    edited = Path(edited)
    self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION, message="transnetv2 boundaries")
    t = tn.boundaries(self.ffmpeg, edited, provider=TN_PROVIDER)
    self._log.info("transnet fps=%.3f frames=%d cuts=%d elapsed=%.1fs",
                   t["fps"], t["n_frames"], len(t["cuts_sec"]), t["elapsed"])

    self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION, message="extracting edited frames")
    frames = list(self.ffmpeg.iter_frames(edited, cfg.edited_segment_fps))
    self._check_cancel(cancel_token)
    if not frames:
        raise RuntimeError("edited video has no frames extracted: %s" % edited.name)
    ed_times = np.array([tt for tt, _ in frames], dtype=np.float32)
    ed_feats = self._embed_batch([f for _, f in frames], cancel_token)
    total = float(ed_times[-1]) if ed_times.size else 0.0

    bounds = _merge_short_bounds(t["cuts_sec"], cfg.seg_twopass_min_shot_s, total)
    idx = [0]
    for tt in bounds:
        i = max(1, min(int(np.searchsorted(ed_times, tt)), len(ed_times) - 1))
        if i > idx[-1]:
            idx.append(i)
    idx.append(len(ed_times))
    shots = [ShotSegment(span=TimeSpan(float(ed_times[idx[k]]), float(ed_times[idx[k + 1] - 1])),
                         feats=ed_feats[idx[k]:idx[k + 1]],
                         times=ed_times[idx[k]:idx[k + 1]])
             for k in range(len(idx) - 1) if idx[k + 1] > idx[k]]
    self._notify(on_progress, ProgressStage.SEGMENT_DETECTION, message="transnetv2 segmentation")
    self._log.info("transnet segments=%d (tn cuts=%d min_shot=%.2fs)",
                   len(shots), len(t["cuts_sec"]), cfg.seg_twopass_min_shot_s)
    return self._apply_card_guard(shots, frames, ed_times, cfg)


class _Progress:
    """阶段/心跳打印(长任务存活与阶段判定用; 每 20s 或阶段变化一行)."""

    def __init__(self):
        self.t0 = time.monotonic()
        self.last = 0.0
        self.stage = None

    def __call__(self, ev):
        now = time.monotonic()
        stage = getattr(getattr(ev, "stage", None), "value", "?")
        if stage != self.stage or now - self.last > 20:
            self.stage = stage
            self.last = now
            print("    [progress +%6.1fs] %-22s %s/%s %s" % (
                now - self.t0, stage, getattr(ev, "current", 0),
                getattr(ev, "total", 0) or "?", getattr(ev, "message", "")), flush=True)


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    configure_logging(stream=sys.stdout)
    import app.locator_service as ls
    ls.SourceLocatorService._segment_twopass_flash = _segment_transnet

    cfg = load_config()
    cfg.pipeline.edited_cache_enabled = False
    srv = SourceLocatorService(config=cfg)
    try:
        b = srv.backend
        print("BACKEND_SELECTED type=%s device=%s dtype=%s" % (
            type(b).__name__, getattr(b, "device_name", lambda: "?")(),
            getattr(b, "device_type", lambda: "?")()), flush=True)
    except Exception as exc:
        print("BACKEND_SELECTED ERROR: %s" % exc, flush=True)
    print("seg_twopass_enabled=%s (patched->_segment_transnet) TN_PROVIDER=%s index_fps=%s edited_fps=%s" % (
        cfg.pipeline.seg_twopass_enabled, TN_PROVIDER, cfg.pipeline.index_sampling_fps,
        cfg.pipeline.edited_segment_fps), flush=True)
    print("SVL_DATA_DIR=%s" % os.environ.get("SVL_DATA_DIR"), flush=True)

    for name, paths in CASES.items():
        if only and name != only:
            continue
        out = BENCH / "work" / ("tn_%s.results.json" % name)
        if out.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print("  %s: skip (result exists)" % name, flush=True)
            continue
        print("\n=== %s : TransNetV2 segmentation + production locate ===" % name, flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(paths["edited"], paths["original"], on_progress=_Progress())
            out.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            print("  %s: %d 段 HIGH=%d elapsed=%.1fs -> %s"
                  % (name, len(batch.results), n_high, time.monotonic() - t0, out.name), flush=True)
        except Exception as exc:
            import traceback
            print("  %s FAILED: %s: %s" % (name, type(exc).__name__, exc), flush=True)
            traceback.print_exc()
    print("\nALL DONE", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
