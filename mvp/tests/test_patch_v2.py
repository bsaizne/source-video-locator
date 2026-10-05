"""patch v2 近场重排门控单测（2026-09-06 立项）。纯合成帧/假后端, 无真实视频。

运行: venv python -m unittest mvp.tests.test_patch_v2 -v
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from app.locator_service import SourceLocatorService
from domain import TimeSpan
from engine.segment import ShotSegment


def _vec(seed):
    rng = np.random.RandomState(seed)
    v = rng.randn(384).astype(np.float32)
    return v / np.linalg.norm(v)


class _FakeRR:
    """假 patch 特征: 按帧内容哈希选预置向量（A=seed1, B=seed2, 其他=seed3）。"""

    def __init__(self, vec_a, vec_b, vec_o):
        self._a, self._b, self._o = vec_a, vec_b, vec_o
        self.available = True
        self.device = "cpu"

    def ensure(self):
        return True

    def frame_patches(self, frame):
        marker = int(frame[0, 0, 0])
        base = {1: self._a, 2: self._b}.get(marker, self._o)
        return np.tile(base, (1369, 1))


class _FakeFfmpeg:
    """grab_frame: t<10 返回 A 帧, t≥10 返回 B 帧（标记在第 1 像素）。"""

    def grab_frame(self, path, t, *, scale=None):
        f = np.zeros((16, 16, 3), dtype=np.uint8)
        f[0, 0, 0] = 1 if t < 10 else 2
        return f

    def iter_frames(self, *a, **k):
        yield from ()


class _FakeBundle:
    class _Meta:
        source_file = "orig.mkv"
    meta = _Meta()


def _make_srv():
    srv = SourceLocatorService(ffmpeg=_FakeFfmpeg(), backend=object())
    vec_a, vec_b, vec_o = _vec(1), _vec(2), _vec(3)
    srv._patch_reranker = _FakeRR(vec_a, vec_b, vec_o)
    srv.config.pipeline.patch_v2_enabled = True
    srv.config.pipeline.patch_v2_radius_s = 30.0
    srv.config.pipeline.patch_v2_stride_s = 4.0
    srv.config.pipeline.patch_v2_margin = 0.08
    return srv, vec_a, vec_b


def _shot():
    return ShotSegment(span=TimeSpan(5.0, 7.0),
                       feats=np.tile(_vec(1), (4, 1)), times=np.array([5.0, 5.5, 6.0, 6.5]))


class PatchV2Test(unittest.TestCase):
    def test_adopt_when_margin_large_and_near(self):
        """查询=B, 主定位=A(10s), 近场含 B(14s): margin 大且 offset≤30 → 改写到 14s。"""
        srv, vec_a, vec_b = _make_srv()
        # 让查询帧产生 B 向量: grab_frame t<10 返回 A——但查询段帧 5-7s 是 A。
        # 改用 marker 控制: 直接构造查询帧 B → 通过把 shot 移到 t≥10 区域
        shot = ShotSegment(span=TimeSpan(11.0, 13.0),
                           feats=np.tile(vec_b, (4, 1)), times=np.array([11.0, 11.5, 12.0, 12.5]))
        cur = (8.0, 10.0)    # 主定位中点 9s → A 帧; 近场 13s=B → margin 大 → 改写
        out = srv._patch_nearfield_rescue(shot, _FakeBundle(), Path("edited.mp4"), cur,
                                          srv.config.pipeline)
        self.assertIsNotNone(out)
        self.assertTrue(13.0 <= (out[0] + out[1]) / 2 <= 15.0)

    def test_reject_when_no_margin(self):
        """查询=A, 主定位=A, 近场全 A: margin≈0 → 不改写。"""
        srv, _, _ = _make_srv()
        shot = _shot()
        out = srv._patch_nearfield_rescue(shot, _FakeBundle(), Path("edited.mp4"),
                                          (8.0, 10.0), srv.config.pipeline)
        self.assertIsNone(out)

    def test_reject_when_disabled(self):
        srv, _, _ = _make_srv()
        srv.config.pipeline.patch_v2_enabled = False
        shot = ShotSegment(span=TimeSpan(11.0, 13.0),
                           feats=np.tile(_vec(2), (4, 1)), times=np.array([11.0, 11.5, 12.0, 12.5]))
        out = srv._patch_nearfield_rescue(shot, _FakeBundle(), Path("edited.mp4"),
                                          (8.0, 10.0), srv.config.pipeline)
        self.assertIsNone(out)

    def test_reject_narrow_shot(self):
        srv, _, _ = _make_srv()
        shot = ShotSegment(span=TimeSpan(11.0, 11.3),
                           feats=np.tile(_vec(2), (2, 1)), times=np.array([11.0, 11.2]))
        out = srv._patch_nearfield_rescue(shot, _FakeBundle(), Path("edited.mp4"),
                                          (8.0, 10.0), srv.config.pipeline)
        self.assertIsNone(out)


class _GridFfmpeg(_FakeFfmpeg):
    """带 grab_grid_times 的假 ffmpeg：记录网格调用，返回值 = 逐帧 grab_frame 的 dict
    （构造上与逐帧路径逐字节一致 ⇒ 网格路径与非网格路径结果可互验）。"""

    def __init__(self):
        self.grid_calls = []

    def grab_grid_times(self, path, times, **k):
        ts = sorted({round(float(t), 6) for t in times})
        self.grid_calls.append(ts)
        return {t: self.grab_frame(path, t) for t in ts}


def _adopt_case(knob_on, ffmpeg=None):
    """test_adopt_when_margin_large_and_near 同场景（查询=B, 主定位=A, 近场 13s=B）。"""
    srv = SourceLocatorService(ffmpeg=ffmpeg or _FakeFfmpeg(), backend=object())
    vec_a, vec_b, vec_o = _vec(1), _vec(2), _vec(3)
    srv._patch_reranker = _FakeRR(vec_a, vec_b, vec_o)
    srv.config.pipeline.patch_v2_enabled = True
    srv.config.pipeline.patch_v2_radius_s = 30.0
    srv.config.pipeline.patch_v2_stride_s = 4.0
    srv.config.pipeline.patch_v2_margin = 0.08
    srv.config.pipeline.rerank_grid_grab = knob_on
    shot = ShotSegment(span=TimeSpan(11.0, 13.0),
                       feats=np.tile(vec_b, (4, 1)), times=np.array([11.0, 11.5, 12.0, 12.5]))
    return srv, shot


class RerankGridGrabTest(unittest.TestCase):
    """续55 下一刀（pipeline.rerank_grid_grab，默认关）：近场池网格抽取接线。"""

    def test_default_off_never_calls_grid(self):
        """旋钮关（默认）= grab_grid_times 一次不调，采纳结果与非网格路径一致。"""
        ff = _GridFfmpeg()
        srv, shot = _adopt_case(knob_on=False, ffmpeg=ff)
        out = srv._patch_nearfield_rescue(shot, _FakeBundle(), Path("edited.mp4"),
                                          (8.0, 10.0), srv.config.pipeline)
        self.assertIsNotNone(out)
        self.assertEqual(ff.grid_calls, [], "rerank_grid_grab=False 时不得走网格路径")

    def test_on_uses_grid_and_same_result(self):
        """旋钮开 = 近场池走网格抽取，采纳决策与关闭臂逐字段一致（零语义）。"""
        out_by_mode = []
        for knob_on in (False, True):
            ff = _GridFfmpeg()
            srv, shot = _adopt_case(knob_on=knob_on, ffmpeg=ff)
            out = srv._patch_nearfield_rescue(shot, _FakeBundle(), Path("edited.mp4"),
                                              (8.0, 10.0), srv.config.pipeline)
            out_by_mode.append(out)
        self.assertIsNotNone(out_by_mode[1])
        self.assertEqual(out_by_mode[0], out_by_mode[1])

    def test_on_grid_gets_all_nearfield_points(self):
        """近场池（±30s@4s=15 点）一次网格调用拿全；负值锚点被 max(0,·) 削成 0.0 去重后
        剩 11 个不同点（真实现内部再聚簇，逐点都有帧）。"""
        ff = _GridFfmpeg()
        srv, shot = _adopt_case(knob_on=True, ffmpeg=ff)
        srv._patch_nearfield_rescue(shot, _FakeBundle(), Path("edited.mp4"),
                                    (8.0, 10.0), srv.config.pipeline)
        self.assertEqual(len(ff.grid_calls), 1)
        self.assertEqual(ff.grid_calls[0], sorted(set(ff.grid_calls[0])))
        self.assertEqual(len(ff.grid_calls[0]), 11)
        self.assertTrue(all(t >= 0.0 for t in ff.grid_calls[0]))

    def test_on_grid_missing_frame_falls_back(self):
        """网格结果漏帧（超片尾/解码失败）⇒ _grab_grid_batch 逐帧回退，不丢点不抛错。"""

        class _HoleyGrid(_GridFfmpeg):
            def grab_grid_times(self, path, times, **k):
                got = super().grab_grid_times(path, times, **k)
                got.pop(round(17.0, 6), None)      # 近场池必含 17s（主定位 9s + 4s×2）
                return got

        srv, shot = _adopt_case(knob_on=True, ffmpeg=_HoleyGrid())
        out = srv._patch_nearfield_rescue(shot, _FakeBundle(), Path("edited.mp4"),
                                          (8.0, 10.0), srv.config.pipeline)
        self.assertIsNotNone(out)
        self.assertTrue(13.0 <= (out[0] + out[1]) / 2 <= 15.0)


class _StubBackend:
    def __init__(self, dtype, dname):
        self._dtype, self._dname = dtype, dname

    def device_type(self):
        return self._dtype

    def device_name(self):
        return self._dname


class _CaptureLog:
    def __init__(self):
        self.lines = []

    def info(self, fmt, *a):
        self.lines.append(("info", fmt % a))

    def warning(self, fmt, *a):
        self.lines.append(("warning", fmt % a))


class AnnouncePatchRerankerTest(unittest.TestCase):
    """精排器设备落日志的分级（2026-10-01 打包态归因）。

    GPU 特征后端 + CPU 精排 = 缺 DML patch ONNX 的**静默降级**形态，整条定位慢 2.6~3.9x；
    这一组合必须是 warning，否则用户只会以为机器本身慢（打包态就是这么瞒了两周）。
    """

    def _run(self, backend_dtype, rr_device):
        srv = SourceLocatorService(ffmpeg=_FakeFfmpeg(), backend=_StubBackend(backend_dtype,
                                                                             "directml"))
        srv._log = _CaptureLog()
        srv._announce_patch_reranker(type("RR", (), {"device": rr_device})())
        return srv._log.lines

    def test_gpu_backend_with_cpu_reranker_warns(self):
        self.assertEqual(self._run("amd", "cpu")[0][0], "warning")

    def test_cpu_backend_with_cpu_reranker_is_info(self):
        self.assertEqual(self._run("cpu", "cpu")[0][0], "info")

    def test_gpu_backend_with_dml_reranker_is_info(self):
        self.assertEqual(self._run("amd", "dml")[0][0], "info")


if __name__ == "__main__":
    unittest.main()
