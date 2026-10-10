"""Unit tests for app.exporters + SourceLocatorService.export_project (Phase 22).

Deterministic: pure formatting over hand-built Result/ResultBatch + fake
IndexBundle.scenes / ffmpeg metadata. No DINOv2 / real video / real ffprobe.
Covers: export plan gating (confidence / not_in_source / failure / zero width),
sub-span dedupe & record capping, scene-boundary snap (±tol, collapse guard,
record side untouched), CMX3600 EDL text, FCP7 XML structure (ElementTree),
剪映 draft files (JSON structure, microsecond timeranges, speed materials),
and the service-level export_project wiring (fmt validation, snap downgrade
without index, file outputs).
Run with the venv python:

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_exporters -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from app.exporters import (ExportClip, build_export_plan, plan_jianying_assets,
                           render_edl, render_fcp7_xml, seconds_to_frames,
                           snap_clips_to_scenes, timecode_ndf,
                           _jianying_segment_speed)
from app.models import CancellationToken
from domain import (Confidence, ConfidenceLevel, IndexMeta, OriginalSegment,
                    Result, ResultBatch, TimeSpan)
from infrastructure.errors import ApplicationError

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"


# --------------------------------------------------------------------- #
# builders
# --------------------------------------------------------------------- #
def _result(ed=(0.0, 2.0), orig=(10.0, 12.0), level="HIGH", score=0.9, *,
            segments=(), not_in_source=False, failure=None) -> Result:
    conf = None if failure else Confidence(ConfidenceLevel(level), score)
    return Result(edited=TimeSpan(*ed), original=TimeSpan(*orig), confidence=conf,
                  original_segments=list(segments), failure_reason=failure,
                  not_in_source=not_in_source)


def _batch(results, *, orig="D:/src/2.mkv", edited="D:/src/1.mp4") -> ResultBatch:
    return ResultBatch(original_video=orig, edited_video=edited, results=list(results))


def _meta(duration=3600.0, fps=25.0) -> IndexMeta:
    return IndexMeta(source_file="D:/src/2.mkv", file_size=1, duration=duration,
                     file_hash="h" * 8)


class _FakeBundle:
    def __init__(self, scenes=None, duration=3600.0):
        self.meta = _meta(duration=duration)
        self.scenes = scenes
        self.scene_feats = None


class _FakeStore:
    def __init__(self, bundle=None, error=None):
        self._bundle = bundle if bundle is not None else _FakeBundle()
        self._error = error

    def load_index(self, path):
        if self._error is not None:
            raise self._error
        return self._bundle


class _FakeMeta:
    def __init__(self, fps=25.0, width=1920, height=1080, duration=3600.0):
        self.fps, self.width, self.height, self.duration = fps, width, height, duration


class _FakeFFmpeg:
    def __init__(self, fps=25.0):
        self._fps = fps

    def metadata(self, path):
        return _FakeMeta(fps=self._fps)


# --------------------------------------------------------------------- #
# time conversion
# --------------------------------------------------------------------- #
class TestTimecode(unittest.TestCase):
    def test_zero_and_exact(self):
        self.assertEqual(timecode_ndf(0.0, 25.0), "00:00:00:00")
        self.assertEqual(timecode_ndf(2.0, 25.0), "00:00:02:00")
        self.assertEqual(timecode_ndf(2.5, 25.0), "00:00:02:12")

    def test_hour(self):
        # round(3601.5*25)=90038 帧 -> 01:00:01:13（NDF，帧号四舍五入）
        self.assertEqual(timecode_ndf(3601.5, 25.0), "01:00:01:13")

    def test_ntsc_nominal_split(self):
        # 23.976 fps: t=10 -> round(239.76)=240 frames -> /24 nominal = 10s00f
        self.assertEqual(timecode_ndf(10.0, 23.976), "00:00:10:00")
        self.assertEqual(seconds_to_frames(-1.0, 25.0), 0)

    def test_fps_zero_fallback(self):
        self.assertEqual(timecode_ndf(1.0, 0.0), "00:00:01:00")


# --------------------------------------------------------------------- #
# export plan (gating / subs / dedupe)
# --------------------------------------------------------------------- #
class TestBuildExportPlan(unittest.TestCase):
    def test_gate_and_order(self):
        batch = _batch([
            _result(ed=(10.0, 12.0), level="MEDIUM"),
            _result(ed=(0.0, 2.0), level="HIGH"),
            _result(ed=(4.0, 6.0), level="LOW"),                      # exclude 默认
            _result(ed=(6.0, 8.0), not_in_source=True),               # 不导
            _result(ed=(8.0, 9.0), failure="segment_error: X"),       # 不导
            _result(ed=(9.0, 9.0), level="HIGH"),                     # 零宽 edited
        ])
        plan = build_export_plan(batch)
        self.assertEqual([c.edited_start for c in plan], [0.0, 10.0])
        self.assertEqual([c.kind for c in plan], ["main", "main"])

    def test_low_backup_policy(self):
        batch = _batch([_result(ed=(0.0, 2.0), level="LOW", score=0.3)])
        plan = build_export_plan(batch, low_policy="backup")
        self.assertEqual([c.kind for c in plan], ["low"])
        self.assertEqual(plan[0].confidence, "LOW")

    def test_min_confidence_low_includes_all(self):
        batch = _batch([_result(ed=(0.0, 2.0), level="LOW")])
        plan = build_export_plan(batch, min_confidence="LOW")
        self.assertEqual(len(plan), 1)

    def test_subs_dedupe_and_cap(self):
        segs = [
            OriginalSegment(10.0, 12.0, 0.9),                # 与主 span 重合 -> 去重
            OriginalSegment(20.0, 35.0, 0.8),                # 记录槽封顶父段 2s
            OriginalSegment(40.0, 41.0, 0.5, from_scene_pool=True),
            OriginalSegment(0.0, 0.0, 0.0),                  # 零宽 -> 丢
        ]
        batch = _batch([_result(ed=(100.0, 102.0), orig=(10.0, 12.0), segments=segs)])
        plan = build_export_plan(batch)
        self.assertEqual([c.kind for c in plan], ["main", "sub", "sub"])
        main, s1, s2 = plan
        self.assertEqual((s1.edited_start, s1.edited_end), (100.0, 102.0))  # cap 至父段宽
        self.assertEqual((s1.orig_start, s1.orig_end), (20.0, 35.0))
        self.assertTrue(s2.from_scene_pool)
        self.assertEqual(main.seg_index, s1.seg_index)

    def test_invalid_args(self):
        batch = _batch([])
        with self.assertRaises(ValueError):
            build_export_plan(batch, min_confidence="ULTRA")
        with self.assertRaises(ValueError):
            build_export_plan(batch, low_policy="maybe")


# --------------------------------------------------------------------- #
# scene snap
# --------------------------------------------------------------------- #
class TestSnapScenes(unittest.TestCase):
    def setUp(self):
        # 三个场景：0-100 / 100-250 / 250-400（边界 = 0,100,250,400）
        self.scenes = np.array([[0.0, 100.0], [100.0, 250.0], [250.0, 400.0]],
                               dtype=np.float32)

    def test_snap_within_tol(self):
        clip = ExportClip("main", 0.0, 2.0, 99.7, 249.4)
        n = snap_clips_to_scenes([clip], self.scenes, tol_s=1.0)
        self.assertEqual(n, 1)
        self.assertEqual((clip.orig_start, clip.orig_end), (100.0, 250.0))
        self.assertTrue(clip.snap_in and clip.snap_out)

    def test_beyond_tol_keeps(self):
        clip = ExportClip("main", 0.0, 2.0, 96.0, 153.0)
        n = snap_clips_to_scenes([clip], self.scenes, tol_s=1.0)
        self.assertEqual(n, 0)
        self.assertEqual((clip.orig_start, clip.orig_end), (96.0, 153.0))

    def test_record_side_untouched(self):
        clip = ExportClip("sub", 50.0, 52.0, 99.5, 101.0)
        snap_clips_to_scenes([clip], self.scenes, tol_s=1.0)
        self.assertEqual((clip.edited_start, clip.edited_end), (50.0, 52.0))

    def test_collapse_guard(self):
        # 两个边界 100/101 距离都在 1s 内：in 吸 100、out 吸 100/101 -> 塌缩回退
        scenes = np.array([[0.0, 100.0], [100.5, 250.0]], dtype=np.float32)
        clip = ExportClip("main", 0.0, 2.0, 99.8, 101.2)
        snap_clips_to_scenes([clip], scenes, tol_s=1.0)
        self.assertGreater(clip.orig_end - clip.orig_start, 0.05)

    def test_none_scenes_noop_and_clamp(self):
        clip = ExportClip("main", 0.0, 2.0, 99.0, 101.0)
        self.assertEqual(snap_clips_to_scenes([clip], None, tol_s=1.0), 0)
        self.assertEqual((clip.orig_start, clip.orig_end), (99.0, 101.0))
        # 边界远（>tol）不吸附，但超出片尾的 out 夹紧到 duration
        far = np.array([[0.0, 300.0]], dtype=np.float32)
        clip2 = ExportClip("main", 0.0, 2.0, 99.0, 101.0)
        self.assertEqual(snap_clips_to_scenes([clip2], far, tol_s=1.0,
                                              orig_duration=100.5), 0)
        self.assertEqual((clip2.orig_start, clip2.orig_end), (99.0, 100.5))


# --------------------------------------------------------------------- #
# EDL
# --------------------------------------------------------------------- #
class TestRenderEDL(unittest.TestCase):
    def _plan(self):
        return [
            ExportClip("main", 0.0, 2.0, 10.0, 12.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 2.0, 4.0, 20.0, 23.0, "MEDIUM", 0.7, seg_index=1),
            ExportClip("sub", 2.0, 3.0, 30.0, 31.0, "HIGH", 0.8, seg_index=1),
        ]

    def test_structure(self):
        text = render_edl(self._plan(), title="1 located", source_name="2.mkv",
                          source_fps=25.0, record_fps=25.0)
        lines = text.splitlines()
        self.assertEqual(lines[0], "TITLE: 1 located")
        self.assertEqual(lines[1], "FCM: NON-DROP FRAME")
        events = [ln for ln in lines if ln and ln[0].isdigit()]
        self.assertEqual(len(events), 2)          # 只有 main/low，子 span 不进 EDL
        self.assertTrue(events[0].startswith("001  2        V     C"))
        self.assertIn("00:00:10:00 00:00:12:00 00:00:00:00 00:00:02:00", events[0])
        self.assertIn("* FROM CLIP NAME: 2.mkv", lines)
        self.assertIn("conf=HIGH", text)
        self.assertIn("seg=1", text)

    def test_reel_sanitized_and_sorted(self):
        plan = [ExportClip("main", 10.0, 12.0, 0.0, 2.0, "LOW", 0.2, seg_index=3),
                ExportClip("main", 0.0, 2.0, 5.0, 7.0, "HIGH", 0.9, seg_index=0)]
        text = render_edl(plan, title="x", source_name="my film!.mkv",
                          source_fps=23.976, record_fps=25.0)
        self.assertIn("MYFILM  ", text)           # 非字母数字剥掉 + 8 字符对齐
        ev = [ln for ln in text.splitlines() if ln and ln[0].isdigit()]
        self.assertIn("00:00:05:00", ev[0])       # 按记录时间升序（0-2s 段在前）


# --------------------------------------------------------------------- #
# FCP7 XML
# --------------------------------------------------------------------- #
class TestFCP7XML(unittest.TestCase):
    def _plan(self):
        return [
            ExportClip("main", 0.0, 2.0, 10.0, 12.0, "HIGH", 0.9, seg_index=0),
            ExportClip("low", 4.0, 6.0, 50.0, 52.0, "LOW", 0.3, seg_index=2),
            ExportClip("sub", 2.0, 3.0, 30.0, 33.0, "MEDIUM", 0.6,
                       from_scene_pool=True, seg_index=1, sub_index=0),
        ]

    def test_xml_structure(self):
        text = render_fcp7_xml(self._plan(), seq_name="1 located",
                               source_path="D:/src/2.mkv", source_fps=23.976,
                               source_duration=3600.0, record_fps=30.0,
                               source_size=(1920, 960))
        root = ET.fromstring(text)
        self.assertEqual(root.tag, "xmeml")
        self.assertEqual(root.get("version"), "4")
        seq = root.find(".//sequence")
        self.assertIsNotNone(seq)
        tracks = seq.findall("./media/video/track")
        self.assertEqual(len(tracks), 3)          # V1 main / V2 low / V3 sub slot1
        items = root.findall(".//clipitem")
        self.assertEqual(len(items), 3)
        main_item = root.find(".//track/clipitem")   # 第一轨第一个 = main
        self.assertEqual(main_item.findtext("in"), "240")   # 10s @23.976 -> 240
        self.assertEqual(main_item.findtext("out"), "288")
        self.assertEqual(main_item.findtext("start"), "0")  # 0s @30
        self.assertEqual(main_item.findtext("end"), "60")   # 2s @30
        file_el = root.find(".//clipitem/file")
        # 平台中立: 相对/盘符路径经 _pathurl(resolve) 的接线正确性 + 文件名后缀
        from app.exporters import _pathurl
        self.assertEqual(file_el.findtext("pathurl"), _pathurl("D:/src/2.mkv"))
        self.assertTrue(file_el.findtext("pathurl").endswith("2.mkv"))
        self.assertIn("scene-pool candidate", text)
        # 素材率 23.976 -> ntsc TRUE；序列率 30.0 -> ntsc FALSE
        self.assertEqual(root.find(".//clipitem/file/rate/ntsc").text, "TRUE")
        self.assertEqual(seq.find("./media/video/format/samplecharacteristics/rate/ntsc").text,
                         "FALSE")

    def test_empty_plan_minimal(self):
        text = render_fcp7_xml([], seq_name="s", source_path="D:/x.mkv",
                               source_fps=25.0, source_duration=None,
                               record_fps=25.0)
        root = ET.fromstring(text)
        self.assertIsNotNone(root.find(".//sequence"))
        self.assertEqual(root.find(".//track").find("clipitem"), None)


# --------------------------------------------------------------------- #
# 剪映 draft (beta)
# --------------------------------------------------------------------- #
class ExpandMaterialSpansTest(unittest.TestCase):
    """取材扩展 v5（反馈四轮）：核心窗口扩成所在完整原片镜头（scenes 定界）。"""

    def setUp(self):
        # 镜头表：0-20 / 20-60 / 60-100
        import numpy as np
        self.scenes = np.array([[0.0, 20.0], [20.0, 60.0], [60.0, 100.0]], dtype=np.float32)

    def test_expands_to_containing_scene(self):
        from app.exporters import expand_material_spans
        clip = ExportClip("main", 0.0, 2.0, 30.0, 39.0, "HIGH", 0.9)   # 核心 30-39 在镜头 [20,60)
        n = expand_material_spans([clip], self.scenes)
        self.assertEqual(n, 1)
        self.assertEqual((clip.orig_start, clip.orig_end), (20.0, 60.0))

    def test_multi_scene_core_unions(self):
        from app.exporters import expand_material_spans
        clip = ExportClip("main", 0.0, 2.0, 55.0, 65.0, "HIGH", 0.9)   # 跨镜头 2/3
        expand_material_spans([clip], self.scenes, max_span_s=100.0)
        self.assertEqual((clip.orig_start, clip.orig_end), (20.0, 100.0))   # 并集到镜头边界

    def test_long_scene_falls_back_to_core(self):
        from app.exporters import expand_material_spans
        scenes = np.array([[0.0, 200.0]], dtype=np.float32)
        clip = ExportClip("main", 0.0, 2.0, 30.0, 39.0, "HIGH", 0.9)
        n = expand_material_spans([clip], scenes, max_span_s=60.0)
        self.assertEqual(n, 0)                                # >60s 长场景不扩
        self.assertEqual((clip.orig_start, clip.orig_end), (30.0, 39.0))

    def test_no_scenes_noop(self):
        from app.exporters import expand_material_spans
        clip = ExportClip("main", 0.0, 2.0, 30.0, 39.0, "HIGH", 0.9)
        self.assertEqual(expand_material_spans([clip], None), 0)
        self.assertEqual((clip.orig_start, clip.orig_end), (30.0, 39.0))


class PlanJianyingAssetsTest(unittest.TestCase):
    """剪映素材计划（2026-10-07 语义统一）：逐 clip 一条素材、原速顺序卷轴；
    去重统一由上游 ``trim_adjacent_source_overlaps`` 承担（不再回并）。"""

    def test_no_merge_one_asset_per_clip(self):
        plan = [
            ExportClip("main", 0.0, 2.0, 2154.0, 2156.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 2.5, 4.5, 2155.0, 2157.0, "HIGH", 0.9, seg_index=1),  # 非贴接重叠=真实复用，保留
            ExportClip("main", 5.0, 9.0, 2180.0, 2182.0, "HIGH", 0.9, seg_index=2),
            ExportClip("sub", 5.0, 6.0, 2200.0, 2201.0, "HIGH", 0.8, seg_index=2, sub_index=0),  # 候选 → 不出
        ]
        assets = plan_jianying_assets(plan)
        self.assertEqual(len(assets), 3)
        self.assertEqual((assets[0].orig_start, assets[0].orig_end), (2154.0, 2156.0))
        self.assertEqual((assets[1].orig_start, assets[1].orig_end), (2155.0, 2157.0))
        self.assertEqual((assets[2].orig_start, assets[2].orig_end), (2180.0, 2182.0))
        # 顺序卷轴：0-2s、2-4s、4-6s；全部原速
        p0, p1, p2 = (a.placements[0] for a in assets)
        self.assertEqual((p0["edited_start"], p0["edited_end"]), (0.0, 2.0))
        self.assertEqual((p1["edited_start"], p1["edited_end"]), (2.0, 4.0))
        self.assertEqual((p2["edited_start"], p2["edited_end"]), (4.0, 6.0))
        self.assertTrue(all(p["speed"] == 1.0 for p in (p0, p1, p2)))

    def test_trimmed_adjacent_pair_yields_disjoint_assets(self):
        # 生产接线（export_project 剪映分支）= 取材扩展后先 trim 再组卷轴：
        # 贴接对源区间交叠 1s，trim 中点切开后两条素材源区间相接不重叠。
        from app.exporters import trim_adjacent_source_overlaps
        plan = [
            ExportClip("main", 0.0, 2.0, 100.0, 102.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 2.0, 4.0, 101.0, 103.0, "HIGH", 0.9, seg_index=1),
        ]
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=25.0), 1)
        assets = plan_jianying_assets(plan)
        self.assertEqual(len(assets), 2)
        self.assertEqual(assets[0].orig_end, assets[1].orig_start)   # 相接
        self.assertEqual(assets[1].orig_end, 103.0)                  # 并集右界不变
        t = 0.0
        for a in assets:
            self.assertEqual(a.placements[0]["edited_start"], round(t, 3))
            t += a.orig_width

    def test_identical_range_reuse_shares_stem(self):
        # 区间逐字节相同 → 同名素材（同内容共文件），不触发撞名加序号。
        # 中间隔一条不同取材：既避开「紧邻同素材去重」（续63 补二会把连放两遍的相同素材
        # 合成一条），也是真实复用在时间线上该有的形态。
        plan = [
            ExportClip("main", 0.0, 2.0, 20.0, 60.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 10.0, 12.0, 300.0, 302.0, "HIGH", 0.9, seg_index=1),
            ExportClip("main", 30.0, 32.0, 20.0, 60.0, "HIGH", 0.9, seg_index=2),
        ]
        assets = plan_jianying_assets(plan)
        self.assertEqual(len(assets), 3)
        self.assertEqual(assets[0].file_stem, assets[2].file_stem)

    def test_nearby_range_stem_collision_gets_suffix(self):
        # 区间不同但秒级取整撞名 → 第二条加序号，防 extract 拿错内容。
        plan = [
            ExportClip("main", 0.0, 2.0, 20.4, 60.4, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 30.0, 32.0, 20.6, 60.6, "HIGH", 0.9, seg_index=1),
        ]
        assets = plan_jianying_assets(plan)
        self.assertNotEqual(assets[0].file_stem, assets[1].file_stem)

    def test_empty_plan(self):
        self.assertEqual(plan_jianying_assets([]), [])

    def test_adjacent_identical_material_appears_once(self):
        """续63 补二（默认开）：剪辑序相邻 + 源区间逐字节相同 = 卷轴里同一段画面连放
        两遍（r15 包内实测 2mkv ``og1373-1397`` 连放 24s）⇒ 后一条不出素材。"""
        plan = [
            ExportClip("main", 0.0, 1.1, 1373.0, 1397.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 2.13, 3.7, 1373.0, 1397.0, "HIGH", 0.9, seg_index=1),
        ]
        assets = plan_jianying_assets(plan)
        self.assertEqual([(a.orig_start, a.orig_end) for a in assets], [(1373.0, 1397.0)])
        self.assertEqual(assets[0].placements[0]["edited_end"], 24.0)   # 原速一条
        # 关掉开关回到逐 clip 两条（口径可回退）
        self.assertEqual(len(plan_jianying_assets(plan, drop_adjacent_duplicates=False)), 2)

    def test_only_immediately_adjacent_and_only_exactly_equal(self):
        """保守边界：中间隔着别条素材不算重复；嵌套前缀（不同取材）一律保留。"""
        plan = [
            ExportClip("main", 0.0, 1.0, 100.0, 127.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 2.0, 3.0, 500.0, 502.0, "HIGH", 0.9, seg_index=1),
            ExportClip("main", 4.0, 5.0, 100.0, 127.0, "HIGH", 0.9, seg_index=2),  # 隔了一条
            ExportClip("main", 6.0, 7.0, 100.0, 113.0, "HIGH", 0.9, seg_index=3),  # 嵌套前缀
        ]
        assets = plan_jianying_assets(plan)
        self.assertEqual([(a.orig_start, a.orig_end) for a in assets],
                         [(100.0, 127.0), (500.0, 502.0), (100.0, 127.0), (100.0, 113.0)])

    def test_dedup_does_not_lose_any_footage(self):
        """去重后并集覆盖必须不变（相同区间本就不增加覆盖）+ placement 仍首尾相接。"""
        plan = [ExportClip("main", float(i), float(i) + 1.0, 1373.0, 1397.0,
                           "HIGH", 0.9, seg_index=i) for i in range(4)]
        assets = plan_jianying_assets(plan)
        self.assertEqual(len(assets), 1)
        for a, b in zip(assets, assets[1:]):
            self.assertEqual(a.placements[0]["edited_end"], b.placements[0]["edited_start"])


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists() and SYNTH.exists(),
                     "real FFmpegIO assets not present")
class WriteJianyingDraftIntegrationTest(unittest.TestCase):
    """剪映导出 v2 集成：真抽 H.264 clip → pyJianYingDraft 写草稿 → 结构断言。"""

    def test_draft_written(self):
        import json
        from media.ffmpeg import FFmpegIO
        from app.exporters import (create_jianying_draft_dir, write_jianying_draft,
                                   trim_adjacent_source_overlaps)

        io = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)
        plan = [
            ExportClip("main", 0.0, 2.0, 0.0, 2.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 2.0, 3.0, 1.5, 3.0, "HIGH", 0.9, seg_index=1),  # 贴接重叠 → trim 中点切开
        ]
        # 生产同款接线：组卷轴前先施加统一去重（export_project 剪映分支同参）
        self.assertEqual(trim_adjacent_source_overlaps(plan, fps=25.0), 1)
        assets = plan_jianying_assets(plan)
        out_root = Path(tempfile.mkdtemp())
        draft_dir, script = create_jianying_draft_dir(out_root, "it draft", fps=30.0,
                                                      width=1280, height=720)
        clips_dir = draft_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        for asset in assets:
            clip_path = clips_dir / f"{asset.file_stem}.mp4"
            io.extract_clip(SYNTH, asset.orig_start, asset.orig_end, clip_path,
                            preset="veryfast", crf=20)
            asset.clip_path = clip_path
            asset.clip_duration = float(io.metadata(clip_path).duration)
        ret = write_jianying_draft(script, assets, draft_dir)
        self.assertEqual(ret, draft_dir)
        content = json.loads((draft_dir / "draft_content.json").read_text(encoding="utf-8"))
        tracks = content["tracks"]
        self.assertEqual([t.get("name") for t in tracks], ["located"])   # 单轨，无候选轨
        segs = [s for t in tracks for s in t["segments"]]
        self.assertEqual(len(segs), 2)                                   # trim 后两条素材（不再回并）
        self.assertEqual(len(content["materials"]["videos"]), 2)
        self.assertTrue(all(s["speed"] == 1.0 for s in segs))            # 原速
        # 并集保持：两条素材首尾相接铺满 0-3s（交叠只裁掉重复那份）
        total = sum(s["target_timerange"]["duration"] for s in segs)
        self.assertAlmostEqual(total / 1_000_000, 3.0, delta=0.15)
        self.assertEqual(segs[0]["target_timerange"]["start"], 0)
        # 素材路径指向草稿内 clips；时间单位必须为微秒（trange float 陷阱回归）
        for v in content["materials"]["videos"]:
            self.assertTrue((Path(v["path"])).exists())


# --------------------------------------------------------------------- #
# 剪映片段变速：source=round(target×speed) 绝不越素材时长（真机 r19 崩溃回归）
# --------------------------------------------------------------------- #
class JianyingSegmentSpeedTest(unittest.TestCase):
    """pyJianYingDraft 里 source_timerange = round(target×speed)，> material.duration 直接抛
    ValueError 打死整条导出。真机支持档：一段 <0.1s 短镜头被 0.1s 下限撑成 100000µs、
    素材只有 64000µs ⇒ 崩（UI 误报「无法连接后端服务 fetch failed」）。"""

    def test_normal_material_locks_original_speed(self):
        # 素材 >= target：逐字保持原速 1.0（集成测试断言的常态）
        sp = _jianying_segment_speed(5_000_000, 5_000_000, 5.0, 5.0)
        self.assertEqual(sp, 1.0)

    def test_short_material_does_not_overflow(self):
        # 真机崩溃形态：target 100000µs、素材 64000µs ⇒ 必须回压速度使 source 落进素材
        target_us, mat_us = 100_000, 64_000
        sp = _jianying_segment_speed(target_us, mat_us, orig_width=0.05, mat_dur=0.064)
        self.assertLess(sp, 1.0)
        self.assertLessEqual(round(target_us * sp), mat_us)

    def test_marginal_short_reencode_does_not_overflow(self):
        # 素材比 target 短 0.2%（重编码少一帧）：旧写法会锁 1.0 → source=target>素材 → 崩
        target_us, mat_us = 5_000_000, 4_990_000
        sp = _jianying_segment_speed(target_us, mat_us, orig_width=5.0, mat_dur=4.99)
        self.assertLessEqual(round(target_us * sp), mat_us)

    def test_write_jianying_draft_routes_through_helper(self):
        """结构锁：write_jianying_draft 的 per-placement 变速必须走 _jianying_segment_speed，
        不得再把公式内联回去（否则越界回归会静默复发）。"""
        import inspect
        from app.exporters import write_jianying_draft
        src = inspect.getsource(write_jianying_draft)
        self.assertIn("_jianying_segment_speed", src)
        self.assertNotIn("max(0.1, min(mat_dur", src)   # 旧内联判据不得复活


# --------------------------------------------------------------------- #
# 取材扩宽相对护栏（2026-10-11 B）：短切不被撑进比自身大 rel_cap 倍的（疑似漏切）镜头
# --------------------------------------------------------------------- #
class ExpandMaterialSpansGuardTest(unittest.TestCase):
    def setUp(self):
        import numpy as np
        # 假镜头表：[0,1] 小、[1,41] 是被漏切并成的 40s 假大镜头、[50,52] 是 2s 真镜头
        self.scenes = np.array([[0.0, 1.0], [1.0, 41.0], [50.0, 52.0]])

    def _clips(self):
        # clipX: 1s 核心落在 40s 假镜头内（应被护栏挡住）；clipY: 1s 核心在 2s 真镜头内（应放行）
        return [
            ExportClip("main", 0.0, 1.0, 2.0, 3.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 1.0, 2.0, 50.5, 51.5, "HIGH", 0.9, seg_index=1),
        ]

    def test_guard_blocks_short_cut_into_huge_scene(self):
        from app.exporters import expand_material_spans
        clips = self._clips()
        n = expand_material_spans(clips, self.scenes, max_span_s=60.0, rel_cap=2.5)
        self.assertEqual(n, 1)
        self.assertEqual((clips[0].orig_start, clips[0].orig_end), (2.0, 3.0))  # X 未扩
        self.assertEqual((clips[1].orig_start, clips[1].orig_end), (50.0, 52.0))  # Y 扩到真镜头

    def test_guard_off_restores_legacy_behavior(self):
        from app.exporters import expand_material_spans
        clips = self._clips()
        n = expand_material_spans(clips, self.scenes, max_span_s=60.0, rel_cap=0.0)
        self.assertEqual(n, 2)  # 关掉护栏 → X 也被撑成 [1,41]
        self.assertEqual((clips[0].orig_start, clips[0].orig_end), (1.0, 41.0))

    def test_abs_cap_still_independent(self):
        from app.exporters import expand_material_spans
        clips = self._clips()
        # rel_cap 关闭，但绝对上限 10s 仍能挡住 40s 假镜头；2s 真镜头照扩
        n = expand_material_spans(clips, self.scenes, max_span_s=10.0, rel_cap=0.0)
        self.assertEqual(n, 1)
        self.assertEqual((clips[0].orig_start, clips[0].orig_end), (2.0, 3.0))

    def test_prepare_channel_plan_threads_rel_cap(self):
        # 结构锁：prepare_channel_plan 必须把 rel_cap 透传给 expand_material_spans（否则旋钮是死值）
        import inspect
        from app.exporters import prepare_channel_plan
        src = inspect.getsource(prepare_channel_plan)
        self.assertIn("material_expand_rel_cap", src)
        self.assertIn("rel_cap=float(material_expand_rel_cap)", src)


# --------------------------------------------------------------------- #
# service.export_project 接线
# --------------------------------------------------------------------- #
class TestServiceExportProject(unittest.TestCase):
    def _service(self, bundle=None, store_error=None):
        from app import SourceLocatorService
        from infrastructure.config import AppConfig
        cfg = AppConfig()
        cfg.media.ffmpeg_path = "ffmpeg"      # 不触发真实 resolve（fake 注入在先）
        cfg.media.ffprobe_path = "ffprobe"
        svc = SourceLocatorService(config=cfg, index_root=tempfile.mkdtemp(),
                                   export_root=tempfile.mkdtemp())
        svc._store = _FakeStore(bundle=bundle, error=store_error)
        svc._ffmpeg = _FakeFFmpeg(fps=25.0)
        return svc

    def _batch(self):
        return _batch([
            _result(ed=(0.0, 2.0), orig=(99.7, 101.3), level="HIGH"),
            _result(ed=(2.0, 4.0), orig=(200.0, 201.0), level="LOW"),
        ])

    def test_invalid_format(self):
        svc = self._service()
        with self.assertRaises(ApplicationError):
            svc.export_project(self._batch(), fmt="premiere_bin")

    def test_no_original_video(self):
        svc = self._service()
        batch = _batch([_result()])
        batch.original_video = None
        with self.assertRaises(ApplicationError):
            svc.export_project(batch, fmt="edl")

    def test_edl_written_and_snapped(self):
        scenes = np.array([[0.0, 100.0], [100.0, 250.0]], dtype=np.float32)
        svc = self._service(bundle=_FakeBundle(scenes=scenes, duration=3600.0))
        out = tempfile.mkdtemp()
        path = svc.export_project(self._batch(), fmt="edl", out_dir=out)
        self.assertTrue(path.name.endswith(".loc.edl"))
        text = path.read_text(encoding="utf-8")
        # 99.7 -> 吸附到 100.0；LOW 默认不导 -> 只有 1 个事件
        self.assertIn("00:01:40:00", text)
        self.assertEqual(len([ln for ln in text.splitlines() if ln[:3].isdigit()]), 1)

    def test_low_backup_policy(self):
        svc = self._service(bundle=_FakeBundle(scenes=None))
        out = tempfile.mkdtemp()
        path = svc.export_project(self._batch(), fmt="edl", out_dir=out,
                                  low_policy="backup")
        text = path.read_text(encoding="utf-8")
        self.assertEqual(len([ln for ln in text.splitlines() if ln[:3].isdigit()]), 2)
        self.assertIn("conf=LOW", text)

    def test_snap_downgrades_without_index(self):
        svc = self._service(store_error=RuntimeError("index gone"))
        out = tempfile.mkdtemp()
        path = svc.export_project(self._batch(), fmt="edl", out_dir=out)
        text = path.read_text(encoding="utf-8")
        self.assertIn("00:01:39:17", text)     # 99.7s 未吸附（索引不可用降级）

    def test_fcp7_xml_outputs(self):
        scenes = np.array([[0.0, 100.0], [100.0, 250.0]], dtype=np.float32)
        svc = self._service(bundle=_FakeBundle(scenes=scenes))
        out = tempfile.mkdtemp()
        xml_path = svc.export_project(self._batch(), fmt="fcp7_xml", out_dir=out,
                                      low_policy="backup")
        root = ET.fromstring(xml_path.read_text(encoding="utf-8"))
        self.assertEqual(len(root.findall(".//track")), 2)   # main + low

    def test_jianying_needs_real_media(self):
        """jianying 导出路径依赖真实 ffmpeg 抽 clip（集成测试覆盖）；fake 下报错即语义正确。"""
        svc = self._service(bundle=_FakeBundle(scenes=None))
        out = tempfile.mkdtemp()
        with self.assertRaises(Exception):
            svc.export_project(self._batch(), fmt="jianying", out_dir=out)

    def test_jianying_branch_trims_before_planning(self):
        """接线锁（2026-10-07 语义统一）：剪映分支在取材扩展后、组卷轴前施加
        ``trim_adjacent_source_overlaps`` ⇒ 传给 ``plan_jianying_assets`` 的计划
        已无贴接交叠（与成片/EDL/XML 一套去重）。"""
        svc = self._service(bundle=_FakeBundle(scenes=None))
        out = tempfile.mkdtemp()
        batch = _batch([
            _result(ed=(0.0, 2.0), orig=(100.0, 102.0), level="HIGH"),
            _result(ed=(2.0, 4.0), orig=(101.0, 103.0), level="HIGH"),   # 贴接重叠 1s
        ])
        captured: dict = {}

        def _fake_plan(plan, **kw):
            captured["plan"] = [(c.orig_start, c.orig_end) for c in plan]
            captured["kw"] = kw
            return []

        with mock.patch("app.locator_service.plan_jianying_assets", _fake_plan), \
                mock.patch("app.locator_service.create_jianying_draft_dir",
                           return_value=(mock.MagicMock(), mock.MagicMock())), \
                mock.patch("app.locator_service.write_jianying_draft"):
            svc.export_project(batch, fmt="jianying", out_dir=out)
        self.assertEqual(captured["plan"], [(100.0, 101.5), (101.5, 103.0)])

    def test_export_results_json_still_works(self):
        svc = self._service()
        out = tempfile.mkdtemp()
        path = svc.export_project(self._batch(), fmt="edl", out_dir=out)
        self.assertTrue(path.exists())
        batch = self._batch()
        p2 = svc.export_results(batch, out_dir=out)
        self.assertTrue(p2.name.endswith(".results.json"))
        self.assertIsNotNone(svc.load_results(p2))


if __name__ == "__main__":
    unittest.main()


class TemporalRepairTest(unittest.TestCase):
    """时序离群修复（test1 r18 实证）：前后段定位彼此接近、本段远离 → 窗口内重定位。"""

    def test_find_outliers(self):
        from engine.localization import find_temporal_outliers
        # r18 形态：前后段都在 60 分钟附近，中段跳到 47 分钟 → 中段离群
        positions = [(60.0, 63.0), (2870.0, 2872.0), (60.4, 62.0), (500.0, 502.0)]
        # i=1: prev=(60,63) next=(60.4,62) 相近(1s)；cur=2871 距两者 >600s → 离群
        self.assertEqual(find_temporal_outliers(positions), [1])
        # i=2: prev=(2870,2872) next=(500,502) 相距远 → 不触发
        self.assertNotIn(2, find_temporal_outliers(positions))

    def test_relocate_in_window(self):
        import numpy as np
        from engine.localization import relocate_in_window
        rng = np.random.RandomState(0)
        feats = rng.randn(100, 384).astype(np.float32) * 0.1
        target = rng.randn(384).astype(np.float32)
        feats[55:58] = target + 0.05 * rng.randn(3, 384).astype(np.float32)
        feats /= np.linalg.norm(feats, axis=1, keepdims=True)
        times = np.arange(100, dtype=np.float64)
        got = relocate_in_window(target, feats, times, (40.0, 70.0), 3.0)
        self.assertIsNotNone(got)
        self.assertEqual(got, (55.0, 58.0))

    def test_neutral_sequence_not_flagged(self):
        from engine.localization import find_temporal_outliers
        # 单调递增的正常序列 → 无离群
        positions = [(10.0, 12.0), (50.0, 52.0), (90.0, 92.0), (130.0, 132.0)]
        self.assertEqual(find_temporal_outliers(positions), [])
        # 小幅乱序（<10min）不触发
        positions = [(10.0, 12.0), (90.0, 92.0), (50.0, 52.0), (130.0, 132.0)]
        self.assertEqual(find_temporal_outliers(positions), [])
