"""API 层多原片合并接线测试（2026-09-29 video.concat 移植）。

覆盖三处：
- ``POST /api/tasks/analyze`` 的 ``original_paths``（≥2 → worker 先合并、合并产物回写
  task.original_path；单元素 → 等价 original_path）；
- ``POST /api/source/merge`` 独立端点（校验 + 响应形态）；
- 进度映射 MERGE_SOURCES → INDEXING 区间插值。

不跑真实 ffmpeg：FakeService 记录 merge/locate 调用。

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_source_merge -v
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

from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context
from mvp.api.tasks import TaskManager, TaskStage, TaskStatus, map_progress_stage, run_worker
from mvp.api.tasks.models import Task

_sync_run = lambda fn: fn()  # noqa: E731


def _sample_batch(original="D:/merged/merged_2_ab12cd34ef5a_copy.mp4") -> ResultBatch:
    return ResultBatch(
        schema_version=1, original_video=original, edited_video="D:/e.mp4",
        results=[Result(edited=TimeSpan(1.0, 5.0), original=TimeSpan(3.0, 7.0),
                        confidence=Confidence(ConfidenceLevel.HIGH, 0.9, ("rank1",)),
                        candidate_rank=1)],
    )


class FakeMergeService:
    def __init__(self):
        self.merge_calls: list[list[str]] = []
        self.locate_calls: list[tuple[str, str]] = []

    def merge_originals(self, sources, *, on_progress=None, cancel_token=None):
        self.merge_calls.append(list(sources))
        if on_progress is not None:
            on_progress(ProgressEvent(ProgressStage.MERGE_SOURCES, 50, 100, "流复制合并 50%"))
        return {"merged_path": "D:/merged/merged_2_ab12cd34ef5a_copy.mp4",
                "mode": "copy", "reused": False, "duration_s": 100.0}

    def locate(self, edited_path, original_path, *, on_progress=None, cancel_token=None):
        self.locate_calls.append((str(edited_path), str(original_path)))
        return _sample_batch()


class ApiTestBase(unittest.TestCase):
    def setUp(self):
        self.fake = FakeMergeService()
        self.tm = TaskManager(self.fake, run_in_background=_sync_run)
        self.context = AppContext(service=self.fake, task_manager=self.tm)
        self.app = create_app()
        self.app.dependency_overrides[get_context] = lambda: self.context
        self._client = TestClient(self.app)
        self._client.__enter__()

    def tearDown(self):
        self._client.__exit__(None, None, None)
        self.app.dependency_overrides.clear()


class AnalyzeWithMultipleOriginalsTest(ApiTestBase):
    def test_two_paths_trigger_merge_then_locate_with_merged(self):
        r = self._client.post("/api/tasks/analyze", json={
            "edited_path": "D:/e.mp4",
            "original_paths": ["D:/v/ep1.mkv", "D:/v/ep2.mkv"],
        })
        self.assertEqual(r.status_code, 200)
        task = self.tm.get(r.json()["task_id"])
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(self.fake.merge_calls, [["D:/v/ep1.mkv", "D:/v/ep2.mkv"]])
        # locate 收到的是合并产物，且 task.original_path 回写（下游结果/导出单原片口径）
        self.assertEqual(self.fake.locate_calls,
                         [("D:/e.mp4", "D:/merged/merged_2_ab12cd34ef5a_copy.mp4")])
        self.assertEqual(task.original_path, "D:/merged/merged_2_ab12cd34ef5a_copy.mp4")

    def test_single_path_in_list_skips_merge(self):
        r = self._client.post("/api/tasks/analyze", json={
            "edited_path": "D:/e.mp4",
            "original_paths": ["D:/v/only.mkv"],
        })
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.fake.merge_calls, [])
        self.assertEqual(self.fake.locate_calls, [("D:/e.mp4", "D:/v/only.mkv")])

    def test_legacy_single_original_path_still_works(self):
        r = self._client.post("/api/tasks/analyze", json={
            "edited_path": "D:/e.mp4", "original_path": "D:/v/single.mkv"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.fake.locate_calls, [("D:/e.mp4", "D:/v/single.mkv")])

    def test_requires_at_least_one_original(self):
        r = self._client.post("/api/tasks/analyze", json={"edited_path": "D:/e.mp4"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "bad_request")

    def test_worker_direct_submit_merge_progress_frame(self):
        seen: list[tuple] = []
        task = Task(edited_path="D:/e.mp4", original_path="",
                    original_paths=["D:/a.mkv", "D:/b.mkv"])

        def record(fn):  # 同步执行 worker 前订阅进度帧
            q = task.subscribe()
            fn()
            while not q.empty():
                seen.append(q.get_nowait())

        record(lambda: run_worker(task, self.fake))
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.original_path, "D:/merged/merged_2_ab12cd34ef5a_copy.mp4")
        frames = [f for f in seen if f["type"] == "progress"]
        self.assertTrue(any(f["stage"] == TaskStage.INDEXING.value and "流复制合并" in f["message"]
                            for f in frames), frames)


class SourceMergeEndpointTest(ApiTestBase):
    def test_merge_endpoint_returns_shape(self):
        r = self._client.post("/api/source/merge",
                              json={"paths": ["D:/v/1.mkv", "D:/v/2.mkv"]})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["mode"], "copy")
        self.assertTrue(body["merged_path"].endswith(".mp4"))
        self.assertFalse(body["reused"])
        self.assertEqual(self.fake.merge_calls, [["D:/v/1.mkv", "D:/v/2.mkv"]])

    def test_merge_endpoint_rejects_fewer_than_two(self):
        r = self._client.post("/api/source/merge", json={"paths": ["D:/v/1.mkv"]})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "bad_request")
        self.assertEqual(self.fake.merge_calls, [])


class MergeStageMappingTest(unittest.TestCase):
    def test_merge_sources_interpolates_in_indexing_range(self):
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.MERGE_SOURCES, 50, 100)),
                         (TaskStage.INDEXING, 6))
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.MERGE_SOURCES)),
                         (TaskStage.INDEXING, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
