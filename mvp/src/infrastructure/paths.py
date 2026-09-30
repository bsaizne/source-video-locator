"""infrastructure.paths — 数据目录 / 索引根 / 输出目录解析（跨平台）。

索引与输出都放在用户数据目录（默认随 OS 的 app-data），**不是**研究期的
``work/``，也不放在视频源目录（INDEX_SPEC §7）。可用环境变量
``SVL_DATA_DIR`` 或在 config 里显式覆盖（开发用）。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_APP_NAME = "SourceVideoLocator"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def app_data_dir(*, override: str | Path | None = None) -> Path:
    """返回用户数据根目录，并确保存在。

    优先级：显式 override > env ``SVL_DATA_DIR`` > 平台 app-data 默认。
    """
    if override is not None:
        return ensure_dir(override)
    env = os.environ.get("SVL_DATA_DIR")
    if env:
        return ensure_dir(env)
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"
    return ensure_dir(base / _APP_NAME)


def index_root(*, override: str | Path | None = None) -> Path:
    """特征索引缓存根目录（一个 Original 一个 ``<stem>.idx/`` 子目录）。"""
    return ensure_dir(app_data_dir(override=override) / "index")


def export_root(*, override: str | Path | None = None) -> Path:
    """导出提取片段默认输出目录。"""
    return ensure_dir(app_data_dir(override=override) / "exports")


def models_root(*, override: str | Path | None = None) -> Path:
    """生产模型资产根目录（如 DirectML 的 ONNX 图 + 外部权重）。"""
    return ensure_dir(app_data_dir(override=override) / "models")


def merged_source_root(*, override: str | Path | None = None) -> Path:
    """多原片合并产物根目录（竞品 video.concat 的稳定命名缓存文件所在，2026-09-29）。

    不写用户素材目录——合并是产品派生产物，与索引/导出同级放在 app data 下，
    删除可由「残留清理」统一管理。
    """
    return ensure_dir(app_data_dir(override=override) / "merged")


def rendered_root(*, override: str | Path | None = None) -> Path:
    """成片渲染产物根目录（2026-09-29 续30，竞品 video_renderer 移植）。

    与 ``merged`` 同族：产品派生产物进 app data，不写用户素材目录；稳定命名可复用，
    残留清理由统一入口管理。用户显式指定 ``render.out_dir`` 时优先该目录。
    """
    return ensure_dir(app_data_dir(override=override) / "rendered")


def dinov2_dml_asset_dir(*, override: str | Path | None = None) -> Path:
    """冻结 DINOv2 CLS-384 的 DirectML ONNX 资产目录。"""
    return ensure_dir(models_root(override=override) / "dinov2_cls_384")
