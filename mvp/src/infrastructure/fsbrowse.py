"""infrastructure.fsbrowse — 素材入库浏览（竞品 web.file_api.browser 四件移植）。

四件 = **盘符枚举**（Windows「此电脑」）+ **自然排序**（2.mkv < 10.mkv）+
**视频扩展名白名单** + **磁盘剩余空间**（预检数据源）。纯函数、只读目录列表，
不读文件内容；API 层只做薄壳，本机服务已有会话门禁（api/session.py）。

竞品语义对照（FINDINGS_CAPABILITY_MAP 表 D#238/#239）：路径校验 + 目录浏览 +
白名单 + 自然排序 + 磁盘预检；我方预检落点在 ``locator_service`` 的合并/渲染入口
（``require_free_space``，不足抛 ``DiskSpaceError`` = LOC-1108）。
"""
from __future__ import annotations

import os
import re
import shutil
import string
import sys
from pathlib import Path

from infrastructure.errors import DiskSpaceError

# 白名单：常见容器；竞品同族口径（视频扩展名）。大小写不敏感（按 suffix.lower()）。
VIDEO_EXTS = frozenset({
    ".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv",
    ".m4v", ".mpg", ".mpeg", ".ts", ".mts", ".m2ts",
})

_DIGITS = re.compile(r"(\d+)")


def natural_key(name: str) -> list:
    """自然排序键：数字段按数值比较（clip2 < clip10），其余按小写文本。"""
    return [int(t) if t.isdigit() else t.lower()
            for t in _DIGITS.split(str(name))]


def sort_natural(items, key=str):
    return sorted(items, key=lambda x: natural_key(key(x)))


def is_video(name: str) -> bool:
    return Path(name).suffix.lower() in VIDEO_EXTS


def list_drives() -> list[dict]:
    """Windows：A-Z 中存在者 + 卷标；macOS：/Volumes 下挂载点；Linux：仅根。"""
    out: list[dict] = []
    if sys.platform == "win32":
        try:
            import ctypes
            mask = ctypes.windll.kernel32.GetLogicalDrives()
            letters = [c for i, c in enumerate(string.ascii_uppercase) if mask >> i & 1]
        except Exception:  # noqa: BLE001 - 位图拿不到就逐字母探测
            letters = [c for c in string.ascii_uppercase
                       if os.path.exists("%s:\\%s" % (c, ""))]
        for c in letters:
            root = "%s:\\" % c
            try:
                total, used, free = shutil.disk_usage(root)
            except OSError:
                continue
            out.append({"name": "%s:" % c, "path": root, "label": _win_label(root),
                        "total_bytes": total, "free_bytes": free})
    else:
        vol = Path("/Volumes")
        if vol.is_dir():
            for p in sorted(vol.iterdir()):
                if p.is_dir():
                    try:
                        total, _, free = shutil.disk_usage(p)
                    except OSError:
                        continue
                    out.append({"name": p.name, "path": str(p), "label": p.name,
                                "total_bytes": total, "free_bytes": free})
        total, _, free = shutil.disk_usage("/")
        out.insert(0, {"name": "/", "path": "/", "label": "System",
                       "total_bytes": total, "free_bytes": free})
    return out


def _win_label(root: str) -> str:
    try:
        import ctypes
        buf = ctypes.create_unicode_buffer(261)
        if ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root), buf, ctypes.sizeof(buf),
                None, None, None, None, 0):
            return buf.value or ""
    except Exception:  # noqa: BLE001 - 卷标是锦上添花
        pass
    return ""


def free_bytes(path: str | Path) -> int:
    """``path`` 所在盘剩余字节；path 尚不存在时向上找存在的祖先目录。"""
    p = Path(path)
    while not p.exists() and p.parent != p:
        p = p.parent
    return shutil.disk_usage(p).free


def require_free_space(target_dir: str | Path, need_bytes: int, *, what: str) -> None:
    """磁盘预检：目标盘剩余不足 ``need_bytes`` 即抛 DiskSpaceError（LOC-1108）。

    在**动手前**失败，而不是让 ffmpeg 写到一半 ENOSPC 留下一堆半截产物。
    """
    free = free_bytes(target_dir)
    if free < need_bytes:
        raise DiskSpaceError(
            "insufficient disk space for %s: need %.1f GB, free %.1f GB (%s)"
            % (what, need_bytes / 1e9, free / 1e9, Path(target_dir).drive or "/"))


def parent_of(path: str | Path) -> str | None:
    """上一级；盘符根返回 ''（= 回「此电脑」），无父返回 None。"""
    p = Path(path)
    if p.parent == p:
        return "" if os.path.splitdrive(str(p))[0] else None
    return str(p.parent)


def browse(path: str | Path | None) -> dict:
    """列一个位置。``path`` 空 = 「此电脑」（盘符列表）；目录 = 子目录 + 白名单视频，
    各自自然排序；附所在盘 free/total。非法/不存在由调用方转 HTTP 码。
    """
    if path is None or str(path).strip() == "":
        return {"kind": "root", "path": "", "parent": None,
                "drives": list_drives(), "entries": []}
    p = Path(path)
    if not str(p).strip():
        raise ValueError("empty path")
    if not p.exists():
        raise FileNotFoundError(p.name)
    if not p.is_dir():
        raise NotADirectoryError(p.name)
    dirs: list[dict] = []
    vids: list[dict] = []
    try:
        it = os.scandir(p)
    except PermissionError as exc:
        raise PermissionError(p.name) from exc
    with it:
        for de in it:
            try:
                if de.name.startswith("."):
                    continue
                if de.is_dir():
                    dirs.append({"name": de.name, "path": str(p / de.name),
                                 "is_video": False})
                elif de.is_file() and is_video(de.name):
                    vids.append({"name": de.name, "path": str(p / de.name),
                                 "is_video": True,
                                 "size_bytes": de.stat().st_size})
            except OSError:
                continue   # 无权限/竞态消失的条目跳过，不炸整个列表
    dirs.sort(key=lambda d: natural_key(d["name"]))
    vids.sort(key=lambda v: natural_key(v["name"]))
    total, _, free = shutil.disk_usage(p)
    return {"kind": "dir", "path": str(p), "parent": parent_of(p),
            "drives": [], "entries": dirs + vids,
            "free_bytes": free, "total_bytes": total}
