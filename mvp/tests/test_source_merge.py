"""Unit tests for mvp.media.ffmpeg.source_merge（多原片合并, 2026-09-29 video.concat 移植）。

纯函数层用伪造 ffprobe dict；E2E 用真实 tools/ffmpeg 生成 2s 小片段验证
copy/转码双路径 + 稳定命名缓存复用。转码 E2E 固定 prefer_hw=False（libx265）保证
测试 Hermetic——硬件编码器在 CI/无显卡驱动环境不可依赖。

Run with the venv python:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_source_merge -v
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from media.ffmpeg import MediaError
from media.ffmpeg.source_merge import (CPU_ENCODER, MergePlan, SourceVideoMerger,
                                       _DEAD_ENCODERS, audio_signature, choose_extension,
                                       color_args, concat_list_text, copy_layout_note,
                                       declared_layout, duration_tolerance, encoder_chain,
                                       error_summary, file_signature, is_copy_compatible,
                                       is_encoder_dead, is_hdr, is_high_bit_depth,
                                       mark_encoder_dead, merge_output_name, named_layout,
                                       parse_hevc_encoders, parse_progress_seconds,
                                       pick_pix_fmt, resolve_audio_layouts, x265_params)

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")


def _vstream(**over) -> dict:
    base = {"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720,
            "pix_fmt": "yuv420p", "avg_frame_rate": "25/1", "sample_aspect_ratio": "1:1",
            "color_primaries": "bt709", "color_trc": "bt709", "color_space": "bt709",
            "color_range": "tv"}
    base.update(over)
    return base


def _probe(v=None, a=None, duration="5.0") -> dict:
    streams = [v] if v else []
    if a:
        streams.append(a)
    return {"streams": streams, "format": {"duration": duration, "filename": "x.mp4"}}


# --------------------------------------------------------------------- 纯函数
class SignatureTest(unittest.TestCase):
    def test_copy_compatible_requires_all_equal(self):
        sig = file_signature(_probe(v=_vstream(), a={"codec_type": "audio", "codec_name": "aac",
                                                     "sample_rate": "48000", "channels": 2}))
        self.assertTrue(is_copy_compatible([sig, sig]))
        other = file_signature(_probe(v=_vstream(width=1920)))
        self.assertFalse(is_copy_compatible([sig, other]))
        self.assertFalse(is_copy_compatible([sig]))  # <2 无意义

    def test_color_meta_participates_in_signature(self):
        a = file_signature(_probe(v=_vstream(color_trc="bt709")))
        b = file_signature(_probe(v=_vstream(color_trc="smpte2084")))
        self.assertFalse(is_copy_compatible([a, b]))

    def test_missing_video_track_raises(self):
        with self.assertRaises(MediaError):
            file_signature({"streams": [], "format": {}})


class HdrAndPixFmtTest(unittest.TestCase):
    def test_is_hdr(self):
        self.assertTrue(is_hdr({"color_trc": "smpte2084"}))            # PQ
        self.assertTrue(is_hdr({"color_trc": "arib-std-b67"}))          # HLG
        self.assertTrue(is_hdr({"color_primaries": "bt2020"}))
        self.assertTrue(is_hdr({"color_space": "bt2020nc"}))
        self.assertFalse(is_hdr({"color_trc": "bt709", "color_primaries": "bt709"}))

    def test_high_bit_depth(self):
        self.assertTrue(is_high_bit_depth({"pix_fmt": "yuv420p10le"}))
        self.assertTrue(is_high_bit_depth({"pix_fmt": "p010le"}))
        self.assertFalse(is_high_bit_depth({"pix_fmt": "yuv420p"}))

    def test_pick_pix_fmt_matrix(self):
        sdr = _vstream()
        hdr = _vstream(color_trc="smpte2084", pix_fmt="yuv420p10le")
        self.assertEqual(pick_pix_fmt(sdr, "libx265"), "yuv420p")
        self.assertEqual(pick_pix_fmt(hdr, "libx265"), "yuv420p10le")
        self.assertEqual(pick_pix_fmt(hdr, "hevc_amf"), "p010le")
        self.assertEqual(pick_pix_fmt(sdr, "hevc_nvenc"), "yuv420p")


class ColorArgsTest(unittest.TestCase):
    def test_color_args_fixed_order_skips_empty(self):
        args = color_args(_vstream(color_primaries="bt2020", color_trc="smpte2084",
                                   color_space="", color_range="tv"))
        self.assertEqual(args, ["-color_primaries", "bt2020", "-color_trc", "smpte2084",
                               "-color_range", "tv"])

    def test_x265_params_repeat_and_hdr(self):
        self.assertEqual(x265_params(_vstream()),
                         "repeat-headers=1:colorprim=bt709:transfer=bt709:colormatrix=bt709")
        self.assertIn("hdr-opt=1", x265_params(_vstream(color_trc="smpte2084")))


class EncoderChainTest(unittest.TestCase):
    def test_parse_encoders_output(self):
        sample = ("Codecs:\n"
                  " V....D libx264              libx264 H.264 / AVC (codec h264)\n"
                  " V....D libx265              libx265 H.265 / HEVC (codec hevc)\n"
                  " V....D hevc_amf             AMD AMF HEVC Encoder (codec hevc)\n"
                  " V..... hevc_qsv             Intel QSV (codec hevc)\n"
                  " V....D h264_amf             AMD AMF H.264 Encoder (codec h264)\n"
                  " A....D aac                  AAC (codec aac)\n")
        self.assertEqual(parse_hevc_encoders(sample), ["libx265", "hevc_amf", "hevc_qsv"])

    def test_chain_hw_order_then_cpu_fallback(self):
        avail = ["libx265", "hevc_amf", "hevc_nvenc"]
        self.assertEqual(encoder_chain(avail), ["hevc_nvenc", "hevc_amf", "libx265"])
        self.assertEqual(encoder_chain(avail, prefer_hw=False), ["libx265"])
        # libx265 在候选中也只出现一次且最后（竞品确证：跳过候选中的 libx265）
        self.assertEqual(encoder_chain(["libx265"]), ["libx265"])


class NamingAndListTest(unittest.TestCase):
    def test_stable_name_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            ps = []
            for i in range(2):
                p = Path(td) / f"ep{i}.mkv"
                p.write_bytes(b"x" * (10 + i))
                ps.append(str(p))
            n1 = merge_output_name(ps, "copy", "mkv")
            n2 = merge_output_name([Path(td) / "ep0.mkv", Path(td) / "ep1.mkv"], "copy", "mkv")
            self.assertEqual(n1, n2)
            self.assertRegex(n1, r"^merged_2_[0-9a-f]{12}_copy\.mkv$")
            self.assertNotEqual(n1, merge_output_name(ps, "transcode", "mp4"))

    def test_extension_choice(self):
        self.assertEqual(choose_extension(["a.mkv", "b.mkv"], "copy"), "mkv")
        self.assertEqual(choose_extension(["a.mkv", "b.mkv"], "transcode"), "mp4")
        self.assertEqual(choose_extension(["a.mkv", "b.mp4"], "copy"), "mp4")

    def test_concat_list_escapes(self):
        text = concat_list_text([r"D:\v\it's 1.mkv", "E:/x/2.mkv"])
        self.assertIn("file 'D:/v/it'\\''s 1.mkv'", text)
        self.assertIn("file 'E:/x/2.mkv'", text)


class ProgressParseTest(unittest.TestCase):
    def test_us_keys_are_microseconds(self):
        self.assertAlmostEqual(parse_progress_seconds("out_time_us=1500000"), 1.5)
        self.assertAlmostEqual(parse_progress_seconds("out_time_ms=2500000"), 2.5)

    def test_out_time_hms(self):
        self.assertAlmostEqual(parse_progress_seconds("out_time=00:01:30.500000"), 90.5)
        self.assertAlmostEqual(parse_progress_seconds("out_time=01:00:00"), 3600.0)

    def test_non_time_lines(self):
        self.assertIsNone(parse_progress_seconds("frame=120"))
        self.assertIsNone(parse_progress_seconds("out_time_us=NA"))
        self.assertIsNone(parse_progress_seconds("progress=continue"))
        self.assertIsNone(parse_progress_seconds(""))

    def test_tolerance_and_summary(self):
        self.assertEqual(duration_tolerance(4.0), 1.0)
        self.assertAlmostEqual(duration_tolerance(600.0), 12.0, places=6)
        self.assertEqual(error_summary("a\n b   c"), "a b c")
        self.assertTrue(error_summary("x" * 500, 100).endswith("…"))


# --------------------------------------------------------------------- E2E
def _make_clip(path: Path, *, fps: int, seconds: int = 2, size: str = "128x96") -> None:
    cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
           "-f", "lavfi", "-i", f"testsrc=size={size}:rate={fps}",
           "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000",
           "-t", str(seconds), "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-shortest", str(path)]
    subprocess.run(cmd, check=True, capture_output=True,
                   creationflags=0x08000000 if sys.platform == "win32" else 0)


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists(), "real ffmpeg/ffprobe not present")
class MergerE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="svl_merge_test_"))
        cls.parts_dir = cls.tmp / "parts"
        cls.parts_dir.mkdir()
        cls.a = cls.parts_dir / "epA.mp4"
        cls.b = cls.parts_dir / "epB.mp4"
        _make_clip(cls.a, fps=25)
        _make_clip(cls.b, fps=25)
        # 不同帧率的第三段——触发转码路径
        cls.c = cls.parts_dir / "epC30.mp4"
        _make_clip(cls.c, fps=30)

    def _merger(self, **kw) -> SourceVideoMerger:
        return SourceVideoMerger(FFMPEG, FFPROBE, self.tmp / "merged",
                                 timeout_s=120, prefer_hw=False, **kw)

    def test_copy_path_and_output_duration(self):
        m = self._merger()
        plan = m.plan([self.a, self.b])
        self.assertEqual(plan.mode, "copy")
        self.assertAlmostEqual(plan.total_duration, 4.0, places=1)
        info = m.merge([self.a, self.b])
        self.assertEqual(info["mode"], "copy")
        # reused 取决于同类内执行顺序（缓存文件同名），不作为本例断言
        out = Path(info["merged_path"])
        self.assertTrue(out.exists())
        self.assertAlmostEqual(float(m.probe(out)["format"]["duration"]),
                                   4.0, delta=1.0)

    def test_cache_reuse_stable_name(self):
        m = self._merger()
        info1 = m.merge([self.a, self.b])
        stat1 = Path(info1["merged_path"]).stat()
        info2 = m.merge([self.a, self.b])
        self.assertTrue(info2["reused"])
        self.assertEqual(info1["merged_path"], info2["merged_path"])
        self.assertEqual(stat1.st_size, Path(info2["merged_path"]).stat().st_size)
        self.assertEqual(stat1.st_mtime_ns, Path(info2["merged_path"]).stat().st_mtime_ns)

    def test_transcode_path_when_fps_mismatch(self):
        m = self._merger()
        plan = m.plan([self.a, self.c])
        self.assertEqual(plan.mode, "transcode")
        info = m.merge([self.a, self.c])
        self.assertEqual(info["mode"], "transcode")
        out = Path(info["merged_path"])
        self.assertTrue(out.exists())
        self.assertAlmostEqual(float(m.probe(out)["format"]["duration"]), 4.0, delta=1.0)

    def test_requires_two_existing_files(self):
        m = self._merger()
        with self.assertRaises(MediaError):
            m.plan([self.a])
        with self.assertRaises(MediaError):
            m.plan([self.a, self.parts_dir / "ghost.mp4"])

    def test_passthrough_and_disabled_via_service_like_flow(self):
        # service 层语义（len<=1 直通 / enabled=false 拒绝）在 app 测试覆盖，
        # 这里验证 merger 自身对单文件即报错，不静默复制。
        m = self._merger()
        with self.assertRaises(MediaError):
            m.merge([self.a])


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists(), "real ffmpeg/ffprobe not present")
class MergeOriginalsServiceFlowTest(unittest.TestCase):
    """SourceLocatorService.merge_originals 的直通/开关分支（不加载模型、不跑 ffmpeg）。"""

    def _service(self):
        from app.locator_service import SourceLocatorService
        from infrastructure.config import AppConfig
        return SourceLocatorService(config=AppConfig())

    def test_single_path_passthrough(self):
        info = self._service().merge_originals([str(FFMPEG)])
        self.assertEqual(info["mode"], "passthrough")
        self.assertEqual(Path(info["merged_path"]), FFMPEG.resolve())

    def test_empty_list_raises(self):
        from infrastructure.errors import LocatorError
        with self.assertRaises(LocatorError):
            self._service().merge_originals([])

    def test_multi_with_disabled_raises(self):
        svc = self._service()
        svc.config.source_merge.enabled = False
        from infrastructure.errors import LocatorError
        with self.assertRaises(LocatorError):
            svc.merge_originals([str(FFMPEG), str(FFMPEG)])


# ------------------------------------------------ 音频布局归一（2026-10-18 缺陷批）
def _a(ch: int, layout: str | None = None) -> dict:
    d = {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": ch}
    if layout is not None:
        d["channel_layout"] = layout
    return d


class AudioLayoutResolveTest(unittest.TestCase):
    """resolve_audio_layouts：「不需要归一时命令逐字不变」这条边界必须真咬。"""

    def test_all_declared_equal_needs_no_filter(self):
        chains, note = resolve_audio_layouts([_a(2, "stereo"), _a(2, "stereo")])
        self.assertEqual(chains, [[], []])
        self.assertEqual(note, "")

    def test_unknown_only_gets_named_by_channel_count(self):
        chains, note = resolve_audio_layouts([_a(6), _a(6)])
        self.assertEqual(chains, [["5.1"], ["5.1"]])
        self.assertIn("声道数不变", note)
        self.assertNotIn("不一致", note)

    def test_mixed_same_count_only_fixes_the_unnamed_one(self):
        chains, _ = resolve_audio_layouts([_a(6), _a(6, "5.1")])
        self.assertEqual(chains, [["5.1"], []])

    def test_input_order_does_not_decide_target(self):
        self.assertEqual(resolve_audio_layouts([_a(6), _a(2, "stereo")])[0], [["5.1"], ["5.1"]])
        self.assertEqual(resolve_audio_layouts([_a(2, "stereo"), _a(6)])[0], [["5.1"], ["5.1"]])

    def test_unnameable_channel_count_falls_back_to_stereo(self):
        chains, note = resolve_audio_layouts([_a(7), _a(2, "stereo")])
        self.assertEqual(chains, [["stereo"], []])
        self.assertIn("统一到 stereo", note)

    def test_missing_audio_is_left_to_upper_layer(self):
        chains, note = resolve_audio_layouts([_a(2, "stereo"), None])
        self.assertEqual(chains, [[], []])
        self.assertEqual(note, "")


class TranscodeArgsChainTest(unittest.TestCase):
    """``_transcode_args``：空链 ⇒ 音轨直连（与改前逐字相同）；有链 ⇒ 依次插 aformat。"""

    def _merger(self) -> SourceVideoMerger:
        return SourceVideoMerger("ffmpeg", "ffprobe", Path(tempfile.mkdtemp(prefix="svl_args_")))

    def _plan(self, chains, has_audio=True) -> MergePlan:
        return MergePlan(paths=["a.mp4", "b.mp4"], mode="transcode", output=Path("out.mp4"),
                         total_duration=10.0, reason="", main_video=_vstream(),
                         has_audio=has_audio, fps="25/1", audio_filters=chains)

    def _fc(self, args: list[str]) -> str:
        return args[args.index("-filter_complex") + 1]

    def test_empty_chain_keeps_direct_wiring(self):
        fc = self._fc(self._merger()._transcode_args(self._plan([[], []]), "libx265", Path("o.mp4")))
        self.assertIn("[v0][0:a:0][v1][1:a:0]concat=n=2:v=1:a=1", fc)
        self.assertNotIn("aformat", fc)

    def test_two_step_chain_names_then_unifies(self):
        fc = self._fc(self._merger()._transcode_args(
            self._plan([["5.1", "stereo"], []]), "libx265", Path("o.mp4")))
        self.assertIn("[0:a:0]aformat=channel_layouts=5.1,aformat=channel_layouts=stereo[a0]", fc)
        self.assertIn("[v0][a0][v1][1:a:0]concat=n=2:v=1:a=1", fc)

    def test_silent_plan_untouched(self):
        fc = self._fc(self._merger()._transcode_args(
            self._plan([[], []], has_audio=False), "libx265", Path("o.mp4")))
        self.assertIn("concat=n=2:v=1:a=0", fc)
        self.assertNotIn("aformat", fc)


def _make_unknown6(dst: Path, *, fps: int, w: int = 640, secs: float = 2.0) -> None:
    """造「6 声道 + 容器未写布局」的形制源。

    不是随手造的形制：``5.1(side)`` 编进 MP4 后布局信息就丢（ffprobe 报 unknown），
    线上产品自抽的 ``og*.mp4`` 实测就是这个形制（用户导出的 35 个文件逐个探过）。
    """
    exprs = "|".join(f"0.3*sin(2*PI*{f}*t)" for f in (200, 350, 500, 650, 800, 950))
    h = int(round(w * 0.5625 / 2) * 2)
    subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", f"testsrc=size={w}x{h}:rate={fps}",
                    "-f", "lavfi", "-i", f"aevalsrc={exprs}:s=48000:c=5.1",
                    "-af", "pan=5.1(side)|c0=c0|c1=c1|c2=c2|c3=c3|c4=c4|c5=c5",
                    "-t", str(secs), "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-shortest", str(dst)],
                   check=True, capture_output=True,
                   creationflags=0x08000000 if sys.platform == "win32" else 0)


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists(), "real ffmpeg/ffprobe not present")
class UnknownAudioLayoutE2ETest(unittest.TestCase):
    """改前实测：全 unknown 输入 ⇒ 每条编码器尝试都白跑后 ``MediaError``（stderr 原文
    ``Cannot select channel layout for the link between filters auto_aresample_0 and
    Parsed_concat_8``）；unknown+stereo 混合 ⇒ 不报错但产物布局由**第一路**决定。"""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="svl_layout_e2e_"))
        cls.u25 = cls.tmp / "u25.mp4"
        cls.u30 = cls.tmp / "u30.mp4"
        cls.st30 = cls.tmp / "st30.mp4"
        _make_unknown6(cls.u25, fps=25)
        _make_unknown6(cls.u30, fps=30, w=700)
        subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                        "-f", "lavfi", "-i", "testsrc=size=700x394:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=1500:sample_rate=48000",
                        "-t", "2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-ac", "2", "-shortest", str(cls.st30)],
                       check=True, capture_output=True,
                       creationflags=0x08000000 if sys.platform == "win32" else 0)

    def _audio(self, p: Path) -> tuple:
        out = subprocess.run([str(FFPROBE), "-v", "error", "-select_streams", "a:0",
                              "-show_entries", "stream=channels,channel_layout",
                              "-of", "default=nw=1:nk=1", str(p)],
                             capture_output=True).stdout.decode().split()
        return (int(out[0]), out[1] if len(out) > 1 else "unknown")

    def test_fixture_is_actually_unnamed(self):
        self.assertEqual(self._audio(self.u25), (6, "unknown"))

    def test_two_unknown_inputs_merge_to_named_51(self):
        seen: list[str] = []
        m = SourceVideoMerger(FFMPEG, FFPROBE, self.tmp / "m_unk", timeout_s=180,
                              prefer_hw=False,
                              log=lambda *a: seen.append(" ".join(str(x) for x in a)))
        info = m.merge([self.u25, self.u30])
        self.assertEqual(self._audio(Path(info["merged_path"])), (6, "5.1"))
        self.assertIn("补名为 5.1", m.plan([self.u25, self.u30]).reason)
        # 判据必须落进日志：reason 此前既不回传也不打日志，用户侧无从知道产物声道结构被动过
        self.assertTrue(any("source merge plan" in s and "补名为 5.1" in s for s in seen),
                        f"布局判据未落日志: {seen}")

    def test_mixed_order_yields_same_layout(self):
        a = SourceVideoMerger(FFMPEG, FFPROBE, self.tmp / "m_a", timeout_s=180, prefer_hw=False)
        b = SourceVideoMerger(FFMPEG, FFPROBE, self.tmp / "m_b", timeout_s=180, prefer_hw=False)
        la = self._audio(Path(a.merge([self.u25, self.st30])["merged_path"]))
        lb = self._audio(Path(b.merge([self.st30, self.u25])["merged_path"]))
        self.assertEqual(la, lb)
        self.assertEqual(la[0], 6)

    def test_uniform_declared_inputs_get_no_chain(self):
        m = SourceVideoMerger(FFMPEG, FFPROBE, self.tmp / "m_st", timeout_s=180, prefer_hw=False)
        plan = m.plan([self.st30, self.st30])
        self.assertEqual(plan.audio_filters, [[], []])
        self.assertNotIn("布局", plan.reason)


class LeftoverFixTest(unittest.TestCase):
    """两项遗留（2026-10-18 补廿二）：copy 判据含布局 + 开不了的编码器不再反复白试。"""

    def test_literal_unknown_from_ffprobe_is_still_unnamed(self):
        # ffprobe 的 csv 视图给字面 "unknown"（json 视图是缺字段）。若把它当"已写明"，
        # 整套补名归因会**静默失效**——这条锁就是防这个。
        self.assertEqual(declared_layout({"channels": 6, "channel_layout": "unknown"}), "")
        self.assertEqual(named_layout({"channels": 6, "channel_layout": "unknown"}), "5.1")
        chains, note = resolve_audio_layouts([{"codec_type": "audio", "channels": 6,
                                               "channel_layout": "unknown"},
                                              {"codec_type": "audio", "channels": 6,
                                               "channel_layout": "unknown"}])
        self.assertEqual(chains, [["5.1"], ["5.1"]])
        self.assertIn("补名为 5.1", note)

    def test_copy_signature_uses_named_layout(self):
        unk = {"codec_name": "aac", "sample_rate": "48000", "channels": 6,
               "channel_layout": "unknown"}
        d51 = {"codec_name": "aac", "sample_rate": "48000", "channels": 6,
               "channel_layout": "5.1"}
        hexa = {"codec_name": "aac", "sample_rate": "48000", "channels": 6,
                "channel_layout": "hexagonal"}
        # 同序（unknown vs 5.1）仍判可流复制：否则分集原片从秒级 copy 掉进几十分钟转码
        self.assertEqual(audio_signature(unk), audio_signature(d51))
        # 声道顺序真不同的两种 6 声道布局不再误判可流复制
        self.assertNotEqual(audio_signature(d51), audio_signature(hexa))
        self.assertTrue(is_copy_compatible([audio_signature(unk), audio_signature(d51)]))
        self.assertFalse(is_copy_compatible([audio_signature(d51), audio_signature(hexa)]))

    def test_side_layout_alias_avoids_needless_transcode(self):
        side = {"codec_name": "aac", "sample_rate": "48000", "channels": 6,
                "channel_layout": "5.1(side)"}
        plain = {"codec_name": "aac", "sample_rate": "48000", "channels": 6,
                 "channel_layout": "5.1"}
        self.assertEqual(audio_signature(side), audio_signature(plain))

    def test_copy_layout_note_only_when_first_is_unnamed(self):
        unk = {"channels": 6, "channel_layout": "unknown"}
        d51 = {"channels": 6, "channel_layout": "5.1"}
        self.assertIn("流复制不改写布局声明", copy_layout_note([unk, d51]))
        self.assertEqual(copy_layout_note([d51, unk]), "")
        self.assertIn("无法命名", copy_layout_note([{"channels": 7}, d51]))

    def test_dead_encoder_cache_and_cpu_guard(self):
        _DEAD_ENCODERS.clear()
        self.addCleanup(_DEAD_ENCODERS.clear)
        mark_encoder_dead("ff", "hevc_nvenc")
        self.assertTrue(is_encoder_dead("ff", "hevc_nvenc"))
        self.assertFalse(is_encoder_dead("other-ff", "hevc_nvenc"))   # 按 ffmpeg 路径分键
        mark_encoder_dead("ff", CPU_ENCODER)
        self.assertFalse(is_encoder_dead("ff", CPU_ENCODER))          # CPU 兜底永不拉黑


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists(), "real ffmpeg/ffprobe not present")
class DeadEncoderSkipE2ETest(unittest.TestCase):
    """跳过分支：本机开不了的编码器第二次不再真开，也**不再向用户播报假故障**。"""

    def setUp(self):
        _DEAD_ENCODERS.clear()
        self.addCleanup(_DEAD_ENCODERS.clear)
        self.tmp = Path(tempfile.mkdtemp(prefix="svl_dead_"))
        self.parts = []
        for i, fps in enumerate((25, 30)):
            p = self.tmp / f"p{i}.mp4"
            subprocess.run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
                            "-f", "lavfi", "-i", f"testsrc=size=640x360:rate={fps}",
                            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
                            "-t", "1.5", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                            "-c:a", "aac", "-shortest", str(p)],
                           check=True, capture_output=True,
                           creationflags=0x08000000 if sys.platform == "win32" else 0)
            self.parts.append(p)

    def _merger(self, **kw):
        return SourceVideoMerger(FFMPEG, FFPROBE, self.tmp / "merged", timeout_s=180, **kw)

    def test_marked_dead_encoder_is_skipped_and_merge_still_succeeds(self):
        m = self._merger(prefer_hw=True)
        chain = encoder_chain(m.available_hevc_encoders(), prefer_hw=True)
        if len(chain) < 2:
            self.skipTest("本机链里只有 CPU 兜底，跳过分支无从观测")
        victim = chain[0]
        mark_encoder_dead(FFMPEG, victim)
        seen: list[str] = []
        m2 = self._merger(prefer_hw=True, log=lambda *a: seen.append(" ".join(str(x) for x in a)))
        info = m2.merge(self.parts)
        self.assertTrue(Path(info["merged_path"]).exists())
        # 注：``_log`` 收到的是 (格式串, *参数)，真日志由调用方 %-格式化
        self.assertTrue(any("source merge skip" in s and victim in s for s in seen),
                        f"已判死的编码器没被跳过: {seen}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
