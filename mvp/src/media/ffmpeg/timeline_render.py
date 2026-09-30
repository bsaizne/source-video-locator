"""timeline_render —— 定位结果 → 成片视频（竞品 ``exporting.rendering.video_renderer`` 移植）。

2026-09-29 续30 立项。竞品差集 TOP1「成片渲染」：我方此前只产 NLE 工程文本
（``render_edl`` / ``render_fcp7_xml`` / 剪映草稿），竞品能直接给出一个可播放的合并成片。
本模块补齐「按定位片段从原片裁段 → 统一口径重编码 → 拼接 → 帧数校验 → 进程监护」。
**成片渲染是新入口**：既有定位/导出链路与生产基线零改动。

证据分级（全文见
``mvp/benchmark/user_case/competitor_cutmatch/FINDINGS_VIDEO_RENDER_PORT.md``）：

- **字节确证**（blob #138 ``video_renderer.py``，527 常量 / 75 条中文 docstring 原文）：
  逐段恒定帧率过滤器（``fps=fps=`` + ``trim`` + ``setpts`` + ``round=near``）；合并优先流复制
  （``-f concat -safe 0 -map 0:v:0 -c:v copy -avoid_negative_ts make_zero
  -movflags +faststart -sn -dn``），复制失败回退重编码合并（``-fps_mode cfr -r``）；
  逐段帧数校验先 ``nb_frames`` 快速、不可信才 ``-count_frames`` 严格（文案
  「帧数错误: 第 N 段预期 X，实际 Y」）；硬件编码器失败拉黑并回退软件
  （``_run_ffmpeg_with_encoder_fallback`` / 进程内禁用集合 /
  ``_reset_disabled_hardware_encoders_for_tests``）；停滞看门狗
  （``_render_stall_timeout_seconds`` / 「FFmpeg rendering stalled for %.1f seconds;
  terminating command」）；``-progress`` 机器可读进度 + 读取线程队列；
  terminate→wait→kill 三段停止；片段并发 ``render_workers`` 且**按索引保序**、并发失败
  「已回退串行」；产物稳定命名可复用。在位数值常量：``1920/1080``、``48000``、
  ``1800.0``、``120.0``、``2``、``6``，进度区间 ``45/57/67/75/85/90``。
- **我方拍板口径（用户 2026-09-29 选定，与竞品两处刻意不同）**：
  ① **紧凑拼接**——不落地竞品的黑场空档腿（``color=c=black`` + ``anullsrc`` 空档渲染项）：
  成片时长 = Σ 片段时长，未定位/被排除段直接跳过；
  ② **音轨取原片对应区间**（竞品同源：首条音频流），不用解说轨；源片无音轨时逐段补等长
  ``anullsrc`` 静音——这不是产品选择，而是各段轨道结构一致的硬要求（结构不一致时
  concat 流复制必失败）。
- **本机实测确立的工程结论（2026-09-29 续30 验收时发现，非竞品确证）**：
  中段音频**不能用 AAC**。AAC 每帧 1024 样本（48k = 21.3ms）会把段尾补齐，使中段音频
  恒比视频长一帧；concat demuxer 按容器内最长流推进偏移，于是成片每个接缝都出现
  ``0.0417s → 0.0630s`` 的视频拉伸缝（2.mkv 60 段实测 **59 处**，容器帧率被探成
  48000/1001）。改成 **中段 MOV + PCM 24bit + 最终合并只复制视频、音频转一次 AAC** 后，
  真实验收复跑 = 3552 帧、**不规则帧距 0 处**、帧率回到 24000/1001。
  ``-shortest`` 是错误解法：实测会反向截掉视频帧（144→141）并把间隙放大到 0.103s。
  回归锁 = ``mvp/tests/test_timeline_render.py`` 帧距集合断言 +
  ``mvp/scripts/accept_video_render_2mkv.py`` 的 ``frame_delta_stats`` / ``alignment_probe``。
- **工程先验（非竞品确证）**：CRF/预设/并发默认值、硬件档码率、超时取值方向由我方本机实测
  决定；不由 GT 反标。HDR/10bit 源成片降 8bit SDR（NLE 工程仍指原片，不损失源数据），
  留痕 ``hdr_downgraded``。

复用不重写：concat 清单转义、``-progress`` 行解析、错误摘要、``CREATE_NO_WINDOW``
来自 :mod:`media.ffmpeg._runner` / :mod:`media.ffmpeg.source_merge`（续27 已真机验收）。
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Callable, Sequence

from ._runner import CREATE_NO_WINDOW, MediaError, _error_tail
from .source_merge import (
    concat_list_text,
    error_summary,
    is_hdr,
    is_high_bit_depth,
    parse_progress_seconds,
)

# 竞品 blob #138 在位数值：48000（音频采样率）/ 1800.0、120.0（总超时、停滞阈值）/
# 2、6（片段并发）。我方默认取保守端，其余由 ``RenderConfig`` 覆盖。
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_STALL_TIMEOUT_S = 120.0
DEFAULT_TIMEOUT_S = 1800.0
SOFTWARE_H264 = "libx264"
# 中段容器 = **MOV + PCM 24bit 音频**（不是 MP4/AAC）。理由见模块头「本机实测确立的
# 工程结论」：MP4 中段的 AAC 补齐让音频比视频长一个 AAC 帧，concat demuxer 按容器时长
# 推进偏移，实测在 2.mkv 60 段成片里留下 59 处 +0.0213s 的视频接缝；PCM 采样精确，
# 实测帧距全部等于 1/fps。中段容器进入稳定命名哈希，旧形态缓存不会被误复用。
SEGMENT_CONTAINER = "mov"
HW_H264_ORDER = ("h264_amf", "h264_qsv", "h264_nvenc")
FALLBACK_FPS = Fraction(25, 1)

# 进程内已禁用硬件编码器集合（竞品确证语义：一次失败即拉黑，本进程内不再尝试）
_DISABLED_HW_ENCODERS: set[str] = set()


def reset_disabled_hardware_encoders() -> None:
    """清空硬件编码器黑名单（竞品同名钩子，供测试复位）。"""
    _DISABLED_HW_ENCODERS.clear()


def disabled_hardware_encoders() -> frozenset[str]:
    return frozenset(_DISABLED_HW_ENCODERS)


# --------------------------------------------------------------------------- #
# 纯函数：口径计算（全部可单测，不碰子进程）
# --------------------------------------------------------------------------- #

def fps_fraction(fps: float | str | Fraction | None) -> Fraction:
    """ffprobe 帧率（``"24000/1001"`` / float / None）→ 有理帧率。

    None/非法/<=0 → 25/1。float 经 ``limit_denominator`` 还原常见分数
    （23.976→24000/1001），避免把浮点帧率写进命令造成累计时长漂移。
    """
    if isinstance(fps, Fraction):
        return fps if fps > 0 else FALLBACK_FPS
    if fps is None:
        return FALLBACK_FPS
    if isinstance(fps, str):
        text = fps.strip()
        if "/" in text:
            try:
                fr = Fraction(text)
            except (ValueError, ZeroDivisionError):
                return FALLBACK_FPS
            return fr if fr > 0 else FALLBACK_FPS
        try:
            fps = float(text)
        except ValueError:
            return FALLBACK_FPS
    try:
        value = float(fps)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return FALLBACK_FPS
    if value <= 0:
        return FALLBACK_FPS
    return Fraction(value).limit_denominator(100_000)


def fps_text(fr: Fraction) -> str:
    """有理帧率 → FFmpeg 分数字符串（竞品 docstring「将有理帧率转换为 FFmpeg 接受的
    分数字符串」）。分母为 1 时给整数，否则保留分数。"""
    return str(fr.numerator) if fr.denominator == 1 else f"{fr.numerator}/{fr.denominator}"


def expected_frames(duration_s: float, fr: Fraction) -> int:
    """时间跨度 → CFR 下应有帧数。

    取「四舍五入（半数向上）」而非 Python 的银行家舍入：``round(0.5)==0`` 会把
    0.02s@25fps 这类极短段判成 0 帧并整段丢弃，与竞品过滤器的 ``round=near``
    不一致，故显式用 ``floor(x + 0.5)``。
    """
    if duration_s <= 0 or fr <= 0:
        return 0
    scaled = Fraction(str(round(float(duration_s), 6))) * fr
    return max(0, (scaled.numerator * 2 + scaled.denominator) // (scaled.denominator * 2))


def frames_to_seconds(frames: int, fr: Fraction) -> float:
    """帧数 → 秒（精确有理换算；成片时长口径与帧数一致）。"""
    if frames <= 0 or fr <= 0:
        return 0.0
    return float(Fraction(frames, 1) / fr)


def even_dimension(value: int, *, minimum: int = 16) -> int:
    """向下取偶（x264/硬件编码器要求偶数尺寸），并保证下界。"""
    return max(minimum, int(value) - int(value) % 2)


def cfr_video_filter(*, width: int, height: int, pix_fmt: str, fps: Fraction) -> str:
    """单片段「恒定帧率 + 尺寸/SAR/色彩统一」过滤器链（竞品 ``_cfr_video_filter`` 同位）。

    顺序固定：``fps``（CFR 重采样，帧数可预测）→ ``scale``（统一偶数尺寸）→
    ``setsar``（SAR 一致，否则拼接后画面拉伸）→ ``format``（位深/色彩统一）。
    """
    return (f"fps=fps={fps_text(fps)},scale={width}:{height}:flags=bicubic,"
            f"setsar=1,format={pix_fmt}")


def h264_encoder_args(encoder: str, *, pix_fmt: str, crf: int, preset: str) -> list[str]:
    """视频编码参数段。软件档用 CRF；硬件档各家 CRF/RC 语义不一，统一给目标码率
    （工程先验，非竞品确证）。"""
    if encoder == SOFTWARE_H264:
        return ["-c:v", encoder, "-preset", preset, "-crf", str(crf),
                "-pix_fmt", pix_fmt]
    return ["-c:v", encoder, "-pix_fmt", pix_fmt, "-b:v", "8M"]


def audio_encoder_args(*, sample_rate: int) -> list[str]:
    """段内音频编码参数：统一 **PCM 24bit / 采样率 / 双声道**（中段容器是 MOV）。

    为什么不用 AAC 中段（本机实测发现的真缺陷，非竞品差异）：AAC 每帧 1024 样本
    （48k 下 = 21.3ms），编码器会把段尾补齐到整帧 ⇒ 中段音频时长恒比视频长一个 AAC
    帧；concat demuxer 按「最长流」推进下一个文件的时间偏移，于是成片每个接缝处
    视频出现 ``0.0417→0.0630s`` 的拉伸缝（60 段实测 59 处，NLE/播放器都会看到抖动）。
    PCM 是采样精确的，段音频时长 = 段视长，接缝帧距完全规则（实测 144 帧全部 0.0417s）。
    最终合并时音频统一转 AAC（见 :func:`concat_copy_command`），只付一次编码代价。
    """
    return ["-c:a", "pcm_s24le", "-ar", str(sample_rate), "-ac", "2"]


def silent_source_args(*, sample_rate: int) -> list[str]:
    """黑场腿不落地，但**静音腿要落地**：源片无音轨时补等长静音（输入 1）。"""
    return ["-f", "lavfi", "-i",
            f"anullsrc=channel_layout=stereo:sample_rate={sample_rate}"]


def segment_command(*, ffmpeg: str, source: Path, out_path: Path, start_s: float,
                    frames: int, fps: Fraction, width: int, height: int, pix_fmt: str,
                    encoder: str, crf: int, preset: str, has_audio: bool,
                    sample_rate: int) -> list[str]:
    """构造单片段渲染命令（fast input seek + CFR 重编码 + 帧数硬上限）。

    - ``-ss`` 前置于 ``-i``（既有产品冻结口径：fast seek，长源不从 0 解码）。
    - ``-frames:v`` 是帧数的**硬保证**：seek 的亚帧偏差只会少给不会多给；配合
      ``-fps_mode cfr`` 让逐段帧数可校验。
    - 无音轨源：追加 ``anullsrc`` 虚拟输入（索引 1），由全局 ``-t`` 裁到段长。
      **不用 ``-shortest``**：本机实测它会反向截掉视频帧（144→141）并把接缝间隙
      放大到 0.103s。中段音频用 PCM（见 :func:`audio_encoder_args`），容器随之 MOV。
    """
    duration_s = frames_to_seconds(frames, fps)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
           "-fflags", "+genpts",
           "-ss", f"{start_s:.6f}", "-i", str(source)]
    if not has_audio:
        cmd += silent_source_args(sample_rate=sample_rate)
    cmd += ["-t", f"{duration_s:.6f}",
            "-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0",
            "-vf", cfr_video_filter(width=width, height=height, pix_fmt=pix_fmt, fps=fps),
            "-r", fps_text(fps), "-fps_mode", "cfr", "-frames:v", str(frames)]
    cmd += h264_encoder_args(encoder, pix_fmt=pix_fmt, crf=crf, preset=preset)
    cmd += audio_encoder_args(sample_rate=sample_rate)
    cmd += ["-avoid_negative_ts", "make_zero", "-map_metadata", "-1",
            "-progress", "pipe:1", str(out_path)]
    return cmd


def concat_copy_command(*, ffmpeg: str, list_path: Path, out_path: Path) -> list[str]:
    """最终合并（视频流复制 + 音频统一转 AAC，竞品 ``_final_concat_copy_command`` 同位）。

    中段音频是 PCM（见 :func:`audio_encoder_args` 的实测理由），进 MP4 必须转 AAC，
    所以这里只复制视频、重编一次音频——比整片重编码便宜得多，仍是"copy 合并"档。
    """
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-fflags", "+genpts", "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-map", "0:v:0", "-map", "0:a:0", "-c:v", "copy",
            "-c:a", "aac", "-b:a", "160k", "-ar", str(DEFAULT_SAMPLE_RATE), "-ac", "2",
            "-avoid_negative_ts", "make_zero", "-movflags", "+faststart",
            "-sn", "-dn", "-map_metadata", "-1", "-progress", "pipe:1", str(out_path)]


def concat_reencode_command(*, ffmpeg: str, list_path: Path, out_path: Path,
                            fps: Fraction, pix_fmt: str, encoder: str, crf: int,
                            preset: str, sample_rate: int, width: int,
                            height: int) -> list[str]:
    """流复制失败后的重编码合并（竞品 ``_final_concat_reencode_command`` 同位）。"""
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "concat", "-safe", "0", "-i", str(list_path),
            "-map", "0:v:0", "-map", "0:a:0",
            "-vf", cfr_video_filter(width=width, height=height, pix_fmt=pix_fmt, fps=fps),
            "-r", fps_text(fps), "-fps_mode", "cfr",
            *h264_encoder_args(encoder, pix_fmt=pix_fmt, crf=crf, preset=preset),
            *audio_encoder_args(sample_rate=sample_rate),
            "-avoid_negative_ts", "make_zero", "-movflags", "+faststart",
            "-map_metadata", "-1", "-progress", "pipe:1", str(out_path)]


def swap_video_encoder(cmd: list[str], encoder: str, *, pix_fmt: str, crf: int,
                       preset: str) -> list[str]:
    """把命令里的视频编码参数整段换成另一编码器（竞品「将渲染命令替换为既有软件
    编码器命令」）。不含 ``-c:v`` 或流复制命令原样返回。"""
    if "-c:v" not in cmd:
        return list(cmd)
    i = cmd.index("-c:v")
    if i + 1 < len(cmd) and cmd[i + 1] == "copy":
        return list(cmd)
    j = i + 2
    owned = {"-preset", "-crf", "-pix_fmt", "-b:v"}
    while j + 1 < len(cmd) and cmd[j] in owned:
        j += 2
    rebuilt = h264_encoder_args(encoder, pix_fmt=pix_fmt, crf=crf, preset=preset)
    return cmd[:i] + rebuilt + cmd[j:]


# --------------------------------------------------------------------------- #
# 帧数读取与校验
# --------------------------------------------------------------------------- #

def frame_count_args(ffprobe: str, path: Path, *, strict: bool) -> list[str]:
    """ffprobe 读帧数；``strict=True`` 走 ``-count_frames`` 逐帧严格计数。"""
    cmd = [ffprobe, "-v", "error", "-select_streams", "v:0"]
    if strict:
        cmd += ["-count_frames"]
        entries = "stream=nb_read_frames"
    else:
        entries = "stream=nb_frames"
    return cmd + ["-show_entries", entries, "-of", "default=nw=1:nk=1", str(path)]


def parse_frame_count(stdout: str | None) -> int | None:
    """ffprobe 单值输出 → int；空/``N/A``/非法/非正 → None（不可信，需严格回退）。"""
    text = (stdout or "").strip()
    if not text:
        return None
    head = text.splitlines()[0].strip()
    if not head or head.upper() == "N/A":
        return None
    try:
        value = int(float(head))
    except ValueError:
        return None
    return value if value > 0 else None


def verify_segment_frames(ffprobe: str, path: Path, expected: int, *,
                          run: Callable[[list[str]], str]) -> tuple[int, bool]:
    """逐段帧数校验：先快速读 ``nb_frames``，与预期一致即采纳；缺失/为 0/与预期不符
    （说明容器计数本身不可信）才付 ``-count_frames`` 的代价再判。

    返回 ``(实际帧数, 是否走了严格计数)``。``run`` 注入便于单测（生产 = subprocess）。
    """
    fast = parse_frame_count(run(frame_count_args(ffprobe, path, strict=False)))
    if fast == expected:
        return expected, False
    strict = parse_frame_count(run(frame_count_args(ffprobe, path, strict=True)))
    if strict is not None:
        return strict, True
    return (fast or 0), True


# --------------------------------------------------------------------------- #
# 探测辅助
# --------------------------------------------------------------------------- #

def _default_run(args: list[str], *, timeout: float = 180.0) -> str:
    """前台执行短命令（ffprobe 类）；失败/超时返回空串，由上层判「不可信」。"""
    try:
        proc = subprocess.run(args, capture_output=True, timeout=timeout, check=False,
                              creationflags=CREATE_NO_WINDOW)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.decode("utf-8", errors="replace")


def probe_streams_args(ffprobe: str, path: Path) -> list[str]:
    return [ffprobe, "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", str(path)]


def probe_streams(path: Path, ffprobe: str, *,
                  run: Callable[[list[str]], str] = _default_run) -> dict:
    text = run(probe_streams_args(ffprobe, Path(path)))
    if not text.strip():
        raise MediaError(f"无法读取原片信息（ffprobe 无输出）: {Path(path).name}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise MediaError(f"原片信息解析失败: {Path(path).name}") from exc


def first_video_stream(probe: dict) -> dict | None:
    for s in probe.get("streams") or []:
        if s.get("codec_type") == "video":
            return s
    return None


def has_audio_stream(probe: dict) -> bool:
    for s in probe.get("streams") or []:
        if s.get("codec_type") == "audio" and s.get("codec_name") not in (None, "none"):
            return True
    return False


def render_pix_fmt(vstream: dict) -> str:
    """成片统一 8bit ``yuv420p``（H.264 与各家硬件 h264 普遍不接受 10bit 输入）。

    HDR/10bit 源在此**降为 SDR 8bit**：成片是预览/交付物，NLE 工程仍指向原片，
    源数据不损失。调用方用 :func:`source_merge.is_hdr` 等留痕 ``hdr_downgraded``。
    """
    del vstream
    return "yuv420p"


def parse_video_encoders(encoders_output: str) -> list[str]:
    """``ffmpeg -encoders`` 文本 → 全部视频编码器名（顺序保留）。"""
    found: list[str] = []
    for line in encoders_output.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V.") and parts[1] not in found:
            found.append(parts[1])
    return found


def h264_chain(encoders_found: Sequence[str], *, prefer_hw: bool = True,
               disabled: frozenset[str] | None = None) -> list[str]:
    """在位 H.264 编码器尝试链：硬件（黑名单外，按机型优先级）→ 软件 libx264。"""
    off = disabled if disabled is not None else frozenset(_DISABLED_HW_ENCODERS)
    present = set(encoders_found)
    chain: list[str] = []
    if prefer_hw:
        chain += [name for name in HW_H264_ORDER if name in present and name not in off]
    if SOFTWARE_H264 in present:
        chain.append(SOFTWARE_H264)
    return chain


def _probe_frames(ffprobe: str, path: Path, *, strict: bool = False,
                  run: Callable[[list[str]], str] = _default_run) -> int | None:
    return parse_frame_count(run(frame_count_args(ffprobe, path, strict=strict)))


# --------------------------------------------------------------------------- #
# 产物稳定命名（同续27 合并缓存思路：同输入同参数 → 复用，不重复渲染）
# --------------------------------------------------------------------------- #

def _safe_stem(path: Path) -> str:
    keep = "".join(c if c.isalnum() or c in "-_" else "_" for c in path.stem)
    return keep[:32].strip("_") or "source"


def render_output_name(source: Path, clips: Sequence[tuple[float, float]],
                       params: Sequence[object], ext: str = "mp4") -> str:
    """稳定命名 = 源片名+大小+片段清单+渲染参数 的 12 位 MD5（竞品确证思路，
    与 :func:`source_merge.merge_output_name` 同族）。"""
    try:
        size = int(source.stat().st_size)
    except OSError:
        size = 0
    payload = "|".join([
        source.name, str(size),
        ";".join(f"{round(float(a), 3)}-{round(float(b), 3)}" for a, b in clips),
        ";".join(str(p) for p in params),
    ])
    digest = hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]
    return f"movie_{_safe_stem(source)}_{digest}.{ext.lstrip('.')}"


def _try_unlink(path: Path) -> None:
    """尽力删除（竞品「尽力删除已有输出或临时文件」）。"""
    try:
        path.unlink()
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# 执行层
# --------------------------------------------------------------------------- #

@dataclass
class RenderJob:
    index: int
    start_s: float
    end_s: float
    frames: int
    out_path: Path


@dataclass
class RenderPlan:
    source: Path
    output: Path
    fps: Fraction
    width: int
    height: int
    pix_fmt: str
    encoder: str
    has_audio: bool
    total_frames: int
    total_seconds: float
    clip_count: int
    jobs: list[RenderJob]
    segment_dir: Path
    concat_list: Path
    reused: bool = False
    reason: str = ""
    hdr_downgraded: bool = False


@dataclass
class SegmentResult:
    index: int
    path: Path
    frames: int
    encoder: str


# 进度契约（与 SourceVideoMerger 一致）：frac∈[0,1]；``None`` = 无进展心跳
ProgressFn = Callable[[float | None, str], None]
# 段内进度回调：frac=None 表示心跳
SegmentCb = Callable[[RenderJob, float | None], None]


class TimelineMovieRenderer:
    """把「原片 + 定位片段清单（秒）」渲染成单个可播放成片。

    ``progress(frac, message)`` 的 ``frac=None`` 表示心跳；阶段区间映射由调用方
    （service / api worker）决定。``cancel()`` 返回 True → 终止子进程并抛
    :class:`MediaError`。与 :class:`media.ffmpeg.source_merge.SourceVideoMerger`
    同契约，service 层一套监护代码。
    """

    def __init__(self, ffmpeg: str | Path, ffprobe: str | Path, out_dir: str | Path, *,
                 crf: int = 18, preset: str = "medium", prefer_hw: bool = True,
                 workers: int = 2, stall_timeout_s: float = DEFAULT_STALL_TIMEOUT_S,
                 timeout_s: float = DEFAULT_TIMEOUT_S,
                 sample_rate: int = DEFAULT_SAMPLE_RATE,
                 log: Callable[..., None] | None = None,
                 run: Callable[[list[str]], str] | None = None,
                 popen: Callable[[list[str]], object] | None = None):
        self.ffmpeg = str(ffmpeg)
        self.ffprobe = str(ffprobe)
        self.out_dir = Path(out_dir)
        self.crf = int(crf)
        self.preset = str(preset)
        self.prefer_hw = bool(prefer_hw)
        self.workers = int(workers)
        self.stall_timeout_s = float(stall_timeout_s)
        self.timeout_s = float(timeout_s)
        self.sample_rate = int(sample_rate)
        self._log = log or (lambda *a, **k: None)
        self._run = run or _default_run
        # 子进程启动器可注入：单测用它伪造进度流/停滞/取消，生产 = subprocess.Popen
        self._popen = popen or subprocess.Popen
        self._encoders: list[str] | None = None

    # ---------------------------------------------------------------- 探测
    def probe(self, path: str | Path) -> dict:
        return probe_streams(Path(path), self.ffprobe, run=self._run)

    def available_h264_encoders(self) -> list[str]:
        if self._encoders is None:
            try:
                proc = subprocess.run(
                    [self.ffmpeg, "-hide_banner", "-loglevel", "error", "-encoders"],
                    capture_output=True, timeout=30, check=False,
                    creationflags=CREATE_NO_WINDOW)
                text = proc.stdout.decode("utf-8", errors="replace")
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise MediaError(f"无法探测 ffmpeg 编码器列表: {exc}") from exc
            self._encoders = h264_chain(parse_video_encoders(text),
                                       prefer_hw=self.prefer_hw)
        return self._encoders

    # ---------------------------------------------------------------- 计划
    def plan(self, clips: Sequence[tuple[float, float]], source: str | Path, *,
             fps: float | str | Fraction | None = None,
             has_audio: bool | None = None) -> RenderPlan:
        """探测源片 → 帧率/尺寸/编码链/稳定命名产物/逐段预期帧数。"""
        src = Path(source).resolve()
        if not src.exists():
            raise MediaError(f"原片文件不存在: {src.name}")
        pairs = [(float(a), float(b)) for a, b in clips]
        pairs = [(a, b) for a, b in pairs if b > a]
        if not pairs:
            raise MediaError("没有可渲染的片段（结果批为空或全部未定位）")

        probe = self.probe(src)
        v = first_video_stream(probe)
        if v is None:
            raise MediaError(f"原片没有视频流，无法渲染成片: {src.name}")
        fr = fps_fraction(fps if fps is not None else v.get("avg_frame_rate"))
        width, height = even_dimension(int(v.get("width") or 0)), \
            even_dimension(int(v.get("height") or 0))
        if int(v.get("width") or 0) <= 0 or int(v.get("height") or 0) <= 0:
            raise MediaError("原片分辨率探测失败，无法渲染成片")
        audio = has_audio_stream(probe) if has_audio is None else bool(has_audio)
        chain = self.available_h264_encoders()
        if not chain:
            raise MediaError("ffmpeg 没有可用的 H.264 编码器，无法渲染成片")
        pix_fmt = render_pix_fmt(v)
        frames_per_clip = [expected_frames(b - a, fr) for a, b in pairs]
        total = sum(frames_per_clip)
        if total <= 0:
            raise MediaError("所有片段时长为零或负，无法渲染成片")

        out_name = render_output_name(src, pairs, [
            fps_text(fr), f"{width}x{height}", pix_fmt, chain[0], self.crf,
            self.preset, int(audio), self.sample_rate, SEGMENT_CONTAINER])
        out_path = self.out_dir / out_name
        seg_dir = self.out_dir / "segments"
        common = dict(source=src, output=out_path, fps=fr, width=width, height=height,
                      pix_fmt=pix_fmt, encoder=chain[0], has_audio=audio,
                      total_frames=total, total_seconds=frames_to_seconds(total, fr),
                      clip_count=len(pairs),
                      segment_dir=seg_dir,
                      concat_list=out_path.parent / f"{out_path.stem}.concat.txt",
                      hdr_downgraded=bool(is_hdr(v) or is_high_bit_depth(v)))
        if out_path.exists() and out_path.stat().st_size > 0:
            return RenderPlan(jobs=[], reused=True,
                              reason="命中既有成片（同原片、同片段清单、同参数）", **common)
        jobs = [RenderJob(index=i, start_s=a, end_s=b, frames=f,
                          out_path=seg_dir / f"{out_path.stem}_{i:04d}.{SEGMENT_CONTAINER}")
                for i, ((a, b), f) in enumerate(zip(pairs, frames_per_clip)) if f > 0]
        return RenderPlan(jobs=jobs, **common)

    def segment_args(self, plan: RenderPlan, job: RenderJob,
                     encoder: str | None = None) -> list[str]:
        """单片段渲染命令（纯函数封装，便于逐段命令级单测）。"""
        return segment_command(
            ffmpeg=self.ffmpeg, source=plan.source, out_path=job.out_path,
            start_s=job.start_s, frames=job.frames, fps=plan.fps,
            width=plan.width, height=plan.height, pix_fmt=plan.pix_fmt,
            encoder=encoder or plan.encoder, crf=self.crf, preset=self.preset,
            has_audio=plan.has_audio, sample_rate=self.sample_rate)

    # ---------------------------------------------------------------- 渲染
    def render(self, clips: Sequence[tuple[float, float]], source: str | Path, *,
               fps: float | str | Fraction | None = None,
               progress: ProgressFn | None = None,
               cancel: Callable[[], bool] | None = None) -> dict:
        """渲染成片。返回 ``{movie_path, mode, reused, segments, fps, duration_s,
        total_frames, actual_encoder, hdr_downgraded}``。

        ``mode``：``reused``（命中缓存）/ ``copy``（流复制合并）/ ``transcode``
        （重编码合并）。
        """
        plan = self.plan(clips, source, fps=fps)
        if plan.reused:
            if progress is not None:
                progress(1.0, "成片已存在，直接复用")
            return self._result(plan, mode="reused", reused=True,
                                segments=plan.clip_count, encoder=plan.encoder)

        plan.output.parent.mkdir(parents=True, exist_ok=True)
        plan.segment_dir.mkdir(parents=True, exist_ok=True)
        if plan.hdr_downgraded:
            self._log("render: HDR/高位深源降为 yuv420p SDR（仅成片，工程仍指原片）")

        done = {"frames": 0}
        lock = threading.Lock()

        def _emit(frac: float | None, message: str) -> None:
            if progress is not None:
                progress(frac, message)

        def _seg_cb(job: RenderJob, inner: float | None) -> None:
            if inner is None:
                _emit(None, f"片段 {job.index + 1}/{len(plan.jobs)} 渲染中，请稍候…")
                return
            with lock:
                base = done["frames"]
            frac = min(0.95, (base + inner * job.frames) / max(1, plan.total_frames))
            _emit(frac, f"片段 {job.index + 1}/{len(plan.jobs)} 渲染 {int(frac * 100)}%")

        results = self._run_jobs(plan, seg_cb=_seg_cb, cancel=cancel)
        with lock:
            done["frames"] = sum(r.frames for r in results)

        for job, res in zip(plan.jobs, results):
            if res.frames != job.frames:
                raise MediaError(f"渲染失败: 第 {job.index + 1} 段帧数错误: "
                                 f"预期 {job.frames}，实际 {res.frames}")

        _emit(0.96, "合并视频")
        mode, encoder = self._concat(plan, results, emit=_emit, cancel=cancel)
        actual = _probe_frames(self.ffprobe, plan.output, run=self._run)
        if actual is None:
            actual = _probe_frames(self.ffprobe, plan.output, strict=True, run=self._run)
        tol = max(2, round(plan.total_frames * 0.005))
        if actual is None or abs(actual - plan.total_frames) > tol:
            raise MediaError(f"输出帧数错误: 预期 {plan.total_frames}，"
                             f"实际 {actual if actual is not None else '未知'}")
        _emit(1.0, "最终视频生成成功")
        for r in results:
            _try_unlink(r.path)
        return self._result(plan, mode=mode, reused=False, segments=len(results),
                            encoder=encoder)

    @staticmethod
    def _result(plan: RenderPlan, *, mode: str, reused: bool, segments: int,
                encoder: str) -> dict:
        return {"movie_path": plan.output, "mode": mode, "reused": reused,
                "segments": segments, "fps": fps_text(plan.fps),
                "duration_s": plan.total_seconds, "total_frames": plan.total_frames,
                "actual_encoder": encoder, "hdr_downgraded": plan.hdr_downgraded}

    # ---------------------------------------------------------------- 并发
    def _run_jobs(self, plan: RenderPlan, *, seg_cb: SegmentCb,
                  cancel) -> list[SegmentResult]:
        """并发跑片段任务并**按索引保序**；并发框架异常回退串行（竞品确证语义）。"""
        workers = max(1, int(self.workers))
        if workers == 1 or len(plan.jobs) == 1:
            return [self._run_one(plan, job, seg_cb, cancel) for job in plan.jobs]
        try:
            from concurrent.futures import ThreadPoolExecutor
            slots: list[SegmentResult | None] = [None] * len(plan.jobs)
            with ThreadPoolExecutor(max_workers=workers,
                                    thread_name_prefix="svl-render") as pool:
                futs = {pool.submit(self._run_one, plan, job, seg_cb, cancel): i
                        for i, job in enumerate(plan.jobs)}
                for fut, i in futs.items():
                    slots[i] = fut.result()
            return [s for s in slots if s is not None]
        except MediaError:
            raise
        except Exception as exc:  # noqa: BLE001 — 并发层异常 → 串行兜底
            self._log("并发渲染失败，已回退串行: %s", exc)
            return [self._run_one(plan, job, seg_cb, cancel) for job in plan.jobs]

    def _run_one(self, plan: RenderPlan, job: RenderJob, seg_cb: SegmentCb,
                 cancel) -> SegmentResult:
        job.out_path.parent.mkdir(parents=True, exist_ok=True)
        _try_unlink(job.out_path)
        cmd = self.segment_args(plan, job)
        rc, stderr, encoder = self._run_monitored(
            cmd, total_seconds=frames_to_seconds(job.frames, plan.fps), plan=plan,
            on_frac=lambda f: seg_cb(job, f), cancel=cancel,
            label=f"片段 {job.index + 1}")
        if rc != 0:
            raise MediaError(f"渲染失败: 第 {job.index + 1} 段（编码器 {encoder}）："
                             f"{error_summary(stderr) or f'ffmpeg rc={rc}'}")
        frames, _strict = verify_segment_frames(
            self.ffprobe, job.out_path, job.frames, run=self._run)
        if frames <= 0:
            raise MediaError(f"渲染失败: 第 {job.index + 1} 段产物无法读取帧数")
        return SegmentResult(index=job.index, path=job.out_path, frames=frames,
                             encoder=encoder)

    # ---------------------------------------------------------------- 合并
    def _concat(self, plan: RenderPlan, results: list[SegmentResult], *,
                emit: ProgressFn, cancel) -> tuple[str, str]:
        """优先流复制（各段口径已统一）；结构不一致或失败 → 重编码合并。"""
        plan.concat_list.write_text(concat_list_text([r.path for r in results]),
                                    encoding="utf-8")
        encoders = {r.encoder for r in results}
        try:
            if len(encoders) == 1:
                rc, err, _ = self._run_monitored(
                    concat_copy_command(ffmpeg=self.ffmpeg, list_path=plan.concat_list,
                                        out_path=plan.output),
                    total_seconds=plan.total_seconds, plan=plan,
                    on_frac=lambda f: emit(min(0.995, 0.96 + 0.035 * f),
                                           "合并视频（流复制）"),
                    cancel=cancel, label="合并视频（流复制）")
                if rc == 0 and plan.output.exists():
                    return "copy", plan.encoder
                self._log("concat 流复制失败（rc=%s）: %s", rc, error_summary(err))
                _try_unlink(plan.output)
            rc, err, encoder = self._run_monitored(
                concat_reencode_command(ffmpeg=self.ffmpeg, list_path=plan.concat_list,
                                        out_path=plan.output, fps=plan.fps,
                                        pix_fmt=plan.pix_fmt, encoder=plan.encoder,
                                        crf=self.crf, preset=self.preset,
                                        sample_rate=self.sample_rate,
                                        width=plan.width, height=plan.height),
                total_seconds=plan.total_seconds, plan=plan,
                on_frac=lambda f: emit(min(0.995, 0.96 + 0.035 * f), "合并视频（重编码）"),
                cancel=cancel, label="合并视频（重编码）")
            if rc != 0 or not plan.output.exists():
                raise MediaError(f"合并失败；工程文件已生成但成片未完成："
                                 f"{error_summary(err) or f'ffmpeg rc={rc}'}")
            return "transcode", encoder
        finally:
            _try_unlink(plan.concat_list)

    # ------------------------------------------------ 监护执行 + 编码器回退
    def _run_monitored(self, args: list[str], *, total_seconds: float, plan: RenderPlan,
                       on_frac: Callable[[float | None], None] | None,
                       cancel: Callable[[], bool] | None,
                       label: str) -> tuple[int, str, str]:
        """跑一条 ffmpeg，返回 ``(rc, stderr 摘要, 实际使用的编码器)``。

        硬件档失败 → 拉黑并沿链重试（末位软件 libx264）；停滞超 ``stall_timeout_s``
        或超总超时 → 终止并报错；``cancel()`` 命中 → 抛取消。
        """
        for encoder in self._attempt_chain(args, plan):
            cmd = swap_video_encoder(args, encoder, pix_fmt=plan.pix_fmt,
                                     crf=self.crf, preset=self.preset)
            rc, err = self._spawn(cmd, total_seconds=total_seconds, on_frac=on_frac,
                                  cancel=cancel, label=label)
            if rc == 0:
                return 0, "", encoder
            if encoder in HW_H264_ORDER:
                _DISABLED_HW_ENCODERS.add(encoder)
                self._log("硬件编码器 %s 失败，回退下一档: %s",
                          encoder, error_summary(err, max_length=200))
                continue
            return rc, err, encoder
        return 1, "", SOFTWARE_H264

    def _attempt_chain(self, args: list[str], plan: RenderPlan) -> list[str]:
        """本命令的编码器重试链（流复制/无 ``-c:v`` 命令只跑一次）。

        顺序 = 当前档 → 其余在位硬件档（黑名单外，实时重取）→ 软件 libx264。
        硬件档失败会写进黑名单，所以重试链必须在每次调用时重新过滤。
        """
        if "-c:v" not in args:
            return [plan.encoder]
        current = args[args.index("-c:v") + 1]
        if current == "copy":
            return [plan.encoder]
        fresh = [e for e in self.available_h264_encoders()
                 if e not in _DISABLED_HW_ENCODERS]
        chain = [current, *[e for e in fresh if e != current]]
        if SOFTWARE_H264 not in chain:
            chain.append(SOFTWARE_H264)
        ordered = [e for e in dict.fromkeys(chain)
                   if e == SOFTWARE_H264 or e not in _DISABLED_HW_ENCODERS]
        return ordered or [SOFTWARE_H264]

    def _spawn(self, args: list[str], *, total_seconds: float,
               on_frac: Callable[[float | None], None] | None,
               cancel: Callable[[], bool] | None,
               label: str) -> tuple[int, str]:
        """子进程 + ``-progress`` 读取线程 + 停滞看门狗 + 取消/超时三段终止。"""
        err_fd, err_path = tempfile.mkstemp(prefix="svl_render_err_", suffix=".log")
        err_file = os.fdopen(err_fd, "w+b")
        try:
            proc = self._popen(args, stdout=subprocess.PIPE, stderr=err_file,
                               stdin=subprocess.DEVNULL,
                               creationflags=CREATE_NO_WINDOW)
        except OSError as exc:
            err_file.close()
            _try_unlink(Path(err_path))
            raise MediaError(f"无法启动 {label}: {exc}") from exc

        lines: queue.Queue = queue.Queue()

        def _reader() -> None:
            try:
                assert proc.stdout is not None
                for raw in proc.stdout:
                    lines.put(raw.decode("utf-8", errors="replace"))
            except (OSError, ValueError):
                pass
            finally:
                lines.put(None)

        threading.Thread(target=_reader, daemon=True, name="svl-render-progress").start()

        def _stop() -> None:
            """terminate → wait → kill（竞品「按终止、等待和强制结束顺序停止受监控进程」）。"""
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:  # noqa: BLE001 — 尽力终止，清理异常不外传
                try:
                    proc.kill()
                    proc.wait(timeout=2)
                except Exception:  # noqa: BLE001
                    pass

        started = time.monotonic()
        last_advance = started
        last_heartbeat = started
        eof = cancelled = stalled = timed_out = False
        while True:
            try:
                line = lines.get(timeout=1.0)
            except queue.Empty:
                line = ""
            if line is None:
                eof = True
            elif line.strip():
                done_s = parse_progress_seconds(line)
                if done_s is not None and total_seconds > 0:
                    last_advance = time.monotonic()
                    if on_frac is not None:
                        on_frac(min(1.0, max(0.0, done_s / total_seconds)))
            now = time.monotonic()
            if cancel is not None and cancel():
                cancelled = True
                _stop()
                break
            if now - started > self.timeout_s:
                timed_out = True
                _stop()
                break
            if now - last_advance > self.stall_timeout_s:
                stalled = True
                _stop()
                break
            if eof and proc.poll() is not None:
                break
            if now - last_heartbeat >= 5.0:
                last_heartbeat = now
                if on_frac is not None:
                    on_frac(None)
        if proc.poll() is None:
            _stop()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        rc = proc.returncode
        # 关闭管道（注入的假进程可能没有 close）
        closer = getattr(getattr(proc, "stdout", None), "close", None)
        if callable(closer):
            try:
                closer()
            except OSError:
                pass
        try:
            err_file.flush()
            err_file.seek(0)
            err_text = err_file.read().decode("utf-8", errors="replace")
        except (OSError, ValueError):
            err_text = ""
        finally:
            err_file.close()
            _try_unlink(Path(err_path))
        if cancelled:
            raise MediaError(f"{label} 已取消")
        if stalled:
            raise MediaError("视频生成长时间没有进展，处理已停止。请检查磁盘和显卡状态后重试。")
        if timed_out:
            raise MediaError(f"{label} 超时（>{self.timeout_s:.0f}s），已终止渲染进程")
        return rc, error_summary(_error_tail(err_text, n=2000))
