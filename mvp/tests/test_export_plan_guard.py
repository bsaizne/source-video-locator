# -*- coding: utf-8 -*-
"""导出**计划层**常态守卫（2026-10-07 续63）。

动因：验收三指标读的是 ``Result`` 字段，只发生在导出/渲染计划层的缺陷在指标口径下
完全不可见——2026-10 连续两批真缺陷都是用户在真机肉眼 + 临时回放脚本发现的：

- 续62 主件：成片相邻段重复画面（``min_span_s=2.0`` 地板 vs 0.7~1.5s 剪辑段 ⇒ 贴接段
  源窗必然交叠），修 = ``trim_adjacent_source_overlaps``；
- 续62 补二：旧剪映卷轴"重叠回并"只看源区间，把源序回跳段**静默吞掉**（2mkv 并集覆盖
  152s→4.28s）。

两批的共同根因不是某个函数写错，而是**同一套计划序列在 service 里抄了三遍**，
出口之间会漏接。本文件锁两件事：

1. **结构锁**：``build_export_plan`` / ``trim_adjacent_source_overlaps`` 的产品调用点
   只允许存在于 ``exporters.prepare_channel_plan`` 内 ⇒ 新出口漏接 = 测试红（AST 扫描）。
2. **不变式锁**：序列自带 ``audit_pre_trim`` / ``audit`` 两份计划层体检，四个出口都必须
   满足「贴接重叠裁到 0 / 并集覆盖 Δ=0 / 真实复用（非贴接重叠）不动」。
"""
from __future__ import annotations

import ast
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np  # noqa: E402

from app.exporters import (CHANNELS, EXPORT_FORMATS, ExportClip,  # noqa: E402
                           audit_source_overlaps, prepare_channel_plan)
from app.locator_service import SourceLocatorService  # noqa: E402
from infrastructure.config import AppConfig  # noqa: E402

from tests.test_exporters import (_FakeBundle, _FakeMeta, _FakeStore,  # noqa: E402
                                  _batch, _result)

MVP_SRC = Path(__file__).resolve().parents[1] / "src"


class _FakeIO:
    """渲染编排要两个二进制路径，导出要 fps；全程不碰真 ffmpeg。"""

    ffmpeg = Path("D:/tools/ffmpeg.exe")
    ffprobe = Path("D:/tools/ffprobe.exe")

    def metadata(self, path):
        return _FakeMeta(fps=25.0)


# --------------------------------------------------------------------- #
def _clip(ed, orig, kind="main", **kw) -> ExportClip:
    return ExportClip(kind=kind, edited_start=ed[0], edited_end=ed[1],
                      orig_start=orig[0], orig_end=orig[1],
                      confidence=kw.pop("confidence", "HIGH"), **kw)


class AuditSourceOverlapsTest(unittest.TestCase):
    """只读体检量的口径（与 trim 同一配对口径：编辑序相邻、gap ≤ 0.05s 算贴接）。"""

    def test_clean_plan_all_zero(self):
        a = audit_source_overlaps([_clip((0, 2), (100, 102)), _clip((2, 4), (110, 112))])
        self.assertEqual(a["adjacent_pairs"], 1)
        self.assertEqual(a["adjacent_overlap_pairs"], 0)
        self.assertEqual(a["reuse_pairs"], 0)
        self.assertEqual(a["union_coverage_s"], 4.0)

    def test_adjacent_overlap_is_a_violation(self):
        a = audit_source_overlaps([_clip((0, 1), (100, 102)), _clip((1, 2), (101, 103))])
        self.assertEqual((a["adjacent_overlap_pairs"], a["adjacent_dup_s"]), (1, 1.0))
        self.assertEqual(a["reuse_pairs"], 0)

    def test_non_adjacent_overlap_counted_as_reuse_not_violation(self):
        """两段之间还夹着别的记录内容 ⇒ 源区间重叠 = 真实复用，只计数（口径边界）。
        注意这对不**紧邻**（第 1 段与第 3 段），所以体检必须扫全对。"""
        plan = [_clip((0, 1), (100, 102)), _clip((1, 2), (120, 122)),
                _clip((2, 3), (101, 103))]
        a = audit_source_overlaps(plan)
        self.assertEqual(a["adjacent_overlap_pairs"], 0)
        self.assertEqual((a["reuse_pairs"], a["reuse_dup_s"]), (1, 1.0))
        self.assertEqual(a["adjacent_pairs"], 2)

    def test_subs_and_zero_width_excluded_from_ranges(self):
        plan = [_clip((0, 2), (100, 102)),
                _clip((0, 1), (500, 501), kind="sub", seg_index=0, sub_index=0),
                _clip((2, 3), (102, 102), kind="main")]     # 零宽
        a = audit_source_overlaps(plan)
        self.assertEqual(a["n_clips"], 2)          # sub 不计
        self.assertEqual(a["zero_width"], 1)
        self.assertEqual(a["union_coverage_s"], 2.0)

    def test_low_kind_counts_and_touching_not_overlap(self):
        plan = [_clip((0, 2), (100, 102), kind="low"), _clip((2, 4), (102, 104), kind="low")]
        a = audit_source_overlaps(plan)
        self.assertEqual(a["n_clips"], 2)
        self.assertEqual(a["adjacent_overlap_pairs"], 0)   # 相接不算交叠


class PrepareChannelPlanTest(unittest.TestCase):
    """四通道共用序列：参数差异 allowed，序列差异禁止；序列自检量成立。"""

    def _adjacent_batch(self):
        return _batch([_result(ed=(0.0, 1.0), orig=(100.0, 102.0)),
                       _result(ed=(1.0, 2.0), orig=(101.0, 103.0))])

    def test_invalid_channel_rejected(self):
        with self.assertRaises(ValueError):
            prepare_channel_plan(self._adjacent_batch(), channel="premiere_bin")

    def test_channels_cover_every_product_exit(self):
        """通道清单 = 成片 + 三种 NLE 工程；漏登记一个出口，守卫就只看得到三个。"""
        self.assertEqual(set(CHANNELS), {"movie"} | set(EXPORT_FORMATS))

    def test_trims_and_reports_invariants(self):
        plan, st = prepare_channel_plan(self._adjacent_batch(), channel="edl", fps=25.0)
        self.assertEqual([t for t in (st["audit_pre_trim"]["adjacent_overlap_pairs"],
                                      st["audit"]["adjacent_overlap_pairs"])], [1, 0])
        self.assertEqual(st["n_trim"], 1)
        self.assertEqual([(c.orig_start, c.orig_end) for c in plan],
                         [(100.0, 101.5), (101.5, 103.0)])
        self.assertEqual(st["audit"]["union_coverage_s"],
                         st["audit_pre_trim"]["union_coverage_s"])   # 一块画面不丢

    def test_no_scenes_all_channels_identical_plan(self):
        """无镜头表时四通道逐字段同 plan（一套语义的正面断言）。"""
        sig = {}
        for ch in CHANNELS:
            plan, st = prepare_channel_plan(self._adjacent_batch(), channel=ch, fps=25.0)
            sig[ch] = [(c.kind, c.edited_start, c.edited_end, c.orig_start, c.orig_end)
                       for c in plan]
            self.assertEqual(st["channel"], ch)
        self.assertEqual(list({tuple(v) for v in sig.values()}), [tuple(sig["movie"])])

    def test_expand_is_jianying_only(self):
        """硬约束：取材扩宽（核心窗→整镜头）是剪映卷轴专属语义。
        2026-10-07 收口当天把它误透给 EDL/XML/成片，包体探针实测 EDL 并集覆盖
        134s→531s（导出画面被整镜头撑大）⇒ 时间线通道误传直接报错，不许静默生效。"""
        batch = self._adjacent_batch()
        scenes = np.array([[95.0, 130.0]], dtype=np.float32)
        for ch in ("movie", "edl", "fcp7_xml"):
            with self.subTest(channel=ch):
                with self.assertRaises(ValueError):
                    prepare_channel_plan(batch, channel=ch, scenes=scenes,
                                         orig_duration=3600.0, material_expand=True)
        plan, st = prepare_channel_plan(batch, channel="jianying", scenes=scenes,
                                        orig_duration=3600.0, material_expand=True)
        self.assertEqual(st["n_expanded"], 2)
        # 扩宽后两段都变成整镜头 95-130（完全重合），再由去重叠按中点切开 ⇒ 一块画面不丢
        self.assertEqual([(c.orig_start, c.orig_end) for c in plan],
                         [(95.0, 112.5), (112.5, 130.0)])
        self.assertEqual(st["audit"]["union_coverage_s"],
                         st["audit_pre_trim"]["union_coverage_s"])

    def test_expand_then_trim_order_is_locked(self):
        """剪映取材扩宽把两段都撑成同一整镜头 ⇒ 交叠是扩宽**新造**的。
        去重叠若跑在扩宽之前就漏裁（2026-10-07 统一语义时踩过的顺序），所以顺序进锁。"""
        batch = _batch([_result(ed=(0.0, 2.0), orig=(100.0, 102.0)),
                        _result(ed=(2.0, 4.0), orig=(103.0, 105.0))])
        scenes = np.array([[100.0, 110.0]], dtype=np.float32)
        plan, st = prepare_channel_plan(batch, channel="jianying", scenes=scenes,
                                        orig_duration=3600.0, fps=25.0,
                                        material_expand=True)
        self.assertEqual(st["n_expanded"], 2)
        self.assertEqual(st["audit_pre_trim"]["adjacent_overlap_pairs"], 1)  # 扩宽撑出来的
        self.assertEqual(st["audit"]["adjacent_overlap_pairs"], 0)           # 被 trim 裁开
        self.assertEqual(st["audit"]["union_coverage_s"],
                         st["audit_pre_trim"]["union_coverage_s"])
        self.assertEqual([(c.orig_start, c.orig_end) for c in plan],
                         [(100.0, 105.0), (105.0, 110.0)])

    def test_expand_skipped_without_scenes(self):
        plan, st = prepare_channel_plan(self._adjacent_batch(), channel="jianying",
                                        scenes=None, material_expand=True, fps=25.0)
        self.assertEqual(st["n_expanded"], 0)

    def test_fragment_warnings_computed_on_gated_plan(self):
        """告警口径不变：在门槛之后、吸附/裁切之前算（只告警不裁，LOC-2001）。"""
        batch = _batch([_result(ed=(0.0, 1.0), orig=(100.0, 100.1))])
        plan, st = prepare_channel_plan(batch, channel="edl", min_clip_s=0.15, fps=25.0)
        self.assertEqual(len(st["warnings"]), 1)
        self.assertIn("LOC-2001", st["warnings"][0])
        self.assertEqual(st["audit"]["adjacent_overlap_pairs"], 0)
        self.assertEqual(len(plan), 1)     # 碎片仍在计划里（只告警）

    def test_reuse_pairs_survive_the_sequence(self):
        batch = _batch([_result(ed=(0.0, 1.0), orig=(100.0, 102.0)),
                        _result(ed=(1.0, 2.0), orig=(120.0, 122.0)),
                        _result(ed=(2.0, 3.0), orig=(101.0, 103.0))])
        plan, st = prepare_channel_plan(batch, channel="movie", fps=25.0)
        self.assertEqual(st["n_trim"], 0)
        self.assertEqual(st["audit"]["reuse_pairs"], 1)     # 第 1 段↔第 3 段：真实复用不裁
        self.assertEqual(st["audit"]["union_coverage_s"],
                         st["audit_pre_trim"]["union_coverage_s"])


class ServiceChannelWiringTest(unittest.TestCase):
    """运行时接线锁：三个 service 入口都走 ``prepare_channel_plan``，且各自出口的不变式成立。"""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.recorded: list[dict] = []

        real = prepare_channel_plan

        def spy(batch, **kw):
            plan, st = real(batch, **kw)
            self.recorded.append(st)
            return plan, st

        patcher = mock.patch("app.locator_service.prepare_channel_plan", spy)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _service(self, bundle=None, **render_overrides) -> SourceLocatorService:
        cfg = AppConfig()
        cfg.data_dir = self.tmp
        cfg.media.ffmpeg_path = "ffmpeg"
        cfg.media.ffprobe_path = "ffprobe"
        for key, value in render_overrides.items():
            setattr(cfg.render, key, value)
        svc = SourceLocatorService(config=cfg, index_root=self.tmp,
                                   export_root=self.tmp)
        svc._store = _FakeStore(bundle=bundle or _FakeBundle(scenes=None))
        svc._ffmpeg = _FakeIO()
        return svc

    def _batch(self):
        return _batch([_result(ed=(0.0, 1.0), orig=(100.0, 102.0)),
                       _result(ed=(1.0, 2.0), orig=(101.0, 103.0))])   # 贴接重叠 1s

    def _assert_invariants(self):
        self.assertTrue(self.recorded, "没有一次计划构建经过 prepare_channel_plan")
        for st in self.recorded:
            self.assertEqual(st["audit"]["adjacent_overlap_pairs"], 0,
                             f"{st['channel']} 出口仍有贴接重叠未裁开")
            self.assertEqual(st["audit"]["union_coverage_s"],
                             st["audit_pre_trim"]["union_coverage_s"],
                             f"{st['channel']} 出口裁重复时丢了画面")

    def test_movie_channel_routes_and_dedupes(self):
        with mock.patch("app.locator_service.TimelineMovieRenderer") as R:
            R.return_value.render.return_value = {
                "movie_path": Path(self.tmp) / "m.mp4", "mode": "copy", "reused": False,
                "segments": 2, "fps": "25", "duration_s": 3.0, "total_frames": 75,
                "actual_encoder": "libx264", "hdr_downgraded": False}
            info = self._service().render_movie(self._batch())
        self.assertEqual(self.recorded[-1]["channel"], "movie")
        self.assertEqual(info["clip_ranges"], [[100.0, 101.5], [101.5, 103.0]])
        self._assert_invariants()

    def test_nle_channels_route_with_their_own_channel_name(self):
        svc = self._service()
        for fmt in EXPORT_FORMATS:
            if fmt == "jianying":
                continue     # 需要真实抽帧，fake ffmpeg 下跑不到写完；由下面单独锁
            svc.export_project(self._batch(), fmt=fmt, out_dir=self.tmp)
            self.assertEqual(self.recorded[-1]["channel"], fmt)
        self._assert_invariants()

    def test_jianying_channel_routes_with_expand_on_and_assets_per_clip(self):
        svc = self._service()
        captured: dict = {}

        def _fake_plan_assets(plan, **kw):
            captured["ranges"] = [(c.orig_start, c.orig_end) for c in plan]
            captured["kw"] = kw
            return []

        with mock.patch("app.locator_service.plan_jianying_assets", _fake_plan_assets), \
                mock.patch("app.locator_service.create_jianying_draft_dir",
                           return_value=(mock.MagicMock(), mock.MagicMock())), \
                mock.patch("app.locator_service.write_jianying_draft"):
            svc.export_project(self._batch(), fmt="jianying", out_dir=self.tmp)
        self.assertEqual(self.recorded[-1]["channel"], "jianying")
        self.assertEqual(captured["ranges"], [(100.0, 101.5), (101.5, 103.0)])
        self.assertEqual(captured["kw"].get("drop_adjacent_duplicates"), True)
        self._assert_invariants()

    def test_timeline_channels_do_not_expand_material(self):
        """服务级口径锁（包体探针抓到的回归）：有镜头表时 EDL/XML 仍用核心窗，
        只有剪映卷轴把取材扩成整镜头。扩宽一旦漏进时间线通道，导出画面范围就变了。"""
        scenes = np.array([[95.0, 130.0]], dtype=np.float32)   # 覆盖两段的核心窗
        svc = self._service(bundle=_FakeBundle(scenes=scenes, duration=3600.0))
        for fmt in ("edl", "fcp7_xml"):
            svc.export_project(self._batch(), fmt=fmt, out_dir=self.tmp)
            self.assertEqual(self.recorded[-1]["channel"], fmt)
            self.assertEqual(self.recorded[-1]["n_expanded"], 0,
                             f"{fmt} 通道不该做取材扩宽")
        text = next(Path(self.tmp).glob("*.loc.edl")).read_text(encoding="utf-8")
        self.assertIn("orig=100.00-101.50", text)   # 核心窗裁开后的区间，未被撑到 95-130

    def test_export_warnings_still_surface(self):
        """收口后 ``last_export_warnings`` 仍来自同一告警腿（UI 契约不变）。"""
        svc = self._service()
        svc.export_project(_batch([_result(ed=(0.0, 1.0), orig=(100.0, 100.1))]),
                           fmt="edl", out_dir=self.tmp)
        self.assertTrue(any("LOC-2001" in w for w in svc.last_export_warnings),
                        svc.last_export_warnings)


class ExportPlanStructureLockTest(unittest.TestCase):
    """AST 结构锁：产品树里计划序列只能有一个入口。"""

    _GUARDED = ("build_export_plan", "trim_adjacent_source_overlaps")

    def _call_sites(self, name: str) -> list[str]:
        sites = []
        for py in sorted(MVP_SRC.rglob("*.py")):
            try:
                tree = ast.parse(py.read_text(encoding="utf-8"))
            except SyntaxError:
                continue
            rel = py.relative_to(MVP_SRC).as_posix()
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                fname = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                if fname != name:
                    continue
                enclosing = [n.name for n in ast.walk(tree)
                             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                             and any(x is node for x in ast.walk(n))]
                sites.append(f"{rel}:{node.lineno} in {','.join(enclosing) or '<module>'}")
        return sites

    def test_plan_sequence_has_a_single_product_call_site(self):
        for name in self._GUARDED:
            with self.subTest(fn=name):
                sites = self._call_sites(name)
                self.assertEqual(
                    sites, [s for s in sites if s.startswith("app/exporters.py")
                            and s.endswith("in prepare_channel_plan")],
                    f"{name} 出现第二处产品调用点 ⇒ 出口之间会漏接（应收进 "
                    f"prepare_channel_plan）：{sites}")

    def test_locatorservice_routes_through_the_helper(self):
        """service 侧必须调用共用序列，且不得残留裸序列步骤（漏接=回归）。"""
        src = (MVP_SRC / "app" / "locator_service.py").read_text(encoding="utf-8")
        self.assertGreaterEqual(src.count("prepare_channel_plan("), 2)   # 成片 + NLE
        for name in self._GUARDED + ("snap_clips_to_scenes",
                                     "split_clips_at_boundaries",
                                     "expand_material_spans"):
            self.assertNotIn(f"{name}(", src, f"service 里又出现裸的 {name}() 调用")


if __name__ == "__main__":
    unittest.main()
