"""④ 任务级进程隔离（2026-10-07 立项）单测。

真实 spawn 用例（Windows spawn 启动子进程，各 ~2-5s）：
- 故障注入（``_test_force_hard_exit``）⇒ 子进程无信封硬退 ⇒ task.failed 带 exitcode
  ——隔离价值所在：主测试进程（=主服务）存活不受影响；
- 子进程应用层错误走信封 ⇒ task.failed 带对外话术；
- 提交后立刻取消 ⇒ terminate + mark_cancelled。
"""
import os
import pickle
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # -> benchmark

from mvp.api.tasks.isolated import (CHILD_GRACE_S, _payload_of, isolation_enabled,  # noqa: E402
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


class GracefulReapTest(unittest.TestCase):
    """终态信封后**先等子进程自然退出**（2026-10-07 r15 accept 抓到的日志吞尾）。

    打包态子进程 stdout 是管道 ⇒ 块缓冲；父进程一拿到结果就 terminate，子进程日志的
    尾巴（精排/ISC 的 device= 行）整段进不了包内 stdout，accept 的「GPU 未回退」硬断言
    因此误红。这里用假 proc 锁死收割顺序：正常终态 = join(宽限) 且不 terminate。
    """

    def _run_with_fake_proc(self, msgs, alive_seq):
        import queue as pyqueue
        from unittest import mock

        from mvp.api.tasks import isolated

        q = mock.MagicMock()
        pending = list(msgs)

        def _get(timeout=None):
            if pending:
                return pending.pop(0)
            raise pyqueue.Empty()

        q.get.side_effect = _get
        q.get_nowait.side_effect = lambda: pending.pop(0) if pending else (_ for _ in ()).throw(pyqueue.Empty())

        proc = mock.MagicMock()
        proc.is_alive.side_effect = list(alive_seq) + [False]
        proc.exitcode = 0
        ctx = mock.MagicMock()
        ctx.Queue.return_value = q
        ctx.Process.return_value = proc
        task = _analyze_task()
        logs: list = []
        with mock.patch.object(isolated.multiprocessing, "get_context", return_value=ctx):
            handled = isolated.run_worker_isolated(task, None,
                                                   log=lambda *a, **k: logs.append(a))
        return handled, task, proc, logs

    def test_result_envelope_waits_instead_of_terminating(self):
        # is_alive 调用序：①监督循环 ②finally 宽限判定 ③terminate 判定（宽限后已退出）
        handled, task, proc, logs = self._run_with_fake_proc(
            [{"type": "result", "result": {"ok": True}}], [True, True, False])
        self.assertTrue(handled)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        proc.terminate.assert_not_called()
        joins = [c.kwargs.get("timeout") for c in proc.join.call_args_list]
        self.assertIn(CHILD_GRACE_S, joins, joins)
        reaped = [x for x in logs if isinstance(x, tuple) and "reaped exitcode" in str(x[0])]
        self.assertTrue(reaped, logs)
        self.assertEqual(reaped[0][-1], 0, reaped)     # 自然退出码，不是 SIGTERM 的 -15

    def test_cancel_path_still_terminates(self):
        """取消语义不变：硬 SIGTERM 收，不等自然退出。"""
        handled, task, proc, _logs = self._run_with_fake_proc(
            [{"type": "cancelled"}], [True, False, True, True])
        self.assertTrue(handled)
        self.assertEqual(task.status, TaskStatus.CANCELLED)
        proc.terminate.assert_called_once()


class SubmitFlagTest(unittest.TestCase):
    """④ 的接线锁：两条 submit 路径都必须把 `isolated` 传下去。

    2026-10-07 r15 包内成片实测：渲染任务日志里没有 `isolated child started`，也没有
    spawn 回落留痕 ⇒ `submit_render` 漏传标志（默认 False），渲染一直在线程内跑，
    「崩溃只损失单任务」对成片不成立。同型调用点漏接 = 必须机械枚举，不能靠印象。
    """

    def test_both_submit_paths_pass_isolated_true(self):
        from unittest import mock

        from mvp.api.tasks import manager as mgr

        seen: dict[str, bool] = {}

        def fake_run_worker(task, service, *, log=None, isolated=False):
            seen[task.kind.value] = isolated

        tm = mgr.TaskManager(mock.MagicMock(), run_in_background=lambda fn: fn(),
                             isolated=True)
        with mock.patch.object(mgr, "run_worker", fake_run_worker):
            tm.submit_analyze(r"Z:\e.mp4", r"Z:\o.mkv")
            tm.submit_render(object())
        self.assertEqual(seen, {"analyze": True, "render": True}, seen)

    def test_no_run_worker_call_site_omits_isolated(self):
        """AST 扫源码：任何 `run_worker(...)` 调用点都必须显式带 `isolated=`。"""
        import ast

        from mvp.api.tasks import manager as mgr
        src = Path(mgr.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        offenders = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", None)
                if name == "run_worker" and not any(k.arg == "isolated" for k in node.keywords):
                    offenders.append(f"line {node.lineno}")
        self.assertEqual(offenders, [], f"漏传 isolated 的调用点：{offenders}")


class SpawnSupervisionTest(unittest.TestCase):
    """真实 spawn（各用例起一个子进程）。"""

    def test_child_writes_info_logs_to_the_shared_log_file(self):
        """④ 打包态 accept 抓到的缺陷回归锁：子进程**不走 ASGI lifespan**，
        ``configure_logging()`` 没人调 ⇒ root logger 无 handler，INFO 被 lastResort
        丢弃 ⇒ 包内 stdout / 支持档 video_locator.log 少了整段分析日志
        （精排/ISC 设备行、阶段耗时），售后无法归因。这里真 spawn 一次，
        要求落盘日志里能看到子进程写的 INFO 行，且带父进程同一个 task_id。"""
        import tempfile
        from pathlib import Path

        old = os.environ.get("SVL_LOG_DIR")
        with tempfile.TemporaryDirectory() as td:
            os.environ["SVL_LOG_DIR"] = td
            task = _analyze_task()
            try:
                self.assertTrue(run_worker_isolated(task, None))
            finally:
                if old is None:
                    os.environ.pop("SVL_LOG_DIR", None)
                else:
                    os.environ["SVL_LOG_DIR"] = old
            text = "\n".join(p.read_text(encoding="utf-8", errors="replace")
                             for p in Path(td).glob("*.log"))
        self.assertIn("isolated child booted pid=", text)
        self.assertIn(task.task_id, text)          # 父子日志同 task_id 可串联
        self.assertRegex(text, r"INFO", text[:200])

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
