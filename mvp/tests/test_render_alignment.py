# -*- coding: utf-8 -*-
"""锁 ``mvp/scripts/accept_video_render_2mkv.py`` 的两处纯判据（不跑 ffmpeg）。

为什么锁在单测里（2026-10-11 复盘）：成片渲染验收的 ``alignment_within_1_frame`` 长期把
「取帧约定产生的常数偏移」当产品缺陷判红，而它在自己该抓的方向上**零余量**——72 段里恒定
就有 35 段偏 -1 帧，阈值写的却是 <=1。改判「离散度」之后，这两条算术必须有常驻锁：

  1. :func:`clip_mid_times` —— 两侧取帧时刻必须落在**目标帧之前、上一帧之后**
     （``-ss`` 前置于 ``-i`` 的语义 = 返回第一个 PTS >= t 的帧）。写成 ``+0.5`` 会恰好
     取到下一帧，我 2026-10-11 就这么错过一次（偏移分布整体又平移一帧）。
  2. :func:`alignment_verdict` —— 常数项放行、段间掉队判死、平曲线（argmin 无信息）不参与判定。

跑：  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_render_alignment -v
"""
from __future__ import annotations

import importlib.util
import io
import math
import sys
import unittest
from fractions import Fraction
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2]
SCRIPT = BENCH / "mvp" / "scripts" / "accept_video_render_2mkv.py"
FPS = Fraction(24000, 1001)          # 2.mkv / 成片同为 23.976 CFR


class _SilentStdout(io.StringIO):
    """加载期挡住脚本的 ``sys.stdout.reconfigure(...)``。

    ⚠️ 必须带 ``reconfigure``：少了它第一次跑就把整批测试静默 skip 掉（锁变空锁）。
    """

    def reconfigure(self, **_kwargs):
        return None


def _load_script():
    """按路径加载验收脚本。

    该脚本在**模块级**执行 ``sys.stdout.reconfigure(encoding="utf-8")`` 与一批
    ``sys.path.insert``；在测试进程里直接 import 会把全局 stdout 改掉，所以临时换掉。
    """
    sys.path.insert(0, str(BENCH / "mvp" / "src"))
    spec = importlib.util.spec_from_file_location("av_render_accept", str(SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    real = sys.stdout
    sys.stdout = _SilentStdout()
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.stdout = real
    return mod


# 只有「重依赖不在」才允许 skip；其它加载失败一律当场炸出来——
# 否则脚本改坏 / 路径挪了 会让这条锁静默消失（2026-10-11 真踩过：7 项全 skip 还报 OK）。
if importlib.util.find_spec("cv2") is None:
    AV, LOAD_ERROR = None, "缺 cv2（成片对照图用）"
else:
    AV, LOAD_ERROR = _load_script(), None

needs_script = unittest.skipIf(AV is None, f"验收脚本不可加载: {LOAD_ERROR!r}")


def grabbed_frame(t: float, fps: Fraction) -> int:
    """``-ss t`` 前置于 ``-i`` 实际返回的帧号 = 第一个 PTS >= t 的帧。"""
    return int(math.ceil(float(t) * float(fps) - 1e-9))


@needs_script
class ClipMidTimesTest(unittest.TestCase):
    def test_times_land_on_the_intended_frame(self):
        """取帧时刻必须落在「目标帧之前、上一帧之后」，否则实际抓到的是下一帧。"""
        clips = [(2417.0, 2419.0), (100.5, 101.6)]
        mids = AV.clip_mid_times(clips, FPS)
        for idx, (a0, a1) in enumerate(clips):
            movie_t, src_t, n = mids[idx]
            m = n // 2
            start = sum(x[2] for x in mids[:idx])
            self.assertEqual(grabbed_frame(movie_t, FPS), start + m,
                             f"clip{idx} 成片侧抓错帧")
            self.assertEqual(grabbed_frame(src_t, FPS),
                             int(math.floor(a0 * float(FPS) + 1e-6)) + m,
                             f"clip{idx} 原片侧抓错帧")

    def test_movie_side_accumulates_frames_not_seconds(self):
        """第二段在成片里的位置 = 前段**帧数**之和（用名义秒累加会假跑出漂移）。"""
        clips = [(0.0, 1.0), (50.0, 51.0)]
        mids = AV.clip_mid_times(clips, FPS)
        n0 = mids[0][2]
        self.assertEqual(grabbed_frame(mids[1][0], FPS), n0 + mids[1][2] // 2)

    def test_half_frame_margin(self):
        """时刻与目标帧 PTS 的距离必须 < 一帧（否则任何 PTS 抖动都会换帧）。"""
        for a0, a1 in ((2417.0, 2419.0), (1580.5, 1581.0), (1330.04, 1330.592)):
            movie_t, src_t, n = AV.clip_mid_times([(a0, a1)], FPS)[0]
            self.assertLess(abs(movie_t * float(FPS) - (n // 2)), 1.0)
            self.assertLess(abs(src_t * float(FPS)
                                - (math.floor(a0 * float(FPS)) + n // 2)), 1.0)


@needs_script
class AlignmentVerdictTest(unittest.TestCase):
    """判据 = 离散度。常数项（取帧约定的 ±1）放行，段间掉队判死。"""

    @staticmethod
    def _rows(pairs):
        return [{"raw_offset_frames": k, "significant": sig} for k, sig in pairs]

    def test_constant_offset_is_not_a_failure(self):
        rows = self._rows([(-1, True)] * 10)
        v = AV.alignment_verdict(rows)
        self.assertEqual(v["base_offset"], -1)
        self.assertEqual(v["dispersion"], 0)
        self.assertTrue(v["ok"])

    def test_one_straggler_clip_fails(self):
        rows = self._rows([(-1, True)] * 9 + [(3, True)])
        v = AV.alignment_verdict(rows)
        self.assertEqual(v["dispersion"], 4)
        self.assertFalse(v["ok"])

    def test_flat_curve_clips_carry_no_information(self):
        """静态镜头上 MAD 曲线是平的（实测 0.378 vs 0.364）=> argmin 挑的是噪声。"""
        v = AV.alignment_verdict(self._rows([(2, False)] * 10))
        self.assertEqual(v["n_significant"], 0)
        self.assertTrue(v["ok"], "全平曲线应判『无可判信息』而不是判死")
        v2 = AV.alignment_verdict(self._rows([(-1, True)] * 5 + [(2, False)] * 5))
        self.assertEqual(v2["n_significant"], 5)
        self.assertEqual(v2["dispersion"], 0)

    def test_two_frame_local_deviation_is_caught(self):
        """改判离散度后仍要抓得住真错：某段比多数段偏 2 帧 = 段长/累加算错。"""
        v = AV.alignment_verdict(self._rows([(0, True)] * 11 + [(2, True)]))
        self.assertGreaterEqual(v["dispersion"], 2)
        self.assertFalse(v["ok"])


if __name__ == "__main__":
    unittest.main()
