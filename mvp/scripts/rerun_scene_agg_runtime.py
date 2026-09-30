# -*- coding: utf-8 -*-
"""A1+方案A —— TransNetV2 切点 + 相邻相似度场景聚合(查询单元), 先结构筛选再四片定位.

动机(2026-09-25 盲判结论): TN 切点精确率/召回都明显高于我方两级像素切分
(2mkv 仅TN 8/8 真 vs 仅基线 2/8 真; test2 基线切点 ⊂ TN 切点), 但把 TN 段**直接当查询单元**
会让定位变差(-16/139) —— 因为定位层吃「大段 + 段内多帧 + 子span枚举」。
本方案: **切点用 TN(准), 查询单元用相似度聚合(大)** —— 相邻 shot 的 CLS 均值相似度 >= thr 则合并,
并按 max_len_s 限制单元长度(避免整段合一)。对应竞品 commentary_scene(场景=多镜头) 的语义。

用法:
  python mvp/scripts/rerun_scene_agg_runtime.py stats            # 结构筛选(四片, 只算不检索)
  python mvp/scripts/rerun_scene_agg_runtime.py locate [case]    # 用 AGG_THR/AGG_MAX_S 跑生产定位
环境: AGG_THR(默认 0.75) AGG_MAX_S(默认 12.0) TN_PROVIDER(默认 DmlExecutionProvider)
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
    "2mkv":  {"edited": r"D:\video\1.mp4", "original": r"D:\video\2.mkv",
              "gt": "datasets/real/ground_truth_v4.json", "base": "work/rerun_2mkv_perfopt.results.json"},
    "test1": {"edited": r"D:\ProjectXIXI\test1\test1-ed.mp4", "original": r"D:\ProjectXIXI\test1\test1-om.mkv",
              "gt": "datasets/real/ground_truth_test1.json", "base": "work/rerun_test1_perfopt.results.json"},
    "test2": {"edited": r"D:\ProjectXIXI\test2\tset2-ed.mp4", "original": r"D:\ProjectXIXI\test2\test2-om.mp4",
              "gt": "datasets/real/ground_truth_test2.json", "base": "work/rerun_test2_perfopt.results.json"},
    "test3": {"edited": r"D:\ProjectXIXI\test3\test3-ed.mp4", "original": r"D:\ProjectXIXI\test3\test3-om.mp4",
              "gt": "datasets/real/ground_truth_test3.json", "base": "work/rerun_test3_perfopt.results.json"},
}
TN_PROVIDER = os.environ.get("TN_PROVIDER", "DmlExecutionProvider")
AGG_THR = float(os.environ.get("AGG_THR", "0.60"))
AGG_MAX_S = float(os.environ.get("AGG_MAX_S", "12.0"))
MIN_SHOT_S = 0.5
THRS = [0.50, 0.55, 0.58, 0.60, 0.65]
MAXS_LIST = [8.0, 12.0, 20.0, 0.0]


# --------------------------------------------------------------------------- #
def _norm(v):
    return v / max(float(np.linalg.norm(v)), 1e-8)


def tn_cut_indices(ff, edited, ed_times):
    """TN 切点(原生 fps) -> 编辑特征帧索引(2fps 网格) 的段划分."""
    t = tn.boundaries(ff, edited, provider=TN_PROVIDER)
    n = len(ed_times)
    idx = [0]
    for c in t["cuts_sec"]:
        i = max(1, min(int(np.searchsorted(ed_times, c)), n - 1))
        if i > idx[-1]:
            idx.append(i)
    idx.append(n)
    segs = [(idx[k], idx[k + 1]) for k in range(len(idx) - 1)]
    return segs, t


def merge_short_segs(segs, ed_times, min_s=MIN_SHOT_S):
    """最短段保护: 反复把最短段并入较小的一侧(与 twopass 的 min_shot 同义)."""
    s = list(segs)
    while len(s) > 1:
        lens = [float(ed_times[b - 1] - ed_times[a]) for a, b in s]
        k = int(np.argmin(lens))
        if lens[k] >= min_s:
            break
        if k == 0:
            s[1] = (s[0][0], s[1][1]); s.pop(0)
        elif k == len(s) - 1:
            s[-2] = (s[-2][0], s[-1][1]); s.pop(-1)
        else:
            left = float(ed_times[s[k][0]] - ed_times[s[k - 1][0]])
            right = float(ed_times[s[k + 1][1] - 1] - ed_times[s[k][1] - 1])
            if left <= right:
                s[k - 1] = (s[k - 1][0], s[k][1]); s.pop(k)
            else:
                s[k + 1] = (s[k][0], s[k + 1][1]); s.pop(k)
    return s


def greedy_merge(segs, feats, ed_times, thr, max_s):
    """从左到右贪心: 相邻单元均值相似度 >= thr 且合并后时长 <= max_s 则合并."""
    if not segs:
        return []
    out = []
    cur_a, cur_b = segs[0]
    cur_v = _norm(feats[cur_a:cur_b].mean(axis=0))
    for a, b in segs[1:]:
        v = _norm(feats[a:b].mean(axis=0))
        sim = float(cur_v @ v)
        dur = float(ed_times[b - 1] - ed_times[cur_a])
        if sim >= thr and (max_s <= 0 or dur <= max_s):
            cur_b = b
            cur_v = _norm(feats[cur_a:cur_b].mean(axis=0))
        else:
            out.append((cur_a, cur_b))
            cur_a, cur_b = a, b
            cur_v = _norm(feats[a:b].mean(axis=0))
    out.append((cur_a, cur_b))
    return out


def build_shots(self, merged, ed_feats, ed_times):
    return [ShotSegment(span=TimeSpan(float(ed_times[a]), float(ed_times[b - 1])),
                        feats=ed_feats[a:b], times=ed_times[a:b])
            for a, b in merged if b > a]


def _segment_scene_agg(self, edited, cfg, on_progress, cancel_token) -> list[ShotSegment]:
    """TN 切点 + 相似度场景聚合(替换 _segment_twopass_flash; 其余生产逻辑不变)."""
    edited = Path(edited)
    self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION, message="transnetv2 cuts")
    self._notify(on_progress, ProgressStage.EDITED_FEATURE_EXTRACTION, message="extracting edited frames")
    frames = list(self.ffmpeg.iter_frames(edited, cfg.edited_segment_fps))
    self._check_cancel(cancel_token)
    if not frames:
        raise RuntimeError("edited video has no frames extracted: %s" % edited.name)
    ed_times = np.array([t for t, _ in frames], dtype=np.float32)
    ed_feats = self._embed_batch([f for _, f in frames], cancel_token)
    segs, tinfo = tn_cut_indices(self.ffmpeg, edited, ed_times)
    segs = merge_short_segs(segs, ed_times, MIN_SHOT_S)
    merged = greedy_merge(segs, ed_feats, ed_times, AGG_THR, AGG_MAX_S)
    self._log.info("scene_agg tn_cuts=%d shot=%d merged=%d thr=%.2f max_s=%.1f",
                   len(tinfo["cuts_sec"]), len(segs), len(merged), AGG_THR, AGG_MAX_S)
    shots = build_shots(self, merged, ed_feats, ed_times)
    self._notify(on_progress, ProgressStage.SEGMENT_DETECTION, message="scene aggregation")
    return self._apply_card_guard(shots, frames, ed_times, cfg)


# --------------------------------------------------------------------------- #
def gt_segments(gt_rel):
    d = json.loads((BENCH / gt_rel).read_text(encoding="utf-8"))
    segs = []
    for k in ("positives", "negatives"):
        for it in d.get(k, []):
            segs.append([float(it["edited"][0]), float(it["edited"][1])])
    return sorted(segs)


def unit_stats(units, gt_segs):
    """units: [(start_s, end_s)] 查询单元; 返回 intact(整段落在同一单元) 等指标."""
    m = len(units)
    intact = 0
    inner = 0
    split = 0
    for a, b in gt_segs:
        if b - a < 1.0:
            continue
        # GT 段被切成几块
        cuts = [x for x in units if a < x[0] < b]
        if not cuts:
            intact += 1
        else:
            split += 1
            inner += len(cuts)
    return {"n_units": m, "intact": intact, "split": split, "inner": inner}


def stage_stats(only=None):
    cfg = load_config()
    cfg.pipeline.edited_cache_enabled = False
    srv = SourceLocatorService(config=cfg)
    out = {}
    for name, p in CASES.items():
        if only and name != only:
            continue
        frames = list(srv.ffmpeg.iter_frames(Path(p["edited"]), cfg.pipeline.edited_segment_fps))
        ed_times = np.array([t for t, _ in frames], dtype=np.float32)
        ed_feats = srv._embed_batch([f for _, f in frames], None)
        segs, tinfo = tn_cut_indices(srv.ffmpeg, Path(p["edited"]), ed_times)
        segs_ms = merge_short_segs(segs, ed_times, MIN_SHOT_S)
        gt_segs = gt_segments(p["gt"])
        # 基线(生产两级切分+白闪)段作为对照
        base = json.loads((BENCH / p["base"]).read_text(encoding="utf-8"))["results"]
        base_units = sorted([[float(r["edited_segment"]["start"]), float(r["edited_segment"]["end"])] for r in base])
        sims = [_norm(ed_feats[a:b].mean(axis=0)) @ _norm(ed_feats[c:d].mean(axis=0))
                for (a, b), (c, d) in zip(segs_ms[:-1], segs_ms[1:])]
        sims = np.array(sims) if sims else np.zeros(0)
        print("\n=== %s | %.1fs | TN 切点 %d -> shot %d (min_shot 后) ===" % (
            name, len(ed_times) / cfg.pipeline.edited_segment_fps, len(tinfo["cuts_sec"]), len(segs_ms)), flush=True)
        if sims.size:
            print("  相邻 shot 相似度: p10=%.3f p25=%.3f p50=%.3f p75=%.3f p90=%.3f" % (
                np.percentile(sims, 10), np.percentile(sims, 25), np.percentile(sims, 50),
                np.percentile(sims, 75), np.percentile(sims, 90)), flush=True)
        print("  %-22s %6s %7s %6s %6s" % ("variant", "units", "intact", "split", "inner"), flush=True)
        bs = unit_stats([[float(u[0]), float(u[1])] for u in base_units], gt_segs)
        print("  %-22s %6d %7d %6d %6d   <- 基线(生产两级切分)" % (
            "BASELINE", bs["n_units"], bs["intact"], bs["split"], bs["inner"]), flush=True)
        row = {"case": name, "tn_cuts": len(tinfo["cuts_sec"]), "shots": len(segs_ms),
               "baseline": bs, "thr": {}}
        if sims.size:
            row["sim_pct"] = {k: round(float(np.percentile(sims, v)), 4)
                              for k, v in (("p10", 10), ("p25", 25), ("p50", 50), ("p75", 75), ("p90", 90))}
        for maxs in MAXS_LIST:
            for thr in THRS:
                merged = greedy_merge(segs_ms, ed_feats, ed_times, thr, maxs)
                units = [[float(ed_times[a]), float(ed_times[b - 1])] for a, b in merged]
                st = unit_stats(units, gt_segs)
                row.setdefault("grid", {})["thr%.2f_max%.0f" % (thr, maxs)] = st
                print("  %-22s %6d %7d %6d %6d" % ("thr=%.2f max=%.0fs" % (thr, maxs), st["n_units"],
                                                   st["intact"], st["split"], st["inner"]), flush=True)
        out[name] = row
    (BENCH / "work" / "scene_agg_stats.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nsaved work/scene_agg_stats.json", flush=True)
    return 0


def stage_locate(only):
    import app.locator_service as ls
    ls.SourceLocatorService._segment_twopass_flash = _segment_scene_agg
    cfg = load_config()
    cfg.pipeline.edited_cache_enabled = False
    srv = SourceLocatorService(config=cfg)
    b = srv.backend
    print("BACKEND_SELECTED type=%s device=%s | AGG_THR=%s AGG_MAX_S=%s" % (
        type(b).__name__, getattr(b, "device_name", lambda: "?")(), AGG_THR, AGG_MAX_S), flush=True)
    tag = "agg%02d_%s" % (int(AGG_THR * 100), str(AGG_MAX_S).replace(".", "p"))
    for name, p in CASES.items():
        if only and name != only:
            continue
        out_p = BENCH / "work" / ("sa_%s_%s.results.json" % (tag, name))
        if out_p.exists() and not os.environ.get("SVL_FORCE_RERUN"):
            print("  %s: skip" % name, flush=True)
            continue
        print("\n=== %s : scene-agg (TN cuts + sim merge) locate ===" % name, flush=True)
        t0 = time.monotonic()
        try:
            batch = srv.locate(p["edited"], p["original"], on_progress=_P())
            out_p.write_text(json.dumps(batch.to_dict(), ensure_ascii=False, indent=1), encoding="utf-8")
            n_high = sum(1 for r in batch.results if r.confidence.level.value == "HIGH")
            print("  %s: %d 段 HIGH=%d elapsed=%.1fs -> %s" % (
                name, len(batch.results), n_high, time.monotonic() - t0, out_p.name), flush=True)
        except Exception as exc:
            import traceback
            print("  %s FAILED: %s: %s" % (name, type(exc).__name__, exc), flush=True)
            traceback.print_exc()
    print("\nALL DONE", flush=True)
    return 0


class _P:
    def __init__(self):
        self.t0 = time.monotonic(); self.last = 0.0; self.stage = None

    def __call__(self, ev):
        now = time.monotonic()
        stage = getattr(getattr(ev, "stage", None), "value", "?")
        if stage != self.stage or now - self.last > 20:
            self.stage = stage; self.last = now
            print("    [progress +%6.1fs] %-22s %s/%s %s" % (
                now - self.t0, stage, getattr(ev, "current", 0), getattr(ev, "total", 0) or "?",
                getattr(ev, "message", "")), flush=True)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "stats"
    only = sys.argv[2] if len(sys.argv) > 2 else None
    configure_logging(stream=sys.stdout)
    if mode == "stats":
        return stage_stats(only)
    if mode == "locate":
        return stage_locate(only)
    print("usage: rerun_scene_agg_runtime.py [stats|locate] [case]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
