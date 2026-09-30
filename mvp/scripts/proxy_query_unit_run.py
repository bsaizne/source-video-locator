# -*- coding: utf-8 -*-
"""D 段对照实验 ①: 用竞品(代理复现)的查询单元跑**我方现行生产栈**.

做法(零 mvp/src 改动, 与 A1 的 rerun_transnet_runtime.py 同款 harness 纪律):
  * monkey-patch SourceLocatorService._segment_twopass_flash -> _segment_proxy_units
    (查询单元边界 = 对方 scene_split_t050.json 的 cuts, 按各自 fps_rational 换秒;
     之后最短镜头保护 + 2fps 编辑侧特征切片 + card_guard 全部沿用生产逻辑);
  * 其余生产管线(索引 1.0fps/518、检索、事件扩池、patch v2、置信)完全不变;
  * 结果写 work/proxy_qu_<case>.results.json, 用 measure_four_results.py 同口径评估.

定级: 这是 "我方栈 + 代理复现查询单元", **不是**竞品实测, 也不是竞品定位口径的复现.
"""
from __future__ import annotations
import json, os, sys, time
from pathlib import Path
import numpy as np

BENCH = Path(r"D:\claudework\benchmark")
PROXY = Path(r"D:\claudework\cutmatch-analysis\sandbox\out")
os.environ.setdefault("SVL_DATA_DIR", r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from domain import TimeSpan
from app.models import ProgressStage
from engine.segment.segment import ShotSegment
from infrastructure.config import load_config
from infrastructure.logging import configure_logging
from app.locator_service import SourceLocatorService

CASES = {"2mkv": ("1.mp4", r"D:\video\1.mp4", r"D:\video\2.mkv"),
         "test1": ("test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
         "test2": ("tset2-ed.mp4", r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
         "test3": ("test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4")}
TH = os.environ.get("QU_THRESHOLD", "t050")


def _merge_short_bounds(bounds, min_shot_s, total):
    b = sorted(set(float(x) for x in bounds if 0.0 < float(x) < total))
    changed = True
    while changed and b:
        changed = False
        pts = [0.0] + b + [total]
        for i in range(1, len(pts) - 1):
            if min(pts[i] - pts[i - 1], pts[i + 1] - pts[i]) < min_shot_s:
                b.pop(i - 1); changed = True; break
    return b


def _proxy_cuts_sec(clip: str) -> list[float]:
    d = json.loads((PROXY / ("scene_split_%s.json" % TH)).read_text(encoding="utf-8"))[clip]
    fr = d["fps_rational"]
    num, den = (fr.split("/") if isinstance(fr, str) else (fr, 1))
    fps = float(num) / float(den)
    return [float(c["time_ms"]) / 1000.0 for c in d["cuts"]]


def _segment_proxy_units(self, edited, cfg, on_progress, cancel_token) -> list[ShotSegment]:
    """查询单元 = 代理复现 B 段(threshold=0.5)的切点; 其余同生产."""
    edited = Path(edited)
    clip = _CLIP_OF.get(edited.name)
    if clip is None:
        for _c, (nm, ed, _om) in CASES.items():
            if Path(ed).name == edited.name:
                clip = nm; break
    self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION, message="proxy query units")
    cuts = _proxy_cuts_sec(clip)
    print("    [proxy-units] %s cuts=%d" % (edited.name, len(cuts)), flush=True)
    frames = list(self.ffmpeg.iter_frames(edited, cfg.edited_segment_fps))
    self._check_cancel(cancel_token)
    if not frames:
        raise RuntimeError("edited video has no frames extracted: %s" % edited.name)
    ed_times = np.array([tt for tt, _ in frames], dtype=np.float32)
    ed_feats = self._embed_batch([f for _, f in frames], cancel_token)
    total = float(ed_times[-1]) if ed_times.size else 0.0
    bounds = _merge_short_bounds(cuts, cfg.seg_twopass_min_shot_s, total)
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
    self._notify(on_progress, ProgressStage.SEGMENT_DETECTION, message="proxy-unit segmentation")
    self._log.info("proxy-unit segments=%d (cuts=%d dropped_by_min_shot=%d)",
                   len(shots), len(cuts), len(cuts) - len(bounds))
    return self._apply_card_guard(shots, frames, ed_times, cfg)


_CLIP_OF = {}


class _Progress:
    def __init__(self):
        self.t0 = time.monotonic(); self.last = 0.0; self.stage = None
    def __call__(self, ev):
        now = time.monotonic()
        stage = getattr(getattr(ev, "stage", None), "value", "?")
        if stage != self.stage or now - self.last > 30:
            self.stage = stage; self.last = now
            print("    [progress +%6.1fs] %-22s %s/%s %s" % (
                now - self.t0, stage, getattr(ev, "current", 0), getattr(ev, "total", 0) or "?",
                getattr(ev, "message", "")), flush=True)


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    configure_logging(stream=sys.stdout)
    for nm, (clip, ed, om) in CASES.items():
        _CLIP_OF[Path(ed).name] = clip
    import app.locator_service as ls
    ls.SourceLocatorService._segment_twopass_flash = _segment_proxy_units
    cfg = load_config()
    cfg.pipeline.edited_cache_enabled = False
    srv = SourceLocatorService(config=cfg)
    try:
        b = srv.backend
        print("BACKEND_SELECTED %s/%s" % (type(b).__name__, getattr(b, "device_name", lambda: "?")()), flush=True)
    except Exception as exc:
        print("BACKEND_SELECTED ERROR: %s" % exc, flush=True)
    print("threshold=%s index_fps=%s edited_fps=%s" % (TH, cfg.pipeline.index_sampling_fps,
                                                      cfg.pipeline.edited_segment_fps), flush=True)
    for name, (clip, ed, om) in CASES.items():
        if only and name != only:
            continue
        out = BENCH / "work" / ("proxy_qu_%s.results.json" % name)
        print("\n=== %s (%s -> %s) ===" % (name, Path(ed).name, Path(om).name), flush=True)
        t0 = time.monotonic()
        res = srv.locate(Path(ed), Path(om), on_progress=_Progress())
        payload = res.to_dict() if hasattr(res, "to_dict") else res
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        n = len(payload.get("results", [])) if isinstance(payload, dict) else -1
        print("SAVED %s  n=%d  %.1fs" % (out, n, time.monotonic() - t0), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())