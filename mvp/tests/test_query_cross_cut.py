"""段内画面跳变标注 `query_cross_cut`（建议 A，2026-10-22）。

定位：编辑片侧切出的查询段有 83% 内含画面跳变（17 段已逐帧读图确证），
「一段 → 一个源片起点」在多数段上不成立。本标注**只如实说清不确定性**：
不改定位判据、不改 `confidence`（公式冻结是护栏）、三指标读数不变。

锁四件事：
1. 判据只吃主链路已算好的 dense —— **不许再取一次帧**。闭区间重筛会把与下一段共享的
   边界帧算进段内，造出「段尾切点 = 段内跨镜头」的假阳
   （`FINDINGS_QUERY_CROSS_CUT_CALIBER_20261022.md` §2：0.859 vs 生产实取 0.153）。
2. 阈值与帧数边界：≤2 帧不判、不过阈不标。
3. 契约往返 + 旧结果 JSON 向后兼容。
4. ⭐ 惰性锁：标注开满 vs 全部关掉，其余字段逐键相同 ⇒ 它改不了定位结果也改不了置信度。

  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_query_cross_cut -v
"""
from __future__ import annotations

import dataclasses
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np

from app import SourceLocatorService
from domain import QueryCrossCut, Result, TimeSpan
from engine.segment import ShotSegment


def _l2(x):
    return x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-8)


def _two_shot_dense():
    """前 4 帧同一画面、后 4 帧另一画面 ⇒ 段内一处硬切，切点在 t=0.5s。"""
    rng = np.random.RandomState(11)
    a = rng.randn(1, 384).astype(np.float32)
    b = rng.randn(1, 384).astype(np.float32)
    feats = _l2(np.vstack([np.tile(a, (4, 1)), np.tile(b, (4, 1))])
                + 1e-3 * rng.randn(8, 384).astype(np.float32))
    times = (np.arange(8) * 0.125).astype(np.float32)
    return (feats, times)


def _flat_dense():
    """八帧几乎同一画面 ⇒ 无跳变。"""
    rng = np.random.RandomState(3)
    base = rng.randn(1, 384).astype(np.float32)
    feats = _l2(np.tile(base, (8, 1)) + 1e-4 * rng.randn(8, 384).astype(np.float32))
    return (feats, (np.arange(8) * 0.125).astype(np.float32))


class QueryCrossCutTest(unittest.TestCase):

    def setUp(self):
        self.srv = SourceLocatorService()
        self.cfg = self.srv.config.pipeline

    def test_flags_intra_segment_jump_with_position_and_count(self):
        dense = _two_shot_dense()
        ann = self.srv._query_cross_cut(None, dense, self.cfg)
        self.assertIsInstance(ann, QueryCrossCut)
        self.assertGreater(ann.max_d, 0.5)
        self.assertEqual(ann.n_jumps, 1)
        # at = 跳变**后**那一帧在编辑片上的时刻（不是原片、不是跳变前）
        self.assertAlmostEqual(ann.at, 0.5, places=3)

    def test_no_annotation_when_segment_is_one_shot(self):
        self.assertIsNone(self.srv._query_cross_cut(None, _flat_dense(), self.cfg))

    def test_no_dense_no_annotation(self):
        self.assertIsNone(self.srv._query_cross_cut(None, None, self.cfg))

    def test_two_frames_are_not_judged(self):
        """≤2 帧分不出「段内切」与「整段都不同」，一律不标（档案 §10：短段统计量会失真）。"""
        dense = _two_shot_dense()
        self.assertIsNotNone(self.srv._query_cross_cut(None, dense, self.cfg))  # 8 帧先确认可标
        short = (dense[0][:2], dense[1][:2])
        self.assertIsNone(self.srv._query_cross_cut(None, short, self.cfg))

    def test_threshold_is_configurable_and_rolls_up(self):
        dense = _two_shot_dense()
        loose = dataclasses.replace(self.cfg, query_cross_cut_thresh=0.999)
        self.assertIsNone(self.srv._query_cross_cut(None, dense, loose))

    def test_annotation_does_not_touch_the_media_layer(self):
        """⭐ 判据只吃 dense：把取帧接口换成「一调就炸」，标注仍须正常产出。"""
        def _boom(*a, **k):
            raise AssertionError("跨镜头标注不得重新取帧（闭区间重筛会造边缘效应假阳）")

        class _NoMedia:
            iter_frames = staticmethod(_boom)
            grab_frame = staticmethod(_boom)

        self.srv._ffmpeg = _NoMedia()
        ann = self.srv._query_cross_cut(None, _two_shot_dense(), self.cfg)
        self.assertIsNotNone(ann)

    def test_contract_roundtrip_and_legacy_json(self):
        r = Result(edited=TimeSpan(0.0, 1.0), original=TimeSpan(10.0, 11.0))
        self.assertIsNone(r.to_dict()["query_cross_cut"])     # 未标注 => 契约里是 null，不是缺键
        r.query_cross_cut = self.srv._query_cross_cut(None, _two_shot_dense(), self.cfg)
        d = r.to_dict()
        self.assertEqual(d["query_cross_cut"]["n_jumps"], 1)
        self.assertEqual(Result.from_dict(d).query_cross_cut, r.query_cross_cut)
        legacy = {k: v for k, v in d.items() if k != "query_cross_cut"}
        self.assertIsNone(Result.from_dict(legacy).query_cross_cut)  # 旧结果文件照常可读


class CrossCutInertnessTest(unittest.TestCase):
    """⭐ 核心锁：这个字段对定位与置信度必须是惰性的。

    同一段、同一 dense、同一 bundle，只改 `query_cross_cut_thresh`（开满 0.0 / 关死 99.0），
    除该字段外**逐键比对**结果 JSON。任何差异都说明标注渗进了判据。
    两端都带「本档应当/不应当产出标注」的反空锁断言。
    """

    def _run(self, thr):
        rng = np.random.RandomState(0)
        orig = _l2(rng.randn(100, 384).astype(np.float32))
        from domain import IndexMeta
        from engine.feature_store import IndexBundle
        bundle = IndexBundle(IndexMeta("src", 0, 198.0, "hash"), orig,
                             (np.arange(100) * 2.0).astype(np.float32))
        src = _l2(orig[20:30] + 1e-3 * rng.randn(10, 384).astype(np.float32))
        shot = ShotSegment(TimeSpan(0.0, 4.5), src, (np.arange(10) * 0.5).astype(np.float32))
        dense = (src.copy(), (np.arange(10) * 0.125).astype(np.float32))

        srv = SourceLocatorService()
        srv._embed_dense_query = lambda s, e: dense
        cfg = dataclasses.replace(srv.config.pipeline, query_cross_cut_thresh=thr)
        res = srv._locate_features([shot], bundle, cfg=cfg, edited="fake.mp4")
        self.assertEqual(len(res), 1)
        d = res[0].to_dict()
        flagged = d["query_cross_cut"] is not None
        d.pop("query_cross_cut")
        # result_id 是每次构造现取的 uuid，与判据无关，不比
        d.pop("result_id")
        return d, flagged

    def test_annotation_changes_nothing_else(self):
        on, off = self._run(0.0), self._run(99.0)
        self.assertTrue(on[1], "阈值 0 时应当产出标注（否则本锁是空锁）")
        self.assertFalse(off[1], "阈值 99 时不应产出标注（否则本锁是空锁）")
        self.assertEqual(on[0], off[0], "标注开闭不得改变任何其他结果字段（含 confidence）")


if __name__ == "__main__":
    unittest.main()
