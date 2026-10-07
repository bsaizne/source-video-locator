"""④ 任务级进程隔离（2026-10-07 立项）单测。

真实 spawn 用例（Windows spawn 启动子进程，各 ~2-5s）：
- 故障注入（``_test_force_hard_exit``）⇒ 子进程无信封硬退 ⇒ task.failed 带 exitcode
  ——隔离价值所在：主测试进程（=主服务）存活不受影响；
- 子进程应用层错误走信封 ⇒ task.failed 带对外话术；
- 提交后立刻取消 ⇒ terminate + mark_cancelled。
"""
import pickle
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> benchmark

from mvp.api.tasks.isolated import (_payload_of, isolation_enabled,   # noqa: E402
                                    _task_from_payload, run_worker_isolated)
from mvp.api.tasks.models import Task, TaskKind, TaskStatus   # noqa: E402


def _analyze_task(**kw) -> Task:
    return Task(kind=TaskKind.ANALYZE, edited_path=r"Z:\nope_ed.mp4",
                original_path=r"Z:\nope_om.mkv", **kw)


class PayloadTest(unittest.TestCase):
    def test_roundtrip(self):
        task = _analyze_task(refine=False)
        payload = _payload_of(task)
        task2 = _task_from_payload(payload)
        self.assertEqual(task2.kind, TaskKind.ANALYZE)
        self.assertEqual(task2.edited_path, task.edited_path)
        self.assertEqual(task2.original_paths, task.original_paths)
        self.assertIsNone(task2.render_batch)

    def test_payload_is_picklable(self):
        task = _analyze_task()
        data = pickle.dumps(_payload_of(task))
        self.assertIsInstance(pickle.loads(data), dict)

    def test_isolation_enabled_env_switch(self):
        import os
        old = os.environ.get("SVL_TASKS_IN_THREAD")
        try:
            os.environ.pop("SVL_TASKS_IN_THREAD", None)
            self.assertTrue(isolation_enabled())
            os.environ["SVL_TASKS_IN_THREAD"] = "1"
            self.assertFalse(isolation_enabled())
        finally:
            if old is None:
                os.environ.pop("SVL_TASKS_IN_THREAD", None)
            else:
                os.environ["SVL_TASKS_IN_THREAD"] = old


class SpawnSupervisionTest(unittest.TestCase):
    """真实 spawn（各用例起一个子进程）。"""

    def test_hard_exit_without_envelope_marks_failed_with_exitcode(self):
        task = _analyze_task()
        task.render_params["_test_force_hard_exit"] = 123   # 经 _payload_of 携带
        logs = []
        handled = run_worker_isolated(task, None, log=lambda *a, **k: logs.append(a))
        self.assertTrue(handled)
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertIn("exitcode=123", task.error)
        self.assertIn("服务未受影响", task.error)
        self.assertIn("DIED", " ".join(str(x) for x in logs))

    def test_child_application_error_arrives_as_envelope(self):
        task = _analyze_task()   # 素材不存在 → 子进程内 locate 快速 ApplicationError
        logs = []
        handled = run_worker_isolated(task, None, log=lambda *a, **k: logs.append(a))
        self.assertTrue(handled)
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertTrue(task.error)                        # 对外话术非空
        self.assertNotIn("exitcode", task.error)           # 不是硬崩路径
        self.assertIsNotNone(task.last_event_at)           # ③ 心跳戳在终态仍有

    def test_cancel_terminates_child_and_marks_cancelled(self):
        task = _analyze_task()
        task.cancel_requested = True                        # 提交即取消
        handled = run_worker_isolated(task, None)
        self.assertTrue(handled)
        self.assertEqual(task.status, TaskStatus.CANCELLED)


if __name__ == "__main__":
    unittest.main()
