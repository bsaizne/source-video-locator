"""``build_original_index`` 在「只有派生表过期」时必须走 refresh_derived，不走全量重建。

这条路由是 scn1->scn2 升级不烧 GPU 推理的唯一保证；判据 = **哪个方法被调用**，
不是日志文本（日志会改，调用序列不会）。
"""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

import numpy as np
from domain import IndexMeta, IndexValidation, IndexValidationStatus
from engine.feature_store import IndexBundle
from app.locator_service import SourceLocatorService

BENCH = Path(__file__).resolve().parents[2]
SYNTH = BENCH / "datasets" / "synthetic" / "edited" / "a1.mp4"
N = 45


def _meta() -> IndexMeta:
    return IndexMeta(source_file=str(SYNTH), file_size=1, duration=float(N),
                     file_hash="sha256:x", sampling_fps=1.0, num_frames=N,
                     feature_version="fv", feature_dim=384, backend="cpu")


class _StubStore:
    """只记录被调了哪些方法；``create_index`` 一旦被调就当场判负（它就是本测试要排除的路径）。"""

    def __init__(self, validation: IndexValidation, *, allow_create=False):
        self.validation = validation
        self.allow_create = allow_create
        self.calls: list[str] = []

    def validate_index(self, video):
        self.calls.append("validate")
        return self.validation

    def create_index(self, video, backend, progress=None):
        self.calls.append("create")
        if not self.allow_create:
            raise AssertionError("走了全量重建：派生表过期不该重抽特征")
        return _meta()

    def refresh_derived(self, video, progress=None):
        self.calls.append("refresh")
        return _meta()

    def load_index(self, video):
        self.calls.append("load")
        feats = np.tile(np.eye(384, dtype=np.float32)[0], (N, 1))
        return IndexBundle(_meta(), feats, np.arange(N, dtype=np.float32),
                           scenes=np.array([[0.0, float(N)]], dtype=np.float32),
                           scene_feats=feats[:1])


@unittest.skipUnless(SYNTH.exists(), "synthetic clip not present")
class DerivedStaleRoutingTest(unittest.TestCase):
    def _run(self, validation, **kw):
        srv = SourceLocatorService()
        store = _StubStore(validation, **kw)
        srv._store = store
        bundle = srv.build_original_index(SYNTH)
        return store.calls, bundle

    def test_derived_stale_routes_to_refresh_not_create(self):
        calls, bundle = self._run(IndexValidation(
            IndexValidationStatus.INVALID,
            "derived table version changed (a+scn1+evt1 -> a+scn2+evt1)", derived_stale=True))
        self.assertEqual(calls, ["validate", "refresh", "load"])
        self.assertIsNotNone(bundle)

    def test_plain_invalid_still_routes_to_create(self):
        """反例：基座/内容变了必须回到全量重建，不能被 refresh 短路。"""
        calls, _ = self._run(IndexValidation(IndexValidationStatus.INVALID,
                                             "feature version changed"),
                             allow_create=True)
        self.assertEqual(calls, ["validate", "create", "load"])

    def test_valid_index_is_reused_without_either(self):
        calls, _ = self._run(IndexValidation(IndexValidationStatus.VALID))
        self.assertEqual(calls, ["validate", "load"])

    def test_derived_stale_flag_is_not_leaked_to_api_contract(self):
        v = IndexValidation(IndexValidationStatus.INVALID, "derived table version changed",
                            derived_stale=True)
        self.assertEqual(set(v.to_dict()), {"status", "reason"})


if __name__ == "__main__":
    unittest.main()
