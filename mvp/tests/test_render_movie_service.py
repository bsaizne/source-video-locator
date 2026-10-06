"""service 层成片渲染编排测试（2026-09-29 续30，竞品 video_renderer 移植）。

只验**编排**——clip 计划口径（门槛/不导规则/记录顺序）、阶段事件、错误分支、
配置旋钮透传；渲染执行本身见 :mod:`mvp.tests.test_timeline_render`。
``TimelineMovieRenderer`` 整体替换为假渲染器，测试全程不碰 ffmpeg。
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app.locator_service import SourceLocatorService
from app.models import ProgressEvent, ProgressStage
from domain import (Confidence, ConfidenceLevel, OriginalSegment, Result, ResultBatch,
                    TimeSpan)
from infrastructure.config import AppConfig
from infrastructure.errors import ApplicationError


class _FakeFfmpeg:
    """service 只把两个二进制路径转交渲染器；编排层不探测、不执行。"""

    ffmpeg = Path("D:/tools/ffmpeg.exe")
    ffprobe = Path("D:/tools/ffprobe.exe")


class RecordingRenderer:
    """记录入参并回放假成片信息的渲染器替身。"""

    calls: list[dict] = []

    def __init__(self, ffmpeg, ffprobe, out_dir, **kw):
        self.binaries = (ffmpeg, ffprobe)
        self.out_dir = Path(out_dir)
        self.kw = kw

    def render(self, clips, source, *, progress=None, cancel=None):
        RecordingRenderer.calls.append({
            "clips": [tuple(c) for c in clips],
            "source": Path(source),
            "out_dir": str(self.out_dir),
            "kw": self.kw,
            "binaries": self.binaries,
        })
        if progress is not None:
            progress(0.0, "开始渲染成片（2 段）")
            progress(None, "片段 1/2 渲染中，请稍候…")        # 心跳（None=无进展）
            progress(1.0, "最终视频生成成功")
        return {"movie_path": self.out_dir / "movie_fake.mp4", "mode": "copy",
                "reused": False, "segments": len(clips), "fps": "25",
                "duration_s": 4.0, "total_frames": 100,
                "actual_encoder": "libx264", "hdr_downgraded": False}


def _result(edited, original, level="HIGH", *, subs=(), not_in_source=False,
            failure=None, excluded=False) -> Result:
    r = Result(edited=TimeSpan(*edited), original=TimeSpan(*original),
               confidence=Confidence(ConfidenceLevel[level], 0.9, ("rank1",)),
               candidate_rank=1)
    r.not_in_source = not_in_source
    r.failure_reason = failure
    r.excluded = excluded
    r.original_segments = [OriginalSegment(start=a, end=b, cover=0.5, score=0.4)
                           for a, b in subs]
    return r


def _batch(results, original="D:/v/om.mkv") -> ResultBatch:
    return ResultBatch(schema_version=1, original_video=original,
                       edited_video="D:/e.mp4", results=list(results))


def _one(edited=(1.0, 2.0), original=(10.0, 11.0), level="HIGH") -> ResultBatch:
    return _batch([_result(edited, original, level)])


def _service(tmp: Path, **render_overrides) -> SourceLocatorService:
    cfg = AppConfig()
    cfg.data_dir = tmp                     # 隔离 app data，测试不写用户目录
    for key, value in render_overrides.items():
        setattr(cfg.render, key, value)
    return SourceLocatorService(config=cfg, ffmpeg=_FakeFfmpeg())


class RenderMoviePlanTest(unittest.TestCase):
    def setUp(self):
        RecordingRenderer.calls = []
        patcher = mock.patch("app.locator_service.TimelineMovieRenderer", RecordingRenderer)
        patcher.start()
        self.addCleanup(patcher.stop)
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = Path(holder.name)

    def _call(self, batch, **kw):
        _service(self.tmp, **kw.pop("render", {})).render_movie(batch, **kw)
        return RecordingRenderer.calls[-1]

    def test_source_ranges_in_record_order_skipping_unresolved(self):
        batch = _batch([
            _result((10.0, 12.0), (300.0, 302.0)),
            _result((2.0, 4.0), (100.0, 102.0)),            # 编辑更早 → 排在前面
            _result((6.0, 8.0), (200.0, 202.0), not_in_source=True),
            _result((20.0, 21.0), (400.0, 401.0), failure="unresolved"),
        ])
        call = self._call(batch)
        self.assertEqual(call["clips"], [(100.0, 102.0), (300.0, 302.0)])
        self.assertEqual(call["source"], Path("D:/v/om.mkv"))
        self.assertEqual(call["binaries"], (Path("D:/tools/ffmpeg.exe"),
                                            Path("D:/tools/ffprobe.exe")))

    def test_adjacent_overlapping_segments_are_deduped_in_the_movie(self):
        """接线锁：相邻贴接段源区间重叠 ⇒ 送进渲染器的 clip 列表不再重复同一画面
        （2026-10-06 用户报「剪出的片里相邻两段有重合」，min_span_s=2.0 地板的常态）。"""
        batch = _batch([
            _result((0.0, 1.0), (100.0, 102.0)),
            _result((1.0, 2.0), (101.0, 103.0)),
        ])
        self.assertEqual(self._call(batch)["clips"], [(100.0, 101.5), (101.5, 103.0)])

    def test_contained_adjacent_segment_holes_out(self):
        """外层段被短段整个盖住 ⇒ 外层挖洞成头/尾两条，内层完整保留（一块画面不丢）。"""
        batch = _batch([
            _result((0.0, 2.0), (100.0, 110.0)),
            _result((2.0, 3.0), (103.0, 105.0)),
        ])
        self.assertEqual(self._call(batch)["clips"],
                         [(100.0, 103.0), (105.0, 110.0), (103.0, 105.0)])

    def test_non_adjacent_reuse_is_not_trimmed(self):
        """两段之间还夹着别的记录内容 ⇒ 源区间重叠是真实复用，不裁（口径边界锁）。"""
        batch = _batch([
            _result((0.0, 1.0), (100.0, 102.0)),
            _result((1.0, 2.0), (120.0, 122.0)),
            _result((2.0, 3.0), (101.0, 103.0)),
        ])
        self.assertEqual(self._call(batch)["clips"],
                         [(100.0, 102.0), (120.0, 122.0), (101.0, 103.0)])

    def test_movie_path_is_str_for_the_wire(self):
        """API/JSON 契约：service 出口把 Path 归一成字符串（此前 merge 也踩过同类坑）。"""
        info = _service(self.tmp).render_movie(_one())
        self.assertIsInstance(info["movie_path"], str)
        self.assertEqual(info["clips"], 1)

    def test_confidence_gate_and_low_policy(self):
        batch = _batch([_result((1.0, 2.0), (10.0, 11.0), "HIGH"),
                        _result((3.0, 4.0), (20.0, 21.0), "LOW")])
        self.assertEqual(self._call(batch)["clips"], [(10.0, 11.0)])   # 默认 MEDIUM 门槛
        self.assertEqual(self._call(batch, min_confidence="LOW",
                                     low_policy="backup")["clips"],
                         [(10.0, 11.0), (20.0, 21.0)])

    def test_excluded_and_zero_width_not_rendered(self):
        batch = _batch([_result((1.0, 2.0), (10.0, 11.0), excluded=True),
                        _result((3.0, 4.0), (20.0, 20.0)),   # 零宽源片区间
                        _result((5.0, 6.0), (30.0, 31.0))])
        self.assertEqual(self._call(batch, min_confidence="LOW")["clips"], [(30.0, 31.0)])

    def test_sub_spans_never_enter_the_movie(self):
        """反馈二轮口径延续：候选子 span 只供结果页复核，不进成片（与 NLE 工程一致）。"""
        batch = _batch([_result((1.0, 5.0), (10.0, 14.0),
                                subs=[(40.0, 44.0), (70.0, 74.0)])])
        self.assertEqual(self._call(batch)["clips"], [(10.0, 14.0)])

    def test_render_stage_events(self):
        seen: list[ProgressEvent] = []
        _service(self.tmp).render_movie(_one(), on_progress=seen.append)
        self.assertTrue(seen)
        self.assertTrue(all(e.stage is ProgressStage.RENDER_MOVIE for e in seen),
                        "渲染阶段必须独立于定位/文本导出阶段（worker 才能给它整条进度区间）")
        self.assertEqual(seen[-1].current, 100)
        self.assertEqual(seen[-1].total, 100)
        self.assertTrue(all(e.total == 100 for e in seen))

    def test_nothing_renderable_raises(self):
        with self.assertRaises(ApplicationError):
            _service(self.tmp).render_movie(_one(level="LOW"))

    def test_switch_off_raises(self):
        with self.assertRaises(ApplicationError) as ctx:
            _service(self.tmp, enabled=False).render_movie(_one())
        self.assertIn("render.enabled", str(ctx.exception))

    def test_missing_original_raises(self):
        """结果批没记住原片路径 ⇒ 无法渲染（与 export_project 同口径，尽早明确报错）。"""
        with self.assertRaises(ApplicationError):
            _service(self.tmp).render_movie(
                _batch([_result((1.0, 2.0), (10.0, 11.0))], original=""))
    def test_bad_strategy_values_rejected(self):
        svc = _service(self.tmp)
        with self.assertRaises(ApplicationError):
            svc.render_movie(_one(), min_confidence="VERY_HIGH")
        with self.assertRaises(ApplicationError):
            svc.render_movie(_one(), low_policy="keep")

    def test_config_knobs_passed_to_renderer(self):
        call = self._call(_one(), render=dict(crf=23, preset="fast", workers=1,
                                              prefer_hw=False, stall_timeout_s=7.0,
                                              timeout_s=9.0, sample_rate=44100))
        kw = call["kw"]
        self.assertEqual(kw["crf"], 23)
        self.assertEqual(kw["preset"], "fast")
        self.assertEqual(kw["workers"], 1)
        self.assertIs(kw["prefer_hw"], False)
        self.assertEqual(kw["stall_timeout_s"], 7.0)
        self.assertEqual(kw["timeout_s"], 9.0)
        self.assertEqual(kw["sample_rate"], 44100)

    def test_default_out_dir_is_app_data_rendered_root(self):
        call = self._call(_one())
        self.assertEqual(Path(call["out_dir"]), self.tmp / "rendered")

    def test_config_out_dir_then_explicit_out_dir_win(self):
        call = self._call(_one(), render=dict(out_dir=self.tmp / "cache"))
        self.assertEqual(Path(call["out_dir"]), self.tmp / "cache")
        call = self._call(_one(), render=dict(out_dir=self.tmp / "cache"),
                          out_dir=self.tmp / "user_exports")
        self.assertEqual(Path(call["out_dir"]), self.tmp / "user_exports")

    def test_index_unavailable_degrades_not_fails(self):
        """索引缺失 → 吸附/切点展开静默跳过，成片仍按主定位 span 渲染（只留日志）。"""
        svc = _service(self.tmp)
        with mock.patch.object(svc.store, "load_index", side_effect=RuntimeError("no index")):
            svc.render_movie(_one())
        self.assertEqual(RecordingRenderer.calls[-1]["clips"], [(10.0, 11.0)])

    def test_snap_moves_source_bounds_to_scene_cut(self):
        """吸附腿与 NLE 工程同源：±tol 内命中原片切点 → 成片用吸附后的边界。"""
        import numpy as np
        svc = _service(self.tmp)
        bundle = mock.Mock()
        bundle.scenes = np.array([[95.0, 100.2], [100.2, 104.1]])
        bundle.meta.duration = 200.0
        batch = _batch([_result((0.0, 4.0), (100.0, 104.0))])
        with mock.patch.object(svc.store, "load_index", return_value=bundle):
            svc.render_movie(batch)
        clips = RecordingRenderer.calls[-1]["clips"]
        self.assertEqual(len(clips), 1)
        self.assertIn(round(clips[0][0], 2), (100.0, 100.2))
        self.assertIn(round(clips[0][1], 2), (104.0, 104.1))


class RenderPathsTest(unittest.TestCase):
    def test_rendered_root_is_app_data_scoped(self):
        from infrastructure import paths
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        root = paths.rendered_root(override=Path(holder.name))
        self.assertEqual(root.name, "rendered")
        self.assertTrue(root.exists())


if __name__ == "__main__":
    unittest.main()
