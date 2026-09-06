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


if __name__ == "__main__":
    unittest.main()
