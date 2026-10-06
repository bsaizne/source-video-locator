# -*- coding: utf-8 -*-
"""LOC-1107 片尾越界修复的真实素材 A/B（2026-10-06 续61）。

素材 = work/e2e_r3/src_part1.mp4（63.000s / 1827 帧 @29fps；r3 E2E 遗留的本机跑手素材，不在 git）。
臂 A source_duration_s=None  = 修复前形态（窗尾 mid+5s 越过片尾，向不存在的帧要网格点）。
臂 B source_duration_s=片尾  = 修复后生产形态（locator_service 传 bundle.meta.duration）。
embed_dual 用确定性假特征（不需要模型/GPU）；抓帧是真 FFmpegIO，故错误路径真跑。

Run: D:/claudework/video-dedup-tool/.venv/Scripts/python.exe mvp/scripts/probe_patch_refine_eof.py
（需 work/e2e_r3/src_part1.mp4 在位；素材缺失时本探针会报文件错，与产品行为无关。）
"""
import os
import sys
import traceback
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
os.environ.setdefault("MEDIA_FFMPEG", str(BENCH / "tools" / "ffmpeg.exe"))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import numpy as np  # noqa: E402

from domain.enums import ConfidenceLevel  # noqa: E402
from domain.models import Confidence, Result, TimeSpan  # noqa: E402
from engine.localization.patch_refine import apply_patch_refine  # noqa: E402
from media.ffmpeg.ffmpeg_io import FFmpegIO  # noqa: E402

SRC = BENCH / "work" / "e2e_r3" / "src_part1.mp4"
DIM = 8

io = FFmpegIO()


def _lib():
    t = np.arange(0.0, 63.0, 1.0)          # 现役 1fps 索引形态，末点 62.0
    rng = np.random.default_rng(7)
    f = rng.normal(size=(len(t), DIM))
    f /= np.linalg.norm(f, axis=1, keepdims=True)
    return t, f


def _mk_result(mid_start=58.0):
    return Result(edited=TimeSpan(40.0, 45.0),
                  original=TimeSpan(mid_start, mid_start + 5.0),
                  confidence=Confidence(ConfidenceLevel.MEDIUM, 0.6))


def run(dur, res=None):
    res = res or _mk_result()
    lib_t, lib_f = _lib()
    asked = []

    def grab(path, t):
        return io.grab_frame(path, float(t), scale=(224, 224))

    def grab_grid(path, times):
        ts = [float(x) for x in times]
        asked.extend(ts)
        return io.grab_grid_times(path, ts)

    def embed_dual(frame):
        v = np.frombuffer(np.asarray(frame).tobytes()[:DIM], dtype=np.uint8).astype(np.float64)
        if v.size < DIM:
            v = np.pad(v, (0, DIM - v.size))
        v = v / max(1e-6, float(np.linalg.norm(v)))
        return v, np.tile(v, (4, 1))

    out = apply_patch_refine([_mk_result()], edited_path=str(SRC), source_path=str(SRC),
                             grab_frame=grab, embed_dual=embed_dual,
                             lib_times=lib_t, lib_feats=lib_f,
                             grab_grid=grab_grid, refine_grid=True,
                             source_duration_s=dur)
    return len(asked), max(asked) if asked else None, len(out), sorted(set(asked))


print("流时长实测 = %s s" % io.metadata(SRC).duration)
DUR = float(io.metadata(SRC).duration)

# 1) 复现 + 修复（段落落在片尾，窗尾越 EOF）
for name, dur in (("A dur=None (修复前形态)", None),
                  ("B dur=片尾 (修复后生产形态)", DUR)):
    try:
        n, hi, nres, _ = run(dur)
        print("%-30s OK  请求点=%d 最大 t=%s 结果段=%d" % (name, n, hi, nres))
    except Exception as exc:                    # noqa: BLE001
        print("%-30s RAISED %s: %s" % (name, type(exc).__name__, exc))

# 2) 零语义：窗不越片尾时，钳制前后请求的时间集合必须逐位相同
tail_free = _mk_result(mid_start=25.0)


def _safe(dur, res):
    try:
        return run(dur, res)
    except Exception as exc:                    # noqa: BLE001
        print("   (arm dur=%s RAISED %s: %s)" % (dur, type(exc).__name__, exc))
        return None


a, b = _safe(None, tail_free), _safe(DUR, tail_free)
if a and b:
    print("零语义(主 span 在片内) identical=%s 点数=%d/%d 最大 t=%s"
          % (a[3] == b[3], len(a[3]), len(b[3]), b[1]))
elif b:
    print("主 span 在片内也会炸：候选簇含片尾 mid ⇒ 未钳制臂抛错，钳制臂 OK（请求点=%d 最大 t=%s）"
          % (b[0], b[1]))
