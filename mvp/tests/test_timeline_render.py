"""Unit tests for mvp.media.ffmpeg.timeline_render（成片渲染, 2026-09-29 续30 竞品 video_renderer 移植）。

分三层：
1. **纯函数**（帧率/帧数/过滤器链/命令构造/编码器链/稳定命名）——零子进程；
2. **监护与回退**（停滞看门狗、取消、硬件编码器拉黑回退软件、编码器重试链）——
   注入假 ``popen``/假 ``run``，不依赖真 ffmpeg；
3. **真 ffmpeg E2E**（tools/ffmpeg.exe + lavfi 合成源）——逐段帧数校验、流复制合并、
   无音轨补静音、稳定命名复用。**固定 ``prefer_hw=False``** 保证 Hermetic
   （硬件编码器在无显卡驱动环境不可依赖，同 test_source_merge 纪律）。

Run with the venv python:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_timeline_render -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from media.ffmpeg import MediaError
from media.ffmpeg.timeline_render import (
    Keyframe,
    RenderJob,
    RenderPlan,
    SegmentResult,
    TimelineMovieRenderer,
    audio_encoder_args,
    cfr_video_filter,
    concat_copy_command,
    concat_reencode_command,
    copy_middle_command,
    disabled_hardware_encoders,
    even_dimension,
    expected_frames,
    fps_fraction,
    fps_text,
    frames_to_seconds,
    h264_chain,
    merge_stage_frac,
    parse_frame_count,
    parse_keyframes,
    parse_video_encoders,
    render_output_name,
    reset_disabled_hardware_encoders,
    segment_command,
    silent_source_args,
    smart_clip_parts,
    smart_render_block_reason,
    swap_video_encoder,
    verify_segment_frames,
)

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")

_ENC_TABLE = """
Frame:
  V..... libx264              libx264 H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10 (codec h264)
  V..... h264_amf             AMD AMF H.264 Encoder (codec h264)
  V..... h264_qsv             H.264 / AVC / MPEG-4 AVC (codec h264)
  A..... aac                  AAC (Advanced Audio Codec)
""".strip()


def _probe(v=None, a=None) -> dict:
    streams = []
    if v:
        streams.append(v)
    if a:
        streams.append(a)
    return {"streams": streams, "format": {"duration": "6.0"}}


def _vstream(**over) -> dict:
    base = {"codec_type": "video", "codec_name": "h264", "width": 320, "height": 240,
            "pix_fmt": "yuv420p", "avg_frame_rate": "25/1"}
    base.update(over)
    return base


class _FakeProc:
    """假子进程：按脚本给出 stdout 行、退出码与 poll 行为。"""

    def __init__(self, lines=(b"",), rc=0, alive_polls=0):
        self._lines = iter(list(lines))
        self.returncode = rc
        self._alive = alive_polls
        self.terminated = False
        self.killed = False
        self.stdout = self
        self.stderr = None

    def __iter__(self):
        return self

    def __next__(self):
        nxt = next(self._lines)
        if nxt is None:
            raise StopIteration
        return nxt

    def poll(self):
        if self._alive > 0:
            self._alive -= 1
            return None
        return self.returncode

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return self.returncode


# --------------------------------------------------------------------------- #
class PureMathTest(unittest.TestCase):
    def test_fps_fraction_parses_rational_and_float(self):
        self.assertEqual(fps_fraction("24000/1001"), Fraction(24000, 1001))
        # float 走**精确**换算（不猜 NTSC）：真实管线帧率一律来自 ffprobe 的分数串，
        # float 只用于配置兜底，精确值比"看起来像 24000/1001"更可预测。
        self.assertEqual(fps_fraction(23.976), Fraction(2997, 125))
        self.assertEqual(fps_fraction("30"), Fraction(30, 1))

    def test_fps_fraction_bad_input_falls_back_to_25(self):
        for bad in (None, "", "abc", "0/1", -5, 0.0):
            self.assertEqual(fps_fraction(bad), Fraction(25, 1))

    def test_fps_text_keeps_fraction_only_when_needed(self):
        self.assertEqual(fps_text(Fraction(25, 1)), "25")
        self.assertEqual(fps_text(Fraction(24000, 1001)), "24000/1001")

    def test_expected_frames_rounds_half_up_not_banker(self):
        fr = Fraction(25, 1)
        self.assertEqual(expected_frames(1.0, fr), 25)
        self.assertEqual(expected_frames(0.02, fr), 1)     # round=near，半数向上
        self.assertEqual(expected_frames(0.5, fr), 13)
        self.assertEqual(expected_frames(0.0, fr), 0)
        self.assertEqual(expected_frames(-1.0, fr), 0)

    def test_frames_seconds_roundtrip(self):
        fr = Fraction(24000, 1001)
        # 帧数是成片时间轴的唯一权威口径：秒→帧→秒 的回程差 < 1 帧即为正确舍入
        self.assertLess(abs(frames_to_seconds(expected_frames(4.0, fr), fr) - 4.0),
                        1.0 / float(fr))
        self.assertEqual(frames_to_seconds(0, fr), 0.0)

    def test_even_dimension(self):
        self.assertEqual(even_dimension(1080), 1080)
        self.assertEqual(even_dimension(1081), 1080)
        self.assertEqual(even_dimension(2), 16)


class CommandBuilderTest(unittest.TestCase):
    def setUp(self):
        self.fr = Fraction(25, 1)

    def test_cfr_filter_order(self):
        vf = cfr_video_filter(width=320, height=240, pix_fmt="yuv420p", fps=self.fr)
        self.assertEqual(vf, "fps=fps=25,scale=320:240:flags=bicubic,setsar=1,format=yuv420p")

    def test_segment_command_has_frame_cap_and_cfr(self):
        cmd = segment_command(ffmpeg="ffmpeg", source=Path("D:/v/om.mkv"),
                              out_path=Path("D:/out/seg_0000.mov"), start_s=12.5,
                              frames=50, fps=self.fr, width=320, height=240,
                              pix_fmt="yuv420p", encoder="libx264", crf=18,
                              preset="medium", has_audio=True, sample_rate=48000)
        # fast seek 前置于 -i（既有产品冻结口径）
        self.assertLess(cmd.index("-ss"), cmd.index("-i"))
        self.assertIn("-frames:v", cmd)
        self.assertEqual(cmd[cmd.index("-frames:v") + 1], "50")
        self.assertEqual(cmd[cmd.index("-fps_mode") + 1], "cfr")
        self.assertIn("-progress", cmd)
        self.assertEqual(cmd[-1], str(Path("D:/out/seg_0000.mov")))
        self.assertEqual(cmd[cmd.index("-map") + 1], "0:v:0")
        self.assertIn("0:a:0", cmd)
        # 中段音频必须是 PCM（AAC 段尾补齐会在成片接缝处留下视频拉伸缝，见模块头实测结论）
        self.assertEqual(cmd[cmd.index("-c:a") + 1], "pcm_s24le")
        # -shortest 是错误解法（实测反向截掉视频帧），任何路径都不允许出现
        self.assertNotIn("-shortest", cmd)
        # 段时长 = 帧数/帧率
        self.assertEqual(cmd[cmd.index("-t") + 1], f"{2.0:.6f}")

    def test_segment_command_without_audio_inserts_silence_input(self):
        cmd = segment_command(ffmpeg="ffmpeg", source=Path("D:/v/om.mkv"),
                              out_path=Path("D:/o.mov"), start_s=0.0, frames=25,
                              fps=self.fr, width=320, height=240, pix_fmt="yuv420p",
                              encoder="libx264", crf=18, preset="medium",
                              has_audio=False, sample_rate=48000)
        self.assertEqual(cmd.count("-i"), 2)
        lavfi = cmd.index("lavfi")
        self.assertEqual(cmd[lavfi - 1], "-f")
        self.assertEqual(cmd[lavfi + 2], "anullsrc=channel_layout=stereo:sample_rate=48000")
        self.assertGreater(lavfi, cmd.index("-i"))          # 静音是**第二个**输入
        self.assertEqual(cmd.count("1:a:0"), 1)             # 音频映射到输入 1
        self.assertNotIn("-shortest", cmd)                  # 长度由 -t 统一决定

    def test_copy_middle_has_exact_frame_cap_and_pcm_audio(self):
        cmd = copy_middle_command(ffmpeg="ffmpeg", source=Path("D:/v/om.mp4"),
                                  out_path=Path("D:/o.mov"), start_s=12.0, frames=50,
                                  fps=self.fr, has_audio=True, sample_rate=48000)
        self.assertEqual(cmd[cmd.index("-c:v") + 1], "copy")
        self.assertEqual(cmd[cmd.index("-frames:v") + 1], "50")
        self.assertEqual(cmd[cmd.index("-c:a") + 1], "pcm_s24le")
        self.assertNotIn("-vf", cmd)
        self.assertNotIn("-shortest", cmd)

    def test_audio_args_are_pcm_in_segments_aac_in_movie(self):
        args = audio_encoder_args(sample_rate=48000)
        self.assertEqual(args[:2], ["-c:a", "pcm_s24le"])
        self.assertEqual(args[args.index("-ar") + 1], "48000")
        self.assertEqual(args[args.index("-ac") + 1], "2")
        self.assertEqual(silent_source_args(sample_rate=44100),
                         ["-f", "lavfi", "-i",
                          "anullsrc=channel_layout=stereo:sample_rate=44100"])

    def test_concat_copy_and_reencode(self):
        copy = concat_copy_command(ffmpeg="ffmpeg", list_path=Path("D:/l.txt"),
                                   out_path=Path("D:/o.mp4"))
        self.assertEqual(copy[copy.index("-c:v") + 1], "copy")     # 视频流复制
        self.assertEqual(copy[copy.index("-c:a") + 1], "aac")      # 音频只在终片转一次
        self.assertIn("+faststart", copy)
        self.assertNotIn("-vf", copy)
        rec = concat_reencode_command(ffmpeg="ffmpeg", list_path=Path("D:/l.txt"),
                                      out_path=Path("D:/o.mp4"), fps=self.fr,
                                      pix_fmt="yuv420p", encoder="libx264", crf=18,
                                      preset="medium", sample_rate=48000,
                                      width=320, height=240)
        self.assertIn("-vf", rec)
        self.assertEqual(rec[rec.index("-fps_mode") + 1], "cfr")

    def test_swap_video_encoder_replaces_only_encoder_block(self):
        cmd = segment_command(ffmpeg="ffmpeg", source=Path("D:/v/om.mkv"),
                              out_path=Path("D:/o.mp4"), start_s=1.0, frames=25,
                              fps=self.fr, width=320, height=240, pix_fmt="yuv420p",
                              encoder="h264_amf", crf=18, preset="medium",
                              has_audio=True, sample_rate=48000)
        swapped = swap_video_encoder(cmd, "libx264", pix_fmt="yuv420p", crf=18,
                                     preset="medium")
        self.assertEqual(swapped[swapped.index("-c:v") + 1], "libx264")
        self.assertIn("-preset", swapped)
        self.assertNotIn("-b:v", swapped)
        self.assertEqual(swapped[-1], cmd[-1])          # 输出路径不变
        self.assertEqual(swapped.count("-pix_fmt"), 1)  # 不重复插入
        # 流复制命令不动
        copy = concat_copy_command(ffmpeg="ffmpeg", list_path=Path("D:/l.txt"),
                                   out_path=Path("D:/o.mp4"))
        self.assertEqual(swap_video_encoder(copy, "libx264", pix_fmt="yuv420p",
                                           crf=18, preset="medium"), copy)


class EncoderChainTest(unittest.TestCase):
    def test_parse_video_encoders(self):
        found = parse_video_encoders(_ENC_TABLE)
        self.assertIn("libx264", found)
        self.assertIn("h264_amf", found)
        self.assertNotIn("aac", found)      # 只收 V 段

    def test_chain_prefers_hw_then_software(self):
        chain = h264_chain(parse_video_encoders(_ENC_TABLE))
        self.assertEqual(chain[0], "h264_amf")
        self.assertEqual(chain[-1], "libx264")

    def test_chain_respects_disabled_and_prefer_hw(self):
        chain = h264_chain(parse_video_encoders(_ENC_TABLE), disabled=frozenset({"h264_amf"}))
        self.assertNotIn("h264_amf", chain)
        self.assertEqual(h264_chain(parse_video_encoders(_ENC_TABLE), prefer_hw=False),
                         ["libx264"])

    def test_attempt_chain_for_copy_command_runs_once(self):
        r = TimelineMovieRenderer("ffmpeg", "ffprobe", Path("."))
        plan = _tiny_plan()
        copy = concat_copy_command(ffmpeg="ffmpeg", list_path=Path("D:/l.txt"),
                                   out_path=Path("D:/o.mp4"))
        self.assertEqual(r._attempt_chain(copy, plan), [plan.encoder])


class FrameCountTest(unittest.TestCase):
    def test_parse_frame_count(self):
        self.assertEqual(parse_frame_count("120\n"), 120)
        self.assertIsNone(parse_frame_count("N/A"))
        self.assertIsNone(parse_frame_count(""))
        self.assertIsNone(parse_frame_count("0"))
        self.assertIsNone(parse_frame_count("abc"))

    def test_verify_accepts_fast_when_matching(self):
        calls = []

        def run(args):
            calls.append(args)
            return "50\n" if "-count_frames" not in args else "50\n"
        got = verify_segment_frames("ffprobe", Path("D:/o.mp4"), 50, run=run)
        self.assertEqual(got, (50, False))
        self.assertEqual(len(calls), 1)                 # 没付严格计数代价

    def test_verify_falls_back_to_strict_when_fast_untrusted(self):
        seen = []

        def run(args):
            seen.append("-count_frames" in args)
            return "48\n" if not seen[-1] else "50\n"
        frames, strict = verify_segment_frames("ffprobe", Path("D:/o.mp4"), 50, run=run)
        self.assertTrue(strict)
        self.assertEqual(frames, 50)

    def test_verify_strict_missing_returns_fast_value(self):
        def run(args):
            return "48\n" if "-count_frames" not in args else "N/A"
        frames, strict = verify_segment_frames("ffprobe", Path("D:/o.mp4"), 50, run=run)
        self.assertEqual((frames, strict), (48, True))


class SmartRenderTest(unittest.TestCase):
    def setUp(self):
        self.fps = Fraction(25, 1)
        self.keys = tuple(Keyframe(float(i), i * 25) for i in range(6))

    def test_smart_render_is_opt_in(self):
        renderer = TimelineMovieRenderer("ffmpeg", "ffprobe", Path("."))
        self.assertFalse(renderer.smart_render)

    def test_smart_final_validation_uses_strict_decode_count(self):
        calls = []

        def run(args):
            calls.append(args)
            return "4513\n" if "-count_frames" not in args else "1975\n"

        renderer = TimelineMovieRenderer("ffmpeg", "ffprobe", Path("."), run=run)
        plan = _tiny_plan(smart_render=True, total_frames=4513)
        with self.assertRaises(MediaError) as ctx:
            renderer._verify_output_frames(plan)
        self.assertIn("预期 4513，实际 1975", str(ctx.exception))
        self.assertEqual(len(calls), 1)
        self.assertIn("-count_frames", calls[0])

    def test_reused_smart_output_is_strictly_validated(self):
        renderer = TimelineMovieRenderer(
            "ffmpeg", "ffprobe", Path("."), run=lambda args: "1975\n")
        plan = _tiny_plan(smart_render=True, total_frames=4513, reused=True)
        renderer.plan = lambda *args, **kwargs: plan
        with self.assertRaises(MediaError):
            renderer.render([], Path("unused"))

    def test_parse_keyframes_keeps_packet_positions(self):
        got = parse_keyframes('{"packets":[{"pts_time":"0.0","flags":"K__"},'
                              '{"pts_time":"0.04","flags":"___"},'
                              '{"pts_time":"1.0","flags":"K__"}]}')
        self.assertEqual(got, (Keyframe(0.0, 0), Keyframe(1.0, 2)))

    def test_split_uses_next_head_and_previous_tail_keyframes(self):
        job = RenderJob(0, 0.4, 3.6, 80, Path("D:/o.mov"))
        parts = smart_clip_parts(job, self.keys, self.fps)
        self.assertEqual([(p.kind, p.start_s, p.frames) for p in parts],
                         [("head", 0.4, 15), ("copy", 1.0, 50), ("tail", 3.0, 15)])

    def test_split_rejects_short_middle_and_frame_mismatch(self):
        short = RenderJob(0, 0.4, 1.6, 30, Path("D:/o.mov"))
        self.assertIsNone(smart_clip_parts(short, self.keys, self.fps))
        mismatch = RenderJob(0, 0.4, 3.6, 79, Path("D:/o.mov"))
        self.assertIsNone(smart_clip_parts(mismatch, self.keys, self.fps))

    def test_eligibility_allows_container_average_rounding_but_rejects_vfr(self):
        v = _vstream(r_frame_rate="24000/1001",
                     avg_frame_rate="1559673568/65051385", sample_aspect_ratio="1:1")
        fps = Fraction("1559673568/65051385")
        self.assertIsNone(smart_render_block_reason(v, fps))
        self.assertEqual(smart_render_block_reason(
            {**v, "avg_frame_rate": "25/1"}, Fraction(25, 1)), "vfr")
        self.assertEqual(smart_render_block_reason(
            {**v, "codec_name": "hevc"}, fps), "codec_not_h264")
        self.assertEqual(smart_render_block_reason(
            {**v, "sample_aspect_ratio": "4:3"}, fps), "sar_not_1")

    def test_smart_failure_falls_back_to_whole_segment_transcode(self):
        renderer = TimelineMovieRenderer("ffmpeg", "ffprobe", Path("."))
        plan = _tiny_plan(smart_render=True, keyframes=self.keys)
        job = RenderJob(0, 0.4, 3.6, 80, Path("D:/o.mov"))

        def fail(*args):
            raise MediaError("bad copy")

        sentinel = SegmentResult(0, job.out_path, 80, "libx264")
        renderer._run_one_smart = fail
        renderer._run_one_transcode = lambda *args: sentinel
        self.assertIs(renderer._run_one(plan, job, lambda *args: None, None), sentinel)


class StableNameTest(unittest.TestCase):
    def test_same_inputs_same_name(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "om.mkv"
            src.write_bytes(b"x")
            a = render_output_name(src, [(1.0, 3.0), (5.0, 8.0)], ["25", "320x240"])
            b = render_output_name(src, [(1.0, 3.0), (5.0, 8.0)], ["25", "320x240"])
            c = render_output_name(src, [(1.0, 3.0), (5.0, 8.0)], ["30", "320x240"])
            d = render_output_name(src, [(1.0, 3.5), (5.0, 8.0)], ["25", "320x240"])
            self.assertEqual(a, b)
            self.assertNotEqual(a, c)
            self.assertNotEqual(a, d)
            self.assertTrue(a.startswith("movie_om_") and a.endswith(".mp4"))


def _tiny_plan(**over) -> RenderPlan:
    base = dict(source=Path("D:/v/om.mkv"), output=Path("D:/out/movie_x.mp4"),
                fps=Fraction(25, 1), width=320, height=240, pix_fmt="yuv420p",
                encoder="libx264", has_audio=True, total_frames=100,
                total_seconds=4.0, clip_count=4, jobs=[],
                segment_dir=Path("D:/out/segments"),
                concat_list=Path("D:/out/movie_x.concat.txt"))
    base.update(over)
    return RenderPlan(**base)


class MergeStageFracTest(unittest.TestCase):
    """合并阶段读数换算（2026-10-09 用户真项目 LOC-9999 回归锁）。

    现场：《巅峰猎杀.1080p.HD中英双字…》两次 ``render failed [LOC-9999]
    TypeError: unsupported operand type(s) for *: 'float' and 'NoneType'``。
    根因 = 合并那两处进度回调写的是 ``0.035 * f``，而 ``_run_monitored`` 在
    **算不出读数**时按约定发 ``f=None``（``_seg_cb`` 有这层判定，合并没抄）
    ⇒ 文案还没发出去就先抛，整条渲染任务被判死。
    """

    def test_none_keeps_reading_unset_instead_of_raising(self):
        self.assertIsNone(merge_stage_frac(None))

    def test_maps_unit_interval_onto_stage_window(self):
        self.assertAlmostEqual(merge_stage_frac(0.0), 0.96)
        self.assertAlmostEqual(merge_stage_frac(0.5), 0.9775)
        self.assertAlmostEqual(merge_stage_frac(1.0), 0.995)

    def test_caps_at_stage_ceiling(self):
        self.assertAlmostEqual(merge_stage_frac(2.0), 0.995)

    def test_merge_callbacks_do_not_multiply_raw_frac(self):
        """结构锁：算术必须留在 ``merge_stage_frac`` 里，别再写回 lambda。"""
        src = (Path(__file__).resolve().parents[1] / "src" / "media" / "ffmpeg"
               / "timeline_render.py").read_text(encoding="utf-8")
        self.assertEqual(src.count("merge_stage_frac(f)"), 2, "两处合并回调都该走该函数")
        bad = [ln.strip() for ln in src.splitlines()
               if "on_frac=lambda f:" in ln and "emit(" in ln and "merge_stage_frac" not in ln]
        self.assertEqual([], bad, "有合并阶段回调把原始 frac 直接喂给 emit")


class WatchdogTest(unittest.TestCase):
    """停滞看门狗 / 取消 / 心跳（竞品确证语义，注入假 popen 不靠真 ffmpeg）。"""

    def test_stall_terminates_and_reports(self):
        procs = []

        def fake_popen(args, **kw):
            p = _FakeProc(lines=[], alive_polls=10**6)     # 永不退出、零进展
            procs.append(p)
            return p
        r = TimelineMovieRenderer("ffmpeg", "ffprobe", Path("."),
                                  popen=fake_popen, stall_timeout_s=0.05)
        with self.assertRaises(MediaError) as ctx:
            r._spawn(["ffmpeg", "-y", "out.mp4"], total_seconds=10.0, on_frac=None,
                     cancel=None, label="片段 1")
        self.assertIn("长时间没有进展", str(ctx.exception))
        self.assertTrue(procs[0].terminated)

    def test_cancel_terminates(self):
        procs = []

        def fake_popen(args, **kw):
            p = _FakeProc(lines=[], alive_polls=10**6)
            procs.append(p)
            return p
        r = TimelineMovieRenderer("ffmpeg", "ffprobe", Path("."), popen=fake_popen,
                                  stall_timeout_s=3600.0)
        with self.assertRaises(MediaError) as ctx:
            r._spawn(["ffmpeg"], total_seconds=10.0, on_frac=None,
                     cancel=lambda: True, label="合并视频（流复制）")
        self.assertIn("已取消", str(ctx.exception))
        self.assertTrue(procs[0].terminated)

    def test_progress_lines_drive_frac_and_heartbeat(self):
        seen = []

        def fake_popen(args, **kw):
            return _FakeProc(lines=[b"frame=10\n", b"out_time_us=1000000\n", b"bitrate=N/A\n",
                                    None], rc=0)
        r = TimelineMovieRenderer("ffmpeg", "ffprobe", Path("."), popen=fake_popen)
        rc, err = r._spawn(["ffmpeg"], total_seconds=2.0,
                           on_frac=lambda f: seen.append(f), cancel=None, label="片段 1")
        self.assertEqual((rc, err), (0, ""))
        self.assertIn(0.5, seen)                        # 1s / 2s

    def test_hardware_failure_blacklists_and_falls_back(self):
        reset_disabled_hardware_encoders()
        r = TimelineMovieRenderer("ffmpeg", "ffprobe", Path("."), prefer_hw=True)
        r._encoders = ["h264_amf", "libx264"]
        used = []

        def fake_spawn(args, **kw):
            enc = args[args.index("-c:v") + 1]
            used.append(enc)
            return (1, "amf exploded") if enc == "h264_amf" else (0, "")
        r._spawn = fake_spawn
        plan = _tiny_plan(encoder="h264_amf")
        cmd = segment_command(ffmpeg="ffmpeg", source=plan.source,
                              out_path=plan.segment_dir / "s.mp4", start_s=0.0,
                              frames=25, fps=plan.fps, width=320, height=240,
                              pix_fmt="yuv420p", encoder="h264_amf", crf=18,
                              preset="medium", has_audio=True, sample_rate=48000)
        rc, err, enc = r._run_monitored(cmd, total_seconds=1.0, plan=plan,
                                        on_frac=None, cancel=None, label="片段 1")
        self.assertEqual((rc, enc), (0, "libx264"))
        self.assertEqual(used, ["h264_amf", "libx264"])
        self.assertIn("h264_amf", disabled_hardware_encoders())
        reset_disabled_hardware_encoders()
        self.assertEqual(set(), set(disabled_hardware_encoders()))


class RealFfmpegTest(unittest.TestCase):
    """真 ffmpeg（tools/ffmpeg.exe）E2E：合成 6s 源 → 渲染 2 段成片。

    固定 ``prefer_hw=False``：硬件编码器在 CI/无驱动环境不可依赖（Hermetic 纪律，
    与 test_source_merge 同）。
    """

    @classmethod
    def setUpClass(cls):
        if not FFMPEG.exists() or not FFPROBE.exists():
            raise unittest.SkipTest("bundled ffmpeg/ffprobe not found")
        cls.td = tempfile.TemporaryDirectory()
        cls.root = Path(cls.td.name)
        cls.src = cls.root / "src.mp4"
        cls._make_source(cls.src, audio=True)
        cls.src_noaudio = cls.root / "src_noaudio.mp4"
        cls._make_source(cls.src_noaudio, audio=False)
        cls.src_smart = cls.root / "src_smart.mp4"
        cls._make_source(cls.src_smart, audio=True, fixed_gop=True)

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    @classmethod
    def _make_source(cls, out: Path, *, audio: bool, fixed_gop: bool = False):
        args = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc=duration=6:size=320x240:rate=25"]
        if audio:
            args += ["-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                     "-map", "0:v", "-map", "1:a", "-c:a", "aac"]
        else:
            args += ["-map", "0:v", "-an"]
        args += ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
        if fixed_gop:
            args += ["-g", "25", "-keyint_min", "25", "-sc_threshold", "0"]
        args.append(str(out))
        subprocess.run(args, check=True, capture_output=True, timeout=180)

    def _renderer(self, sub: str) -> TimelineMovieRenderer:
        return TimelineMovieRenderer(FFMPEG, FFPROBE, self.root / sub,
                                     prefer_hw=False, workers=1, preset="veryfast",
                                     crf=28)

    def _frame_delta_histogram(self, path: Path) -> list[float]:
        """成片视频帧的相邻 PTS 差（秒）——接缝间隙缺陷的直测判据。"""
        out = subprocess.run(
            [str(FFPROBE), "-v", "error", "-select_streams", "v:0",
             "-show_entries", "frame=pts_time", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=300).stdout
        times = [float(x.strip().rstrip(",")) for x in out.replace("\r", "").split("\n")
                 if x.strip().rstrip(",")]
        return [round(b - a, 4) for a, b in zip(times, times[1:])]

    def test_renders_movie_with_expected_frames(self):
        r = self._renderer("basic")
        clips = [(0.0, 2.0), (3.0, 5.0)]        # 25fps → 50 + 50 = 100 帧
        out = r.render(clips, self.src)
        self.assertEqual(out["total_frames"], 100)
        self.assertEqual(out["segments"], 2)
        self.assertIn(out["mode"], ("copy", "transcode"))
        self.assertEqual(Path(out["movie_path"]).exists(), True)
        self.assertAlmostEqual(out["duration_s"], 4.0, places=3)
        # 帧数实测 = 预期（逐段帧数校验已在 render 内部通过）
        got = subprocess.run(
            [str(FFPROBE), "-v", "error", "-select_streams", "v:0", "-count_frames",
             "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1",
             out["movie_path"]], capture_output=True, text=True, timeout=120)
        self.assertEqual(int(got.stdout.strip()), 100)
        # **接缝回归锁**：中段用 AAC 时会在每个接缝留下 1 个 AAC 帧的视频间隙
        # （0.0417→0.0630s），PCM 中段后帧距必须全部等于 1/fps。
        deltas = self._frame_delta_histogram(Path(out["movie_path"]))
        self.assertEqual(len(deltas), 99)
        self.assertEqual(set(deltas), {0.04}, f"帧距不规则: {sorted(set(deltas))}")
        # 音轨在位（原片区间音频口径，终片转 AAC）
        st = subprocess.run(
            [str(FFPROBE), "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name,sample_rate,channels",
             "-of", "default=nw=1", out["movie_path"]],
            capture_output=True, text=True, timeout=60).stdout
        self.assertIn("codec_name=aac", st)
        self.assertIn("sample_rate=48000", st)
        self.assertIn("channels=2", st)

    def test_smart_render_copies_middle_gops_and_preserves_timeline(self):
        renderer = TimelineMovieRenderer(
            FFMPEG, FFPROBE, self.root / "smart", prefer_hw=False, workers=1,
            preset="veryfast", crf=28, smart_render=True)
        smart = renderer.render([(0.4, 3.6)], self.src_smart)
        self.assertTrue(smart["smart_render"])
        self.assertEqual(smart["smart_segments"], 1)
        self.assertEqual(smart["smart_copy_frames"], 50)
        self.assertEqual(smart["total_frames"], 80)
        self.assertEqual(set(self._frame_delta_histogram(Path(smart["movie_path"]))), {0.04})

        baseline_renderer = TimelineMovieRenderer(
            FFMPEG, FFPROBE, self.root / "smart_baseline", prefer_hw=False,
            workers=1, preset="veryfast", crf=28, smart_render=False)
        baseline = baseline_renderer.render([(0.4, 3.6)], self.src_smart)
        self.assertFalse(baseline["smart_render"])
        self.assertEqual(baseline["total_frames"], smart["total_frames"])
        self.assertAlmostEqual(baseline["duration_s"], smart["duration_s"], places=3)
        self.assertEqual(set(self._frame_delta_histogram(Path(baseline["movie_path"]))), {0.04})

    def test_second_render_reuses_stable_named_output(self):
        r = self._renderer("reuse")
        clips = [(1.0, 2.0), (4.0, 5.5)]
        first = r.render(clips, self.src)
        second = r.render(clips, self.src)
        self.assertEqual(second["mode"], "reused")
        self.assertEqual(second["movie_path"], first["movie_path"])

    def test_silent_source_still_gets_audio_track(self):
        r = self._renderer("silent")
        out = r.render([(0.0, 1.0), (2.0, 3.0)], self.src_noaudio)
        self.assertEqual(out["total_frames"], 50)
        st = subprocess.run(
            [str(FFPROBE), "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=codec_name", "-of", "default=nw=1:nk=1",
             out["movie_path"]], capture_output=True, text=True, timeout=60).stdout.strip()
        self.assertEqual(st, "aac")     # 无音轨源 → 补静音，保证 concat 结构一致

    def test_empty_clip_list_raises(self):
        r = self._renderer("empty")
        with self.assertRaises(MediaError):
            r.render([], self.src)
        with self.assertRaises(MediaError):
            r.render([(2.0, 1.0)], self.src)   # 只有一条负宽段 → 过滤后为空


if __name__ == "__main__":
    unittest.main()
