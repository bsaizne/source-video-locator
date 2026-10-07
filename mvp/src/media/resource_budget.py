"""resource_budget — 按系统可用内存收缩推理/抓帧资源（② 六项立项 ①，2026-10-07）。

竞品形态（`FINDINGS_CUTMATCH_ENTRY_LAYER_20261006.md` §2.2）：按可用内存**同时**收缩
batch 与预取批数，`low_memory_mode` 作为状态字段上报（可观测降档，非静默变慢）。

我方接线点：
- ``MediaBudget.grab_workers``   → ``locator_service._grab_frames_parallel`` 线程数；
- ``MediaBudget.max_cluster_frames`` → ``isc_l2_index.build_tp_index`` 单簇在内存中
  持有的帧数上限（120s 簇 × 1fps = 120 帧 × ~6MB ≈ 720MB 在飞——低内存机的换页热点）。

口径：``available_bytes=None``（探针不可用）⇒ 全默认、不降档（宁缺毋假）；
分档阈值见 ``compute_media_budget``。纯函数，阈值行为全部单测覆盖。
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

# ---- 阈值（全部以 usable = available − reserve 为准）----------------------- #
DEFAULT_RESERVE_BYTES = 2 * 1024**3          # 给系统/其它进程留 2GB，不计入可用
DEFAULT_PER_FRAME_BYTES = 6 * 1024**2        # 1080p RGB24 解码帧 + numpy 开销实测量级
THREE_TIERS = (                             # (usable 下限, grab_workers, max_cluster_frames)
    (6 * 1024**3, 4, 120),                  # 宽裕：现役默认（零语义）
    (2 * 1024**3, 2, 64),                   # 紧张：线程减半 + 簇减半
    (0,           1, 16),                   # 极限：串行 + 最小簇（吞吐下限，进度粒度保住）
)
DEFAULT_GRAB_WORKERS = 4
DEFAULT_MAX_CLUSTER_FRAMES = 120
MIN_CLUSTER_FRAMES = 16


@dataclass(frozen=True)
class MediaBudget:
    """一次内存预算判定结果（不可变，随用随取）。"""

    available_bytes: int | None       # None = 探针不可用
    total_bytes: int | None
    grab_workers: int                 # 抓帧线程池宽度
    max_cluster_frames: int           # L2 建表单簇在飞帧数上限
    low_memory_mode: bool             # 供 /api/settings/device 与进度事件上报
    tier: str                         # "ok" / "tight" / "critical" / "unknown"


def compute_media_budget(available_bytes: int | None, *,
                         reserve_bytes: int = DEFAULT_RESERVE_BYTES,
                         per_frame_bytes: int = DEFAULT_PER_FRAME_BYTES) -> MediaBudget:
    """可用内存 → 资源预算。探针不可用（None）⇒ 全默认不降档。"""
    if available_bytes is None:
        return MediaBudget(None, None, DEFAULT_GRAB_WORKERS,
                           DEFAULT_MAX_CLUSTER_FRAMES, False, "unknown")
    usable = max(0, available_bytes - reserve_bytes)
    for lo, workers, cluster in THREE_TIERS:
        if usable >= lo:
            tier = {4: "ok", 2: "tight", 1: "critical"}[workers]
            return MediaBudget(available_bytes, None, workers, cluster,
                               tier != "ok", tier)
    return MediaBudget(available_bytes, None, 1, MIN_CLUSTER_FRAMES, True, "critical")


def probe_memory() -> tuple[int | None, int | None]:
    """(available_bytes, total_bytes)。Windows GlobalMemoryStatusEx → psutil → (None, None)。"""
    try:
        if sys_platform_windows():
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            st = MEMORYSTATUSEX()
            st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                return int(st.ullAvailPhys), int(st.ullTotalPhys)
        else:
            import psutil                                  # noqa: PLC0415 — 兜底可选依赖
            vm = psutil.virtual_memory()
            return int(vm.available), int(vm.total)
    except Exception:                                      # noqa: BLE001 — 观测失败不阻断
        pass
    return None, None


def sys_platform_windows() -> bool:
    import sys                                        # noqa: PLC0415 — 延迟导入便于测试
    return sys.platform == "win32"


def current_budget() -> MediaBudget:
    """运行时入口：探针 + 判定一次完成（调用方随用随取，内存状态实时）。"""
    avail, total = probe_memory()
    b = compute_media_budget(avail)
    return MediaBudget(b.available_bytes, total, b.grab_workers, b.max_cluster_frames,
                       b.low_memory_mode, b.tier)
