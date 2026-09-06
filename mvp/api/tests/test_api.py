"""Unit tests for mvp.api (FastAPI bridge).

Run with the venv python:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_api -v

栈：unittest + fastapi.testclient.TestClient。用 FakeService/FakeContext 覆盖 service 方法，
``app.dependency_overrides[get_context]`` 一处注入，避免真实模型/视频计算。
"""
from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import SimpleNamespace

_MVP = Path(__file__).resolve().parents[2]   # .../mvp
if str(_MVP.parent) not in sys.path:
    sys.path.insert(0, str(_MVP.parent))     # .../ (benchmark)，使 `import mvp.api.*` 生效

from fastapi.testclient import TestClient

from domain import (Confidence, ConfidenceLevel, IndexMeta, Result, ResultBatch,
                    TimeSpan)
from infrastructure.errors import ApplicationError, LocatorError
from infrastructure.logging import configure_logging, set_session_id

from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context


# --------------------------------------------------------------------- Fakes
class FakeService:
    """镜像 SourceLocatorService 的调用签名，返回可序列化的轻量结果。"""

    def __init__(self, *, fail_build=False):
        self.fail_build = fail_build
        self.build_calls: list[str] = []
        self.analyze_calls: list[str] = []
        self.locate_calls: list[tuple[str, str]] = []
        self.export_calls: list[tuple | None] = []

    def build_original_index(self, video_path, *, on_progress=None, cancel_token=None):
        if self.fail_build:
            raise LocatorError("boom in index")
        self.build_calls.append(video_path)
        meta = IndexMeta(
            source_file=Path(video_path).name, file_size=1_073_741_824,
            duration=8310.0, file_hash="sha256:3f1c",
            num_frames=3834, backend="cpu",
        )
        return SimpleNamespace(meta=meta)

    def analyze_edited_video(self, edited_path, *, on_progress=None, cancel_token=None):
        self.analyze_calls.append(edited_path)
        return [SimpleNamespace(span=TimeSpan(3.1, 21.4), nq=36)]

    def locate(self, edited_path, original, *, on_progress=None, cancel_token=None,
               index_bundle=None):
        self.locate_calls.append((edited_path, str(original)))
        return _sample_batch()

    def export_results(self, batch, *, out_dir=None, filename=None,
                       on_progress=None, cancel_token=None):
        self.export_calls.append((out_dir, filename))
        return Path(out_dir) / "result.results.json"

    def export_project(self, batch, *, fmt, out_dir=None, filename=None,
                       min_confidence=None, low_policy=None, snap_scenes=None,
                       material_width=None, on_progress=None, cancel_token=None):
        self.export_calls.append((fmt, out_dir, min_confidence, low_policy, snap_scenes))
        if fmt not in ("edl", "fcp7_xml", "jianying"):
            raise ApplicationError(f"invalid export format: {fmt!r}")
        base = Path(out_dir) if out_dir else Path("exports")
        name = filename or f"x.loc.{'jy_draft' if fmt == 'jianying' else fmt}"
        return base / name

    def last_result_batch(self):
        # Fake 默认无异步结果批；export 端点 current_batch 为空时会回退到这里。
        return getattr(self, "_last_batch", None)

    def load_results(self, path):
        return _sample_batch()


def _sample_batch() -> ResultBatch:
    return ResultBatch(
        schema_version=1,
        original_video="Interstellar (2014).mkv",
        edited_video="trailer_compilation.mp4",
        results=[
            Result(
                edited=TimeSpan(3.1, 21.4),
                original=TimeSpan(5025.0, 5042.0),
                confidence=Confidence(ConfidenceLevel.HIGH, 0.94, ("rank1", "high_query_coverage")),
                candidate_rank=1,
            ),
        ],
    )


# ------------------------------------------------------------------ Root isolate
class _RootIsolateMixin:
    """快照并恢复 root logger 的 level/handlers，避免测试污染其它测试。"""

    def _snapshot(self):
        root = logging.getLogger()
        return (root.level, list(root.handlers))

    def _restore(self, snap):
        root = logging.getLogger()
        root.setLevel(snap[0])
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()
        for h in snap[1]:
            root.addHandler(h)

    def _flush_files(self):
        for h in logging.getLogger().handlers:
            if isinstance(h, RotatingFileHandler):
                h.flush()


class ApiTestBase(unittest.TestCase, _RootIsolateMixin):
    """每用例：新 fake + 覆盖 get_context + 新 TestClient（触发 lifespan 的 configure_logging）。"""

    def setUp(self):
        self.fake = FakeService()
        self.context = AppContext(service=self.fake)
        self.app = create_app()
        self.app.dependency_overrides[get_context] = lambda: self.context
        self._client = TestClient(self.app)
        self._client.__enter__()

    def tearDown(self):
        self._client.__exit__(None, None, None)
        self.app.dependency_overrides.clear()


# --------------------------------------------------------------------- Tests
class HealthTest(ApiTestBase):
    def test_health_returns_200(self):
        r = self._client.get("/api/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "ok", "version": "0.1"})


class IndexTest(ApiTestBase):
    def test_index_calls_service(self):
        r = self._client.post("/api/index", json={"video_path": "D:/movie/source.mkv"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["frames"], 3834)
        self.assertEqual(body["backend"]["device_name"], "cpu")
        self.assertEqual(body["backend"]["device_type"], "cpu")
        self.assertEqual(self.fake.build_calls, ["D:/movie/source.mkv"])
        self.assertEqual(self.context.current_original, Path("D:/movie/source.mkv"))

    def test_index_exception_maps_to_500(self):
        self.fake.fail_build = True
        r = self._client.post("/api/index", json={"video_path": "D:/movie/source.mkv"})
        self.assertEqual(r.status_code, 500)
        body = r.json()
        self.assertIn("error", body)
        self.assertIn("detail", body)


class AnalysisTest(ApiTestBase):
    def test_analyze_returns_segments_array(self):
        r = self._client.post("/api/analyze", json={"edited_path": "D:/clip.mp4"})
        self.assertEqual(r.status_code, 200)
        segs = r.json()["segments"]
        self.assertEqual(len(segs), 1)
        seg = segs[0]
        self.assertEqual(set(seg.keys()), {"id", "label", "span", "nq"})
        self.assertEqual(seg["span"], {"start": 3.1, "end": 21.4})
        self.assertEqual(seg["nq"], 36)
        self.assertEqual(self.fake.analyze_calls, ["D:/clip.mp4"])


class ResultsTest(ApiTestBase):
    def test_results_flattened_confidence_and_calls_locate(self):
        r = self._client.post(
            "/api/results", json={"edited_path": "D:/clip.mp4", "original_path": "D:/movie/source.mkv"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["schema_version"], 1)
        res = body["results"][0]
        self.assertEqual(res["confidence"], "HIGH")
        self.assertIn("confidence_score", res)
        self.assertIn("reasons", res)
        # 拍平：不应有嵌套 level object
        self.assertNotIn("level", res)
        self.assertEqual(res["confidence_score"], 0.94)
        self.assertEqual(self.fake.locate_calls, [("D:/clip.mp4", "D:/movie/source.mkv")])
        self.assertEqual(self.context.current_original, Path("D:/movie/source.mkv"))
        self.assertIsNotNone(self.context.current_batch)

    def test_results_uses_current_original_when_not_provided(self):
        orig = Path("D:/movie/source.mkv")
        self.context.current_original = orig
        r = self._client.post("/api/results", json={"edited_path": "D:/clip.mp4"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.fake.locate_calls, [("D:/clip.mp4", str(orig))])

    def test_results_no_original_returns_400(self):
        r = self._client.post("/api/results", json={"edited_path": "D:/clip.mp4"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "no_original")


class ExportTest(ApiTestBase):
    def test_export_without_batch_returns_400(self):
        r = self._client.post("/api/export", json={"output_dir": "D:/export"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "no_results")

    def test_export_with_batch_calls_service(self):
        self._client.post("/api/results",
                          json={"edited_path": "D:/clip.mp4", "original_path": "D:/movie/source.mkv"})
        r = self._client.post("/api/export", json={"output_dir": "D:/export"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(str(r.json()["path"]).endswith("result.results.json"))
        self.assertEqual(self.fake.export_calls[0][0], "D:/export")

    def test_export_edl_format_routes_to_export_project(self):
        self._client.post("/api/results",
                          json={"edited_path": "D:/clip.mp4", "original_path": "D:/movie/source.mkv"})
        r = self._client.post("/api/export",
                              json={"output_dir": "D:/export", "format": "edl",
                                    "min_confidence": "MEDIUM", "low_policy": "backup",
                                    "snap_scenes": True})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(str(r.json()["path"]).endswith(".loc.edl"))
        self.assertEqual(self.fake.export_calls[-1],
                         ("edl", "D:/export", "MEDIUM", "backup", True))

    def test_override_updates_batch_and_preserves_auto(self):
        resp = self._client.post("/api/results",
                                 json={"edited_path": "D:/clip.mp4", "original_path": "D:/movie/source.mkv"})
        rid = resp.json()["results"][0]["result_id"]   # ctx.current_batch 里的同一实例
        r = self._client.post("/api/results/override",
                              json={"result_id": rid, "start": 100.0, "end": 105.0})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["original"], {"candidate_start": 100.0, "candidate_end": 105.0})
        self.assertTrue(body["manual_override"])
        self.assertEqual(body["source"], "manual")
        self.assertIsNotNone(body["auto_result"])

    def test_override_bad_range_returns_400(self):
        from mvp.api.tests.test_api import _sample_batch  # noqa: PLC0415
        self._client.post("/api/results",
                          json={"edited_path": "D:/clip.mp4", "original_path": "D:/movie/source.mkv"})
        resp = self._client.post("/api/results",
                                 json={"edited_path": "D:/clip.mp4", "original_path": "D:/movie/source.mkv"})
        rid = resp.json()["results"][0]["result_id"]
        r = self._client.post("/api/results/override",
                              json={"result_id": rid, "start": 105.0, "end": 100.0})
        self.assertEqual(r.status_code, 400)

    def test_logs_recent_and_archive(self):
        recent = self._client.get("/api/logs/recent")
        self.assertEqual(recent.status_code, 200)
        self.assertIn("text", recent.json())
        archive = self._client.get("/api/logs/archive")
        self.assertEqual(archive.status_code, 200)
        self.assertIn("zip", archive.headers.get("content-type", ""))

    def test_export_unknown_format_returns_400(self):
        self._client.post("/api/results",
                          json={"edited_path": "D:/clip.mp4", "original_path": "D:/movie/source.mkv"})
        r = self._client.post("/api/export",
                              json={"output_dir": "D:/export", "format": "veg"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "export_failed")


class CorsTest(HealthTest):
    def test_cors_header_allowed_origin(self):
        r = self._client.get("/api/health", headers={"Origin": "http://localhost:5173"})
        self.assertEqual(r.headers.get("access-control-allow-origin"), "http://localhost:5173")


class SessionLogTest(ApiTestBase):
    def test_request_log_has_module_and_session(self):
        snap = self._snapshot()
        with tempfile.TemporaryDirectory() as td:
            try:
                configure_logging(log_dir=td)
                r = self._client.post("/api/index", json={"video_path": "D:/movie/source.mkv"})
                self.assertEqual(r.status_code, 200)
                self._flush_files()
                text = (Path(td) / "video_locator.log").read_text(encoding="utf-8")
                self.assertIn("module=api", text)
                self.assertIn("POST /api/index", text)
                self.assertRegex(text, r"session=[0-9a-f]{8}")
            finally:
                set_session_id("")  # 清理上下文
                self._restore(snap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
