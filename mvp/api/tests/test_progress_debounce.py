"""③ 进度发布层防抖（2026-10-07 立项）单测。

`ProgressDebouncer` 契约：同阶段连续帧按最小间隔合并（只留最新 held）；
阶段切换与终态立即直通；held 在下一次发布前补发（旧值先于新值）。
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> benchmark（import mvp.api.*）

from mvp.api.tasks.debounce import ProgressDebouncer        # noqa: E402


class _Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def advance(self, s):
        self.t += s


class _S:
    """假阶段：模拟 TaskStage 的成员相等语义（同名即同阶段）。"""

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return isinstance(other, _S) and self.name == other.name

    def __hash__(self):
        return hash(self.name)


def _frames(deb, stage, pct, msg=""):
    return [(f[0], f[1]) for f in deb.submit(stage, pct, msg)]


class ProgressDebouncerTest(unittest.TestCase):
    def test_first_frame_publishes_immediately(self):
        clock = _Clock()
        deb = ProgressDebouncer(0.5, clock=clock)
        self.assertEqual(_frames(deb, _S("a"), 10.0), [(_S("a"), 10.0)])

    def test_same_stage_rapid_frames_coalesce_to_latest(self):
        clock = _Clock()
        deb = ProgressDebouncer(0.5, clock=clock)
        _frames(deb, _S("a"), 10.0)
        clock.advance(0.1)
        self.assertEqual(_frames(deb, _S("a"), 12.0), [])   # 间隔未到 → held
        clock.advance(0.1)
        self.assertEqual(_frames(deb, _S("a"), 14.0), [])   # held 被新值覆盖
        clock.advance(0.5)
        # 间隔已过：先补发 held(14) 再发本帧(16) —— 旧值先于新值，无信息丢失
        self.assertEqual(_frames(deb, _S("a"), 16.0),
                         [(_S("a"), 14.0), (_S("a"), 16.0)])

    def test_stage_change_publishes_immediately(self):
        clock = _Clock()
        deb = ProgressDebouncer(0.5, clock=clock)
        a, b = _S("a"), _S("b")
        _frames(deb, a, 10.0)
        clock.advance(0.1)
        out = deb.submit(b, 20.0)              # 阶段切换：立即发布，不进 held
        self.assertEqual([(f[0].name, f[1]) for f in out], [(b.name, 20.0)])

    def test_terminal_frame_bypasses_debounce(self):
        clock = _Clock()
        deb = ProgressDebouncer(0.5, clock=clock)
        _frames(deb, _S("a"), 10.0)
        clock.advance(0.05)
        out = deb.submit(_S("a"), 100.0)
        self.assertEqual([f[1] for f in out], [100.0])

    def test_flush_returns_and_clears_held(self):
        clock = _Clock()
        deb = ProgressDebouncer(0.5, clock=clock)
        _frames(deb, _S("a"), 10.0)
        clock.advance(0.1)
        _frames(deb, _S("a"), 12.0)            # held=12
        out = deb.flush()
        self.assertEqual([f[1] for f in out], [12.0])
        self.assertEqual(deb.flush(), [])      # 二次 flush 为空

    def test_no_information_loss_across_window(self):
        """任意帧序列：flush 后合并出的发布序列 = 单调、覆盖首尾。"""
        clock = _Clock()
        deb = ProgressDebouncer(0.5, clock=clock)
        published = []
        seq = [(0.0, 10), (0.1, 12), (0.2, 14), (0.9, 20), (1.0, 22), (1.1, 24)]
        for dt, pct in seq:
            clock.advance(dt)
            published.extend(f[1] for f in deb.submit(_S("a"), float(pct)))
        published.extend(f[1] for f in deb.flush())
        self.assertEqual(published[0], 10)
        self.assertEqual(published[-1], 24)
        self.assertEqual(published, sorted(published))     # 单调


if __name__ == "__main__":
    unittest.main()
