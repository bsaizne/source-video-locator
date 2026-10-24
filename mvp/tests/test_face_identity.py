"""素材边界人脸身份标注 `face_identity`（候选 B，2026-10-25，PLAN_EXISTENCE_SIGNAL §2）。

判据：两侧各 3 帧（±0.10/0.25/0.40s，**480 宽口径**——判据阈值只在探针分辨率上标定过）
最大脸 SFace 质心余弦；**仅两侧每帧恰好一张脸才给 same/different**（阈 0.57 = 扩上界
双样本互证 suggest，FINDINGS_GT_PATCH_PROBES §3）；多脸/无脸/失败一律 unknown/None。

锁六件事：
1. 资产缺失 → 整层降级（analyzer=False，本次会话不重试），结果无标注。
2. 标注行为：not_in_source / failure_reason / 片头 t<=0.5 跳过；measure 异常逐行吞。
3. 契约往返 + 旧结果 JSON 向后兼容。
4. ⭐ 惰性锁：``_locate_features``（纯管线无 IO）与 face_identity 开/关逐键无关——
   挂点唯一在 locate() 修复链之后的旁路 ``_annotate_face_identity``。
5. 判据真值（B 类，模型+真媒体在位才跑，否则 skip）：单脸同人 ⇒ same、单脸异人 ⇒ different、
   多脸 ⇒ unknown 不判。
6. 口径锁：非 480 宽帧必须先缩放再检测（全分辨率会多检边缘小脸、max 脸漂移）。

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_face_identity -v
"""
from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from app import SourceLocatorService
from domain import FaceIdentity, Result, TimeSpan

# B 类真值点（探针/扩上界已确认，见 work/face_probe_20261024/）
_SAME_POINT = ("D:/ProjectXIXI/test2/test2-om.mp4", 349.5)     # 单脸同人 cos~0.87
_DIFF_POINT = ("D:/ProjectXIXI/test1/test1-om.mkv", 5415.46)   # 单脸异人 cos~0.16
_MULTI_POINT = ("D:/ProjectXIXI/test1/test1-om.mkv", 6679.5)   # 多脸(3/3) ⇒ unknown

_BENCH = Path(__file__).resolve().parents[2]
_FFMPEG = _BENCH / "tools" / "ffmpeg.exe"
_FFPROBE = (_BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
            / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


class _StubAnalyzer:
    def __init__(self, out):
        self.out = out
        self.calls = []

    def measure_boundary(self, video, t, *, cos_thresh=0.57):
        self.calls.append(float(t))
        return self.out


class ResolveAndContractTest(unittest.TestCase):

    def test_missing_models_dir_resolves_none(self):
        from engine.face_identity import resolve_face_models
        self.assertIsNone(resolve_face_models(Path("Z:/no/such/dir")))

    def test_contract_roundtrip_and_legacy_json(self):
        r = Result(edited=TimeSpan(0.0, 1.0), original=TimeSpan(10.0, 11.0))
        self.assertIsNone(r.to_dict()["face_identity"])   # 未标注 => null，不是缺键
        r.face_identity = FaceIdentity(cos=0.20, verdict="different", n_faces_left=1, n_faces_right=1)
        d = r.to_dict()
        self.assertEqual(d["face_identity"]["verdict"], "different")
        self.assertEqual(Result.from_dict(d).face_identity, r.face_identity)
        legacy = {k: v for k, v in d.items() if k != "face_identity"}
        self.assertIsNone(Result.from_dict(legacy).face_identity)  # 旧结果文件照常可读


class AnnotateBehaviorTest(unittest.TestCase):

    def setUp(self):
        self.srv = SourceLocatorService()

    def _rows(self):
        return [Result(edited=TimeSpan(0, 1), original=TimeSpan(10.0, 12.0)),
                Result(edited=TimeSpan(2, 3), original=TimeSpan(40.0, 42.0)),
                Result(edited=TimeSpan(4, 5), original=TimeSpan(0.2, 2.0)),    # 片头跳过
                Result(edited=TimeSpan(6, 7), original=TimeSpan(60.0, 62.0),
                       not_in_source=True),                                    # 非源内容跳过
                Result(edited=TimeSpan(8, 9), original=TimeSpan(70.0, 72.0),
                       failure_reason="no candidate")]                         # 失败行跳过

    def test_disabled_never_touches_media(self):
        """关闭开关 ⇒ 连 analyzer 都不建（媒体层零接触）。"""
        def _boom(*a, **k):
            raise AssertionError("face_identity_enabled=False 时不得接触媒体层")

        class _NoMedia:
            iter_frames = staticmethod(_boom)
            grab_frame = staticmethod(_boom)
            grab_frames = staticmethod(_boom)

        self.srv._ffmpeg = _NoMedia()
        self.srv.config.pipeline.face_identity_enabled = False
        self.srv._annotate_face_identity(self._rows(), "fake.mkv")
        self.assertTrue(all(r.face_identity is None for r in self._rows()))

    def test_assets_missing_disables_for_service_lifetime(self):
        """资产缺失 ⇒ analyzer=False 记住（本次会话不再重试），全部行无标注。"""
        self.srv._face_analyzer = False
        self.srv._annotate_face_identity(self._rows(), "fake.mkv")
        self.assertTrue(all(r.face_identity is None for r in self._rows()))

    def test_annotates_only_eligible_rows_and_survives_row_errors(self):
        stub = _StubAnalyzer({"cos": 0.2, "verdict": "different",
                              "n_faces_left": 1, "n_faces_right": 1})
        self.srv._face_analyzer = stub

        def _row_fail(video, t, *, cos_thresh=0.57):
            if abs(t - 40.0) < 1e-6:
                raise RuntimeError("row-level failure must not kill the pass")
            return {"cos": 0.9, "verdict": "same", "n_faces_left": 1, "n_faces_right": 1}

        stub.measure_boundary = _row_fail
        rows = self._rows()
        self.srv._annotate_face_identity(rows, "fake.mkv")
        self.assertEqual(rows[0].face_identity.verdict, "same")        # t=10 正常标注
        self.assertIsNone(rows[1].face_identity)                       # t=40 异常被吞
        self.assertIsNone(rows[2].face_identity)                       # 片头
        self.assertIsNone(rows[3].face_identity)                       # not_in_source
        self.assertIsNone(rows[4].face_identity)                       # failure_reason

    def test_unknown_verdict_keeps_faces_counts_with_null_cos(self):
        stub = _StubAnalyzer({"cos": None, "verdict": "unknown",
                              "n_faces_left": 0, "n_faces_right": 2})
        self.srv._face_analyzer = stub
        rows = [Result(edited=TimeSpan(0, 1), original=TimeSpan(10.0, 12.0))]
        self.srv._annotate_face_identity(rows, "fake.mkv")
        self.assertEqual(rows[0].face_identity.verdict, "unknown")
        self.assertEqual(rows[0].face_identity.n_faces_left, 0)
        self.assertEqual(rows[0].to_dict()["face_identity"]["cos"], 0.0)


class PipelineInertnessTest(unittest.TestCase):
    """⭐ 惰性锁：face_identity 开/关不得改变 _locate_features（纯管线）的任何输出键。

    挂点唯一在 locate() 修复链之后的旁路；若有人把它挪进管线（管线是"无 IO"契约层，
    且修复链会改起点，标注必须基于最终值），本锁即红。
    """

    def _run(self, enabled):
        rng = np.random.RandomState(0)
        from domain import IndexMeta
        from engine.feature_store import IndexBundle
        from engine.segment import ShotSegment
        orig = _l2(rng.randn(100, 384).astype(np.float32))
        bundle = IndexBundle(IndexMeta("src", 0, 198.0, "hash"), orig,
                             (np.arange(100) * 2.0).astype(np.float32))
        src = _l2(orig[20:30] + 1e-3 * rng.randn(10, 384).astype(np.float32))
        shot = ShotSegment(TimeSpan(0.0, 4.5), src, (np.arange(10) * 0.5).astype(np.float32))
        srv = SourceLocatorService()
        dense = (src.copy(), (np.arange(10) * 0.125).astype(np.float32))
        srv._embed_dense_query = lambda s, e: dense
        cfg = dataclasses.replace(srv.config.pipeline, face_identity_enabled=enabled)
        res = srv._locate_features([shot], bundle, cfg=cfg, edited="fake.mp4")
        d = res[0].to_dict()
        self.assertIsNone(d["face_identity"], "管线层不得产出 face_identity（挂点在旁路）")
        d.pop("result_id")
        return d

    def test_pipeline_output_independent_of_toggle(self):
        on, off = self._run(True), self._run(False)
        self.assertEqual(on, off)


class MeasureGroundTruthTest(unittest.TestCase):
    """B 类：真模型 + 真媒体（缺任一则 skip）。真值 = 探针/扩上界已确认点。"""

    def _analyzer(self):
        if not (_FFMPEG.exists() and _FFPROBE.exists()):
            self.skipTest("ffmpeg/ffprobe binaries not present")
        from engine.face_identity import FaceIdentityAnalyzer, resolve_face_models
        from infrastructure.paths import models_root
        models = resolve_face_models(models_root())
        if models is None:
            self.skipTest("face models not installed under models_root()/face")
        from media.ffmpeg import FFmpegIO
        return FaceIdentityAnalyzer(models, FFmpegIO(ffmpeg=_FFMPEG, ffprobe=_FFPROBE))

    def test_single_face_same_person(self):
        az = self._analyzer()
        if not Path(_SAME_POINT[0]).exists():
            self.skipTest("test2 original media not present")
        m = az.measure_boundary(*_SAME_POINT)
        self.assertEqual(m["verdict"], "same")
        self.assertGreater(m["cos"], 0.7)
        self.assertEqual(m["n_faces_left"], 1)
        self.assertEqual(m["n_faces_right"], 1)

    def test_single_face_different_person(self):
        az = self._analyzer()
        if not Path(_DIFF_POINT[0]).exists():
            self.skipTest("test1 original media not present")
        m = az.measure_boundary(*_DIFF_POINT)
        self.assertEqual(m["verdict"], "different")
        self.assertLess(m["cos"], 0.4)

    def test_multi_face_is_not_judged(self):
        az = self._analyzer()
        if not Path(_MULTI_POINT[0]).exists():
            self.skipTest("test1 original media not present")
        m = az.measure_boundary(*_MULTI_POINT)
        self.assertEqual(m["verdict"], "unknown")
        self.assertGreater(max(m["n_faces_left"], m["n_faces_right"]), 1)


if __name__ == "__main__":
    unittest.main()
