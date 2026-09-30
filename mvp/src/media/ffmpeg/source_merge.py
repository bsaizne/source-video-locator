"""source_merge — 多原片无损/转码合并（竞品 processing.video.concat + web.file_api.concat 移植，2026-09-29）。

竞品语义（D#221/#240 docstring 挖穿，见 FINDINGS_CAPABILITY_MAP_20260928.md 表 D）：
用户给「分集/多段原片」时，在入库前把多个视频文件物理拼接成**单个**文件，
下游索引/匹配/导出仍面对单原片——不是多索引并行匹配。决策链：

  1) 流签名全等（codec/分辨率/pix_fmt/色彩元数据/帧率/SAR/音频）→ ffmpeg concat
     demuxer 流复制（``copy``）；
  2) 否则 → HEVC 转码尝试链：探测在位的硬件编码器（nvenc/qsv/amf/videotoolbox…）
     → libx265（medium/CRF 18，竞品字节确证）兜底，每步失败打印中文回退说明；
  3) HDR/高位深片源：硬件编码器 → p010le，libx265 → yuv420p10le，普通片源 yuv420p；
     色彩元数据透传（-color_primaries/-color_trc/-colorspace/-color_range），
     libx265 追加 x265-params（repeat-headers=1 [+ hdr-opt]）；
  4) 稳定命名缓存：``merged_<数量>_<12位MD5(name|size|mtime|mode)>_<模式>.<ext>``，
     已存在且探测有效（时长≈各段之和）→ 直接复用；无效 → 删除重建；
  5) 运行监护：``-progress pipe:1`` 解析 out_time 映射进度、stderr 写临时文件供失败
     摘要、默认 1h 超时（terminate→kill）、取消轮询、无输出每 5s 等待心跳、
     完成后输出校验（存在 + 有视频流 + 时长在容差内）。

口径差异（如实记录，非等价复刻）：
  - 竞品打包 MKVToolNix，全 MKV 输入走 mkvmerge 无损；我方发行物未含 mkvmerge，
    同签名 MKV 的无损路径 = concat demuxer ``-c copy``（流复制语义等价，
    编码器尝试链与「MKV→mkvmerge」路由缺失）。
  - 竞品各硬件编码器的质量控制参数未字节确证（docstring 只到「分别采用各自质量
    控制参数」）→ ``_HW_QUALITY_ARGS`` 为我方工程先验值。
  - 文件夹扫描入口（竞品 file_api 目录展开/自然排序）未随本模块移植——属素材入库
    工具面差集项，另行立项。
  - 音频「有/无」混用的输入：转码降级为纯视频（竞品未确证该边界处理）。
"""
from __future__ import annotations

import hashlib
import os
import queue
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from ._runner import CREATE_NO_WINDOW, MediaError, _error_tail
from .ffprobe import probe_metadata

# --------------------------------------------------------------------------- #
# 纯函数层（无子进程，可单测）
# --------------------------------------------------------------------------- #

# 竞品硬件编码器候选（win: nvenc/qsv/amf，mac: videotoolbox）；顺序=尝试顺序。
HW_ENCODER_ORDER = ["hevc_nvenc", "hevc_qsv", "hevc_amf", "hevc_videotoolbox"]
CPU_ENCODER = "libx265"

_HDR_TRC = {"smpte2084", "arib-std-b67"}  # PQ / HLG（竞品 docstring 确证判据）

# 竞品未字节确证各硬件编码器质量参数 → 工程先验值（见模块头口径差异）。
_HW_QUALITY_ARGS: dict[str, list[str]] = {
    "hevc_nvenc": ["-preset", "p4", "-cq", "23"],
    "hevc_qsv": ["-global_quality", "23"],
    "hevc_amf": ["-quality", "balanced"],
    "hevc_videotoolbox": ["-vb", "8M"],
}


def video_signature(vstream: dict) -> tuple:
    """首个视频流的「可无损拼接」签名：全等才允许 copy。"""
    return (
        str(vstream.get("codec_name") or ""),
        int(vstream.get("width") or 0),
        int(vstream.get("height") or 0),
        str(vstream.get("pix_fmt") or ""),
        str(vstream.get("avg_frame_rate") or ""),
        str(vstream.get("sample_aspect_ratio") or "1:1"),
        str(vstream.get("color_primaries") or ""),
        str(vstream.get("color_trc") or ""),
        str(vstream.get("color_space") or ""),
        str(vstream.get("color_range") or ""),
    )


def audio_signature(astream: dict | None) -> tuple | None:
    if astream is None:
        return None
    return (
        str(astream.get("codec_name") or ""),
        str(astream.get("sample_rate") or ""),
        int(astream.get("channels") or 0),
    )


def _first_video_stream(probe: dict) -> dict | None:
    return next((s for s in (probe.get("streams") or [])
                 if s.get("codec_type") == "video"), None)


def file_signature(probe: dict) -> tuple:
    streams = probe.get("streams") or []
    v = _first_video_stream(probe)
    if v is None:
        name = (probe.get("format") or {}).get("filename") or "?"
        raise MediaError(f"视频文件缺少画面轨道: {name}")
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    return (video_signature(v), audio_signature(a))


def is_copy_compatible(sigs: Sequence[tuple]) -> bool:
    """竞品「选择主媒体规格」判据的等价：全部片段音视频签名全等 → 流复制可达。"""
    if len(sigs) < 2:
        return False
    return all(s == sigs[0] for s in sigs[1:])


def is_hdr(vstream: dict) -> bool:
    """竞品确证判据：PQ / HLG / BT.2020 原色 / bt2020* 色彩空间 任一命中。"""
    trc = str(vstream.get("color_trc") or "")
    pri = str(vstream.get("color_primaries") or "")
    space = str(vstream.get("color_space") or "")
    return trc in _HDR_TRC or pri == "bt2020" or space.startswith("bt2020")


def is_high_bit_depth(vstream: dict) -> bool:
    pix = str(vstream.get("pix_fmt") or "")
    return any(t in pix for t in ("10le", "10be", "12le", "16le", "p010", "gbrp16"))


def pick_pix_fmt(vstream: dict, encoder: str) -> str:
    """竞品确证语义：高位深/HDR + 硬件编码器 → p010le；+ libx265 → yuv420p10le；普通 → yuv420p。"""
    if is_high_bit_depth(vstream) or is_hdr(vstream):
        return "yuv420p10le" if encoder == CPU_ENCODER else "p010le"
    return "yuv420p"


def color_args(vstream: dict) -> list[str]:
    """存在的色彩元数据 → ffmpeg 参数（固定顺序，竞品确证）。空值不产生参数。"""
    args: list[str] = []
    for key, flag in (("color_primaries", "-color_primaries"),
                      ("color_trc", "-color_trc"),
                      ("color_space", "-colorspace"),
                      ("color_range", "-color_range")):
        val = str(vstream.get(key) or "").strip()
        if val and val.lower() not in ("unknown", "unspecified"):
            args += [flag, val]
    return args


def x265_params(vstream: dict) -> str:
    """libx265 色彩参数字符串：始终 repeat headers，HDR 加 hdr-opt，附原色/传递/矩阵。"""
    parts = ["repeat-headers=1"]
    if is_hdr(vstream):
        parts.append("hdr-opt=1")
    for key, pname in (("color_primaries", "colorprim"), ("color_trc", "transfer"),
                       ("color_space", "colormatrix")):
        val = str(vstream.get(key) or "").strip()
        if val and val.lower() not in ("unknown", "unspecified"):
            parts.append(f"{pname}={val}")
    return ":".join(parts)


def encoder_args(encoder: str, vstream: dict, crf: int = 18) -> list[str]:
    """一次转码尝试的视频编码参数（pix_fmt 随源位深/HDR 与编码器选择）。"""
    pix = pick_pix_fmt(vstream, encoder)
    if encoder == CPU_ENCODER:
        return ["-c:v", CPU_ENCODER, "-preset", "medium", "-crf", str(crf),
                "-pix_fmt", pix, "-x265-params", x265_params(vstream)]
    return ["-c:v", encoder, *_HW_QUALITY_ARGS.get(encoder, []), "-pix_fmt", pix]


def encoder_chain(available: Sequence[str], *, prefer_hw: bool = True) -> list[str]:
    """去重硬件尝试序 + libx265 唯一兜底（竞品确证：候选空/重复/libx265 跳过，最后回退）。"""
    chain: list[str] = []
    if prefer_hw:
        for name in HW_ENCODER_ORDER:
            if name in available and name not in chain:
                chain.append(name)
    chain.append(CPU_ENCODER)
    return chain


def parse_hevc_encoders(encoders_output: str) -> list[str]:
    """从 ``ffmpeg -encoders`` 文本提取可用的 HEVC/h265 视频编码器名。"""
    found: list[str] = []
    for line in encoders_output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V."):
            name = parts[1]
            if (name.startswith("hevc_") or name == CPU_ENCODER) and name not in found:
                found.append(name)
    return found


def merge_output_name(paths: Sequence[str | Path], mode: str, ext: str) -> str:
    """竞品确证的稳定命名：数量 + 12 位 MD5（名称/大小/修改时间/模式）+ 模式后缀 + 扩展名。
    元数据读取失败时仅用名称。"""
    hasher = hashlib.md5()
    for p in paths:
        p = Path(p)
        try:
            st = p.stat()
            hasher.update(f"{p.name}|{st.st_size}|{int(st.st_mtime)}|{mode}".encode("utf-8"))
        except OSError:
            hasher.update(f"{p.name}|||{mode}".encode("utf-8"))
    return f"merged_{len(paths)}_{hasher.hexdigest()[:12]}_{mode}.{ext}"


def choose_extension(paths: Sequence[str | Path], mode: str) -> str:
    """全 MKV 输入且流复制 → mkv；其余 mp4（竞品：模式配置决定目标扩展名）。"""
    if mode == "copy" and all(Path(p).suffix.lower() == ".mkv" for p in paths):
        return "mkv"
    return "mp4"


def concat_list_text(paths: Sequence[str | Path]) -> str:
    """ffmpeg concat demuxer 清单：绝对路径 + ``'`` 转义、反斜杠归一为正斜杠。"""
    lines = []
    for p in paths:
        text = str(Path(p)).replace("\\", "/")
        lines.append("file '" + text.replace("'", "'\\''") + "'")
    return "\n".join(lines) + "\n"


_OUT_TIME_KEYS = ("out_time_us", "out_time_ms")  # 两个键都是**微秒**（ffmpeg 历史命名坑）


def parse_progress_seconds(line: str) -> float | None:
    """解析一行 ``-progress`` 输出为已处理秒数；不匹配/非法 → None。"""
    line = line.strip()
    key, sep, val = line.partition("=")
    if not sep:
        return None
    key = key.strip()
    val = val.strip()
    try:
        if key in _OUT_TIME_KEYS:
            return max(0.0, int(val) / 1_000_000.0)
        if key == "out_time":
            head, _, frac = val.partition(".")
            h, m, s = head.split(":")
            return int(h) * 3600 + int(m) * 60 + int(s) + float("0." + frac if frac else "0.0")
    except (ValueError, AttributeError):
        return None
    return None


def duration_tolerance(total: float) -> float:
    return max(1.0, total * 0.02)


def error_summary(text: str, max_length: int = 400) -> str:
    """失败详情压缩为单行限长（竞品确证语义：连续空白折叠、超长省略号截断）。"""
    flat = " ".join(text.split())
    if not flat:
        return ""
    return flat if len(flat) <= max_length else flat[:max_length] + "…"


# --------------------------------------------------------------------------- #
# 执行层（子进程 + 监护）
# --------------------------------------------------------------------------- #

@dataclass
class MergePlan:
    paths: list[str]
    mode: str                    # copy | transcode
    output: Path
    total_duration: float
    reason: str = ""
    reused: bool = False
    main_video: dict = field(default_factory=dict)
    has_audio: bool = True
    fps: str = "25/1"


class SourceVideoMerger:
    """多原片 → 单文件（copy 优先，失败/签名不合 → HEVC 转码尝试链）。

    ``progress(frac, message)``：frac∈[0,1] 表示实际进度，``None`` 表示无输出等待
    心跳；阶段区间映射由调用方决定。``cancel()`` 返回 True 时终止子进程并抛
    :class:`MediaError`。
    """

    def __init__(self, ffmpeg: str | Path, ffprobe: str | Path, out_dir: str | Path, *,
                 timeout_s: float = 3600.0, prefer_hw: bool = True, crf: int = 18,
                 log: Callable[..., None] | None = None):
        self.ffmpeg = str(ffmpeg)
        self.ffprobe = str(ffprobe)
        self.out_dir = Path(out_dir)
        self.timeout_s = float(timeout_s)
        self.prefer_hw = prefer_hw
        self.crf = int(crf)
        self._log = log or (lambda *a, **k: None)
        self._encoders: list[str] | None = None

    # -- probe ------------------------------------------------------------ #
    def probe(self, path: Path) -> dict:
        return probe_metadata(path, self.ffprobe)

    @staticmethod
    def _duration(probe: dict) -> float:
        fmt = probe.get("format") or {}
        try:
            return float(fmt.get("duration") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def available_hevc_encoders(self) -> list[str]:
        if self._encoders is None:
            try:
                proc = subprocess.run(
                    [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-encoders"],
                    capture_output=True, timeout=30, check=False,
                    creationflags=CREATE_NO_WINDOW)
                out = proc.stdout.decode("utf-8", errors="replace")
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise MediaError(f"无法探测 ffmpeg 编码器列表: {exc}") from exc
            self._encoders = parse_hevc_encoders(out)
        return self._encoders

    # -- plan -------------------------------------------------------------- #
    def plan(self, paths: Sequence[str | Path]) -> MergePlan:
        ps = [Path(p).resolve() for p in paths]
        if len(ps) < 2:
            raise MediaError("没有可合并的视频（需要至少 2 个原片文件）")
        probes = []
        for p in ps:
            if not p.exists():
                raise MediaError(f"原片文件不存在: {p}")
            probes.append(self.probe(p))
        sigs = [file_signature(pb) for pb in probes]
        durations = [self._duration(pb) for pb in probes]
        if any(d <= 0 for d in durations):
            bad = ps[min(range(len(durations)), key=durations.__getitem__)]
            raise MediaError(f"无法确定视频时长: {bad.name}")
        total = float(sum(durations))
        copy_ok = is_copy_compatible(sigs)
        mode = "copy" if copy_ok else "transcode"
        ext = choose_extension(ps, mode)
        out = self.out_dir / merge_output_name(ps, mode, ext)
        main_v = _first_video_stream(probes[0]) or {}
        has_audio = sigs[0][1] is not None
        reason = "签名全等，流复制"
        if not copy_ok:
            reason = "签名不一致（或 copy 未开放），转码补齐"
            presence = {s[1] is not None for s in sigs}
            if len(presence) > 1:
                has_audio = False
                reason += "；音频有无不一致，降级纯视频"
        fps = str(main_v.get("avg_frame_rate") or "0/0")
        if fps in ("0/0", ""):
            fps = "25/1"
        return MergePlan(paths=[str(p) for p in ps], mode=mode, output=out,
                         total_duration=total, reason=reason, main_video=main_v,
                         has_audio=has_audio, fps=fps)

    def _valid_output(self, out: Path, total: float) -> bool:
        """竞品「输出校验」语义：存在 + 有视频流 + 时长≈各段之和（容差内）。"""
        if not out.exists():
            return False
        try:
            probe = self.probe(out)
        except MediaError:
            return False
        if _first_video_stream(probe) is None:
            return False
        return abs(self._duration(probe) - total) <= duration_tolerance(total)

    # -- commands ----------------------------------------------------------- #
    def _copy_args(self, plan: MergePlan, list_path: Path, tmp_out: Path) -> list[str]:
        return [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
                "-f", "concat", "-safe", "0", "-i", str(list_path),
                "-map", "0:v:0", "-map", "0:a?",
                "-c", "copy", "-avoid_negative_ts", "make_zero",
                "-progress", "pipe:1", str(tmp_out)]

    def _transcode_args(self, plan: MergePlan, encoder: str, tmp_out: Path) -> list[str]:
        args = [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
        for p in plan.paths:
            args += ["-i", p]
        v = plan.main_video
        w = int(v.get("width") or 0)
        h = int(v.get("height") or 0)
        n = len(plan.paths)
        fc = [f"[{i}:v:0]scale={w}:{h}:force_original_aspect_ratio=decrease,"
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={plan.fps}[v{i}]"
              for i in range(n)]
        ins = "".join(f"[v{i}]" + (f"[{i}:a:0]" if plan.has_audio else "") for i in range(n))
        if plan.has_audio:
            fc.append(f"{ins}concat=n={n}:v=1:a=1[outv][outa]")
        else:
            fc.append(f"{ins}concat=n={n}:v=1:a=0[outv]")
        args += ["-filter_complex", ";".join(fc), "-map", "[outv]"]
        if plan.has_audio:
            args += ["-map", "[outa]", "-c:a", "aac", "-b:a", "192k"]
        else:
            args += ["-an"]
        args += encoder_args(encoder, v, self.crf)
        args += color_args(v)
        args += ["-avoid_negative_ts", "make_zero", "-progress", "pipe:1", str(tmp_out)]
        return args

    # -- run with supervision ------------------------------------------------ #
    def _run(self, args: list[str], *, total: float, progress, cancel,
             label: str) -> tuple[int, str]:
        """跑一条命令，返回 (rc, stderr 单行摘要)。terminate/kill/超时全兜住，取消转 MediaError。"""
        err_fd, err_path = tempfile.mkstemp(prefix="svl_merge_err_", suffix=".log")
        err_file = os.fdopen(err_fd, "w+b")
        try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=err_file,
                                    stdin=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        except OSError as exc:
            err_file.close()
            try:
                os.unlink(err_path)
            except OSError:
                pass
            raise MediaError(f"无法启动 {label}: {exc}") from exc

        lines: queue.Queue = queue.Queue()

        def _reader():
            try:
                assert proc.stdout is not None
                for raw in proc.stdout:
                    lines.put(raw.decode("utf-8", errors="replace"))
            except (OSError, ValueError):
                pass
            finally:
                lines.put(None)

        threading.Thread(target=_reader, daemon=True, name="svl-merge-progress").start()

        def _kill():
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001 — 尽力终止（竞品确证语义），清理异常不外传
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:  # noqa: BLE001
                    pass

        deadline = time.monotonic() + self.timeout_s
        last_heartbeat = time.monotonic()
        cancelled = timed_out = eof = False
        while True:
            try:
                line = lines.get(timeout=1.0)
            except queue.Empty:
                line = ""
            if line is None:
                eof = True
            elif line.strip():
                secs = parse_progress_seconds(line)
                if secs is not None and total > 0 and progress is not None:
                    frac = min(1.0, max(0.0, secs / total))
                    progress(frac, f"{label} {int(frac * 100)}%")
            if cancel is not None and cancel():
                cancelled = True
                _kill()
                break
            if time.monotonic() > deadline:
                timed_out = True
                _kill()
                break
            if eof and proc.poll() is not None:
                break
            if time.monotonic() - last_heartbeat >= 5.0:
                last_heartbeat = time.monotonic()
                if progress is not None:
                    progress(None, f"{label}：素材合并中，请稍候…")
        if proc.poll() is None:
            _kill()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        rc = proc.returncode
        try:
            err_file.flush()
            err_file.seek(0)
            err_text = err_file.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            err_text = ""
        finally:
            err_file.close()
            try:
                os.unlink(err_path)
            except OSError:
                pass
        if cancelled:
            raise MediaError(f"{label} 已取消")
        if timed_out:
            raise MediaError(f"{label} 超时（>{self.timeout_s:.0f}s），已终止合并进程")
        return rc, error_summary(_error_tail(err_text, n=2000))

    # -- public API ---------------------------------------------------------- #
    def merge(self, paths: Sequence[str | Path], *,
              progress: Callable[[float | None, str], None] | None = None,
              cancel: Callable[[], bool] | None = None) -> dict:
        """合并多个原片为单文件；返回 ``{merged_path, mode, reused, duration_s}``。

        copy 失败（rc≠0 或输出校验不过）自动降级转码链——与竞品
        「MKV 无损合并失败 → 回退」语义一致。
        """
        plan = self.plan(paths)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        if self._valid_output(plan.output, plan.total_duration):
            plan.reused = True
            self._log("source merge reuse cache: %s", plan.output.name)
            if progress is not None:
                progress(1.0, f"复用已有合并原片: {plan.output.name}")
            return {"merged_path": str(plan.output), "mode": plan.mode,
                    "reused": True, "duration_s": plan.total_duration}

        # tmp 必须保留目标扩展名（ffmpeg 按扩展选 muxer），.part 走前缀位
        tmp = plan.output.parent / (plan.output.stem + ".part" + plan.output.suffix)
        attempts: list[tuple[str, Callable[[Path, Path], list[str]], bool]] = []
        if plan.mode == "copy":
            attempts.append(("copy", self._copy_args, True))
        for enc in encoder_chain(self.available_hevc_encoders(), prefer_hw=self.prefer_hw):
            attempts.append((enc, self._transcode_builder(enc), False))

        last_err = ""
        for idx, (label, build, uses_list) in enumerate(attempts):
            nxt = attempts[idx + 1][0] if idx + 1 < len(attempts) else None
            if uses_list:
                list_path = plan.output.parent / (plan.output.name + ".list.txt")
                list_path.write_text(concat_list_text(plan.paths), encoding="utf-8")
                cmd = build(plan, list_path, tmp)
                run_label = "流复制合并"
            else:
                cmd = build(plan, tmp)  # type: ignore[arg-type]
                run_label = f"转码合并（{label}）"
            try:
                rc, err = self._run(cmd, total=plan.total_duration, progress=progress,
                                    cancel=cancel, label=run_label)
            finally:
                if uses_list:
                    try:
                        list_path.unlink(missing_ok=True)  # type: ignore[possibly-undefined]
                    except OSError:
                        pass
            if rc == 0 and self._valid_output(tmp, plan.total_duration):
                os.replace(tmp, plan.output)
                self._log("source merge ok via %s: %s", label, plan.output.name)
                if progress is not None:
                    progress(1.0, "原片合并完成")
                return {"merged_path": str(plan.output),
                        "mode": "copy" if label == "copy" else "transcode",
                        "reused": False, "duration_s": plan.total_duration}
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            last_err = err
            self._log("source merge attempt %s failed (rc=%s): %s", label, rc, err)
            if progress is not None and label != "copy":
                progress(None, f"硬件编码器 {label} 执行失败，已回退到 {nxt or 'CPU 兜底（仍失败）'}")
        raise MediaError(f"原片合并失败（所有尝试均未产出有效输出）。最后错误: {last_err or '无输出文件'}")

    def _transcode_builder(self, encoder: str):
        def build(plan: MergePlan, tmp_out: Path) -> list[str]:
            return self._transcode_args(plan, encoder, tmp_out)
        return build
