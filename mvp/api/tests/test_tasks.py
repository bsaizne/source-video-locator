"""Unit tests for mvp.api.tasks + /api/tasks/* routes.

Run with the venv python:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_tasks -v

栈：unittest + fastapi.testclient.TestClient。用 FakeService + 同步 run_in_background
（不起真线程，worker 在请求线程内同步跑完），override get_context 注入
AppContext(service=fake, task_manager=TaskManager(fake, run_in_background=同步))。
不跑真实模型/视频。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_MVP = Path(__file__).resolve().parents[2]   # .../mvp
if str(_MVP.parent) not in sys.path:
    sys.path.insert(0, str(_MVP.parent))     # .../ (benchmark)，使 `import mvp.api.*` 生效

from fastapi.testclient import TestClient

from app.models import ProgressEvent, ProgressStage
from domain import Confidence, ConfidenceLevel, Result, ResultBatch, TimeSpan
from infrastructure.errors import ApplicationError, LocatorError

from mvp.api.app import create_app
from mvp.api.dependencies import AppContext, get_context
from mvp.api.tasks import Task, TaskManager, TaskStage, TaskStatus, map_progress_stage, run_worker


# --------------------------------------------------------------------- Fakes
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


class FakeService:
    """镜像 SourceLocatorService.locate 签名；mode 决定 ok / fail / cancel。"""

    def __init__(self, mode: str = "ok"):
        self.mode = mode
        self.locate_calls: list[tuple] = []

    def locate(self, edited_path, original_path, *, on_progress=None, cancel_token=None, refine=None):
        self.locate_calls.append((edited_path, str(original_path), cancel_token))
        self.last_refine = refine
        if self.mode == "fail":
            raise LocatorError("boom")
        if on_progress is not None:
            on_progress(ProgressEvent(ProgressStage.INDEX_BUILD, 0, 0, "indexing"))
            on_progress(ProgressEvent(ProgressStage.SEGMENT_DETECTION, 0, 0, "segmenting"))
        # 模拟 SourceLocatorService 检测到取消 → 以 ApplicationError 穿透
        if cancel_token is not None and cancel_token.is_cancelled():
            raise ApplicationError("operation cancelled")
        return _sample_batch()


_sync_run = lambda fn: fn()  # noqa: E731 — 同步执行 worker（测试确定性）


class TaskApiTestBase(unittest.TestCase):
    def setUp(self):
        self.fake = FakeService("ok")
        self.tm = TaskManager(self.fake, run_in_background=_sync_run)
        self.context = AppContext(service=self.fake, task_manager=self.tm)
        self.app = create_app()
        self.app.dependency_overrides[get_context] = lambda: self.context
        self._client = TestClient(self.app)
        self._client.__enter__()

    def tearDown(self):
        self._client.__exit__(None, None, None)
        self.app.dependency_overrides.clear()

    def _start(self, edited="D:/e.mp4", original="D:/o.mkv"):
        return self._client.post(
            "/api/tasks/analyze", json={"edited_path": edited, "original_path": original}
        )


# --------------------------------------------------------------------- Tests
class CreateTaskTest(TaskApiTestBase):
    def test_create_returns_task_id_then_completed(self):
        r = self._start()
        self.assertEqual(r.status_code, 200)
        task_id = r.json()["task_id"]
        self.assertTrue(task_id)
        # 同步 worker 已跑完 -> completed + result
        q = self._client.get(f"/api/tasks/{task_id}")
        self.assertEqual(q.status_code, 200)
        body = q.json()
        self.assertEqual(body["status"], "completed")
        self.assertEqual(body["stage"], "finished")
        self.assertEqual(body["progress"], 100)
        self.assertEqual(body["result"]["schema_version"], 1)
        self.assertIsNone(body["error"])

    def test_create_requires_both_paths(self):
        r = self._client.post("/api/tasks/analyze", json={"edited_path": "D:/e.mp4"})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "bad_request")


class WorkerSuccessTest(TaskApiTestBase):
    def test_worker_success_records_result(self):
        task = self.tm.submit_analyze("D:/e.mp4", "D:/o.mkv")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.stage, TaskStage.FINISHED)
        self.assertEqual(task.result["schema_version"], 1)
        self.assertEqual(len(self.fake.locate_calls), 1)

    def test_refine_passthrough_to_locate(self):
        # 快/精双模式（2026-10-02）：submit_analyze(refine) 必须原样到达 service.locate
        self.tm.submit_analyze("D:/e.mp4", "D:/o.mkv", refine=False)
        self.assertIs(self.fake.last_refine, False)
        self.tm.submit_analyze("D:/e2.mp4", "D:/o.mkv")
        self.assertIsNone(self.fake.last_refine)   # 不传 = config 默认


class WorkerExceptionTest(TaskApiTestBase):
    def test_worker_exception_marks_failed(self):
        self.fake.mode = "fail"
        task = self.tm.submit_analyze("D:/e.mp4", "D:/o.mkv")
        self.assertEqual(task.status, TaskStatus.FAILED)
        # 续19-T1-2 口径：task.error 直接进前端错误条幅 → 对外话术 + 稳定码（技术串走日志）。
        self.assertIn("LOC-1000", task.error)
        self.assertIn("支持人员", task.error)
        self.assertIsNone(task.result)


class QueryStatusTest(TaskApiTestBase):
    def test_query_returns_shapes(self):
        task_id = self._start().json()["task_id"]
        r = self._client.get(f"/api/tasks/{task_id}")
        self.assertEqual(r.status_code, 200)
        for key in ("task_id", "status", "stage", "progress", "created_at", "result", "error",
                    "finished_at", "cancel_requested"):
            self.assertIn(key, r.json())

    def test_query_unknown_task_404(self):
        r = self._client.get("/api/tasks/does-not-exist")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(r.json()["error"], "not_found")


class CancelTest(TaskApiTestBase):
    def test_cancel_returns_cancel_requested(self):
        task_id = self._start().json()["task_id"]
        r = self._client.post(f"/api/tasks/{task_id}/cancel")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"status": "cancel_requested"})

    def test_cancel_unknown_task_404(self):
        r = self._client.post("/api/tasks/does-not-exist/cancel")
        self.assertEqual(r.status_code, 404)

    def test_cancelled_worker_is_marked_cancelled(self):
        task = Task(edited_path="D:/e.mp4", original_path="D:/o.mkv")
        task.cancel()
        run_worker(task, FakeService("ok"))
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        self.assertTrue(task.to_dict()["cancel_requested"])


class StageMappingTest(unittest.TestCase):
    def test_maps_progress_stage_base(self):
        # 无 current/total 的阶段事件取区间起点
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.INDEX_BUILD)), (TaskStage.INDEXING, 0))
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.SEGMENT_DETECTION)), (TaskStage.SEGMENTING, 30))
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.EXPORT)), (TaskStage.EXPORTING, 98))

    def test_maps_progress_stage_interpolates(self):
        # 逐帧阶段（1-based current/total）：12 + 18*155/311 = 20.97 → 21
        self.assertEqual(
            map_progress_stage(ProgressEvent(ProgressStage.EDITED_FEATURE_EXTRACTION, 155, 311)),
            (TaskStage.EMBEDDING, 21))
        # 逐段阶段（0-based 段下标）：38 + 54*(2/4) = 65
        self.assertEqual(
            map_progress_stage(ProgressEvent(ProgressStage.LOCALIZATION, 1, 4)),
            (TaskStage.RETRIEVAL, 65))

    def test_refine_phase_slices(self):
        """REFINE 子阶段切片（2026-10-06 修「92% 卡死」）：各 phase 独占互不重叠小段。

        旧形态 = 修复链/拆分/精排/ISC 共用同一条 92→98 ramp，而修复链只发一条
        current=0 事件 ⇒ 实测几分钟停在 92.1，逐段精排又被单调钳制挡住。
        """
        def ev(phase, cur, tot):
            return ProgressEvent(ProgressStage.REFINE, cur, tot, "", phase)

        # 显示宽度 = 实测耗时占比（run1+run3：修复链 28% · 拆分 3% · patch 38% · ISC 31%）。
        # 中间点用容差断言：一位小数四舍五入正好压在 .x5 上时浮点表示会抖。
        def near(pct, want):
            self.assertAlmostEqual(pct, want, delta=0.06)

        self.assertEqual(map_progress_stage(ev("fix", 0, 48)), (TaskStage.RETRIEVAL, 92.0))
        self.assertEqual(map_progress_stage(ev("fix", 48, 48)), (TaskStage.RETRIEVAL, 93.7))
        near(map_progress_stage(ev("fix", 10, 48))[1], 92.35)             # 字牌腿起点
        near(map_progress_stage(ev("fix", 42, 48))[1], 93.48)             # 字牌腿终点
        self.assertEqual(map_progress_stage(ev("split", 0, 1)), (TaskStage.RETRIEVAL, 93.7))
        self.assertEqual(map_progress_stage(ev("split", 1, 1)), (TaskStage.RETRIEVAL, 93.9))
        self.assertEqual(map_progress_stage(ev("patch", 0, 67)), (TaskStage.RETRIEVAL, 93.9))
        near(map_progress_stage(ev("patch", 33, 67))[1], 95.05)
        self.assertEqual(map_progress_stage(ev("patch", 67, 67)), (TaskStage.RETRIEVAL, 96.2))
        self.assertEqual(map_progress_stage(ev("isc", 0, 1)), (TaskStage.RETRIEVAL, 96.2))
        self.assertEqual(map_progress_stage(ev("isc", 1, 1)), (TaskStage.RETRIEVAL, 98.0))
        # 跳格间隔模型：字牌腿 32/48 单位 × 1.7 点 = 1.13 点 ÷ 67 段 ⇒ 0.1 读数约每 6 段一跳
        step_s = round(0.1 / (1.7 * 32 / 48 / 67) * (363 / 67))
        self.assertLessEqual(step_s, 40, f"字牌腿预计跳格 {step_s}s，应 ≤40s")
        # 无 phase = 旧行为逐位不变（回归锁）
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.REFINE, 0, 82)),
                         (TaskStage.RETRIEVAL, 92.1))
        self.assertEqual(
            map_progress_stage(ProgressEvent(ProgressStage.CANDIDATE_RETRIEVAL, 3, 4)),
            (TaskStage.RETRIEVAL, 92))
        self.assertEqual(
            map_progress_stage(ProgressEvent(ProgressStage.CONFIDENCE, 0, 34)),
            (TaskStage.RETRIEVAL, 39.6))  # 一位小数（续40）：38 + 54/34 = 39.588 → 39.6

    def test_maps_progress_stage_refine_range(self):
        # 深度复核（续40 UX）：92→98 逐段推进，修复「92% 钳死」；仍映射到 RETRIEVAL 步骤。
        self.assertEqual(
            map_progress_stage(ProgressEvent(ProgressStage.REFINE, 0, 67)),
            (TaskStage.RETRIEVAL, 92.1))
        self.assertEqual(
            map_progress_stage(ProgressEvent(ProgressStage.REFINE, 66, 67)),
            (TaskStage.RETRIEVAL, 98))

    def test_maps_progress_stage_unknown(self):
        # str-Enum：未知阶段值走字典缺省回退 IDLE
        self.assertEqual(map_progress_stage(ProgressEvent("BOGUS")), (TaskStage.IDLE, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
