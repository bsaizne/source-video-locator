"""API 层导出任务接线测试（2026-10-13 B 方案：分钟级导出走任务通道）。

覆盖六处（不跑真实 ffmpeg，FakeExportService 记录调用）：
- ``TaskManager.submit_export``：**提交时锁定结果批** + 参数集合与同步 ``/api/export`` 一致；
- ``POST /api/tasks/export``：会话批缺失 → 400；有批 → task_id；service 侧批回退；
- **进度区间按 kind 分派（R1 锁）**：kind=export 的 EXPORT 事件吃 0→99 全区间，
  而 analyze 收尾的同一批事件必须逐字维持 98→99.5 的老口径；
- 失败/取消 → ``failed``（对外话术 + LOC 码）/ ``cancelled``；
- ④ 隔离：``submit_export`` 必须把 ``isolated`` 传到 ``run_worker``（漏传 = 永远线程内跑）；
- 隔离 payload 往返携带 export 字段 + export 信封不被误当结果批回登记。

Run:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.api.tests.test_export_task -v
"""
from __future__ import annotations

import os
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

_DRAFT = "D:/appdata/exports/e.loc.jy_draft"
# str(Path(...)) 在 Windows 上是反斜杠；断言按生产同款规范化，别拿字面量比
_DRAFT_STR = str(Path(_DRAFT))
_JSON_STR = str(Path("D:/out/e.results.json"))


def _sample_batch() -> ResultBatch:
    return ResultBatch(
        schema_version=1, original_video="D:/v/om.mkv", edited_video="D:/e.mp4",
        results=[Result(edited=TimeSpan(1.0, 5.0), original=TimeSpan(3.0, 7.0),
                        confidence=Confidence(ConfidenceLevel.HIGH, 0.9, ("rank1",)),
                        candidate_rank=1)],
    )


class FakeExportService:
    """只记账的导出 service：按现役 locator_service 的两个真实签名收参数。"""

    def __init__(self, *, events: list[ProgressEvent] | None = None, fail: Exception | None = None,
                 cancel: bool = False, warnings: list[str] | None = None):
        self.calls: list[dict] = []
        self._events = events if events is not None else []
        self._fail = fail
        self._cancel = cancel
        self._batch = None
        self.last_export_warnings = list(warnings or [])

    def last_result_batch(self):
        return self._batch

    def export_results(self, batch, *, out_dir=None, filename=None,
                       on_progress=None, cancel_token=None):
        self.calls.append({"channel": "json", "batch": batch, "out_dir": out_dir})
        return Path("D:/out/e.results.json")

    def export_project(self, batch, *, fmt, out_dir=None, filename=None, min_confidence=None,
                       low_policy=None, snap_scenes=None, material_width=None,
                       on_progress=None, cancel_token=None):
        self.calls.append({"channel": fmt, "batch": batch, "out_dir": out_dir,
                           "min_confidence": min_confidence, "low_policy": low_policy,
                           "snap_scenes": snap_scenes, "material_width": material_width})
        if on_progress is not None:
            for ev in self._events:
                on_progress(ev)
        if self._cancel:
            # 与真 service 同形：取消 = 置位 token（协作式）后抛 ApplicationError，
            # worker 据 token.is_cancelled() 转 cancelled 而非 failed。
            if cancel_token is not None:
                cancel_token.cancel()
            raise ApplicationError("导出已取消")
        if self._fail is not None:
            raise self._fail
        return Path(_DRAFT)


def _jianying_events() -> list[ProgressEvent]:
    """复刻剪映腿的真实事件序列（locator_service.py:1646 起跑 + :1742 逐 clip + :1757 收尾）。"""
    return [
        ProgressEvent(ProgressStage.EXPORT, 0, 0, "正在导出 jianying"),
        ProgressEvent(ProgressStage.EXPORT, 1, 3, "准备素材 1/3"),
        ProgressEvent(ProgressStage.EXPORT, 2, 3, "准备素材 2/3"),
        ProgressEvent(ProgressStage.EXPORT, 3, 3, "准备素材 3/3"),
        ProgressEvent(ProgressStage.EXPORT, 3, 3, "已导出 e.loc.jy_draft"),
    ]


class ExportTaskSubmitTest(unittest.TestCase):
    def test_submit_export_locks_batch_and_completes(self):
        svc = FakeExportService(warnings=["LOC-2001 碎片告警"])
        tm = TaskManager(svc, run_in_background=_sync_run)
        batch = _sample_batch()
        task = tm.submit_export(batch, fmt="jianying", out_dir="D:/out",
                                min_confidence="HIGH", low_policy="backup",
                                snap_scenes=False, material_width="core")
        self.assertIs(task.kind, TaskKind.EXPORT)
        self.assertIs(svc.calls[0]["batch"], batch)           # 提交时锁定的批，不是"最新批"
        self.assertEqual(svc.calls[0]["out_dir"], "D:/out")
        self.assertEqual(svc.calls[0]["min_confidence"], "HIGH")
        self.assertEqual(svc.calls[0]["low_policy"], "backup")
        self.assertIs(svc.calls[0]["snap_scenes"], False)
        self.assertEqual(svc.calls[0]["material_width"], "core")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.result["kind"], "export")
        self.assertEqual(task.result["format"], "jianying")
        self.assertEqual(task.result["path"], _DRAFT_STR)
        # warnings 由产出它的 service 带进信封（隔离子进程与父进程不同实例）
        self.assertEqual(task.result["warnings"], ["LOC-2001 碎片告警"])

    def test_json_channel_uses_export_results_and_no_policy_params(self):
        svc = FakeExportService()
        tm = TaskManager(svc, run_in_background=_sync_run)
        task = tm.submit_export(_sample_batch(), fmt="json", out_dir="")
        self.assertEqual(svc.calls[0]["channel"], "json")
        self.assertIsNone(svc.calls[0]["out_dir"])             # "" → None → service 默认根
        self.assertEqual(task.result["path"], "D:\\out\\e.results.json")

    def test_export_without_batch_fails_gracefully(self):
        svc = FakeExportService()
        run_worker = _import_run_worker()
        task = Task(kind=TaskKind.EXPORT)                      # export_batch=None 且会话无批
        run_worker(task, svc)
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertIn("没有可导出的结果批", task.error or "")

    def test_failure_maps_to_public_error_text(self):
        svc = FakeExportService(fail=ApplicationError("剪映草稿写入失败"))
        tm = TaskManager(svc, run_in_background=_sync_run)
        task = tm.submit_export(_sample_batch(), fmt="jianying")
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertIn("（LOC-", task.error or "")

    def test_unexpected_exception_becomes_failed_not_raised(self):
        """第二层边界在任务通道里的等价物：意外异常 ⇒ failed，绝不逃出 worker。"""
        svc = FakeExportService(fail=RuntimeError("pyJianYingDraft SegmentOverlap"))
        tm = TaskManager(svc, run_in_background=_sync_run)
        task = tm.submit_export(_sample_batch(), fmt="jianying")
        self.assertEqual(task.status, TaskStatus.FAILED)

    def test_cancel_marks_cancelled(self):
        svc = FakeExportService(cancel=True)
        tm = TaskManager(svc, run_in_background=_sync_run)
        task = tm.submit_export(_sample_batch(), fmt="jianying")
        self.assertEqual(task.status, TaskStatus.CANCELLED)


def _import_run_worker():
    from mvp.api.tasks.worker import run_worker
    return run_worker


class ExportProgressMappingTest(unittest.TestCase):
    """R1 锁：导出任务不能复用 analyze 收尾的 98→99.5 区间。"""

    def test_export_task_first_event_is_zero_not_98(self):
        stage, pct = map_progress_stage(ProgressEvent(ProgressStage.EXPORT, 0, 0, "正在导出 jianying"),
                                        TaskKind.EXPORT)
        self.assertIs(stage, TaskStage.EXPORTING)
        self.assertLess(pct, 98.0, "导出任务首帧不得落在 analyze 收尾的 98 —— 那会让进度条一提交就假完成")
        self.assertEqual(pct, 0.0)

    def test_export_task_interpolates_over_full_range(self):
        stage, pct = map_progress_stage(ProgressEvent(ProgressStage.EXPORT, 30, 100, "准备素材 30/100"),
                                        TaskKind.EXPORT)
        self.assertIs(stage, TaskStage.EXPORTING)
        self.assertEqual(pct, 99.0 * 0.30)                     # current=已完成数，不再 +1

    def test_export_task_last_event_reaches_right_end(self):
        stage, pct = map_progress_stage(ProgressEvent(ProgressStage.EXPORT, 64, 64, "已导出"),
                                        TaskKind.EXPORT)
        self.assertEqual(pct, 99.0)

    def test_analyze_tail_range_is_unchanged(self):
        """回归锁：不传 kind（或 kind=analyze）时，老口径逐字不变（test_tasks.py 同一条）。"""
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.EXPORT)),
                         (TaskStage.EXPORTING, 98))
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.EXPORT), TaskKind.ANALYZE),
                         (TaskStage.EXPORTING, 98))

    def test_worker_emits_monotone_progress_below_98_then_completes(self):
        """端到端（防抖之后那一段）：第一帧就得是低值，序列单调不减，完成时 100。"""
        frames: list[tuple[str, float]] = []
        holder: dict = {}

        def _capture(fn):
            holder["fn"] = fn                                  # 延后执行，好先装记录仪

        svc = FakeExportService(events=_jianying_events())
        tm = TaskManager(svc, run_in_background=_capture)
        task = tm.submit_export(_sample_batch(), fmt="jianying")
        original = task.update_progress

        def _record(stage, percent, message=""):
            frames.append((stage.value, percent))
            return original(stage, percent, message=message)

        task.update_progress = _record
        holder["fn"]()
        pcts = [p for _, p in frames]
        self.assertTrue(pcts, "导出任务必须发进度帧")
        self.assertLess(pcts[0], 98.0, f"首帧假高：{pcts[0]}")
        self.assertEqual(pcts, sorted(pcts), f"进度回跳：{pcts}")
        self.assertEqual(pcts[-1], 99.0)
        self.assertEqual(task.progress, 100)                   # mark_completed 置 100
        self.assertTrue(all(s == "exporting" for s, _ in frames))


class ExportIsolationTest(unittest.TestCase):
    """④ 隔离：submit_export 必须把 isolated 传到 run_worker（submit_render 当年漏过一次）。"""

    def setUp(self):
        self._old = os.environ.get("SVL_TASKS_IN_THREAD")
        os.environ.pop("SVL_TASKS_IN_THREAD", None)            # isolation_enabled() = True

    def tearDown(self):
        if self._old is None:
            os.environ.pop("SVL_TASKS_IN_THREAD", None)
        else:
            os.environ["SVL_TASKS_IN_THREAD"] = self._old

    def _patched_child(self, recorder):
        import mvp.api.tasks.isolated as iso
        old = iso.run_worker_isolated
        iso.run_worker_isolated = recorder
        self.addCleanup(lambda: setattr(iso, "run_worker_isolated", old))
        return iso

    def test_isolated_manager_routes_export_to_child(self):
        calls: list = []

        def _recorder(task, service, *, log=None):
            calls.append(task.kind)
            task.mark_running()
            task.mark_completed({"kind": "export", "path": _DRAFT})
            return True

        svc = FakeExportService()
        self._patched_child(_recorder)
        tm = TaskManager(svc, run_in_background=_sync_run, isolated=True)
        task = tm.submit_export(_sample_batch(), fmt="jianying")
        self.assertEqual(calls, [TaskKind.EXPORT], "isolated=True 却没进子进程 ⇒ 标志漏传")
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(svc.calls, [], "父进程不该自己跑一遍")

    def test_non_isolated_manager_stays_in_thread(self):
        calls: list = []
        svc = FakeExportService()
        self._patched_child(lambda task, service, *, log=None: calls.append(1) or False)
        tm = TaskManager(svc, run_in_background=_sync_run, isolated=False)
        task = tm.submit_export(_sample_batch(), fmt="jianying")
        self.assertEqual(calls, [])
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(len(svc.calls), 1)

    def test_payload_roundtrip_carries_export_fields(self):
        from mvp.api.tasks.isolated import _payload_of, _task_from_payload
        batch = _sample_batch()
        task = Task(kind=TaskKind.EXPORT, export_batch=batch,
                    export_params={"fmt": "jianying", "out_dir": "D:/out"})
        task2 = _task_from_payload(_payload_of(task))
        self.assertIs(task2.kind, TaskKind.EXPORT)
        self.assertIs(task2.export_batch, batch, "漏字段 ⇒ 子进程拿到空批，导出永远失败")
        self.assertEqual(task2.export_params["fmt"], "jianying")

    def test_export_envelope_is_not_adopted_as_result_batch(self):
        from mvp.api.tasks.isolated import _adopt_parent_batch

        class Svc:
            adopted = None

            def adopt_result_batch(self, batch):
                self.adopted = batch

        svc = Svc()
        _adopt_parent_batch(svc, Task(kind=TaskKind.EXPORT),
                            {"kind": "export", "path": _DRAFT}, lambda *a, **k: None)
        self.assertIsNone(svc.adopted, "export 的批是提交时锁定的，不该被回登记覆盖")


class ExportRouteTest(unittest.TestCase):
    def _client(self, svc: FakeExportService, batch) -> TestClient:
        ctx = AppContext(service=svc,
                         task_manager=TaskManager(svc, run_in_background=_sync_run),
                         current_batch=batch)
        app = create_app()
        app.dependency_overrides[get_context] = lambda: ctx
        return TestClient(app)

    def test_post_tasks_export_returns_task_id_and_completes(self):
        svc = FakeExportService(events=_jianying_events())
        client = self._client(svc, _sample_batch())
        r = client.post("/api/tasks/export",
                        json={"output_dir": "D:/out", "format": "jianying",
                              "min_confidence": "LOW", "low_policy": "backup",
                              "snap_scenes": True, "material_width": "scene"})
        self.assertEqual(r.status_code, 200, r.text)
        got = client.get(f"/api/tasks/{r.json()['task_id']}").json()
        self.assertEqual(got["kind"], "export")
        self.assertEqual(got["status"], "completed")
        self.assertEqual(got["result"]["path"], _DRAFT_STR)
        self.assertEqual(got["stage"], "finished")            # mark_completed 置 FINISHED

    def test_post_tasks_export_falls_back_to_service_batch(self):
        svc = FakeExportService()
        svc._batch = _sample_batch()                           # 异步定位只写 service 侧批
        client = self._client(svc, None)
        r = client.post("/api/tasks/export", json={"format": "edl"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIs(svc.calls[0]["batch"], svc._batch)
        self.assertEqual(svc.calls[0]["channel"], "edl")

    def test_post_tasks_export_without_batch_is_400(self):
        svc = FakeExportService()
        client = self._client(svc, None)
        r = client.post("/api/tasks/export", json={})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["error"], "no_results")

    def test_sync_export_route_still_exists(self):
        """边界锁：B 方案**不删**同步 /api/export（向后兼容 + 包侧既有 jianying_http 锁依赖它）。"""
        src = (Path(__file__).resolve().parents[1] / "routes" / "results.py"
               ).read_text(encoding="utf-8")
        self.assertIn('@router.post("/api/export")', src)

    def test_cancel_route_reaches_export_task(self):
        holder: dict = {}
        svc = FakeExportService(cancel=True)                   # 取消由 service 抛 ApplicationError
        ctx = AppContext(service=svc,
                         task_manager=TaskManager(svc, run_in_background=lambda fn: holder.__setitem__("fn", fn)),
                         current_batch=_sample_batch())
        app = create_app()
        app.dependency_overrides[get_context] = lambda: ctx
        client = TestClient(app)
        # 先提交（未执行）→ 经 /cancel 路由置位 → 再执行 worker ⇒ 终态必须 cancelled
        task = ctx.task_manager.submit_export(_sample_batch(), fmt="jianying")
        r = client.post(f"/api/tasks/{task.task_id}/cancel")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "cancel_requested")
        holder["fn"]()
        self.assertEqual(task.status, TaskStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
