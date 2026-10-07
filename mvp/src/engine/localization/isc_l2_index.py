# -*- coding: utf-8 -*-
"""L2 源片 ISC 索引库（2026-10-04 续52 接线批次）。

一张「每部母片一次顺序网格解码 + 1s 网格 ISC 特征表」，宽扫粗排从「2s 网格逐点抓帧+嵌入」
换成 matmul（形态 B：索引 top-3 → 真帧 ±2s 精化，margin 门复用）。取帧 = L1 ``grab_grid``
select 抽取（真实 pts + first_ge，与扫描侧 ``grab_frame`` 同帧同契约——续52-C 实测
``iter_frames`` 合成标签比真实 pts 晚 ~0.5s，切点处索引帧≠扫描帧，故必须 truepts）。

失效判定：meta 记源片 sha256；``is_valid`` 逐字节比对当前源片（会话级按 (path,mtime,size)
缓存，跨会话重算——sha256 全盘读一次 ~5-10s/片）。不匹配/损坏 = 重建。
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np

_SCHEMA = "isc_l2_index_v1"
_DIM = 256


def index_path_for(source: str | Path, root: Path, fps: float = 1.0) -> Path:
    """索引文件路径：``{root}/{stem}@{fps:.3f}fps.tp.isci.npz``。"""
    return Path(root) / ("%s@%.3ffps.tp.isci.npz" % (Path(source).stem, fps))


def sha256_of(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _last_video_pts(ffprobe: str, src: Path, *, from_s: float,
                    timeout: float = 120.0) -> float | None:
    """源片视频流最后一个包的 pts（秒）；扫不到/异常 = None。

    demux-only 包扫描（不解码）；``from_s`` 用 ``-read_intervals`` 只回看文件尾部，
    实测 137min mkv 尾部 120s 扫描 ~0.15s。
    """
    try:
        proc = subprocess.Popen(
            [ffprobe, "-v", "error", "-select_streams", "v:0", "-show_entries",
             "packet=pts_time", "-of", "csv=p=0",
             "-read_intervals", "%.6f%%99999999" % max(0.0, from_s), str(src)],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        last: float | None = None
        with proc:
            for raw in proc.stdout:
                s = raw.strip()
                if not s:
                    continue
                try:
                    v = float(s)
                except ValueError:      # "N/A" 等无 pts 包
                    continue
                if last is None or v > last:
                    last = v
            proc.wait(timeout)
        return last
    except Exception:
        return None


def _capped_target_n(ffmpeg, src: Path, dur: float, fps: float) -> int:
    """目标网格数按「最后一个视频帧 pts」截断（2026-10-05 修正）。

    旧口径 ``int((dur - 0.5/fps) * fps) + 1`` 用**容器时长**推网格，但容器时长可以大于
    视频流尾部（test1-om.mkv 实测音频比最后一帧视频晚 8.4s ⇒ 尾部 8 个目标永远抓不到，
    每个失败目标触发整表重试 = 全片重复解码，实测 2.57 帧/s；截断后同内容 10+ 帧/s）。
    先回看容器尾部 120s，空（视频流提前结束更多）再全量扫一次；都失败 = 退回旧口径
    （尾部守卫仍由逐簇 trim 兜底）。截断只删「本来就抓不到帧」的目标 ⇒ 索引内容不变。
    """
    base = int((dur - 0.5 / fps) * fps) + 1
    for from_s in (dur - 120.0, 0.0):
        last = _last_video_pts(str(ffmpeg.ffprobe), src, from_s=from_s)
        if last is not None:
            return min(base, int(last * fps) + 1)
    return base


def build_tp_index(source: str | Path, *, ffmpeg, scorer, fps: float = 1.0,
                   limit_s: float = 0.0, cluster_s: float = 120.0,
                   max_cluster_frames: int | None = None,
                   on_frame=None) -> tuple[np.ndarray, np.ndarray, dict]:
    """构建 tp 索引：目标网格 k/fps → ``grab_grid``（select 抽取，first_ge）→ ISC 嵌入。

    返回 ``(times, feats, meta)``。**逐簇流式嵌入**（每簇 grab→embed→释放帧；v1 初版把全片
    网格帧攒在内存再统一嵌入，test3（47GB）被换页拖慢 3×+，续52-G 修复）。片尾守卫 =
    目标网格先按最后一个视频帧 pts 截断（``_capped_target_n``，2026-10-05），EOF 硬失败
    仍按「渐进裁剪该簇尾部目标」兜底；**整簇不可取 = 跳过该簇**（c0 必须前进，防死循环）。
    ``on_frame(done, total)`` 可选进度回调。
    ``max_cluster_frames``（2026-10-07 ① 低内存收缩）：单簇在飞帧数上限——默认 None =
    无额外约束（现役 120 帧/簇）；低内存档由 ``media.resource_budget`` 给 64/16。簇切小
    只改批次不改帧（times/feats 逐字节一致）。"""
    src = Path(source)
    info = ffmpeg.metadata(src)
    dur = float(info.duration)
    n = _capped_target_n(ffmpeg, src, dur, fps)
    if limit_s > 0:
        n = min(n, int(limit_s * fps) + 1)
    total = n
    times: list = []
    feats: list = []
    t0 = time.monotonic()
    done = 0
    c0 = 0.0
    while c0 * fps < n:                       # 逐簇：grab → embed → 释放帧
        planned = min(int(cluster_s * fps), n - int(c0 * fps))
        if max_cluster_frames is not None and max_cluster_frames > 0:
            planned = min(planned, int(max_cluster_frames))
        if planned <= 0:
            break
        grid: dict = {}
        n_c = planned
        while n_c > 0:
            try:
                grid = ffmpeg.grab_grid(src, c0, 1.0 / fps, n_c, max_span_s=cluster_s)
                break
            except Exception:                 # 片尾帧缺失 → 裁掉该簇尾部目标重试
                n_c -= 1
        if n_c <= 0:
            # 整簇不可取（媒体异常/全死目标）→ 跳过，c0 前进防死循环
            c0 += planned / fps
            continue
        for t in sorted(grid):
            times.append(round(float(t), 6))
            feats.append(np.asarray(scorer.embed(grid[t]), dtype=np.float32))
        done += n_c
        if on_frame is not None:
            on_frame(done, total)
        c0 += n_c / fps                       # 目标数 → 秒（fps≠1 时旧写法多推进 fps 倍）
    wall = time.monotonic() - t0
    T = np.asarray(times, dtype=np.float64)
    F = np.asarray(feats, dtype=np.float32)
    meta = {"schema": _SCHEMA, "source": str(src), "source_sha256": sha256_of(src),
            "fps": fps, "sampling": "truepts", "frames": int(F.shape[0]),
            "dim": int(F.shape[1]), "device": str(getattr(scorer, "device", "")),
            "wall_s": round(wall, 1), "limit_s": limit_s,
            "created": time.strftime("%Y-%m-%d %H:%M:%S")}
    return T, F, meta


def save_index(path: Path, T: np.ndarray, F: np.ndarray, meta: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, times=T, feats=F, meta=json.dumps(meta, ensure_ascii=False))


def load_index(path: Path) -> tuple[np.ndarray, np.ndarray, dict] | None:
    """加载；缺文件/键不全/维度不符 = None（调用方决定重建或回退）。"""
    p = Path(path)
    if not p.exists():
        return None
    try:
        with np.load(p, allow_pickle=False) as z:
            T = np.asarray(z["times"], dtype=np.float64)
            F = np.asarray(z["feats"], dtype=np.float32)
            meta = json.loads(str(z["meta"]))
    except Exception:
        return None
    if T.ndim != 1 or F.ndim != 2 or T.shape[0] != F.shape[0] or T.shape[0] == 0 \
            or F.shape[1] != _DIM:
        return None
    return T, F, meta


def is_valid(path: Path, source: str | Path, *, source_sha: str | None = None) -> bool:
    """索引有效性：可加载且 meta.schema 匹配且（显式给出或现算的）源片 sha256 一致。"""
    got = load_index(path)
    if got is None:
        return False
    _, _, meta = got
    if str(meta.get("schema")) != _SCHEMA:
        return False
    sha = source_sha if source_sha is not None else sha256_of(Path(source))
    return str(meta.get("source_sha256")) == sha
