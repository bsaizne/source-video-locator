# -*- coding: utf-8 -*-
"""MVP_ROADMAP §4/§7 性能基准实测（2026-09-28，GPU DirectML/amd）。

要回答的问题很具体：``PRODUCT_INTRO`` 对外承诺「2 小时影片索引一次构建约 7~12 分钟（GPU 加速）」
与「同一成片重复定位约 2~4 分钟」，而档案里**没有任何一张填好的基准表**（只有零散历史数字）。
本脚本把 10 / 60 / 128 min 三档的 Index Build 实测补齐，并在**真实配对素材**上测首次定位与
缓存复定位（编辑片与被截短档原片不同内容，故 locate 只在 128min 档测，其余档如实标 N/A）。

指标：wall 时间 / 帧数 / 吞吐 fps / 峰值 RSS / 进程 CPU 秒 / 索引目录字节。
RAM 与 CPU 用 ctypes 走 Windows API（psapi GetProcessMemoryInfo + GetProcessTimes），
**不为此引入 psutil 依赖**。

隔离：``SVL_DATA_DIR=work/bench_data/<tier>``，绝不污染生产索引目录。
截短片：ffmpeg ``-t N -c copy``（流复制，不重编码），产物落 ``work/bench_src/``（可删）。

运行（后台）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" mvp/scripts/bench_perf_tiers.py
产出: work/bench_perf_tiers.json + 控制台表
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

BENCH = Path(r"D:\claudework\benchmark")
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
os.environ.setdefault("MEDIA_FFMPEG", str(FFMPEG))
os.environ.setdefault("MEDIA_FFPROBE", (r"D:\claudework\video-dedup-tool\.venv\Lib\site-packages"
                                        r"\static_ffmpeg\bin\win32\ffprobe.exe"))
sys.path.insert(0, str(BENCH / "mvp" / "src"))
sys.path.insert(0, str(BENCH / "mvp"))

SRC_128 = Path(r"D:\video\2.mkv")            # 128 min，真实配对
EDITED = Path(r"D:\video\1.mp4")             # 126 s 解说（属于 2.mkv）
# 生产 DML 资产（A1 已补 sha256 并校验通过）；隔离 data dir 时必须显式指过来
PRODUCTION_DML_MODEL = (Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
                        / "SourceVideoLocator/models/dinov2_cls_384/dinov2_cls_384.onnx")
SRC_BENCH_DIR = BENCH / "work" / "bench_src"
DATA_ROOT = BENCH / "work" / "bench_data"
OUT = BENCH / "work" / "bench_perf_tiers.json"


# ------------------------------------------------------------------ 资源计量
class _PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def _kernel32():
    k32 = ctypes.windll.kernel32
    k32.GetCurrentProcess.restype = wintypes.HANDLE
    k32.GetProcessTimes.restype = wintypes.BOOL
    k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + [
        ctypes.POINTER(wintypes.FILETIME)] * 4
    return k32


def _to_secs(ft: wintypes.FILETIME) -> float:
    return ((ft.dwHighDateTime << 32) | ft.dwLowDateTime) / 1e7


def peak_rss_mb() -> float:
    """本进程峰值工作集（MB）。非 Windows 或调用失败返回 -1（如实标 NOT TESTED，不猜）。"""
    if not sys.platform.startswith("win"):
        return -1.0
    pmc = _PMC()
    pmc.cb = ctypes.sizeof(_PMC)
    fn = ctypes.windll.psapi.GetProcessMemoryInfo
    fn.restype = wintypes.BOOL
    fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PMC), wintypes.DWORD]
    if not fn(_kernel32().GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
        return -1.0
    return pmc.PeakWorkingSetSize / (1024 * 1024)


def proc_cpu_s() -> float:
    """本进程累计 CPU 秒 = user + kernel（只取 user 会低估多线程开销）。"""
    if not sys.platform.startswith("win"):
        return -1.0
    creation, exit_, kernel, user = (wintypes.FILETIME() for _ in range(4))
    if not _kernel32().GetProcessTimes(
            _kernel32().GetCurrentProcess(),
            ctypes.byref(creation), ctypes.byref(exit_),
            ctypes.byref(kernel), ctypes.byref(user)):
        return -1.0
    return _to_secs(kernel) + _to_secs(user)


def dir_bytes(p: Path) -> int:
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


# ------------------------------------------------------------------ 素材准备
def truncated_source(seconds: int) -> Path:
    """从 2.mkv 流复制截出 N 分钟档（不重编码；同内容同帧率，索引规模按秒线性缩放）。"""
    SRC_BENCH_DIR.mkdir(parents=True, exist_ok=True)
    out = SRC_BENCH_DIR / f"src_{seconds // 60}min.mkv"
    if out.exists() and out.stat().st_size > 1024 * 1024:
        return out
    cmd = [str(FFMPEG), "-y", "-hide_banner", "-loglevel", "error",
           "-i", str(SRC_128), "-t", str(seconds), "-c", "copy", str(out)]
    t0 = time.perf_counter()
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg truncate failed: {r.stderr[-400:]}")
    print(f"[bench] 截出 {seconds // 60}min 档 用时 {time.perf_counter() - t0:.1f}s -> {out.name}")
    return out


def measure_tier(label: str, original: Path, data_dir: Path, *, locate: bool) -> dict:
    # paths.data_root() 在调用期读 SVL_DATA_DIR（infrastructure/paths.py:29），
    # 因此只需在构造 service 前设好 env——不必删模块重导入（那会留下悬空引用风险）。
    os.environ["SVL_DATA_DIR"] = str(data_dir)
    # ⚠️ 隔离数据目录会**连带**隔离模型资产查找（dinov2_dml_asset_dir 挂在 data_root 下），
    # 于是 resolve_backend 静默 fallback 到 CPU —— 那样测出来的数字不能用来验证
    # "GPU 加速"承诺（本脚本第一版就踩了这个坑，日志里 "backend unavailable ... selected=cpu"）。
    # 所以显式指向生产资产，并在下面**硬断言**后端是 DirectMLBackend，不是就中止。
    os.environ.setdefault("SVL_DML_MODEL", str(PRODUCTION_DML_MODEL))
    from app.locator_service import SourceLocatorService      # noqa: E402
    from infrastructure.config import load_config             # noqa: E402

    srv = SourceLocatorService(config=load_config())
    b = srv.backend
    btype = type(b).__name__
    print(f"[bench] {label} BACKEND_SELECTED type={btype} "
          f"device={getattr(b, 'device_name', lambda: '?')()} "
          f"dtype={getattr(b, 'device_type', lambda: '?')()}", flush=True)
    if btype != "DirectMLBackend":
        raise SystemExit(f"[bench] 中止：后端是 {btype} 而非 DirectMLBackend——CPU 数字不能当 GPU 承诺的依据")

    row: dict = {"label": label, "original": str(original), "gpu": btype}
    rss0, cpu0 = peak_rss_mb(), proc_cpu_s()
    t0 = time.perf_counter()
    meta = srv.build_original_index(original).meta
    wall = time.perf_counter() - t0
    row.update(index_build_s=round(wall, 1), frames=int(meta.num_frames),
               sampling_fps=float(meta.sampling_fps),
               throughput_fps=round(meta.num_frames / wall, 2),
               feature_version=meta.feature_version,
               index_bytes=dir_bytes(data_dir))
    print(f"[bench] {label} index={wall:.1f}s frames={meta.num_frames} "
          f"{meta.num_frames / wall:.2f}fps rss={peak_rss_mb():.0f}MB", flush=True)

    if locate:
        t0 = time.perf_counter()
        batch = srv.locate(EDITED, original)
        first = time.perf_counter() - t0
        t0 = time.perf_counter()
        srv.locate(EDITED, original)
        again = time.perf_counter() - t0
        row.update(locate_segments=len(batch.results), locate_first_s=round(first, 1),
                   locate_cached_s=round(again, 1))
        print(f"[bench] {label} locate 首跑 {first:.1f}s / 复跑(缓存) {again:.1f}s "
              f"段数 {len(batch.results)}", flush=True)
    row.update(peak_rss_mb=round(peak_rss_mb(), 1), proc_cpu_s=round(proc_cpu_s() - cpu0, 1),
               rss_before_mb=round(rss0, 1))
    (data_dir.parent / f"_done_{label}.flag").write_text("1", encoding="utf-8")
    return row


def main() -> int:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    tiers = [("10min", truncated_source(600), False),
             ("60min", truncated_source(3600), False),
             ("128min", SRC_128, True)]
    rows = []
    for label, src, do_locate in tiers:
        flag = DATA_ROOT / label / f"_done_{label}.flag"
        if flag.exists():
            print(f"[bench] {label} 已完成，跳过（删 {flag} 可重测）")
            continue
        rows.append(measure_tier(label, src, DATA_ROOT / label, locate=do_locate))
    prev = OUT.read_text(encoding="utf-8") if OUT.exists() else '{"rows": []}'
    doc = json.loads(prev)
    doc["rows"] = [r for r in doc.get("rows", []) if r["label"] not in {x["label"] for x in rows}] + rows
    doc["measured_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    doc["notes"] = ("locate 只在 128min 真实配对(2.mkv + 1.mp4)上测；10/60min 档无同内容编辑片, "
                    "标 N/A 不虚构。RAM=进程峰值工作集, CPU=进程累计 CPU 秒(非整机利用率)。")
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print("\n=== 基准汇总 ===")
    for r in sorted(doc["rows"], key=lambda x: x["label"]):
        print(f"  {r['label']:8} index={r['index_build_s']:>7}s  "
              f"{r['throughput_fps']:>5}fps  frames={r['frames']:>6}  "
              f"index={r['index_bytes'] / 1e6:.1f}MB  rss={r['peak_rss_mb']}MB  "
              f"locate={r.get('locate_first_s', 'N/A')}/{r.get('locate_cached_s', 'N/A')}s")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
