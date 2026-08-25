"""infrastructure.results_repo — Result 批量信封的 JSON 落盘 / 读取。

一次分析任务 = 一个 ``*.results.json``，复用 ``domain.Result.to_dict()/from_dict()``
保留 auto/manual 双轨（``manual_override`` 时的 ``auto_result`` / ``manual_timestamp``）。
文件名约定：``<edited_stem>__<hash8(edited abspath)>.results.json``，落 ``paths.export_root()``
（可覆盖 ``out_dir``）。MVP 用 stdlib json + ``ensure_ascii=False`` 可读可编辑。
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from domain import ResultBatch

from .paths import ensure_dir, export_root


def _result_filename(edited: str | Path | None) -> str:
    """``<stem>__<hash8(abspath)>.results.json``；hash 来自绝对路径，与 FeatureStore 同款约定。"""
    if edited is None:
        return "results.results.json"
    p = Path(edited).resolve()
    h = hashlib.sha256(str(p).encode("utf-8")).hexdigest()[:8]
    return f"{p.stem}__{h}.results.json"


def save_results(batch: ResultBatch, *, out_dir: str | Path | None = None,
                 filename: str | None = None) -> Path:
    """写一个结果批到 JSON。返回写入路径。"""
    d = ensure_dir(out_dir if out_dir is not None else export_root())
    name = filename or _result_filename(batch.edited_video)
    p = d / name
    p.write_text(json.dumps(batch.to_dict(), indent=2, ensure_ascii=False),
                 encoding="utf-8")
    return p


def load_results(path: str | Path) -> ResultBatch:
    """从 JSON 读回一个结果批。"""
    p = Path(path)
    return ResultBatch.from_dict(json.loads(p.read_text(encoding="utf-8")))
