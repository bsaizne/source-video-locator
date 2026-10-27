from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from app import SourceLocatorService
from domain import Result, TimeSpan
from engine.xfeat_start import resolve_xfeat_models, resolve_xfeat_models_auto

_BENCH = Path(__file__).resolve().parents[2]
_FFMPEG = _BENCH / "tools/ffmpeg.exe"
_FFPROBE = (_BENCH.parent / "video-dedup-tool/.venv/Lib/site-packages/static_ffmpeg/bin/win32"
            / "ffprobe.exe")


class ResolveTest(unittest.TestCase):
    def test_missing_and_env_override(self):
        import tempfile

        self.assertIsNone(resolve_xfeat_models(Path("Z:/no/such/dir")))
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "xfeat").mkdir()
            (root / "xfeat/xfeat.pt").write_bytes(b"x")
            (root / "xfeat/xfeat-lighterglue.pt").write_bytes(b"y")
            got = resolve_xfeat_models_auto(Path("Z:/no/such/dir"),
                                            env={"SVL_XFEAT_MODELS_ROOT": str(root)})
            self.assertIsNotNone(got)
            self.assertEqual(got[0].parent, root / "xfeat")
            (root / "xfeat/xfeat.pt").unlink()
            self.assertIsNone(resolve_xfeat_models(root))

    def test_default_on(self):
        self.assertTrue(SourceLocatorService().config.pipeline.xfeat_start_enabled)


class ServiceTest(unittest.TestCase):
    def test_applies_stub_and_keeps_width(self):
        service = SourceLocatorService()

        class Stub:
            def refine(self, *args, **kwargs):
                return {"start": 11.25, "current_inliers": 4, "best_inliers": 12}

        service._xfeat_refiner = Stub()
        row = Result(edited=TimeSpan(0, 1), original=TimeSpan(10, 12))
        service._apply_xfeat_start_refinement([row], "edited.mp4", "source.mp4")
        self.assertEqual(row.original, TimeSpan(11.25, 12))

    def test_failure_keeps_original(self):
        service = SourceLocatorService()

        class Stub:
            def refine(self, *args, **kwargs):
                raise RuntimeError("expected")

        service._xfeat_refiner = Stub()
        row = Result(edited=TimeSpan(0, 1), original=TimeSpan(10, 12))
        service._apply_xfeat_start_refinement([row], "edited.mp4", "source.mp4")
        self.assertEqual(row.original, TimeSpan(10, 12))


class RealModelTest(unittest.TestCase):
    def test_known_hard_sample(self):
        from infrastructure.paths import models_root
        from media.ffmpeg import FFmpegIO
        from engine.xfeat_start import XFeatStartRefiner

        models = resolve_xfeat_models(models_root())
        if models is None or not _FFMPEG.exists() or not _FFPROBE.exists():
            self.skipTest("xfeat models or ffmpeg missing")
        edited = _BENCH.parent.parent / "ProjectXIXI/test1/test1-ed.mp4"
        source = _BENCH.parent.parent / "ProjectXIXI/test1/test1-om.mkv"
        if not edited.exists() or not source.exists():
            self.skipTest("test1 media missing")
        refiner = XFeatStartRefiner(models, FFmpegIO(ffmpeg=_FFMPEG, ffprobe=_FFPROBE))
        refined = refiner.refine(edited, source, 49.9333, 51.5333, 3135.2)
        self.assertIsNotNone(refined)
        self.assertAlmostEqual(refined["start"], 3135.94, places=2)
        self.assertGreaterEqual(refined["best_inliers"], 300)


if __name__ == "__main__":
    unittest.main()
