"""smoke_directml_backend — 用正式生产 DirectMLBackend 跑真实原片 2.mkv 的索引构建。

验证 §8/§9：真实原片 @0.5fps 用 ``SourceLocatorService``(自动解析 backend=directml)
建索引，report time/frame count/fps/memory/feature shape；并确认 FeatureStore
create/load 完整兼容（[N,384]）。对照 H1 CPU 历史真实结果 CPU≈3793.6s，H2 目标≈POC 的~324s。

只做观察与结构断言，不改任何算法/参数。用法：
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/smoke_directml_backend.py
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app import SourceLocatorService  # noqa: E402
from media.ffmpeg import FFmpegIO  # noqa: E402

BENCH = Path(__file__).resolve().parents[2]          # -> benchmark
REAL_ORIG = BENCH / "datasets" / "real" / "originals" / "2.mkv"
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")


class _PMC(ctypes.Structure):
    _fields_ = [("cb", wt.DWORD), ("PageFaultCount", wt.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def rss_mb() -> float | None:
    try:
        c = _PMC(); c.cb = ctypes.sizeof(_PMC)
        k = ctypes.windll.kernel32; k.GetCurrentProcess.restype = ctypes.c_void_p
        h = k.GetCurrentProcess()
        p = ctypes.windll.psapi
        p.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMC), wt.DWORD]
        p.GetProcessMemoryInfo.restype = ctypes.c_bool
        return float(c.WorkingSetSize) / 1048576.0 if p.GetProcessMemoryInfo(h, ctypes.byref(c), c.cb) else None
    except Exception:
        return None


def _progress(evt):
    pass  # 只取最后的统计，不逐条打印


def main() -> int:
    print(f"=== smoke_directml_backend: real original index build ===")
    print(f"source: {REAL_ORIG} ({REAL_ORIG.stat().st_size / 1e6:.1f} MB)")

    with tempfile.TemporaryDirectory() as td:
        svc = SourceLocatorService(ffmpeg=FFmpegIO(FFMPEG, FFPROBE),
                                   index_root=td, export_root=td)
        be = svc.backend                      # 自动解析（config.device.preferred=auto -> DirectML）
        print(f"resolved backend: device_type={be.device_type()} name={be.device_name()} "
              f"({type(be).__name__})")
        assert be.device_type() == "amd", f"expected amd/DirectML, got {be.device_type()}"

        mem0 = rss_mb()
        t0 = time.perf_counter()
        bundle = svc.build_original_index(REAL_ORIG, on_progress=_progress)
        dt = time.perf_counter() - t0
        mem1 = rss_mb()

        fps = bundle.num_frames / dt if dt > 0 else float("nan")
        print(f"index build: {dt:.1f}s  frames={bundle.num_frames}  dim={bundle.features.shape[1]}  "
              f"avg_fps={fps:.2f}")
        print(f"feature shape: {bundle.features.shape}  dtype={bundle.features.dtype}")
        # 报告
        print(f"memory: start={mem0 and round(mem0,1)} MB  end={mem1 and round(mem1,1)} MB  "
              f"growth={round(mem1 - mem0, 1) if (mem0 and mem1) else 'n/a'} MB")

        # FeatureStore 返回的 IndexMeta 记录 backend
        meta = svc.store.get_metadata(REAL_ORIG)
        print(f"index meta: backend={meta.backend} feature_version={meta.feature_version} "
              f"feature_dim={meta.feature_dim} sampling_fps={meta.sampling_fps}")

        # 再次 load 同一索引（复用路径）确认可直接读回，不重扫
        t1 = time.perf_counter()
        b2 = svc.store.load_index(REAL_ORIG)
        print(f"reload (reuse) in {time.perf_counter() - t1:.3f}s  frames={b2.num_frames} "
              f"shape={b2.features.shape}")
        assert b2.features.shape == (bundle.num_frames, 384)
        assert bundle.features.dtype.name == "float32"
        print("\nALL SMOKE CHECKS PASSED (DirectMLBackend real 2.mkv index build)")
        print(f"note: H1 CPU historical ~3793.6s; H2(POC) ~324s -> this run {dt:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
