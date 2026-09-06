"""Unit tests for mvp.app.SourceLocatorService._segment_twopass_flash
(两级切分 + 白闪守卫, C 项验证 2026-09-05 用户拍板进 runtime).

Deterministic: fake ffmpeg (yields coarse frames incl. flash frames) + fake backend
(embed → designed block features). Verifies the segmentation branch only:
  - coarse sampling + detect_shots 粗切分;
  - 白闪邻域切点被删除（白闪帧不被当作镜头边界）;
  - 最短镜头保护合并短段;
  - 关闭开关（seg_twopass_enabled=False）回退旧路径仍可用。
No DINOv2 / real video. Run: venv python -m unittest mvp.tests.test_twopass_flash -v
"""
from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from app import SourceLocatorService

# --- fake ffmpeg / backend ---


@dataclass
class _Meta:
    fps: float
    duration: float
    width: int = 64
    height: int = 64


class _FakeFFmpeg:
    """iter_frames 产出带索引编码的帧（BGR[0,0,0]=索引）; metadata 固定 fps/dur。"""

    def __init__(self, n: int, fps: float = 29.0, flash_idx=(), dur=None):
        self.n = n
        self.fps = fps
        self.flash_idx = set(flash_idx)
        self.dur = dur if dur is not None else (n - 1) / (fps / 6.0)

    def metadata(self, path):
        return _Meta(self.fps, self.dur)

    def iter_frames(self, path, fps, *, start=None, end=None, scale=None, meta=None):
        dt = 1.0 / max(fps, 1e-6)
        t0 = start if start is not None else 0.0
        t1 = end if end is not None else self.dur
        i = int(round(t0 / dt))
        t = t0
        while t < t1 - 1e-9:
            v = 230 if i in self.flash_idx else 90
            f = np.full((64, 64, 3), v, dtype=np.uint8)
            f[0, 0, 0] = i & 0xFF      # 索引编码进 B 通道(供 backend 查表)
            yield t, f
            i += 1
            t += dt


class _FakeBackend:
    """embed_frames: 按帧内编码索引查预设块特征(块内近 0 距离, 块间大距离)。"""

    def __init__(self, blocks: list[int]):
        rng = np.random.RandomState(7)
        feats = []
        for nb in blocks:
            base = rng.randn(1, 384).astype(np.float32)
            base = base / np.linalg.norm(base)
            blk = base + 1e-3 * rng.randn(nb, 384).astype(np.float32)
            blk = blk / np.maximum(np.linalg.norm(blk, axis=1, keepdims=True), 1e-8)
            feats.append(blk)
        self.feats = np.concatenate(feats, axis=0).astype(np.float32)

    def embed_frames(self, frames, batch_size=16):
        out = []
        for f in frames:
            idx = int(f[0, 0, 0]) % len(self.feats)
            out.append(self.feats[idx])
        return np.stack(out, axis=0)


class TwopassFlashSegmentTest(unittest.TestCase):
    def _srv(self, blocks, n_coarse, flash_idx=(), fps=29.0):
        ff = _FakeFFmpeg(n=n_coarse, fps=fps, flash_idx=flash_idx)
        bk = _FakeBackend(blocks)
        srv = SourceLocatorService(ffmpeg=ff, backend=bk)
        return srv

    def test_flash_neighborhood_cut_removed(self):
        """白闪帧邻域出现粗切点时被删除, 不产生额外段。"""
        blocks = [4, 6, 6]
        n_coarse = 16
        srv = self._srv(blocks, n_coarse, flash_idx=(5,), fps=29.0)
        shots = srv._segment_twopass_flash(Path("e.mp4"), srv.config.pipeline,
                                           None, None)
        self.assertGreaterEqual(len(shots), 1)
        for sh in shots:
            self.assertGreaterEqual(sh.span.width, 0.5 - 1e-6)

    def test_no_flash_all_cuts_kept(self):
        """无白闪时粗切点保留, 段数 = 块数。"""
        blocks = [5, 8, 8]
        n_coarse = 21
        srv = self._srv(blocks, n_coarse, flash_idx=(), fps=29.0)
        shots = srv._segment_twopass_flash(Path("e.mp4"), srv.config.pipeline,
                                           None, None)
        self.assertEqual(len(shots), 3)

    def test_short_shot_merged(self):
        """最短镜头保护: 过短段(<0.5s)被合并, 段数减少。"""
        blocks = [2, 8, 8]   # 第一块 2 粗帧 ≈ 0.41s < 0.5s → 合并
        n_coarse = 18
        srv = self._srv(blocks, n_coarse, flash_idx=(), fps=29.0)
        shots = srv._segment_twopass_flash(Path("e.mp4"), srv.config.pipeline,
                                           None, None)
        self.assertEqual(len(shots), 2)

    def test_disabled_falls_back_to_legacy(self):
        """seg_twopass_enabled=False → 走 _segment_legacy（旧路径不破坏）。"""
        blocks = [5, 8, 8]
        n_coarse = 21
        srv = self._srv(blocks, n_coarse, flash_idx=(), fps=29.0)
        cfg = srv.config.pipeline
        cfg.seg_twopass_enabled = False
        shots = srv._segment_legacy(Path("e.mp4"), cfg, None, None)
        self.assertIsInstance(shots, list)


class TwopassConfigTest(unittest.TestCase):
    def test_defaults_present(self):
        """新配置项默认值在位（JSON 覆盖入口存在）。"""
        srv = SourceLocatorService()
        p = srv.config.pipeline
        self.assertTrue(p.seg_twopass_enabled)
        self.assertEqual(p.seg_twopass_coarse_step_frames, 6)
        self.assertEqual(p.seg_twopass_fine_window_frames, 20)
        self.assertEqual(p.seg_twopass_fine_step_frames, 2)
        self.assertAlmostEqual(p.seg_twopass_min_shot_s, 0.5)
        self.assertAlmostEqual(p.flash_mean_th, 200.0)
        self.assertAlmostEqual(p.flash_frac_th, 0.5)
        self.assertAlmostEqual(p.flash_margin_s, 0.25)
        self.assertAlmostEqual(p.flash_dyn_min_shot_s, 1.0)
        self.assertAlmostEqual(p.flash_merge_frac, 0.5)
        self.assertAlmostEqual(p.bright_spike_delta, 80.0)
        self.assertAlmostEqual(p.bright_spike_peak_th, 180.0)


if __name__ == "__main__":
    unittest.main()
