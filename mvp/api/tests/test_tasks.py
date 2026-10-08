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
        # 跳格间隔锁 = 见下面的 test_refine_leg_dwell_lock_is_max_based：原先写在这里的
        # `round(0.1/(1.7*32/48/67)*(363/67)) = 32 ≤ 40` 是**均值**口径建模，2026-10-08
        # 按两趟独占实测改口径（见那条测试的 docstring）。
        # 无 phase = 旧行为逐位不变（回归锁）
        self.assertEqual(map_progress_stage(ProgressEvent(ProgressStage.REFINE, 0, 82)),
                         (TaskStage.RETRIEVAL, 92.1))
        self.assertEqual(
            map_progress_stage(ProgressEvent(ProgressStage.CANDIDATE_RETRIEVAL, 3, 4)),
            (TaskStage.RETRIEVAL, 92))
        self.assertEqual(
            map_progress_stage(ProgressEvent(ProgressStage.CONFIDENCE, 0, 34)),
            (TaskStage.RETRIEVAL, 39.6))  # 一位小数（续40）：38 + 54/34 = 39.588 → 39.6

    # ---- 跳格锁（2026-10-08 续63 补九 ③：口径由「均值」改「最大值」）------------- #
    # 实测来源 = 同一份 test2 两趟**独占设备**运行（并发 DML 会把字牌腿从 41.6s 抬到 52.8s，
    # 那趟已作废）：读数表 `work/progress_chain_review/test2_dwell.txt`（源码树 1476.5s）与
    # `work/r16_pkg/cadence/test2_packaged_dwell_pctcollapse.txt`（包内 r16 1407.5s）。
    # 逐腿复核（2026-10-08 用「墙钟区间裁剪」重算两趟原始数据；顺带更正 续63 补八 的归因：
    # 档案曾写「ISC 腿 41 格 最大 37.3s」，那 41 格其实是 patch+ISC 合起来的格数，
    # 37.3s 是 **patch 腿**的最大停留，ISC 腿最大 = 33.9s）：
    #   腿            腿墙钟(源码树/包内)   最大停留(源码树/包内)   显示读数(代码算)
    #   字牌 OCR       245.9 / 236.6 s      41.6 / 41.4 s          12
    #   切镜拆分        33.8 /  31.7 s      33.8 / 31.7 s           2
    #   patch 精排     470.9 / 423.1 s      37.3 / 28.3 s          24
    #   ISC 第二意见   419.7 / 408.9 s      33.9 / 33.8 s          19
    #   ⇒ 全程最坏单格 = 字牌腿 41.6s；两趟结果段数都 67。
    # 旧锁算的是「均匀假设下的均值」= 32s，实测均值 20.5~24.7s 一直**优于**它，而用户
    # 感知的是**最大停留** 41.4~41.6s —— 超那条 40s 阈值 1.4~1.6s。这不是「改善没生效」
    # （改前形态 = 字牌腿 363s 一动不动，量级 8.7x），是**锁的口径选错了**：阈值 40s 的
    # 本意是「一格别停太久」，那就该按最大值判。⇒ 拆成两条：
    #   锁 A「显示宽度不许塌」= 可见读数数由现役宽度表**现算**（不抄档案），均值 ≤30s；
    #   锁 B「实测最大停留」= 登记两趟最坏值 ≤45s。
    # 45s 的由来：旧阈值 40s 是拍的，两趟实测 41.4/41.6 如实超它；放 5s = 承认现状
    # 并要求「别继续变差」。**不加宽字牌腿显示宽度**（会挤占 patch/ISC 的 4s 预算，
    # 且 1.4~1.6s 不构成体验问题）。
    LEG_STEPS_AND_DWELL = (
        # (腿名, phase, 该腿事件刻度区间, total, 可见读数数, 实测腿墙钟 s, 实测最大停留 s)
        ("字牌 OCR 腿", "fix", (10, 42), 48, 12, 245.9, 41.6),
        ("切镜拆分", "split", (0, 1), 1, 2, 33.8, 33.8),
        ("patch 逐段精排", "patch", (0, 66), 67, 24, 470.9, 37.3),
        ("ISC 第二意见", "isc", (0, 66), 67, 19, 419.7, 33.9),
    )

    def _visible_steps(self, phase: str, lo: int, hi: int, total: int) -> int:
        """该腿在**现役显示宽度表**下能产生多少个不同读数（= 用户看到的跳格数）。

        故意从 `map_progress_stage` 现算而不是抄档案：run3 那种失败形态（把 9 条腿按数量
        平分 ⇒ 字牌腿的 32 单位被挤进 0.2 个点）只有「宽度表一改、读数立刻塌」才抓得住。
        """
        seen = {map_progress_stage(ProgressEvent(ProgressStage.REFINE, c, total, "", phase))[1]
                for c in range(lo, hi + 1)}
        return len(seen)

    def test_refine_leg_dwell_lock_is_max_based(self):
        """锁 A 显示宽度不塌（代码现算读数数 + 均值 ≤30s）+ 锁 B 实测最大停留 ≤45s。

        两条口径分工：A 抓「宽度表被改窄 ⇒ 读数塌 ⇒ 单格更长」（run3 那种回归），B 登记
        「现役真实体验」。A 的分母 = 宽度表**能产生**的读数数（ISC 19），实测只出现 17 个
        （防抖合并了亚 0.5s 突发），所以 A 的均值比实测乐观；`review_progress_chain.py` 用
        实测分母（ISC 24.7s），阈值取 30s 两边对齐 ⇒ 别把这两处的均值当同一个数。
        """
        for name, phase, (lo, hi), total, steps_want, leg_s, measured_max in \
                self.LEG_STEPS_AND_DWELL:
            with self.subTest(leg=name):
                steps = self._visible_steps(phase, lo, hi, total)
                self.assertEqual(steps, steps_want,
                                 f"{name} 可见读数 {steps} != 登记值 {steps_want}"
                                 "（宽度表被改过 ⇒ 必须重测腿墙钟并重新登记，不能只改这个数）")
                mean_s = leg_s / steps
                self.assertLessEqual(mean_s, 30.0,
                                     f"{name} 预计均值跳格 {mean_s:.1f}s"
                                     f"（{leg_s:.1f}s ÷ {steps} 读数）应 ≤30s")
                self.assertLessEqual(measured_max, 45.0,
                                     f"{name} 实测最大停留 {measured_max}s 应 ≤45s")
        # 全程最坏单格 = 字牌腿（两趟 41.4~41.6s），改前形态是 363s 冻结 ⇒ 量级 8.7x
        worst = max(row[6] for row in self.LEG_STEPS_AND_DWELL)
        self.assertLessEqual(worst, 45.0)

    def test_width_collapse_would_trip_the_lock(self):
        """反向验证锁 A 有效：把字牌腿宽度压成 run3 那种「按腿数量平分」形态（0.2 点）
        ⇒ 读数塌缩、均值超阈值。不这么写的话，「锁会抓到回归」只是一句自夸。"""
        # 现役 1.7 点 vs 模拟 0.2 点（同 32/48 单位、同 0.1 舍入）
        now = {round(92.0 + 1.7 * (u / 48), 1) for u in range(10, 43)}
        collapsed = {round(92.0 + 0.2 * (u / 48), 1) for u in range(10, 43)}
        self.assertEqual(len(now), 12)
        self.assertLess(len(collapsed), len(now), "模拟形态没塌 ⇒ 这条反向验证无效")
        self.assertGreater(245.9 / len(collapsed), 30.0,
                           "塌缩后均值应超阈值（= 锁 A 会红）")

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
