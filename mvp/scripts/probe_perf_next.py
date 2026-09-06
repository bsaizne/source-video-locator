# -*- coding: utf-8 -*-
"""下一批性能优化探针（研究侧, 零 runtime 改动, monkey-patch 计时）。

回答四个问题:
  1. patch.rerank 133s 的构成: grab_frame(ffmpeg spawn) vs DML patch forward vs patch_score
  2. dense 8fps(81s) 的实际使用率: 多少段真的产出 moments / 触发密帧重试
  3. embed 帧按阶段分账: 切分(coarse+fine+card) / dense / patch / 其他
  4. 编辑侧持久缓存(A4)的上限: 同进程二次定位(热 session 缓存)能省多少
运行: python mvp/scripts/probe_perf_next.py [test1]
"""
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
from engine.localization import evidence_localize as EL  # noqa: E402
from engine.localization.evidence_localize import EvidenceLocalizer  # noqa: E402
from engine.localization.patch_rerank import PatchReranker, patch_score  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from infrastructure.logging import configure_logging  # noqa: E402
from media.ffmpeg.ffmpeg_io import FFmpegIO  # noqa: E402

T = defaultdict(float)
N = defaultdict(int)
STAGE = {"cur": "other"}


def timed(name, fn):
    def wrapper(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            T[name] += time.perf_counter() - t0
            N[name] += 1
    return wrapper


def staged(name, fn):
    """包一层阶段标记(内部 embed/grab 计入该阶段)。"""
    def wrapper(*a, **k):
        prev = STAGE["cur"]
        STAGE["cur"] = name
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            T[name] += time.perf_counter() - t0
            N[name] += 1
            STAGE["cur"] = prev
    return wrapper


def main():
    configure_logging(stream=sys.stdout, level=30)
    only = sys.argv[1] if len(sys.argv) > 1 else "test1"
    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    be = srv.backend

    # ---- 全局原语: grab_frame / embed_frames / frame_patches / patch_score 按当前阶段分账 ----
    _grab = FFmpegIO.grab_frame
    def grab_frame(self, path, t, *, scale=None):
        t0 = time.perf_counter()
        out = _grab(self, path, t) if scale is None else _grab(self, path, t, scale=scale)
        key = f"grab.{STAGE['cur']}"
        T[key] += time.perf_counter() - t0
        N[key] += 1
        return out
    FFmpegIO.grab_frame = grab_frame

    _embed = be.embed_frames
    def embed_frames(frames, *a, **k):
        t0 = time.perf_counter()
        out = _embed(frames, *a, **k)
        key = f"embed.{STAGE['cur']}"
        T[key] += time.perf_counter() - t0
        N[key] += 1
        N[f"frames.{STAGE['cur']}"] += len(frames)
        return out
    be.embed_frames = embed_frames

    _fp = PatchReranker.frame_patches
    def frame_patches(self, f):
        t0 = time.perf_counter()
        out = _fp(self, f)
        T["patch.frame_patches"] += time.perf_counter() - t0
        N["patch.frame_patches"] += 1
        return out
    PatchReranker.frame_patches = frame_patches

    _ps = patch_score
    def scored(q, c, **k):
        t0 = time.perf_counter()
        out = _ps(q, c, **k)
        T["patch.patch_score"] += time.perf_counter() - t0
        N["patch.patch_score"] += 1
        return out
    LS.patch_score = scored

    # ---- 阶段入口: 切分 / dense / patch / text anchor ----
    LS.SourceLocatorService._segment_twopass_flash = staged("seg", LS.SourceLocatorService._segment_twopass_flash)
    LS.SourceLocatorService._embed_dense_query = staged("dense", LS.SourceLocatorService._embed_dense_query)
    LS.SourceLocatorService._patch_rerank_span = staged("patch", LS.SourceLocatorService._patch_rerank_span)
    LS.SourceLocatorService._apply_text_anchor = staged("text", LS.SourceLocatorService._apply_text_anchor)

    # ---- dense 使用率: localize 产物是否真有 moments / 密帧重试 ----
    _loc = EvidenceLocalizer.localize
    stats = {"calls": 0, "with_moments": 0, "empty": 0}
    def localize(self, qf, qt, bundle, dense_query=None):
        r = _loc(self, qf, qt, bundle, dense_query=dense_query)
        stats["calls"] += 1
        if r.primary is None or r.primary.original_span is None:
            stats["empty"] += 1
        elif any(getattr(s, "moments", None) for s in ([r.primary] + list(r.spans or []))):
            stats["with_moments"] += 1
        return r
    EvidenceLocalizer.localize = localize

    CASES = {
        "2mkv": (r"D:\video\1.mp4", r"D:\video\2.mkv"),
        "test1": (r"D:\ProjectXIXI\test1\test1-ed.mp4", r"D:\ProjectXIXI\test1\test1-om.mkv"),
        "test2": (r"D:\ProjectXIXI\test2\tset2-ed.mp4", r"D:\ProjectXIXI\test2\test2-om.mp4"),
        "test3": (r"D:\ProjectXIXI\test3\test3-ed.mp4", r"D:\ProjectXIXI\test3\test3-om.mp4"),
    }[only]

    t0 = time.perf_counter()
    batch = srv.locate(CASES[0], CASES[1])
    wall1 = time.perf_counter() - t0
    print(f"\n===== {only} 第一次定位 {wall1:.1f}s, {len(batch.results)} 段 =====")
    print(f"{'项':<26}{'耗时s':>9}{'调用':>8}{'帧数':>8}")
    for k in sorted(T):
        frames_key = "frames." + k.split(".", 1)[1] if "." in k else ""
        print(f"{k:<26}{T[k]:>9.1f}{N[k]:>8}{N.get(frames_key, ''):>8}")
    print(f"dense 使用: localize {stats['calls']} 次, 产 moments {stats['with_moments']} 段, "
          f"空证据 {stats['empty']} 次")

    # ---- A4 上限: 同进程二次定位(session 内 _dense_cache/_tr_query_cache/_grab_cache 热) ----
    t0 = time.perf_counter()
    batch2 = srv.locate(CASES[0], CASES[1])
    wall2 = time.perf_counter() - t0
    print(f"\n===== 同进程二次定位 {wall2:.1f}s (热 session 缓存; 持久化缓存的下限参照) =====")
    print(f"A4 可省上限(首跑-热跑): {wall1 - wall2:.1f}s; "
          f"切分+embed 若也持久化, 理论再省见上面 seg/embed.dense 行")


if __name__ == "__main__":
    main()
