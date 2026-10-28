# -*- coding: utf-8 -*-
"""索引期两遍解码并发（PLAN_BATCH3 B3-1）的常驻锁。

锁三件事：
1. 默认关（未验收前不许翻默认）；
2. 开关真的进到 FeatureStore（生产走 locator_service 逐字段注入，漏接会静默退回默认值）；
3. 并发路径与串行路径调用的仍是同两个函数（结构锁：不许在并发分支里改写口径）。
"""
import inspect
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from app import SourceLocatorService
from engine.feature_store.feature_store import FeatureStore, _merged_progress
from domain.models import IndexProgress
from infrastructure.config import PipelineConfig
from media.ffmpeg import FFmpegIO

BENCH = Path(__file__).resolve().parents[2]
FFMPEG = BENCH / "tools" / "ffmpeg.exe"
FFPROBE = (BENCH.parent / "video-dedup-tool" / ".venv" / "Lib" / "site-packages"
           / "static_ffmpeg" / "bin" / "win32" / "ffprobe.exe")


class IndexParallelPassesTest(unittest.TestCase):
    def test_default_on(self):
        # 2026-10-28 全片双臂验收通过后翻默认（关掉即回串行老路径）
        self.assertTrue(PipelineConfig().index_parallel_passes)

    def _service(self, parallel):
        tmp = tempfile.mkdtemp()
        srv = SourceLocatorService(ffmpeg=FFmpegIO(ffmpeg=FFMPEG, ffprobe=FFPROBE),
                                   index_root=tmp, export_root=tmp)
        srv.config.pipeline.index_parallel_passes = parallel
        srv._store = None
        return srv

    def test_store_receives_flag_from_config(self):
        self.assertTrue(self._service(True).store.parallel_passes)

    def test_store_receives_false(self):
        self.assertFalse(self._service(False).store.parallel_passes)

    def test_merged_progress_monotone(self):
        seen = []
        cb = _merged_progress(lambda p: seen.append((p.stage, p.done, p.total)))
        self.assertIsNotNone(cb)
        seq = [("embedding", 10, 100), ("pixel_scan", 500, 1000), ("embedding", 20, 100),
               ("pixel_scan", 900, 1000), ("embedding", 100, 100), ("pixel_scan", 1000, 1000)]
        for st, d, t in seq:
            cb(IndexProgress(st, done=d, total=t))
        dones = [d for _, d, _ in seen]
        self.assertEqual(dones, sorted(dones), "合成进度必须单调不回退")
        self.assertEqual(seen[0][0], "index_combined")
        self.assertEqual(seen[-1][1:], (1000, 1000))

    def test_parallel_branch_still_calls_same_two_passes(self):
        src = inspect.getsource(FeatureStore.create_index)
        self.assertIn("_embed_stream", src)
        self.assertIn("_scan_pixel_boundaries", src)
        # 并发分支只是换个位置调用，不得出现第三遍解码或替代实现
        self.assertEqual(src.count("_embed_stream("), 1)
        self.assertEqual(src.count("_scan_pixel_boundaries("), 2)


if __name__ == "__main__":
    unittest.main()
