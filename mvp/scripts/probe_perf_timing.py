# -*- coding: utf-8 -*-
"""性能分阶段计时探针（研究侧, 零 runtime 改动, monkey-patch 计时）。

包点:
  - FFmpegIO.iter_frames          全部解码/seek
  - backend.embed_frames          全部 embed（含帧数）
  - _segment_twopass_flash        两级切分总耗时
  - _embed_dense_query            每段 8fps 密帧
  - EvidenceLocalizer.localize    每段定位
  - evidence_localize.finloc_window   finloc 精化
  - locator_service.align_moments    帧级 moment DP
  - _patch_rerank_span            patch rerank
  - ConfidenceEngine.assess_evidence 置信
  - 进度回调时间戳 -> 每段墙钟分布
运行: python mvp/scripts/probe_perf_timing.py [2mkv|test1|test2|test3]
"""
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

os.environ["SVL_DATA_DIR"] = r"C:\Users\Bsaizne\AppData\Roaming\Video Locator AI\data"
os.environ["MEDIA_FFMPEG"] = r"D:\claudework\benchmark\tools\ffmpeg.exe"
os.environ["MEDIA_FFPROBE"] = r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages\static_ffmpeg\bin\win32\ffprobe.exe"
BENCH = Path(r"D:\claudework\benchmark")
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

from app import locator_service as LS  # noqa: E402
from app.locator_service import SourceLocatorService  # noqa: E402
from engine.confidence.confidence import ConfidenceEngine  # noqa: E402
from media.ffmpeg.ffmpeg_io import FFmpegIO  # noqa: E402
from engine.localization import evidence_localize as EL  # noqa: E402
from engine.localization.evidence_localize import EvidenceLocalizer  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from infrastructure.logging import configure_logging  # noqa: E402

T = defaultdict(float)
N = defaultdict(int)


def timed(name, fn):
    def wrapper(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            T[name] += time.perf_counter() - t0
            N[name] += 1
    return wrapper


def main():
    configure_logging(stream=sys.stdout, level=30)  # WARNING 只留警告, INFO 不刷屏
    only = sys.argv[1] if len(sys.argv) > 1 else "test1"
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)

    # 全部解码 与 全部 embed
    _iter = FFmpegIO.iter_frames
    def iter_frames(self, *a, **k):
        t0 = time.perf_counter()
        frames = list(_iter(self, *a, **k))
        T["decode.iter_frames"] += time.perf_counter() - t0
        N["decode.iter_frames"] += 1
        N["decode.frames"] += len(frames)
        return frames
    FFmpegIO.iter_frames = iter_frames

    # backend 惰性创建: 先取一次再包实例方法
    be = srv.backend
    _embed = be.embed_frames
    def embed_frames(frames, *a, **k):
        t0 = time.perf_counter()
        out = _embed(frames, *a, **k)
        T["embed.embed_frames"] += time.perf_counter() - t0
        N["embed.embed_frames"] += 1
        N["embed.frames"] += len(frames)
        return out
    be.embed_frames = embed_frames

    LS.SourceLocatorService._segment_twopass_flash = timed(
        "seg.twopass_flash", LS.SourceLocatorService._segment_twopass_flash)
    LS.SourceLocatorService._embed_dense_query = timed(
        "dense.8fps_query", LS.SourceLocatorService._embed_dense_query)
    LS.SourceLocatorService._patch_rerank_span = timed(
        "patch.rerank", LS.SourceLocatorService._patch_rerank_span)
    EvidenceLocalizer.localize = timed("loc.localize", EvidenceLocalizer.localize)
    EL.finloc_window = timed("loc.finloc_window", EL.finloc_window)
    LS.align_moments = timed("loc.align_moments", LS.align_moments)
    ConfidenceEngine.assess_evidence = timed(
        "conf.assess", ConfidenceEngine.assess_evidence)

    # 每段墙钟: 进度回调时间戳(CANDIDATE_RETRIEVAL 段 i 开始 -> 下一段开始)
    seg_walls = []
    last = {"t": None, "idx": None}
    CASES = {
        "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
        "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
        "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
        "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
    }[only]

    def progress(ev):
        now = time.perf_counter()
        cur = getattr(ev, "current", None)
        stage = getattr(ev, "stage", None)
        if stage is not None and getattr(stage, "name", "") == "CANDIDATE_RETRIEVAL":
            if last["t"] is not None and cur != last["idx"]:
                seg_walls.append((last["idx"], now - last["t"]))
            if cur != last["idx"]:
                last["t"], last["idx"] = now, cur

    t0 = time.perf_counter()
    batch = srv.locate(CASES[0], CASES[1], on_progress=progress)
    wall = time.perf_counter() - t0

    print(f"\n===== {only} 总墙钟 {wall:.1f}s, {len(batch.results)} 段 =====")
    print(f"{'阶段':<22}{'耗时s':>10}{'调用':>8}{'帧数':>10}{'占比':>8}")
    stage_sum = 0.0
    order = ["seg.twopass_flash", "decode.iter_frames", "embed.embed_frames",
             "dense.8fps_query", "loc.localize", "loc.finloc_window",
             "loc.align_moments", "patch.rerank", "conf.assess"]
    for k in order:
        if k in T:
            print(f"{k:<22}{T[k]:>10.1f}{N[k]:>8}{N.get(k.replace('embed_frames','frames').replace('iter_frames','frames'), ''):>10}"
                  f"{T[k]/wall*100:>7.1f}%")
    dec_frames = N.get("decode.frames", 0)
    emb_frames = N.get("embed.frames", 0)
    print(f"\n解码总帧数 {dec_frames}, embed 总帧数 {emb_frames}, "
          f"embed 吞吐 {emb_frames / max(T['embed.embed_frames'], 1e-6):.1f} fps")
    if seg_walls:
        ws = sorted(w for _, w in seg_walls)
        n = len(ws)
        print(f"每段墙钟 n={n} 中位 {ws[n//2]:.1f}s p90 {ws[int(n*0.9)]:.1f}s "
              f"max {ws[-1]:.1f}s 总和 {sum(ws):.0f}s")


if __name__ == "__main__":
    main()
