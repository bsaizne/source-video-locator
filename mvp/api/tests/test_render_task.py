"""API 层成片渲染任务接线测试（2026-09-29 续30，竞品 video_renderer 移植）。

覆盖四处（不跑真实 ffmpeg，FakeRenderService 记录调用）：
- ``TaskManager.submit_render`` + ``run_worker`` 按 ``kind`` 分派到渲染 worker；
- ``POST /api/tasks/render``：会话批缺失 → 400；有批 → task_id，渲染目标**在提交时锁定**；
- 渲染进度 ``ProgressStage.RENDER_MOVIE`` → ``TaskStage.EXPORTING`` 全区间插值；
- 失败/取消 → ``failed``（对外话术 + LOC 码）/ ``cancelled``。

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_render_task -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_MVP = Path(__file__).resolve().parents[2]
if str(_MVP.parent) not in sys.path:
    sys.path.insert(0, str(_MVP.parent))

from fastapi.testclient import TestClient

from app.models import ProgressEvent, ProgressStage
from domain import Confidence, ConfidenceLevel, Result, ResultBatch, TimeSpan
from infrastructure.errors import ApplicationError

from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context
from mvp.api.tasks import TaskManager, TaskStage, TaskStatus, map_progress_stage
from mvp.api.tasks.models import Task, TaskKind

_sync_run = lambda fn: fn()  # noqa: E731

_MOVIE = "D:/appdata/rendered/movie_x_ab12cd34ef5a.mp4"


def _sample_batch() -> ResultBatch:
    return ResultBatch(
        schema_version=1, original_video="D:/v/om.mkv", edited_video="D:/e.mp4",
        results=[Result(edited=TimeSpan(1.0, 5.0), original=TimeSpan(3.0, 7.0),
                        confidence=Confidence(ConfidenceLevel.HIGH, 0.9, ("rank1",)),
                        candidate_rank=1)],
    )


class FakeRenderService:
    def __init__(self, *, fail: bool = False, cancel: bool = False):
        self.calls: list[dict] = []
        self._fail = fail
        self._cancel = cancel
        self._batch = None

    def last_result_batch(self):
        return self._batch

    def render_movie(self, batch, *, out_dir=None, min_confidence=None, low_policy=None,
                     snap_scenes=None, on_progress=None, cancel_token=None):
        self.calls.append({"batch": batch, "out_dir": out_dir,
                           "min_confidence": min_confidence, "low_policy": low_policy,
                           "snap_scenes": snap_scenes})
        if on_progress is not None:
            on_progress(ProgressEvent(ProgressStage.RENDER_MOVIE, 30, 100,
                                      "片段 3/10 渲染 30%"))
        if self._cancel:
            raise ApplicationError("片段 1 已取消")
        if self._fail:
            raise ApplicationError("没有可渲染的片段")
        return {"movie_path": _MOVIE, "mode": "copy", "reused": False, "segments": 10,
                "fps": "24000/1001", "duration_s": 42.5, "total_frames": 1019,
                "actual_encoder": "libx264", "hdr_downgraded": False, "clips": 10}


class RenderTaskTest(unittest.TestCase):
    def test_submit_render_locks_batch_and_completes(self):
        svc = FakeRenderService()
        tm = TaskManager(svc, run_in_background=_sync_run)
        batch = _sample_batch()
        task = tm.submit_render(batch, out_dir="D:/out", min_confidence="HIGH",
                                 snap_scenes=False)
        self.assertIs(task.kind, TaskKind.RENDER)
        self.assertIs(svc.calls[0]["batch"], batch)          # 提交时锁定的批，不是"最新批"
        self.assertEqual(svc.calls[0]["out_dir"], "D:/out")
        self.assertEqual(svc.calls[0]["min_confidence"], "HIGH")
        self.assertIs(svc.calls[0]["snap_scenes"], False)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.result["kind"], "render")
        self.assertEqual(task.result["movie_path"], _MOVIE)
        self.assertEqual(task.result["total_frames"], 1019)

    def test_render_without_batch_fails_gracefully(self):
        svc = FakeRenderService()
        tm = TaskManager(svc, run_in_background=_sync_run)
        task = Task(kind=TaskKind.RENDER)                   # render_batch=None 且会话无批
        from mvp.api.tasks.worker import run_worker
        run_worker(task, svc)
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertIn("没有可渲染的结果批", task.error or "")

    def test_render_failure_maps_to_public_error(self):
        svc = FakeRenderService(fail=True)
        tm = TaskManager(svc, run_in_background=_sync_run)
        task = tm.submit_render(_sample_batch())
        self.assertEqual(task.status, TaskStatus.FAILED)
        # 对外话术 + 稳定码（与 task 通道既有纪律一致，不吐技术串）
        self.assertIn("（LOC-", task.error or "")

    def test_render_cancel_marks_cancelled(self):
        class CancellingService(FakeRenderService):
            def render_movie(self, batch, **kw):
                token = kw.get("cancel_token")
                if token is not None:
                    token.cancel()
                return super().render_movie(batch, **kw)

        svc = CancellingService(cancel=True)
        tm = TaskManager(svc, run_in_background=_sync_run)
        task = tm.submit_render(_sample_batch())
        self.assertEqual(task.status, TaskStatus.CANCELLED)


class RenderStageMappingTest(unittest.TestCase):
    def test_render_movie_maps_to_exporting_full_range(self):
        stage, pct = map_progress_stage(
            ProgressEvent(ProgressStage.RENDER_MOVIE, 40, 100, "片段 4/10 渲染 40%"))
        self.assertIs(stage, TaskStage.EXPORTING)
        self.assertEqual(pct, 39.6)                          # 0-99 区间按 current/total 插值（续40 一位小数）

    def test_render_movie_unknown_total_uses_base(self):
        stage, pct = map_progress_stage(
            ProgressEvent(ProgressStage.RENDER_MOVIE, 0, 0, "心跳"))
        self.assertIs(stage, TaskStage.EXPORTING)
        self.assertEqual(pct, 0)


class RenderRouteTest(unittest.TestCase):
    def _client(self, svc: FakeRenderService, batch) -> TestClient:
        ctx = AppContext(service=svc,
                         task_manager=TaskManager(svc, run_in_background=_sync_run),
                         current_batch=batch)
        app = create_app()
        app.dependency_overrides[get_context] = lambda: ctx
        return TestClient(app)

    def test_post_tasks_render_returns_task_id(self):
        svc = FakeRenderService()
        client = self._client(svc, _sample_batch())
        r = client.post("/api/tasks/render",
                        json={"output_dir": "D:/out", "min_confidence": "MEDIUM",
                              "low_policy": "exclude", "snap_scenes": True})
        self.assertEqual(r.status_code, 200, r.text)
        task_id = r.json()["task_id"]
        got = client.get(f"/api/tasks/{task_id}").json()
        self.assertEqual(got["kind"], "render")
        self.assertEqual(got["status"], "completed")
        self.assertEqual(got["result"]["movie_path"], _MOVIE)

    def test_post_tasks_render_falls_back_to_service_batch(self):
        svc = FakeRenderService()
        svc._batch = _sample_batch()                        # 异步定位只写 service 侧批
        client = self._client(svc, None)
        r = client.post("/api/tasks/render", json={})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIs(svc.calls[0]["batch"], svc._batch)

    def test_post_tasks_render_without_batch_is_400(self):
        svc = FakeRenderService()
        client = self._client(svc, None)
        r = client.post("/api/tasks/render", json={})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "no_results")

    def test_analyze_task_still_reports_analyze_kind(self):
        """回归锁：新增 kind 字段不得改变既有分析任务的对外形态。"""

        class AnalyzeSvc:
            def locate(self, edited, original, *, on_progress=None, cancel_token=None, refine=None):
                return _sample_batch()

        svc = AnalyzeSvc()
        tm = TaskManager(svc, run_in_background=_sync_run)
        task = tm.submit_analyze("D:/e.mp4", "D:/v/om.mkv")
        self.assertEqual(task.to_dict()["kind"], "analyze")
        self.assertEqual(task.status, TaskStatus.COMPLETED)


if __name__ == "__main__":
    unittest.main()
