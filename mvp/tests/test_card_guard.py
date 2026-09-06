"""card_guard 单测——黑底文字卡/logo 帧检测(GT v3 n04 迭代)。

真实失败:编辑片 TikTok 片尾 logo(黑底白 logo)↔ 电影片尾版权卡(黑底白字卡)
cos≈0.736 → HIGH 0.95「自信答错」。像素层版式检测在检索前拦截。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engine.segment import card_frame_ratios, card_shot_ratio, is_card_frame


def _black_frame(h=64, w=48) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


def _card_frame(h=64, w=48, bright=255) -> np.ndarray:
    """黑底 + 居中白色块(模拟字卡/logo;black=1-400/3072≈0.87 ≥ 0.85 新阈)。"""
    f = np.zeros((h, w, 3), dtype=np.uint8)
    f[h // 3 + 1:2 * h // 3, w // 4 + 2:3 * w // 4 - 2] = bright
    return f


def _noisy_frame(h=64, w=48, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(40, 220, size=(h, w, 3), dtype=np.uint8)


class CardFrameTest(unittest.TestCase):
    def test_black_with_white_block_is_card(self):
        self.assertTrue(is_card_frame(_card_frame()))

    def test_pure_black_is_not_card(self):
        """纯黑场(bright<lo)不算文字卡——黑场转场是另一类,不在此守卫。"""
        self.assertFalse(is_card_frame(_black_frame()))

    def test_noisy_photo_like_is_not_card(self):
        """普通画面:近黑占比低 → 非文字卡。"""
        self.assertFalse(is_card_frame(_noisy_frame()))

    def test_ratios_ranges(self):
        black, bright = card_frame_ratios(_card_frame())
        self.assertGreaterEqual(black, 0.60)
        self.assertGreaterEqual(bright, 0.01)
        self.assertLessEqual(bright, 0.30)

    def test_dim_frame_grayscale_tolerated(self):
        """灰度(HxW)输入不崩(防御性)。"""
        f = np.zeros((32, 32), dtype=np.uint8)
        f[10:20, 10:22] = 250   # 10*12=120 → black≈0.883 ≥ 0.85
        self.assertTrue(is_card_frame(f))


class CardShotRatioTest(unittest.TestCase):
    def test_all_card_frames(self):
        frames = [_card_frame() for _ in range(5)]
        self.assertEqual(card_shot_ratio(frames), 1.0)

    def test_mixed(self):
        frames = [_card_frame(), _noisy_frame(seed=1), _card_frame(), _noisy_frame(seed=2)]
        self.assertAlmostEqual(card_shot_ratio(frames), 0.5)

    def test_empty(self):
        self.assertEqual(card_shot_ratio([]), 0.0)


if __name__ == "__main__":
    unittest.main()


class NightSceneMisfireTest(unittest.TestCase):
    """夜间场景误杀修复:暗底+橙火/暖灯不满足「白色文字」判据(GT v3 加固实测回归)。"""

    def test_orange_explosion_on_dark_is_not_card(self):
        """暗底 + 橙色爆炸斑(p37 夜战围栏形态)→ 非文字卡。"""
        f = np.zeros((64, 48, 3), dtype=np.uint8)
        h, w = 20, 16
        f[24:40, 14:30] = (40, 120, 250)  # BGR:橙色(高通道扩散)
        self.assertFalse(is_card_frame(f))

    def test_warm_lamp_on_dark_is_not_card(self):
        f = np.zeros((64, 48, 3), dtype=np.uint8)
        f[10:18, 8:16] = (120, 180, 230)  # BGR:暖白灯(扩散~110)
        self.assertFalse(is_card_frame(f))

    def test_white_text_on_dark_still_card(self):
        """白字三通道接近(扩散≈0)→ 仍是文字卡(守卫主功能不回退)。"""
        f = np.zeros((64, 48, 3), dtype=np.uint8)
        f[24:40, 14:30] = (250, 252, 249)  # BGR:白色(扩散~3)
        self.assertTrue(is_card_frame(f))


class SparseHighlightTest(unittest.TestCase):
    """夜间散点高光误杀修复二:亮斑稀疏(低包围盒填充率)→ 非文字卡。"""

    def test_scattered_white_dots_on_dark_is_not_card(self):
        """夜间铁丝网反光形态:暗底 + 分散白点(p35 误杀回归)。"""
        f = np.zeros((64, 48, 3), dtype=np.uint8)
        for y, x in [(5, 3), (8, 30), (15, 10), (25, 40), (35, 5), (45, 25),
                     (55, 44), (30, 20), (50, 12), (12, 38)]:
            f[y:y + 2, x:x + 2] = 240
        self.assertFalse(is_card_frame(f))

    def test_dense_text_block_still_card(self):
        f = np.zeros((64, 48, 3), dtype=np.uint8)
        f[20:40, 14:34] = 245  # 大块致密白色文字区(大连通域;black=1-400/3072≈0.87≥0.85)
        self.assertTrue(is_card_frame(f))

    def test_two_big_blobs_like_tiktok_outro_is_card(self):
        """TikTok 片尾形态:logo+搜索框两个分离大实体 → 仍是文字卡(n04 回归)。"""
        f = np.zeros((270, 480, 3), dtype=np.uint8)
        f[30:80, 180:300] = 250   # logo 块
        f[150:170, 140:340] = 250  # 搜索框条
        self.assertTrue(is_card_frame(f))


class NightSubtitleMisfireTest(unittest.TestCase):
    """夜间误杀修复三(test1 r10 实证):夜间剧情画面 black≈0.73-0.78,其解说字幕
    白字行=宽扁大连通域+窗光低扩散,骗过 spread/连通域判据;真卡 black≥0.93,
    ``card_black_ratio`` 0.60→0.85 完成分离。"""

    def _r10_like_frame(self) -> np.ndarray:
        """夜间屋内形态:大部分近黑 + 25% 暗灰内容 + 底部字幕白条 + 上部窗光。"""
        f = np.zeros((64, 48, 3), dtype=np.uint8)
        f[10:40, 0:26] = 90          # 人物/墙壁暗灰内容(非黑非亮)
        f[55:58, 4:44] = 250         # 解说字幕行(白色宽扁大连通域)
        f[4:12, 30:40] = 245         # 窗户亮光(低扩散白斑)
        return f

    def test_night_scene_with_subtitle_strip_is_not_card(self):
        """r10 形态:black≈0.68,旧阈 0.60 误判卡 → 新阈 0.85 正确放行。"""
        f = self._r10_like_frame()
        black, bright = card_frame_ratios(f)
        self.assertGreaterEqual(black, 0.60)      # 旧阈下确实会误判(实证形态)
        self.assertLess(black, 0.85)
        self.assertTrue(is_card_frame(f, black_ratio=0.60))   # 旧行为:误杀
        self.assertFalse(is_card_frame(f))                     # 新默认:放行

    def test_real_card_black_096_still_card(self):
        """真卡形态(test1 片尾卡 black≈0.96 / n04 0.967)→ 新阈下仍判卡。"""
        f = np.zeros((64, 48, 3), dtype=np.uint8)
        f[28:34, 12:32] = 250     # 白字行(6*20)
        f[6:10, 38:46] = 250      # logo 块(4*8)
        black, _ = card_frame_ratios(f)
        self.assertGreaterEqual(black, 0.93)   # 与实测真卡同量级
        self.assertTrue(is_card_frame(f))
