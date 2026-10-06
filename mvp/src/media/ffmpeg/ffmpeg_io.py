"""FFmpegIO — production video random-access I/O.

Replaces the research ``cv2.VideoCapture`` frame sampling
(``src/experiments/dinov2_features.sample_frames``), which is NOT safe for random
access on MKV (``CAP_PROP_POS_MSEC`` can trigger a full decode from the start).
Everything time-accurate here goes through ffmpeg / ffprobe subprocesses.

Frame contract (frozen): decoded frames are **BGR uint8 at original resolution**,
matching ``DeviceBackend.embed_frames(bgr_frames: list[np.ndarray])`` and
``dinov2_features._imagenet_preprocess`` (which itself resizes to 518x518). We
therefore do NOT scale frames in the feature path; ``scale=`` is only for
preview / thumbnails where the exact resize interpolation does not matter.

Sampling convention (time-based, differs from the research frame-index grid):
``iter_frames(fps=f)` outputs one frame every ``1/f`` seconds and yields the
timestamp ``t = i / f`` (absolute, relative to ``start`` when ``start`` given).
This is deterministic and aligned with the FeatureStore ``t = row / fps``.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import threading
import time
from pathlib import Path
from typing import Iterator

import numpy as np

from ._runner import BASE_ARGS, CREATE_NO_WINDOW, MediaError, check_run, popen, resolve_binaries
from .ffprobe import VideoMetadata, metadata_from

# Default encoder used for precise clip extraction. Re-encoding (not stream copy)
# is required for frame-accurate output: `-c copy` is keyframe-aligned and loses
# the sub-goP precision that the product promises. libx264 is a GPL encoder; see
# TECH_STACK_DECISION.md §6 — the LGPL FFmpeg build decision is a packaging task.
# 网格抽取的最小步长（2026-10-03 续50 实测边界）：select 的规则是「距上一选中帧 ≥ step」，
# 当 step 不是源帧长的整数倍时会**逐步累积漂移**（每步多取一帧 ⇒ 走到后面整格错位）。
# 实测（test1-ed，3s 段 / 0.208s 步长 / 15 点）：2.10× 提速但只有 3/15 逐字节同帧、
# ISC cos 最低 0.335 ⇒ 不可用；而 2s 步长（≈整数倍）时 79/91 同帧、cos 均值 0.997。
# ⇒ 亚秒级网格一律回退旧路径（那些调用的收益本来也只有 1.0~2.1×，不值得冒险）。
MIN_GRID_STEP_S = 1.0

_DEFAULT_CODEC = "libx264"
_DEFAULT_PRESET = "veryfast"
_DEFAULT_CRF = 18


class FFmpegIO:
    """Injected-binary video I/O. Never hard-codes a machine-specific path."""

    def __init__(self, ffmpeg: str | Path | None = None,
                 ffprobe: str | Path | None = None, *, timeout_s: float = 600.0,
                 cluster_workers: int = 1):
        self.ffmpeg, self.ffprobe = resolve_binaries(ffmpeg, ffprobe)
        self.timeout_s = timeout_s
        # 簇级并行解码（2026-10-05 续55）：一次批量抓帧里的多个时间簇互相独立
        # （每簇一个 ffmpeg 进程，选帧只依赖本簇起点之后的解码）⇒ 可并发。
        # **默认 1 = 现役串行逐簇**，>1 由 ``media.cluster_workers`` 开（待双臂验收再翻）。
        self.cluster_workers = max(1, int(cluster_workers))
        # metadata 实例级缓存（2026-10-05 续54）：``_decode_window`` 每 spawn 调一次
        # metadata（实测 ~0.08s/次，定位全程 ~800 次 spawn ⇒ ~66s 纯 ffprobe 开销）。
        # 媒体文件元数据在运行期不变 ⇒ 按 (路径, size, mtime_ns) 缓存，安全。
        self._metadata_cache: dict[tuple, VideoMetadata] = {}
        # EOF 兜底帧缓存（2026-10-06 续61）：片尾越界的请求成批出现，见 _grab_last_frame。
        self._last_frame_cache: dict[tuple, np.ndarray] = {}

    def metadata(self, path: str | Path) -> VideoMetadata:
        p = Path(path)
        try:
            st = p.stat()
            ck = (str(p), st.st_size, st.st_mtime_ns)
        except OSError:
            ck = None
        if ck is not None:
            hit = self._metadata_cache.get(ck)
            if hit is not None:
                return hit
        info = metadata_from(p, str(self.ffprobe), timeout=self.timeout_s)
        if ck is not None:
            self._metadata_cache[ck] = info
        return info

    # ------------------------------------------------------------------ #
    # Frame sampling (streaming)
    # ------------------------------------------------------------------ #
    def iter_frames(self, path: str | Path, fps: float = 0.5, *,
                    start: float | None = None, end: float | None = None,
                    scale: tuple[int, int] | None = None,
                    meta: VideoMetadata | None = None) -> Iterator[tuple[float, np.ndarray]]:
        """Yield ``(timestamp, bgr_frame)`` at ``fps`` frames/sec.

        - ``start``/``end`` (seconds, absolute) restrict the decoded range; they are
          implemented with ``-ss`` before ``-i`` (fast input seek) so a long source
          is never decoded from the start.
        - ``timestamp = (start or 0) + i / fps`` — an absolute time grid. Sub-frame
          skew (<= one source frame) is possible after a seek.
        - ``scale`` is ONLY for preview; the feature path must leave it None so the
          frozen resize semantics in ``_imagenet_preprocess`` are preserved.

        Memory bounded: frames are read from the rawvideo pipe one at a time.
        """
        path = Path(path)
        info = meta or self.metadata(path)
        if not info.has_video:
            raise MediaError(f"{path.name}: no video stream to sample")
        width, height = self._output_size(info, scale)
        frame_bytes = width * height * 3

        vf = f"fps={fps:g}"
        if scale is not None:
            vf += f",scale={scale[0]}:{scale[1]}"
        base = start if start is not None else 0.0

        args = [str(self.ffmpeg), *BASE_ARGS]
        if start is not None:
            args += ["-ss", f"{start:.6f}"]
        args += ["-i", str(path)]
        if start is not None and end is not None:
            args += ["-t", f"{end - start:.6f}"]
        elif end is not None:
            # seek-to-start with an absolute end: use -to relative to input
            args += ["-to", f"{end:.6f}"]
        args += ["-vf", vf, "-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]

        proc = popen(args)
        try:
            i = 0
            while True:
                buf = proc.stdout.read(frame_bytes)
                if len(buf) < frame_bytes:
                    break  # EOF (or final partial frame) — nothing more to emit
                frame = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3)
                yield base + i / fps, frame
                i += 1
        finally:
            proc.stdout.close()
            rc = proc.wait()
            err = proc.stderr.read().decode("utf-8", errors="replace")
            proc.stderr.close()
        if rc != 0:
            raise MediaError(
                f"frame extraction failed (rc={rc}): {path.name}\n{err[-1500:]}"
            )

    def _decodable_cap(self, info) -> float | None:
        """末帧时间的**下界**估计（容器时长 − 1 帧）；元数据不可信时返回 None。

        片尾之外的 t 没有"正确答案"：``first_ge`` 语义下 ffmpeg 吐不出帧，而此前一律抛
        ``MediaError`` ⇒ **任何一个候选窗越过片尾就把整条 locate 打死**（LOC-1107 根因）。
        2026-10-06 mac CI 门槛抓到第二处调用点（``isc_refine`` 宽扫/精扫，本地复现
        t=20.500 vs 20.0s 原片），故统一收在解码层而不是逐个引擎补。

        ⚠️ 这是**末帧时间的下界估计**，不是精确值：``dur − 1/fps`` 可能**早于**末帧真实 pts。
        所以它只能当**判据**（"这次失败像不像片尾越界"），绝不能用它**预先钳制** ——
        那会把 ``(cap, dur]`` 区间内本来能取到正确帧的请求换成 cap 处的另一帧。
        """
        try:
            dur = float(getattr(info, "duration", 0.0) or 0.0)
            fps = float(getattr(info, "fps", 0.0) or 0.0)
        except (TypeError, ValueError):
            return None
        if dur <= 0:
            return None
        return max(0.0, dur - (1.0 / fps if fps > 0 else 0.0))

    def grab_frame(self, path: str | Path, t: float, *, scale: tuple[int, int] | None = None) -> np.ndarray:
        """Return one decoded BGR frame at time ``t`` (frame-accurate single seek).

        Uses ``-ss`` before ``-i`` (fast input seek, decode-and-discard up to
        ``t``) then ``-frames:v 1``. Used for previews and QA.

        **严格惰性的片尾兜底**：只有「按原始 t 确实吐不出帧」且「t 越过末帧下界」时，
        才改为返回片内最后一帧（过去这些请求抛 ``MediaError`` ⇒ 打死整条 locate）。
        凡过去能成功的请求一帧不动 —— 包括 t 落在 ``(cap, 时长]`` 的（cap 只是下界，
        预先钳制会换帧；见 ``_decodable_cap`` 的警告）。
        """
        path = Path(path)
        info = self.metadata(path)
        if not info.has_video:
            raise MediaError(f"{path.name}: no video stream")
        width, height = self._output_size(info, scale)
        frame_bytes = width * height * 3

        args = [str(self.ffmpeg), *BASE_ARGS, "-ss", f"{t:.6f}", "-i", str(path),
                "-frames:v", "1"]
        if scale is not None:
            args += ["-vf", f"scale={scale[0]}:{scale[1]}"]
        args += ["-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]

        try:
            proc = subprocess.run(
                args, capture_output=True, timeout=self.timeout_s,
                check=False, creationflags=CREATE_NO_WINDOW,
            )
        except subprocess.TimeoutExpired as exc:
            raise MediaError(f"grab_frame timed out at t={t:.3f} for {path.name}") from exc
        if proc.returncode != 0:
            raise MediaError(
                f"grab_frame failed (rc={proc.returncode}) at t={t:.3f}: {path.name}\n"
                f"{proc.stderr.decode(errors='replace')[-1000:]}"
            )
        if len(proc.stdout) < frame_bytes:
            cap = self._decodable_cap(info)
            # 严格惰性：只有「原始 t 真的取不到帧」且 t 在片尾之外，才退到片内最后一帧。
            # cap 在这里只当**判据**（区分"片尾越界"与"中段流损坏"，后者照旧抛），不当钳制值。
            if cap is not None and t > cap:
                last = self._grab_last_frame(path, info, scale, width, height, frame_bytes)
                if last is not None:
                    return last
            raise MediaError(f"grab_frame returned no frame at t={t:.3f}: {path.name}")
        return np.frombuffer(proc.stdout[:frame_bytes], dtype=np.uint8).reshape(height, width, 3)

    def _grab_last_frame(self, path: Path, info, scale, width: int, height: int,
                         frame_bytes: int) -> np.ndarray | None:
        """片内最后一帧（EOF 兜底专用）：从片尾前一帧区间起解到 EOF，流式只留最后一帧。

        不做精确 pts 匹配 —— 调用方已经在原 t 取不到帧，这里要的是「片内任一帧」而非
        第四种选取语义。内存有界：逐帧读管道，不整段进内存（1080p × 25 帧 ≈ 156MB）。
        结果按 (路径, size, mtime_ns, scale) 记忆：片尾越界的请求常成批出现（实测短原片
        一次 locate 命中 11 次），否则每次都重解一遍片尾。
        """
        try:
            st = Path(path).stat()
            key = (str(path), st.st_size, st.st_mtime_ns,
                   None if scale is None else (int(scale[0]), int(scale[1])))
        except OSError:
            key = None
        if key is not None and key in self._last_frame_cache:
            return self._last_frame_cache[key]
        dur = float(getattr(info, "duration", 0.0) or 0.0)
        fps = float(getattr(info, "fps", 0.0) or 0.0)
        tail = max(1.0, 2.0 / fps) if fps > 0 else 1.0
        args = [str(self.ffmpeg), *BASE_ARGS, "-ss", f"{max(0.0, dur - tail):.6f}",
                "-i", str(path)]
        if scale is not None:
            args += ["-vf", f"scale={scale[0]}:{scale[1]}"]
        args += ["-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
        try:
            proc = popen(args)
        except OSError:
            return None
        last: bytes | None = None
        try:
            while True:
                buf = proc.stdout.read(frame_bytes)
                if len(buf) < frame_bytes:
                    break
                last = buf
        finally:
            try:
                if proc.poll() is None:
                    proc.terminate()
                proc.stdout.close()
                if proc.stderr is not None:
                    proc.stderr.close()
                proc.wait()
            except Exception:
                pass
        if last is None:
            return None
        frame = np.frombuffer(last, dtype=np.uint8).reshape(height, width, 3).copy()
        if key is not None:
            if len(self._last_frame_cache) >= 8:      # 只留最近几片，别把帧堆在内存里
                self._last_frame_cache.pop(next(iter(self._last_frame_cache)))
            self._last_frame_cache[key] = frame
        return frame

    # ------------------------------------------------------------------ #
    # Window batch grab (2026-10-03 续46)
    # ------------------------------------------------------------------ #
    _PTS_TIME_RE = re.compile(rb"pts_time:([0-9]+\.?[0-9]*)")

    def grab_frames(self, path: str | Path, times, *,
                    max_gap_s: float = 4.0, max_span_s: float = 40.0,
                    filters: str | None = None, size: tuple[int, int] | None = None,
                    match: str = "first_ge",
                    passthrough: bool = False,
                    max_pts_lag: float | None = None) -> dict[float, np.ndarray]:
        """批量取帧：每个「时间聚类」一次 ffmpeg spawn（而非每帧一次），返回
        ``{round(t,6): BGR frame}``。

        零语义口径（对齐 ``grab_frame``）：``grab_frame(t)`` = ``-ss t`` 输入快 seek 后
        **首个 pts≥t 的解码帧**。本方法把聚类 [lo, …] 从 lo 起一次解码（H.264 解码确定性
        ⇒ 从更早处开始解码不改变任何帧内容），加 **``-copyts``** 保原始时间轴，
        ``showinfo`` 逐帧读出**原始** pts_time，对每个 t 取**首个 pts ≥ t 的帧**——同一
        选取规则在不同 seek 起点下逐位一致（验收 = 与 grab_frame 逐字节 array_equal）。
        ⚠️ 无 -copyts 时输出时间轴被重置且首帧受 seek 舍入影响（2026-10-03 实测差一帧）
        ——该 flag 是本方法成立的前提，不可省。

        聚类：升序时间相邻间隔 ≤``max_gap_s`` 且簇总跨度 ≤``max_span_s``（界内存*3 帧缓冲）。
        任一簇解码失败/流提前结束 → 该簇未满足的 t 逐帧回退 ``grab_frame``（补一次 seek 机会）。
        越界 t 不在这里钳制：簇内目标一律按**原始请求时间**解码，缺帧的 t 由 ``grab_frame``
        的严格惰性片尾兜底处理（第一版曾在此按 cap 预钳 —— cap 只是末帧下界，
        预钳会替 ``(cap, 时长]`` 内本来成功的请求换帧，2026-10-06 续61 撤掉）。

        ``filters`` 可为**字符串或 callable(簇起点) -> 字符串**（后者用于把网格锚定到簇起点，
        见 ``grab_grid_times`）。``filters``（2026-10-03 续50，L1 管道优化）：插到 ``showinfo`` 之前的附加滤波串，
        典型 = ``"fps=1/2"``（网格抽取，管道量 ÷~30）或 ``"scale=512:512"``（消费者侧预缩放）。
        ``size`` 必须与之匹配（缩放后的输出尺寸），否则回退路径形状不一致。
        ``match``：``"first_ge"``（默认，冻结契约：首个 pts≥t 的帧）或 ``"nearest"``（与
        fps 网格抽取配套：把每个目标 t 分配给 pts 最近的一帧，避免"网格相位差一帧"导致
        整格跳位）。``filters=None`` 时 ``match="nearest"`` 与 ``"first_ge"`` 等价（逐帧都在）。
        """
        path = Path(path)
        raw = [round(float(t), 6) for t in times]
        uniq = sorted(set(raw))
        if not uniq:
            return {}
        clusters: list[list[float]] = [[uniq[0]]]
        for t in uniq[1:]:
            c = clusters[-1]
            if t - c[-1] <= max_gap_s and t - c[0] <= max_span_s:
                c.append(t)
            else:
                clusters.append([t])
        got: dict[float, np.ndarray] = {}

        def _run_cluster(cl):
            flt = filters(cl[0]) if callable(filters) else filters
            try:
                return self._decode_window(path, cl, filters=flt, size=size,
                                           match=match, passthrough=passthrough,
                                           max_pts_lag=max_pts_lag)
            except MediaError:
                return None      # 该簇整体失败 → 簇内目标走下方逐帧回退

        # 簇间并发（media.cluster_workers>1；默认 1 = 现役串行逐簇，逐位不变）。
        # 各簇目标互不相交 ⇒ 合并顺序无关；失败隔离与逐帧回退语义同串行版。
        if self.cluster_workers > 1 and len(clusters) > 1:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(
                    max_workers=min(self.cluster_workers, len(clusters))) as ex:
                for res in ex.map(_run_cluster, clusters):
                    if res:
                        got.update(res)
        else:
            for cl in clusters:
                res = _run_cluster(cl)
                if res:
                    got.update(res)
        for t in uniq:
            if t not in got:
                got[t] = self.grab_frame(path, t, scale=size)
        return got

    def grab_grid(self, path: str | Path, t0: float, step: float, n: int, *,
                  filters: str | None = None, size: tuple[int, int] | None = None,
                  max_span_s: float = 40.0) -> dict[float, np.ndarray]:
        """均匀时间网格抓帧（L1 管道优化，2026-10-03 续50）：目标 = `t0 + i*step`（i=0..n-1）。

        `filters` 默认 = `select` 表达式「首帧 + 距上一选中帧 ≥ step」——**只让 ffmpeg 吐网格帧**，
        管道量从「解码秒数 × 源帧率」降到「网格点数」（1920x960 源实测 ÷~30）＝本方法存在的唯一理由。
        实测（a1.mp4）：`select` **保留原始 PTS**（fps 滤波会重定时间轴 ⇒ 相位整体偏移，已弃用），
        且必须配 `-fps_mode passthrough`（否则 vsync 复制帧补 CFR：5 帧 → 149 帧）。

        选帧仍走冻结契约 `match="first_ge"`：网格点上的目标拿到的帧与 `grab_frame` **逐字节一致**
        （网格点与 select 网格对齐，误差 ≤1 源帧）。**非网格调用方请继续用 `grab_frames`**。
        """
        if step <= 0:
            raise ValueError("step must be > 0")
        times = [round(t0 + i * step, 6) for i in range(max(0, int(n)))]
        if step < MIN_GRID_STEP_S:          # 亚秒级网格漂移不可控 ⇒ 回退旧路径（见常量注释）
            return self.grab_frames(path, times)
        times = [t for t in times if t >= 0.0]
        if not times:
            return {}
        scale = "" if size is None else ",scale=%d:%d" % (int(size[0]), int(size[1]))
        step_f = float(step)

        def _flt(lo):
            return FFmpegIO._grid_select_expr(lo, step_f) + scale

        flt = filters if filters is not None else _flt
        return self.grab_frames(path, times, max_span_s=max(step * 1.5, max_span_s),
                                filters=flt, size=size, match="first_ge",
                                passthrough=filters is None,
                                max_pts_lag=min(step_f, 0.5))
    @staticmethod
    def _grid_select_expr(lo: float, step: float) -> str:
        """网格抽取的 select 表达式（2026-10-03 续50，**无漂移版**）。

        早期用「距上一选中帧 ≥ step」（gte(t-prev_selected_t,step)）——浮点与源帧长不对齐时
        **每步都可能多走一帧并累积**：实测 1s 网格 600 点只有 121/600 逐字节同帧。
        改为「锚定簇起点的绝对窗口」：选中每个 [lo+k*step, lo+(k+1)*step) 窗口内的**第一帧**，
        窗口由绝对时间决定 ⇒ 误差不累积（每点 ≤1 源帧）。
        """
        return ("select='isnan(prev_selected_t)+gt(floor((t-%.6f)/%.6f),floor((prev_selected_t-%.6f)/%.6f))'"
                % (lo, step, lo, step))
    def grab_grid_times(self, path: str | Path, times, *, step: float | None = None,
                        size: tuple[int, int] | None = None,
                        max_span_s: float = 40.0) -> dict[float, np.ndarray]:
        """网格抓帧（显式时间表版，2026-10-03 续50 接线用）：`times` 允许**带洞**。

        抽帧步长取 `step` 或时间表的最小间距：select 抽出的帧是**目标集合的超集**，
        再由冻结规则 `first_ge` 把每个 t 配到「首个 pts≥t 的已抽取帧」⇒ 有洞也不会错位
        （这是接线阶段必须支持带洞的原因：宽扫的 `coarse_ts` 会剔除近主点）。
        """
        ts = sorted({round(float(t), 6) for t in times})
        if not ts:
            return {}
        if step is None:
            gaps = [b - a for a, b in zip(ts, ts[1:]) if b - a > 1e-6]
            step = min(gaps) if gaps else 1.0
        if step <= 0:
            raise ValueError("step must be > 0")
        if step < MIN_GRID_STEP_S:          # 亚秒级网格漂移不可控 ⇒ 回退旧路径（见常量注释）
            return self.grab_frames(path, ts)
        scale = "" if size is None else ",scale=%d:%d" % (int(size[0]), int(size[1]))
        step_f = float(step)

        def _flt(lo):
            return FFmpegIO._grid_select_expr(lo, step_f) + scale

        return self.grab_frames(path, ts, max_span_s=max_span_s, filters=_flt, size=size,
                                match="first_ge", passthrough=True,
                                max_pts_lag=min(step_f, 0.5))

    def _decode_window(self, path: Path, ts_sorted: list[float], *,
                       filters: str | None = None,
                       size: tuple[int, int] | None = None,
                       match: str = "first_ge",
                       passthrough: bool = False,
                       max_pts_lag: float | None = None) -> dict[float, np.ndarray]:
        """单 spawn 解一个时间簇，返回 ``{t: frame}``。选帧规则见 ``grab_frames``。

        ``filters`` 非空时插在 ``showinfo`` 前（网格抽取/预缩放）；``size`` = 滤波后的输出尺寸；
        ``match`` = ``"first_ge"``（冻结契约）或 ``"nearest"``（配合 fps 网格：按 pts 最近分配）。

        ``max_pts_lag``（2026-10-03 续51 安全网）：网格抽取时，若某目标 t 被分配到的帧 pts 比 t
        晚超过该阈值，则**拒绝该分配**（不进 picked）⇒ 调用方逐帧回退 ``grab_frame``（精确）。存在的理由：
        生产网格是 ``round(wlo + i*2, 3)``，步长有 0.001s 级抖动 + select 窗口按统一 step 生成，
        窗口起点会缓慢漂到目标之前 ⇒ 偶发**整格（2s）跳位**（实测 test2 3/67 段因此翻落点）。
        阈值 0.5s 可区分「正常 ≤1 源帧的抖动」与「整格跳位」。
        """
        if match not in ("first_ge", "nearest"):
            raise ValueError(f"unknown match mode: {match}")
        lo = ts_sorted[0]
        info = self.metadata(path)
        if not info.has_video:
            raise MediaError(f"{path.name}: no video stream")
        width, height = size if size is not None else self._output_size(info, None)
        frame_bytes = width * height * 3

        # BASE_ARGS 带 -loglevel error（会吞掉 showinfo 的 info 级输出）⇒ 此处显式改回 info；
        # -copyts 保原始时间轴（无它输出轴被重置且首帧受 seek 舍入影响 ⇒ 映射差一帧，实测）。
        vf = "showinfo" if not filters else f"{filters},showinfo"
        args = [str(self.ffmpeg), *BASE_ARGS, "-loglevel", "info",
                "-ss", f"{lo:.6f}", "-i", str(path), "-copyts",
                "-vf", vf]
        if passthrough:
            # select 滤波会改变帧率，默认 vsync 会**复制帧补足 CFR**（实测 5 帧 → 149 帧）
            args += ["-fps_mode", "passthrough"]
        args += ["-an", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
        proc = popen(args)
        pts_list: list[float] = []

        def _pump_stderr() -> None:
            try:
                for line in iter(proc.stderr.readline, b""):
                    m = self._PTS_TIME_RE.search(line)
                    if m:
                        pts_list.append(float(m.group(1)))
            except Exception:
                pass
            finally:
                try:
                    proc.stderr.close()
                except Exception:
                    pass

        terr = threading.Thread(target=_pump_stderr, daemon=True)
        terr.start()
        picked: dict[float, np.ndarray] = {}
        fi = 0          # 已读 stdout 帧数
        ti = 0          # 已满足的 target 数
        prev: tuple[float, np.ndarray] | None = None   # nearest 模式的一帧延迟缓冲
        rejected: set[float] = set()   # 网格安全网：晚于目标超过 max_pts_lag 的分配被拒
        try:
            while ti < len(ts_sorted):
                # 等 showinfo 给出第 fi 帧的 pts（stderr 略滞后于 stdout）
                deadline = time.monotonic() + self.timeout_s
                while len(pts_list) <= fi:
                    if proc.poll() is not None and len(pts_list) <= fi:
                        break  # 流结束
                    if time.monotonic() > deadline:
                        raise MediaError(f"decode_window pts wait timeout: {path.name}")
                    time.sleep(0.001)
                if len(pts_list) <= fi:
                    if fi == 0 and not pts_list:
                        # 一帧 pts 都没有 = showinfo 被日志级别吞掉（防呆）→ 整簇回退逐帧
                        raise MediaError(f"decode_window: no showinfo pts output: {path.name}")
                    break  # EOF：剩余 target 走回退
                buf = proc.stdout.read(frame_bytes)
                if len(buf) < frame_bytes:
                    break
                if fi >= len(pts_list):  # 理论不可达（上面已等）
                    break
                picked_pts = pts_list[fi]
                fi += 1
                frame = np.frombuffer(buf, dtype=np.uint8).reshape(height, width, 3).copy()
                if match == "first_ge":
                    # 满足所有 pts ≥ t 尚未满足的 target（-copyts ⇒ pts 已是原始轴）
                    while ti < len(ts_sorted) and ts_sorted[ti] <= picked_pts + 1e-6:
                        t_i = ts_sorted[ti]
                        if max_pts_lag is not None and (picked_pts - t_i) > max_pts_lag:
                            rejected.add(t_i)      # 整格跳位 ⇒ 交回调用方逐帧精确抓取
                            ti += 1
                            continue
                        picked[t_i] = frame
                        ti += 1
                else:
                    if prev is None:
                        # 首帧 = 第一个 pts ≥ 簇起点的帧 ⇒ 起点侧（含等于）目标归它
                        while ti < len(ts_sorted) and ts_sorted[ti] <= picked_pts + 1e-6:
                            picked[ts_sorted[ti]] = frame
                            ti += 1
                    else:
                        # 目标落在两帧之间：取 pts 更近的那一帧（fps 网格抽取的相位容错）
                        mid = (prev[0] + picked_pts) / 2.0
                        while ti < len(ts_sorted) and ts_sorted[ti] <= mid + 1e-6:
                            picked[ts_sorted[ti]] = prev[1]
                            ti += 1
                    prev = (picked_pts, frame)
        finally:
            try:
                if proc.poll() is None:
                    proc.terminate()
                proc.stdout.close()
                proc.wait()
            except Exception:
                pass
            terr.join(timeout=5.0)
        return picked

    # ------------------------------------------------------------------ #
    # Clip extraction
    # ------------------------------------------------------------------ #
    def extract_clip(self, path: str | Path, start: float, end: float,
                     out_path: str | Path, *, codec: str = _DEFAULT_CODEC,
                     preset: str = _DEFAULT_PRESET, crf: int = _DEFAULT_CRF,
                     include_audio: bool = True, overwrite: bool = True) -> Path:
        """Extract the exact ``[start, end]`` interval into a re-encoded file.

        Frame-accurate via ``-ss <start> -i ... -t <len>`` (fast input seek) plus
        re-encode. ``-c copy`` would be keyframe-aligned and NOT precise — rejected
        per MVP product spec. Returns the output ``out_path``.
        """
        path = Path(path)
        out_path = Path(out_path)
        if end <= start:
            raise MediaError(
                f"extract_clip end must be > start ({start} -> {end}) for {path.name}"
            )

        # Range sanity against known duration (warn only; never silently clamp).
        info = self.metadata(path)
        if info.duration and start >= info.duration:
            raise MediaError(
                f"extract_clip start {start}s is beyond duration {info.duration:.1f}s"
            )
        if info.duration and end > info.duration + 0.5:
            raise MediaError(
                f"extract_clip end {end}s exceeds duration {info.duration:.1f}s"
            )

        out_path.parent.mkdir(parents=True, exist_ok=True)
        args = [str(self.ffmpeg), *BASE_ARGS]
        if overwrite:
            args += ["-y"]
        args += ["-ss", f"{start:.6f}", "-i", str(path), "-t", f"{end - start:.6f}",
                 "-map", "0:v:0"]
        if include_audio:
            args += ["-map", "0:a:0?"]          # audio optional (source may lack it)
        args += ["-c:v", codec, "-preset", preset, "-crf", str(crf),
                 "-pix_fmt", "yuv420p", "-avoid_negative_ts", "make_zero"]
        if include_audio:
            args += ["-c:a", "aac"]
        args += [str(out_path)]

        check_run(args, timeout=self.timeout_s)
        return out_path

    # ------------------------------------------------------------------ #
    # File hashing (for index validation)
    # ------------------------------------------------------------------ #
    def hash_file(self, path: str | Path, algo: str = "sha256") -> str:
        """Streaming file hash. Bounded memory; 1 MiB chunks.

        NOTE: for a multi-GB original a full hash costs a few seconds. The
        FeatureStore may do a fast validation (size + duration + mtime + model
        version) and only compute this full hash when a fast check is ambiguous.
        """
        path = Path(path)
        hasher = hashlib.new(algo)
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _output_size(info: VideoMetadata, scale: tuple[int, int] | None) -> tuple[int, int]:
        if scale is not None:
            return int(scale[0]), int(scale[1])
        return info.width, info.height

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"FFmpegIO(ffmpeg={self.ffmpeg.name}, ffprobe={self.ffprobe.name}, "
            f"timeout_s={self.timeout_s})"
        )
