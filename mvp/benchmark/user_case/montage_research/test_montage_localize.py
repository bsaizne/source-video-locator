"""montage_localize 模块单测（确定性，无 IO，无模型/素材依赖）。

构造合成索引 + 编辑查询特征，验证：
  - cluster_by_gap：纯聚类函数（切簇/合并边界）。
  - clean 段（单个连贯簇）→ mode=clean、单 span、区间贴近匹配簇。
  - montage 段（两个相距远的簇）→ mode=montage、两个 span、各自不同原片区。
  - empty（0 帧查询 / 无显著簇）→ mode=empty。
  - 弱簇过滤：双低（低 cover 且低 best_sim）子 span 被丢弃。

运行（venv python，需 mvp/src 在 path）:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest \
     mvp/benchmark/user_case/montage_research/test_montage_localize -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

_MPV_SRC = Path(__file__).resolve().parents[3] / "src"   # -> mvp/src (parents[3]=.../mvp)
sys.path.insert(0, str(_MPV_SRC))

from domain import IndexMeta                            # noqa: E402
from engine.feature_store import IndexBundle            # noqa: E402

from montage_localize import MontageLocalizer, cluster_by_gap  # noqa: E402

RNG = np.random.RandomState(42)


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-8)


def _make_bundle(n=100, fps=2.0, dim=384):
    feats = _unit(RNG.randn(n, dim).astype(np.float32))
    times = (np.arange(n) * fps).astype(np.float32)
    meta = IndexMeta(source_file="test", file_size=0, duration=float(times[-1]),
                     file_hash="h", num_frames=n, feature_dim=dim)
    return IndexBundle(meta=meta, features=feats, times=times)


def _query_from_rows(bundle, rows, noise=0.01):
    """从索引行构造查询特征（接近归一化）+ 对应编辑时间。返回 (feats, ed_times)。"""
    feats = _unit(bundle.features[rows] + noise * RNG.randn(len(rows), bundle.features.shape[1]).astype(np.float32))
    ed_times = (np.arange(len(rows)) * 0.5).astype(np.float32)
    return feats, ed_times


class TestClusterByGap(unittest.TestCase):
    def test_single_cluster(self):
        self.assertEqual(cluster_by_gap(np.array([10.0, 11.0, 13.0], dtype=np.float32), 5.0),
                         [(10.0, 13.0, 3)])
        self.assertEqual(cluster_by_gap(np.array([], dtype=np.float32), 5.0), [])

    def test_split_clusters(self):
        cl = cluster_by_gap(np.array([10.0, 12.0, 40.0, 42.0], dtype=np.float32), 5.0)
        self.assertEqual([(round(a, 0), round(b, 0), c) for a, b, c in cl],
                         [(10.0, 12.0, 2), (40.0, 42.0, 2)])

    def test_gap_boundary(self):
        # 相邻 <= gap 合并；> gap 切分
        cl = cluster_by_gap(np.array([10.0, 15.0, 15.1], dtype=np.float32), 5.0)
        self.assertEqual(len(cl), 1)


class TestMontageLocalizer(unittest.TestCase):
    def setUp(self):
        self.b = _make_bundle()

    def _mk(self, **kw):
        return MontageLocalizer(**kw)

    def test_clean_single_span(self):
        rows = np.array([10, 11, 12])
        qf, qt = _query_from_rows(self.b, rows)
        r = self._mk().localize(qf, qt, self.b)
        self.assertEqual(r.mode, "clean")
        self.assertEqual(len(r.spans), 1)
        sp = r.spans[0].original_span
        self.assertGreaterEqual(sp[0], 18)
        self.assertLessEqual(sp[1], 26)
        # 编辑区间与查询帧时间一致
        self.assertEqual(r.spans[0].edited_interval, (0.0, 1.0))

    def test_montage_two_spans_distinct(self):
        rows = np.array([10, 11, 12, 60, 61, 62])
        qf, qt = _query_from_rows(self.b, rows)
        r = self._mk().localize(qf, qt, self.b)
        self.assertEqual(r.mode, "montage")
        self.assertGreaterEqual(len(r.spans), 2)
        spans = sorted(s.original_span for s in r.spans)
        self.assertLess(spans[0][1], spans[1][0])     # 两个子 span 在原片上不相交
        self.assertLess(spans[0][1], 40)
        self.assertGreater(spans[1][1], 110)

    def test_empty_no_frames(self):
        qf = np.zeros((0, 384), dtype=np.float32)
        r = self._mk().localize(qf, np.zeros(0, dtype=np.float32), self.b)
        self.assertEqual(r.mode, "empty")

    def test_empty_no_significant_cluster(self):
        # 每帧各自匹配到唯一且仅 1-2 帧的簇（< min_frames=3）→ 无显著簇 → empty
        rows = np.array([5, 15, 25, 35, 45])           # 均相隔 10s，各自小簇
        qf, qt = _query_from_rows(self.b, rows)
        r = self._mk(min_frames=3).localize(qf, qt, self.b)
        self.assertEqual(r.mode, "empty")

    def test_weak_cluster_dropped(self):
        # 强簇：精确不同索引行（best_sim 高，保留）；弱簇：3 帧全部匹配同一索引行
        # （run 短 + 窗宽 → finloc cover 低 + best_sim 降到 ~0.67，被弱簇丢弃）。
        strong = _unit(self.b.features[[5, 6, 7]])
        weak = _unit(np.repeat(self.b.features[95:96], 3, axis=0)
                     + 0.05 * RNG.randn(3, 384).astype(np.float32))
        qf = _unit(np.vstack([strong, weak]))
        qt = np.arange(6, dtype=np.float32) * 0.5
        r = self._mk(weak_cover=0.6, weak_sim=0.70).localize(qf, qt, self.b)
        self.assertEqual(r.mode, "montage")           # 强簇保留
        self.assertGreaterEqual(len(r.spans), 1)
        self.assertGreaterEqual(r.n_dropped_weak, 1)  # 弱簇被丢弃


if __name__ == "__main__":
    unittest.main()
