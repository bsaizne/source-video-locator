"""解码/推理流水线（2026-09-06 性能批①, 零语义）。

``pipeline_map``：生产者线程跑可迭代（如 ffmpeg 解码分块）, 消费者在**调用方线程**
逐项处理（如 embed——DML session 非线程安全, forward 必须单线程）。解码与推理重叠,
帧/特征产出与串行逐字节一致。
"""
from __future__ import annotations

import queue
import threading
from collections.abc import Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")

_SENTINEL = object()


def pipeline_map(produce: Iterable[T], fn: Callable[[T], R], *, maxsize: int = 2) -> list[R]:
    """生产者线程 + 主线程消费的保序 map。

    - ``produce``：可迭代（在后台线程耗尽, 如 ffmpeg 解码）;
    - ``fn``：逐项处理（在调用方线程执行——GPU session 非线程安全）;
    - 异常安全：``produce`` 或 ``fn`` 抛错都尽快终止对方, 并把首个异常重抛;
    - 返回 ``[fn(x) for x in produce]`` 的等价结果（保序）。
    """
    q_in: queue.Queue = queue.Queue(maxsize=maxsize)
    err: list[BaseException] = []
    stop = threading.Event()

    def _put_data(item) -> None:
        while not stop.is_set():
            try:
                q_in.put(item, timeout=0.5)
                return
            except queue.Full:
                continue

    def _put_sentinel() -> None:
        # 哨兵投递不受 stop 影响（stop 置位后仍必须送达, 否则消费者死等——实测教训）
        while True:
            try:
                q_in.put(_SENTINEL, timeout=0.5)
                return
            except queue.Full:
                continue

    def _produce() -> None:
        try:
            for item in produce:
                if stop.is_set():
                    return
                _put_data(item)
        except BaseException as exc:  # noqa: BLE001 —— 转交给主线程重抛
            err.append(exc)
        finally:
            stop.set()
            _put_sentinel()

    th = threading.Thread(target=_produce, daemon=True, name="svl-decode-pipeline")
    th.start()
    out: list[R] = []
    try:
        while True:
            item = q_in.get()
            if item is _SENTINEL:
                break
            out.append(fn(item))
    except BaseException as exc:  # noqa: BLE001 —— 停掉生产者后重抛
        err.insert(0, exc)
    finally:
        stop.set()
        th.join(timeout=10)
    if err:
        raise err[0]
    return out
