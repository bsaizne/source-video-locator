"""text_anchor 单测——OCR 文字锚点(Phase 21 首选第二信号)。

真实案例:同场景字牌在 CLS 特征下不可分(ed84.5-86 真值 sim 0.84 vs 错误 0.91),
文字可判(rapidocr 对全部字牌读出清晰文本)。覆盖:归一化/相似度/水印过滤/晋级逻辑/
依赖缺失降级。Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_text_anchor -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from app import SourceLocatorService
from domain import IndexMeta, TimeSpan
from engine.feature_store import IndexBundle
from engine.localization.evidence_localize import EvidenceLocalizer, EvidenceResult
from engine.localization.text_anchor import (OcrEngine, filter_watermark,
                                             line_vs_lines, normalize_text,
                                             text_similarity)
from engine.segment import ShotSegment


class NormalizeTest(unittest.TestCase):
    def test_lowercase_and_strip(self):
        """全部去非字母数字(含空格):OCR 黏词('YOURNAME')归一后与分词版本一致。"""
        self.assertEqual(normalize_text("WHAT is YOUR NAME?"), "whatisyourname")

    def test_ocr_glued_words_match(self):
        """OCR 把空格吞掉('YOURNAME')时仍应高度相似。"""
        a = line_vs_lines("WHAT is YOURNAME?", ["WHAT is YOUR NAME?"])
        self.assertGreater(a, 0.85)


class WatermarkTest(unittest.TestCase):
    def test_tiktok_watermark_filtered(self):
        lines = ["WHAT is YOUR NAME?", "TikTok", "@fyprecap", "She asked Levi his name"]
        out = filter_watermark(lines)
        joined = " ".join(out).lower()
        self.assertNotIn("tiktok", joined)
        self.assertNotIn("fyprecap", joined)
        self.assertIn("what is your name", joined)


class SimilarityTest(unittest.TestCase):
    def test_identical(self):
        self.assertGreater(line_vs_lines("MY NAME IS DRASA", ["MY NAME IS DRASA"]), 0.95)

    def test_unrelated_low(self):
        self.assertLess(line_vs_lines("WHAT is YOUR NAME?", ["THREE THINGS CANNOT BE LONG"]), 0.3)

    def test_empty_candidate(self):
        self.assertEqual(text_similarity(["WHAT is YOUR NAME?"], []), 0.0)

    def test_single_strong_anchor_wins(self):
        """max 口径:一条强锚点行命中即得高分(不被无关字幕行稀释)。"""
        s = text_similarity(["We ARE NOT ALLOWED", "unrelated gibberish zz"],
                            ["WE ARE NOT ALLOWED CONTACT"])
        self.assertGreater(s, 0.8)  # 查询行被候选完整包含 → 对称包含率 0.825


class _FakeOcr:
    """脚本化 OCR:lines() 依次弹出预置行(供晋级逻辑测试)。"""

    def __init__(self, script):
        self.script = list(script)

    def ensure(self):
        return True

    def lines(self, frames):
        return self.script.pop(0) if self.script else []


class _DeadOcr:
    def ensure(self):
        return False

    def lines(self, frames):
        return []


class PromotionTest(unittest.TestCase):
    def _svc(self):
        return SourceLocatorService()

    def _bundle(self):
        rng = np.random.RandomState(0)
        orig = rng.randn(100, 384).astype(np.float32)
        orig /= np.linalg.norm(orig, axis=1, keepdims=True)
        return IndexBundle(IndexMeta("src", 0, 198.0, "hash"), orig,
                           (np.arange(100) * 2.0).astype(np.float32))

    def _result(self):
        from domain import OriginalSegment
        rng = np.random.default_rng(0)
        feats = rng.standard_normal((4, 384)).astype(np.float32)
        feats /= np.linalg.norm(feats, axis=1, keepdims=True)
        shot = ShotSegment(span=TimeSpan(81.0, 85.5), feats=feats,
                           times=np.linspace(81.0, 85.5, 4))
        svc = self._svc()
        with patch.object(EvidenceLocalizer, "localize",
                          return_value=EvidenceResult(mode="empty")):
            results = svc._locate_features([shot], self._bundle(),
                                           cfg=svc.config.pipeline)
        r = results[0]
        r.original = TimeSpan(1788.0, 1797.0)
        r.original_segments = [OriginalSegment(1809.0, 1813.0, 0.55, 0.65),
                               OriginalSegment(1875.0, 1884.0, 0.42, 0.66)]
        return svc, r

    def _fake_ffmpeg(self):
        return patch.object(type(self._svc()), "ffmpeg", new_callable=PropertyMock)

    def test_promotes_text_better_subspan(self):
        """查询=问句字牌文字,子span窗(1809)OCR 同文 → 晋级为主 original。"""
        svc, r = self._result()
        ffmock = self._fake_ffmpeg()
        svc._ocr_engine = _FakeOcr([
            ["WHAT is YOUR NAME?"],          # 查询段
            ["we are not allowed contact"],  # 主窗 1788-1797
            ["WHAT IS YOUR NAME"],           # 子窗 1809-1813
            ["my name is drasa"],            # 子窗 1875-1884
        ])
        cfg = svc.config.pipeline
        with ffmock as prop:
            prop.return_value = MagicMock()
            svc._apply_text_anchor([r], Path("x.mp4"), "y.mkv", cfg=cfg)
        self.assertEqual((r.original.start, r.original.end), (1809.0, 1813.0))

    def test_no_promotion_without_gain(self):
        """子窗文字不比主窗好 → 不晋级。"""
        svc, r = self._result()
        ffmock = self._fake_ffmpeg()
        svc._ocr_engine = _FakeOcr([
            ["WHAT is YOUR NAME?"],
            ["WHAT IS YOUR NAME"],   # 主窗已同样好
            ["WHAT IS YOUR NAME"],
            ["my name is drasa"],
        ])
        cfg = svc.config.pipeline
        with ffmock as prop:
            prop.return_value = MagicMock()
            svc._apply_text_anchor([r], Path("x.mp4"), "y.mkv", cfg=cfg)
        self.assertEqual((r.original.start, r.original.end), (1788.0, 1797.0))

    def test_scene_pool_subspan_never_promoted(self):
        """场景扩池 span(Phase 21)不作为晋级候选窗——即使其文字最匹配。

        多模态实测:场景 span 经 OCR 巧合晋级会产生新错误匹配(test2 s7 人物 A→人物 B);
        场景级只扩池,不参与主定位改写。
        """
        from domain import OriginalSegment
        svc, r = self._result()
        r.original_segments = [
            OriginalSegment(1809.0, 1813.0, 0.55, 0.65, from_scene_pool=True),
            OriginalSegment(1875.0, 1884.0, 0.42, 0.66),
        ]
        ffmock = self._fake_ffmpeg()
        svc._ocr_engine = _FakeOcr([
            ["WHAT is YOUR NAME?"],          # 查询段
            ["we are not allowed contact"],  # 主窗 1788-1797
            ["WHAT IS YOUR NAME"],           # 场景扩池窗 1809-1813(文字最匹配,但跳过)
            ["my name is drasa"],            # 帧级子窗 1875-1884
        ])
        cfg = svc.config.pipeline
        with ffmock as prop:
            prop.return_value = MagicMock()
            svc._apply_text_anchor([r], Path("x.mp4"), "y.mkv", cfg=cfg)
        # 场景扩池窗(文字最匹配)不被晋级;帧级子窗按基线规则仍可晋级
        self.assertNotEqual((r.original.start, r.original.end), (1809.0, 1813.0))

    def test_ocr_unavailable_is_noop(self):
        svc, r = self._result()
        svc._ocr_engine = _DeadOcr()
        cfg = svc.config.pipeline
        svc._apply_text_anchor([r], Path("x.mp4"), "y.mkv", cfg=cfg)
        self.assertEqual((r.original.start, r.original.end), (1788.0, 1797.0))


if __name__ == "__main__":
    unittest.main()
