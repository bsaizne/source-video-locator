"""infrastructure.logging — 统一日志（stderr，带时间戳/级别/模块名）。

刻意简单：MVP 用 stdlib logging，无第三方依赖。UI 可调用一次
``configure_logging`` 设置级别，剩余模块用 ``get_logger(__name__)``。
"""
from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)-5s %(name)s: %(message)s"
_configured = False


def configure_logging(level: int = logging.INFO, *, stream=None) -> None:
    """幂等地配置 root logger。``stream`` 默认 stderr（GUI 不污染 stdout）。"""
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    if not any(getattr(h, "_svl", False) for h in root.handlers):
        setattr(handler, "_svl", True)
        root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
