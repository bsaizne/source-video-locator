"""sequence_rerank 单测——全局时序一致性 DP(Phase 21 场景身份)。

真实案例:test4(水上乐园片)同场景相似滑道镜头,逐段独立定位产生 7 次时间倒退
——每段挑了"长得像"的错误实例。DP 用编辑顺序约束在候选里挑正确实例。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from engine.localization.sequence_rerank import sequence_rerank


def _item(idx, edited_mid, cands):
    return {"index": idx, "edited_mid": edited_mid,
            "cands": [{"mid": m, "score": s, "is_main": i == 0}
                      for i, (m, s) in enumerate(cands)]}


class SequenceRerankTest(unittest.TestCase):
    def test_monotone_case_unchanged(self):
        """编辑顺序与原片一致(test1/test3 形态)→ 主定位不被改动。"""
        items = [
            _item(0, 5.0, [(100, 1.0), (900, 0.6)]),
            _item(1, 15.0, [(300, 1.0), (1000, 0.6)]),
            _item(2, 30.0, [(500, 1.0), (1100, 0.6)]),
        ]
        out = sequence_rerank(items, order_lambda=0.001, skip_penalty=0.30)
        for o, it in zip(out, items):
            self.assertFalse(o["changed"])
            self.assertAlmostEqual(o["chosen_mid"], it["cands"][0]["mid"], places=5)

    def test_backward_violation_fixed(self):
        """test4 形态:s2 主定位倒退到 3191,但前段在 3341-3700——DP 应选顺序一致实例。"""
        items = [
            _item(0, 1.2, [(3341, 1.0), (900, 0.5)]),
            _item(1, 4.0, [(3699, 1.0), (900, 0.5)]),
            _item(2, 7.2, [(3191, 1.0), (3400, 0.8), (900, 0.5)]),
        ]
        out = sequence_rerank(items, order_lambda=0.001, skip_penalty=0.30)
        chosen = [o["chosen_mid"] for o in out]
        self.assertEqual(chosen[0], 3341)
        self.assertEqual(chosen[1], 3699)
        # s2:倒退 3699→3191 罚 0.508 > 弱候选差(0.8 vs 1.0 归一后 1.0/0.8)→ 应改选 3400
        self.assertEqual(chosen[2], 3400)
        self.assertTrue(out[2]["changed"])

    def test_skip_escapes_for_flashback(self):
        """闪回段:SKIP(保原位)比强顺序罚更优时,允许逃生。"""
        items = [
            _item(0, 5.0, [(3000, 1.0), (100, 0.9)]),
            _item(1, 30.0, [(100, 1.0), (2900, 0.95)]),  # 闪回:真位置在很早处
        ]
        out = sequence_rerank(items, order_lambda=0.001, skip_penalty=0.30)
        # s1 的 100 处:从 3000 倒退 2900 罚 2.9 > skip 0.3 + 弱差 → 仍选 3000 或 SKIP
        # 断言:不会因为顺序约束被强行掰到明显低分的位置
        chosen = out[1]["chosen_mid"]
        if chosen is not None:
            self.assertGreaterEqual(out[1]["chosen_score"], 0.5)

    def test_single_candidate_passthrough(self):
        """单候选段无重排余地:chosen_mid=None(调用方保持原主定位)。"""
        items = [_item(0, 5.0, [(100, 1.0)])]
        out = sequence_rerank(items, order_lambda=0.001, skip_penalty=0.30)
        self.assertFalse(out[0]["changed"])
        self.assertIsNone(out[0]["chosen_mid"])


if __name__ == "__main__":
    unittest.main()
