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

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from app.exporters import (ExportClip, build_export_plan, plan_jianying_assets,
                           render_edl, render_fcp7_xml, seconds_to_frames,
                           snap_clips_to_scenes, timecode_ndf)
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
        self.assertEqual(file_el.findtext("pathurl"),
                         "file://localhost/D:/src/2.mkv")
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
    """剪映素材计划 v3（反馈二轮）：只出主定位单轨、合并重叠、原速顺序卷轴。"""

    def test_merge_overlap_and_sequential(self):
        plan = [
            ExportClip("main", 0.0, 2.0, 2154.0, 2156.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 2.5, 4.5, 2155.0, 2157.0, "HIGH", 0.9, seg_index=1),  # 重叠 1s → 合并
            ExportClip("main", 5.0, 9.0, 2180.0, 2182.0, "HIGH", 0.9, seg_index=2),  # 有间隔 → 独立
            ExportClip("sub", 5.0, 6.0, 2200.0, 2201.0, "HIGH", 0.8, seg_index=2, sub_index=0),  # 候选 → 不出
        ]
        assets = plan_jianying_assets(plan)
        self.assertEqual(len(assets), 2)
        self.assertEqual((assets[0].orig_start, assets[0].orig_end), (2154.0, 2157.0))
        self.assertEqual((assets[1].orig_start, assets[1].orig_end), (2180.0, 2182.0))
        # 顺序卷轴：0-3s、3-5s；全部原速
        p0, p1 = assets[0].placements[0], assets[1].placements[0]
        self.assertEqual((p0["edited_start"], p0["edited_end"]), (0.0, 3.0))
        self.assertEqual((p1["edited_start"], p1["edited_end"]), (3.0, 5.0))
        self.assertEqual(p0["speed"], 1.0)
        self.assertEqual(p1["speed"], 1.0)

    def test_empty_plan(self):
        self.assertEqual(plan_jianying_assets([]), [])


@unittest.skipUnless(FFMPEG.exists() and FFPROBE.exists() and SYNTH.exists(),
                     "real FFmpegIO assets not present")
class WriteJianyingDraftIntegrationTest(unittest.TestCase):
    """剪映导出 v2 集成：真抽 H.264 clip → pyJianYingDraft 写草稿 → 结构断言。"""

    def test_draft_written(self):
        import json
        from media.ffmpeg import FFmpegIO
        from app.exporters import (create_jianying_draft_dir, write_jianying_draft)

        io = FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE)
        plan = [
            ExportClip("main", 0.0, 2.0, 0.0, 2.0, "HIGH", 0.9, seg_index=0),
            ExportClip("main", 2.0, 3.0, 1.5, 3.0, "HIGH", 0.9, seg_index=1),  # 重叠 → 合并为 0-3s
        ]
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
        self.assertEqual(len(segs), 1)                                   # 重叠合并 → 1 段
        self.assertEqual(len(content["materials"]["videos"]), 1)
        self.assertEqual(segs[0]["speed"], 1.0)                          # 原速
        self.assertEqual(segs[0]["target_timerange"]["duration"], 3_000_000)  # 0-3s
        # 速度语义：剪辑 2s / 源 2s → speed 1.0；素材路径指向草稿内 clips
        for v in content["materials"]["videos"]:
            self.assertTrue((Path(v["path"])).exists())
        # 时间单位必须为微秒（trange float 陷阱回归）
        main_track = next(t for t in tracks if t.get("name") == "located")
        s0 = main_track["segments"][0]
        self.assertEqual(s0["target_timerange"]["start"], 0)
        self.assertEqual(s0["target_timerange"]["duration"], 3_000_000)   # 合并后 0-3s


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
