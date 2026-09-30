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
from media.ffmpeg.source_merge import (SourceVideoMerger, choose_extension, color_args,
                                       concat_list_text, duration_tolerance, encoder_chain,
                                       error_summary, file_signature, is_copy_compatible,
                                       is_hdr, is_high_bit_depth, merge_output_name,
                                       parse_hevc_encoders, parse_progress_seconds,
                                       pick_pix_fmt, x265_params)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
