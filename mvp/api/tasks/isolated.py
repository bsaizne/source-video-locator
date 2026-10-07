"""tasks.isolated — 任务级进程隔离（④ 独立 GPU 工作进程监督，2026-10-07 立项）。

**背景**：本机两次实测 DML 多模型并发段错误会拖垮整个后端进程（续6/续43）；
当前单进程内跑任务 ⇒ 一崩全崩。本模块把 analyze/render 任务移入**独立子进程**：
子进程硬崩（段错误/abort）只损失单个任务（task 转 failed 带退出码），主服务与
其它任务存活。取消 = 父进程 ``terminate`` 子进程（立即生效；service 内部的协作式
取消检查被绕过——终止语义本就强于协作检查）。

机制：
- 子进程自建 ``SourceLocatorService()``（SVL_* env 与父进程同源 ⇒ 配置一致）；
  父进程实例内的内存缓存不跨进程（索引/嵌入缓存是文件层，天然共享）。
- 进度经 ``multiprocessing.Queue`` 回传（已映射的 ``(stage_str, pct, message)``）；
  结果/错误经同一队列的信封 ``{"type": ...}``。
- **信封缺失的异常退出 = 段错误/硬崩** ⇒ ``mark_failed(exitcode=...)``——这正是隔离
  的价值所在。正常完成/应用层错误都有信封。
- 渲染批经 pickle 传参（ResultBatch 为纯 dataclass；提交时锁定的批在子进程内渲染）。
- 打包态（PyInstaller）spawn：入口 ``run_backend.main`` 已调 ``freeze_support()``；
  子进程按引用 import 目标函数（打包形态顶层 ``api.tasks.worker`` 可导入）。
- 故障注入钩子 ``payload["_test_force_hard_exit"]``：``os._exit`` 硬崩模拟，仅供
  监督路径单测使用（不携带任何生产语义）。

监督重启（连续崩溃计数 + 冷却）暂未实现：当前任务全部用户显式发起，无自动重试
消费方；等批量/自动重跑形态出现再立项。
"""
from __future__ import annotations

import multiprocessing
import os
import queue as _queue
import sys
from typing import Callable

LogFn = Callable[..., None]

# 正常终态后等子进程自然退出的宽限（秒）：让它冲刷日志缓冲，别急着 SIGTERM（见
# ``run_worker_isolated`` 的 finally）。超时就按隔离语义硬收。
CHILD_GRACE_S = 10.0


def isolation_enabled() -> bool:
    """总开关：TaskManager(isolated=True) 且未被 ``SVL_TASKS_IN_THREAD=1`` 关闭。"""
    return os.environ.get("SVL_TASKS_IN_THREAD", "") != "1"


def _payload_of(task) -> dict:
    """子进程入参：纯可 pickle 对象（路径/参数/锁定的渲染批）。

    带 ``task_id`` = 父进程任务号，子进程日志用它落同一行前缀——否则父进程按
    task_id 检索包内日志时，隔离子进程里那半段（真正干活的）无法对上。
    """
    return {"kind": task.kind.value,
            "task_id": task.task_id,
            "edited_path": task.edited_path,
            "original_path": task.original_path,
            "original_paths": list(task.original_paths),
            "refine": task.refine,
            "render_params": dict(task.render_params),
            "render_batch": task.render_batch}


def _task_from_payload(payload: dict):
    from .models import Task, TaskKind
    task = Task(kind=TaskKind(payload["kind"]),
                edited_path=payload["edited_path"],
                original_path=payload["original_path"],
                original_paths=list(payload["original_paths"]),
                refine=payload["refine"],
                render_params=dict(payload["render_params"]),
                render_batch=payload.get("render_batch"))
    # 父子日志同 task_id（售后归因：一条任务跨两个进程的日志要能串起来）
    if payload.get("task_id"):
        task.task_id = payload["task_id"]
    return task


def _child_main(payload: dict, q) -> None:
    """子进程入口（spawn 按引用 pickle：勿改成 lambda/闭包）。"""
    # 子进程**不走 ASGI lifespan**，而 ``configure_logging()`` 挂在 lifespan startup 上
    # ⇒ root logger 无 handler，INFO 记录被 lastResort(WARNING) 整段丢掉。
    # 2026-10-07 r15 accept 实测：包内 stdout 少了 `backend selected=` /
    # `patch reranker device=dml` / `isc refine device=dml`，「精排/ISC 未回退 CPU」
    # 两条硬断言因此误红；支持档 video_locator.log 同样缺这段——三级日志是售后
    # 诊断能力，不是装饰，所以在这里自己配（幂等，读 SVL_LOG_DIR 与父进程同落盘）。
    try:
        from infrastructure.logging import configure_logging
        configure_logging()
    except Exception:                                      # noqa: BLE001
        pass                                               # 日志配不上也不能带崩任务
    # 打包态子进程 stdout 是管道 ⇒ 默认块缓冲。改行缓冲 + 退出前 flush：取消/硬崩路径
    # 里最后几行日志（设备回报、阶段耗时）也要进得到包内 stdout。
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(line_buffering=True)
        except Exception:                                  # noqa: BLE001
            pass
    # 与父进程同一份还原逻辑（勿在此重抄构造：同一段代码抄两遍就会漏接——续62 教训）
    task = _task_from_payload(payload)
    from infrastructure.logging import get_logger
    get_logger("tasks").info("task %s isolated child booted pid=%s",
                             task.task_id, os.getpid())
    try:
        # 故障注入钩子（监督路径单测）：payload 顶层或 render_params 皆可携带
        force = (payload.get("_test_force_hard_exit")
                 or (payload.get("render_params") or {}).get("_test_force_hard_exit"))
        if force:
            os._exit(int(force))                              # 硬崩模拟
        from app.locator_service import SourceLocatorService
        service = SourceLocatorService()

        def on_progress(ev) -> None:
            from .worker import map_progress_stage
            stage, pct = map_progress_stage(ev)
            q.put({"type": "progress", "stage": stage.value,
                   "pct": pct, "message": getattr(ev, "message", "") or ""})

        from .worker import execute_task
        result = execute_task(task, service, on_progress=on_progress)
        q.put({"type": "result", "result": result})
    except Exception as exc:                              # noqa: BLE001 — 错误也走信封
        from infrastructure.errors import ApplicationError, public_error
        if isinstance(exc, ApplicationError) and task.token.is_cancelled():
            q.put({"type": "cancelled"})
        else:
            try:
                pub = public_error(exc)
                detail = f"{pub['message']}（{pub['code']}）"
            except Exception:                             # noqa: BLE001
                detail = f"{type(exc).__name__}: {exc}"
            q.put({"type": "error", "error": detail,
                   "traceback": _traceback(exc)})
    finally:
        try:
            q.close()
            q.join_thread()               # 确保 feeder 冲刷完再退出
        except Exception:                                 # noqa: BLE001
            pass
        for _s in (sys.stdout, sys.stderr):               # 日志尾巴落到包内 stdout
            try:
                _s.flush()
            except Exception:                             # noqa: BLE001
                pass
        # 自然 return（不 os._exit）：解释器收尾会把缓冲冲干净，父进程按 CHILD_GRACE_S
        # 等这一刻。硬崩/取消由父进程 terminate，靠上面的行缓冲+flush  already 尽力留痕。


def _traceback(exc) -> str:
    import traceback
    try:
        return "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    except Exception:                                     # noqa: BLE001
        return ""


def run_worker_isolated(task, service, *, log: LogFn | None = None) -> bool:
    """在独立子进程里跑任务并监督。

    返回 True = 任务已在此路径到达终态（或 spawn 失败前的失败已另行处理）；
    返回 False = spawn 不可用 ⇒ 调用方回落线程内执行（``run_worker`` 同语义）。
    """
    if log is None:
        log = lambda *a, **k: None  # noqa: E731
    ctx = multiprocessing.get_context("spawn")
    q = ctx.Queue()
    try:
        proc = ctx.Process(target=_child_main, args=(_payload_of(task), q),
                           daemon=True)
        proc.start()
    except Exception as exc:                              # noqa: BLE001 — 回落线程内
        log("task %s isolated spawn unavailable (%s: %s) → in-thread fallback",
            task.task_id, type(exc).__name__, exc)
        return False
    task.mark_running()
    log("task %s isolated child started pid=%s", task.task_id, proc.pid)

    terminal = False
    cancelled = False

    def apply(msg: dict) -> bool:
        """把子进程消息落到 task 状态；返回是否终态。"""
        kind = msg.get("type")
        if kind == "progress":
            from .models import TaskStage
            task.update_progress(TaskStage(msg["stage"]), msg["pct"],
                                 message=msg.get("message", ""))
            return False
        if kind == "result":
            task.mark_completed(msg["result"])
            return True
        if kind == "error":
            tb = msg.get("traceback") or ""
            task.mark_failed(msg["error"])
            if tb:
                log("task %s child traceback:\n%s", task.task_id, tb)
            return True
        if kind == "cancelled":
            task.mark_cancelled()
            return True
        log("task %s unknown child message ignored: %r", task.task_id, kind)
        return False

    try:
        while proc.is_alive():
            if task.cancel_requested and not cancelled:
                cancelled = True
                proc.terminate()
                log("task %s isolated child terminated (cancel)", task.task_id)
            try:
                msg = q.get(timeout=0.5)
            except _queue.Empty:
                continue
            except (OSError, EOFError):                   # 管道随子进程死亡
                break
            if apply(msg):
                terminal = True
                break
        if not terminal:
            for _ in range(64):                           # 排空残留（可能藏着终态信封）
                try:
                    msg = q.get_nowait()
                except (_queue.Empty, EOFError, OSError):
                    break
                if apply(msg):
                    terminal = True
                    break
        if not terminal and cancelled:
            task.mark_cancelled()
            terminal = True
        if not terminal:
            # 子进程无信封退出 = 段错误/硬崩 —— 隔离价值所在：只损失本任务。
            task.mark_failed(f"工作进程异常退出（exitcode={proc.exitcode}）。"
                             f"服务未受影响，可重新提交任务。")
            log("task %s isolated child DIED without envelope exitcode=%s",
                task.task_id, proc.exitcode)
            terminal = True
        return True
    finally:
        # 拿到终态信封的正常路径：**先等子进程自己退出**再考虑 terminate。
        # 子进程 stdout 在打包态是管道（块缓冲），立刻 SIGTERM 会把它日志的尾巴整段吞掉——
        # 2026-10-07 r15 accept 实测：包内 stdout 少了精排/ISC 的 device= 行，
        # 「精排在 GPU（未回退 CPU torch）」两条硬断言直接红，而任务本身是成功的。
        # 诊断日志是这层的产品能力（三级日志 / 客服定位真因），不能为了收得快而丢。
        # 取消与硬崩路径不变：仍立即 terminate，那是隔离的语义。
        if terminal and not cancelled and proc.is_alive():
            proc.join(timeout=CHILD_GRACE_S)
        if proc.is_alive():
            proc.terminate()
        proc.join(timeout=30)
        log("task %s isolated child reaped exitcode=%s", task.task_id, proc.exitcode)
