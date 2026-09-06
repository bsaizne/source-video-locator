"""mvp.api — FastAPI 桥（Adapter Layer）。

把前端 HTTP 请求转发到已有的 :class:`SourceLocatorService`，只做转发，不实现算法。
import 本包时把 ``mvp/src`` 挂入 ``sys.path``，使桥能 import ``app``/``domain``/``infrastructure``
（``app`` 即服务包，取自 ``mvp/src/app``；与 ``mvp.tests.*`` 通过 ``sys.path.insert(...,/src)`` 同款）。
"""
from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"   # mvp/src
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
