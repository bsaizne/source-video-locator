"""Unit tests for mvp.api.routes.progress (WS 实时进度).

Run with the venv python:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_progress -v

栈：unittest + fastapi.testclient.TestClient。**不跑真实 worker**（run_in_background=no-op）；
测试手动驱动 ``Task`` 状态（update_progress/mark_completed/mark_failed/mark_cancelled），让
WS 订阅从 Task 广播里收到帧——完全确定性，无关 worker 时序。worker 的进度/取消逻辑已由
``test_tasks`` 覆盖；这里是 WS 通信层。
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

_MVP = Path(__file__).resolve().parents[2]
if str(_MVP.parent) not in sys.path:
    sys.path.insert(0, str(_MVP.parent))

from fastapi.testclient import TestClient

from domain import Confidence, ConfidenceLevel, Result, ResultBatch, TimeSpan

from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context
from mvp.api.tasks import TaskManager, TaskStage

_noop_run = lambda fn: None  # noqa: E731 — 不真跑 worker（测试手动驱动 Task 状态）


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


class ProgressTestBase(unittest.TestCase):
    def setUp(self):
        self.tm = TaskManager(object(), run_in_background=_noop_run)
        self.context = AppContext(service=object(), task_manager=self.tm)
        self.app = create_app()
        self.app.dependency_overrides[get_context] = lambda: self.context
        self._client = TestClient(self.app)
        self._client.__enter__()

    def tearDown(self):
        self._client.__exit__(None, None, None)
        self.app.dependency_overrides.clear()

    def _start(self, edited="D:/e.mp4", original="D:/o.mkv") -> str:
        r = self._client.post(
            "/api/tasks/analyze", json={"edited_path": edited, "original_path": original}
        )
        self.assertEqual(r.status_code, 200)
        return r.json()["task_id"]


class ProgressTest(ProgressTestBase):
    def test_connect_receives_snapshot_then_progress_then_completed(self):
        task_id = self._start()
        with self._client.websocket_connect(f"/ws/progress/{task_id}") as ws:
            snap = ws.receive_json()
            self.assertEqual(snap["type"], "progress")
            self.assertEqual(snap["task_id"], task_id)
            self.assertEqual(snap["stage"], "idle")

            task = self.tm.get(task_id)
            task.update_progress(TaskStage.INDEXING, 10, "indexing frames")
            mid = ws.receive_json()
            self.assertEqual(mid["type"], "progress")
            self.assertEqual(mid["stage"], "indexing")
            self.assertEqual(mid["progress"], 10)
            self.assertEqual(mid["message"], "indexing frames")

            task.mark_completed(_sample_batch().to_dict())
            done = ws.receive_json()
            self.assertEqual(done["type"], "completed")
            self.assertEqual(done["task_id"], task_id)

    def test_failed_emits_error_frame(self):
        task_id = self._start()
        task = self.tm.get(task_id)
        with self._client.websocket_connect(f"/ws/progress/{task_id}") as ws:
            ws.receive_json()  # snapshot
            task.mark_failed("boom during localization")
            fail = ws.receive_json()
            self.assertEqual(fail["type"], "failed")
            self.assertIn("boom", fail.get("error", ""))

    def test_cancel_message_invokes_cancel_then_cancelled(self):
        task_id = self._start()
        task = self.tm.get(task_id)
        with self._client.websocket_connect(f"/ws/progress/{task_id}") as ws:
            ws.receive_json()  # snapshot
            ws.send_json({"type": "cancel"})
            # 等 WS handler 处理完 cancel（主协程最长 _POLL_TIMEOUT=0.5s 才醒来检查）
            deadline = time.time() + 1.0
            while time.time() < deadline and not task.cancel_requested:
                time.sleep(0.05)
            self.assertTrue(task.cancel_requested, "WS cancel should set cancel_requested")
            # 模拟 worker 响应取消（真正响应在 run_worker，已由 test_tasks 覆盖）
            task.mark_cancelled()
            cancelled = ws.receive_json()
            self.assertEqual(cancelled["type"], "cancelled")
            self.assertEqual(cancelled["task_id"], task_id)

    def test_unknown_task_returns_error(self):
        with self._client.websocket_connect("/ws/progress/nope") as ws:
            frame = ws.receive_json()
        self.assertEqual(frame.get("type"), "error")
        self.assertEqual(frame.get("error"), "unknown_task")


if __name__ == "__main__":
    unittest.main(verbosity=2)
