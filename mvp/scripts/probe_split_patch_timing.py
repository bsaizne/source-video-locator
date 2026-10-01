# -*- coding: utf-8 -*-
"""shot_split + patch_refine 归因/提速微探针（研究侧，零 runtime 改动）。

背景：续33 后续把两旋钮接进生产路径，ON 臂单片 31-44min vs OFF 7-8min（旋钮自身
~24-36min），但档案明确「未做单臂拆分归因」。本探针回答两件事：
  1) 归因：旋钮耗时里 grab_frame（ffmpeg spawn）vs embed（DML forward）vs patch_score
     （numpy）各占多少 —— 决定「并行抓帧」值不值。
  2) 提速 A/B：同输入子集在「改前(baseline)/改后(optimized)」跑，dump 每段 span，
     供逐位一致 diff + 墙钟对比。

两模用**同一套实例级打点**（补丁 srv.ffmpeg.grab_frame，线程安全 rec）保证 A/B 公平：
  - baseline ：grab_frame=raw 串行、无缓存、无并行（= 改动前生产接线）
  - optimized：grab_frame=_grab_frame_cached + grab_frames=_grab_frames_parallel（= 改动后）
optimized 下缓存命中会跳过 raw grab ⇒「raw grab 计数差 = 缓存省下次数」，
「raw grab 聚合时间差 = 并行+缓存省下时间」（并行下聚合 thread-time > 墙钟，仅看总墙钟）。

不重跑整条 locate()：旋钮在 locate() 末端、前段管线与开关无关，故
  off_{case}.results.json（旋钮前批）→ shot_split → patch_refine
精确复现 ON 臂后半段（参照 on_{case}.results.json，按 span 比对，排除 uuid result_id）。

Run:
  D:/claudework/video-dedup-tool/.venv/Scripts/python.exe \
      mvp/scripts/probe_split_patch_timing.py [case] [limit] [tag]
  # case=test1|2mkv|test2|test3  limit=0 表示全部段  tag=baseline|optimized
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.path.insert(0, str(BENCH / "mvp" / "scripts"))

import numpy as np  # noqa: E402

from app.locator_service import SourceLocatorService  # noqa: E402
from device.directml_backend import DirectMLBackend  # noqa: E402
from domain.models import ResultBatch  # noqa: E402
from engine.localization import patch_refine as PR  # noqa: E402
from engine.localization import shot_split as SS  # noqa: E402
from engine.localization.patch_rerank import (PatchReranker, resolve_patch_onnx,
                                              resolve_weights)  # noqa: E402
from infrastructure.config import load_config  # noqa: E402
from infrastructure.logging import configure_logging  # noqa: E402
from rerun_fast_global import CASES  # noqa: E402

OUT = BENCH / "work" / "spl_patch_timing"
T: dict[str, list] = {}   # name -> [total_seconds, count]
LOCK = threading.Lock()   # 并行抓帧线程安全累加


def rec(name: str, dt: float) -> None:
    with LOCK:
        a = T.setdefault(name, [0.0, 0])
        a[0] += dt
        a[1] += 1


def span_of(r) -> dict:
    """规范化 span（排除 shot_split 的 uuid result_id，用于逐位一致 diff）。"""
    return {
        "ed": [round(r.edited.start, 3), round(r.edited.end, 3)],
        "og": [round(r.original.start, 3), round(r.original.end, 3)],
        "segs": sorted([[round(s.start, 3), round(s.end, 3)] for s in r.original_segments]),
        "conf": r.confidence.level.value,
        "nis": bool(r.not_in_source),
    }


def main() -> int:
    configure_logging(stream=sys.stdout, level=30)
    case = sys.argv[1] if len(sys.argv) > 1 else "test1"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    tag = sys.argv[3] if len(sys.argv) > 3 else "baseline"
    optimized = tag.startswith("optimized")
    paths = CASES[case]
    edited, orig = paths["edited"], paths["original"]
    edited_rp = str(Path(edited).resolve())

    cfg = load_config()
    srv = SourceLocatorService(config=cfg)
    assert isinstance(srv.backend, DirectMLBackend), \
        "必须 DirectMLBackend, 实际 %s" % type(srv.backend).__name__
    print("BACKEND_SELECTED type=%s mode=%s" % (type(srv.backend).__name__, tag), flush=True)

    t0 = time.perf_counter()
    bundle = srv.build_original_index(orig)
    print("index ready in %.1fs frames=%d (reuse if <5s)"
          % (time.perf_counter() - t0, bundle.meta.num_frames), flush=True)
    lib_times = np.asarray(bundle.times, dtype=np.float64)
    lib_feats = bundle.features

    off = BENCH / "work" / "spl_patch_arms" / ("off_%s.results.json" % case)
    batch = ResultBatch.from_dict(json.loads(off.read_text(encoding="utf-8")))
    results = batch.results
    n_in = len(results)
    if limit > 0:
        results = results[:limit]
    print("input segments: %d of %d (limit=%d)" % (len(results), n_in, limit), flush=True)

    # patch reranker：与 locate() 同规格懒加载（DML ONNX 双输出优先）
    srv._patch_reranker = PatchReranker(
        resolve_weights(cfg.pipeline.patch_weights_path or None),
        resolve_patch_onnx((cfg.pipeline.patch_onnx_model or "").strip() or None),
        dml_device_id=cfg.device.dml_device_id)
    assert srv._patch_reranker.ensure(), "patch reranker 不可用（DML/torch 均失败）"
    print("patch reranker device=%s" % srv._patch_reranker.device, flush=True)

    # ---- 实例级打点：raw ffmpeg grab（两模都经此；线程安全，optimized 并行下也计量）----
    raw_grab = srv.ffmpeg.grab_frame

    def timed_grab(path, t, **k):
        s = time.perf_counter()
        fr = raw_grab(path, t, **k)
        rec("grab.edited" if str(Path(path).resolve()) == edited_rp else "grab.source",
            time.perf_counter() - s)
        return fr

    srv.ffmpeg.grab_frame = timed_grab   # _grab_frame_cached 内部也走这条 ⇒ 命中会跳过计时

    raw_embed = srv.backend.embed_frames

    def embed_cls(fr):
        s = time.perf_counter()
        out = raw_embed([fr])[0]
        rec("embed.cls", time.perf_counter() - s)
        return out

    raw_dual = srv._patch_reranker.frame_dual

    def embed_dual(fr):
        s = time.perf_counter()
        out = raw_dual(fr)
        rec("embed.dual", time.perf_counter() - s)
        return out

    raw_score = PR._patch_score

    def score(q, c):
        s = time.perf_counter()
        v = raw_score(q, c)
        rec("patch_score.numpy", time.perf_counter() - s)
        return v

    PR._patch_score = score

    # ---- 接线：baseline=raw 串行；optimized=缓存+并行批量（= 各自的生产接线）----
    if optimized:
        grab_kw = dict(grab_frame=srv._grab_frame_cached,
                       grab_frames=srv._grab_frames_parallel)
    else:
        grab_kw = dict(grab_frame=srv.ffmpeg.grab_frame)   # = timed_grab（串行、无缓存）

    # ---- shot_split（编辑侧 CLS）----
    t0 = time.perf_counter()
    split_out = SS.split_results(results, edited_path=edited, embed=embed_cls,
                                 lib_times=lib_times, lib_feats=lib_feats,
                                 log=srv._log, **grab_kw)
    t_split = time.perf_counter() - t0
    print("shot_split: %.1fs  results %d->%d" % (t_split, len(results), len(split_out)),
          flush=True)

    # ---- patch_refine（源侧 CLS+patch）----
    t0 = time.perf_counter()
    ref_out = PR.apply_patch_refine(split_out, edited_path=edited, source_path=orig,
                                    embed_dual=embed_dual, lib_times=lib_times,
                                    lib_feats=lib_feats, log=srv._log, **grab_kw)
    t_pr = time.perf_counter() - t0
    print("patch_refine: %.1fs  results %d->%d" % (t_pr, len(split_out), len(ref_out)),
          flush=True)

    wall = t_split + t_pr
    print("\n===== %s | case=%s limit=%d | 旋钮总墙钟 %.1fs (split %.1f + refine %.1f) ====="
          % (tag, case, limit, wall, t_split, t_pr), flush=True)
    print("%-20s%10s%8s%10s%8s" % ("stage", "sec", "calls", "s/call", "%wall"), flush=True)
    for k in ("grab.edited", "grab.source", "embed.cls", "embed.dual", "patch_score.numpy"):
        if k in T:
            sec, n = T[k]
            print("%-20s%10.1f%8d%10.3f%7.1f%%"
                  % (k, sec, n, sec / max(n, 1), sec / wall * 100), flush=True)
    accounted = sum(T[k][0] for k in T)
    print("%-20s%10.1f%8s%10s%7.1f%%"
          % ("(residual numpy/other)", wall - accounted, "-", "-",
             (wall - accounted) / wall * 100), flush=True)
    grab_n = T.get("grab.edited", [0, 0])[1] + T.get("grab.source", [0, 0])[1]
    grab_s = T.get("grab.edited", [0, 0])[0] + T.get("grab.source", [0, 0])[0]
    note = "（并行下为聚合 thread-time，>墙钟）" if optimized else ""
    print("\n>> raw grab %d 次 / 聚合 %.1fs %s；总墙钟 %.1fs 才是提速判据"
          % (grab_n, grab_s, note, wall), flush=True)

    OUT.mkdir(parents=True, exist_ok=True)
    payload = {
        "tag": tag, "case": case, "limit": limit,
        "wall_s": round(wall, 2), "split_s": round(t_split, 2),
        "refine_s": round(t_pr, 2),
        "stages": {k: [round(v[0], 3), v[1]] for k, v in T.items()},
        "n_in": len(results), "n_split": len(split_out), "n_ref": len(ref_out),
        "spans": [span_of(r) for r in ref_out],
    }
    fp = OUT / ("%s_%s.spans.json" % (tag, case))
    fp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote %s" % fp.name, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
