"""infrastructure.settings_repo — 轻量应用设置持久化（stdlib json）。

只持久化会跨重启生效的用户偏好（当前：推理后端首选 ``device.preferred``），
写入 ``<data_dir>/settings.json``。MVP 用 stdlib json（TECH_STACK §4），无第三方。
返回原始 key，运行时业务校验交给 app service / 路由层；本模块**不**做语义校验。
"""
from __future__ import annotations

import json
from pathlib import Path

from . import paths

# 合法的推理后端偏好。auto = 能力探测（GPU 可用则 GPU，否则 CPU）。
VALID_DEVICE_PREFS = ("auto", "cpu", "directml", "mps")


def _settings_path(data_dir: str | Path | None = None) -> Path:
    return paths.app_data_dir(override=data_dir) / "settings.json"


def load_device_preferred(data_dir: str | Path | None = None) -> str | None:
    """读取持久化的 ``device.preferred``；文件缺失/非法返回 ``None``（用默认）。"""
    p = _settings_path(data_dir)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        v = raw.get("device", {}).get("preferred")
    except (json.JSONDecodeError, OSError):
        return None
    return v if isinstance(v, str) else None


def save_device_preferred(preferred: str, data_dir: str | Path | None = None) -> None:
    """写 ``device.preferred`` 到 settings.json（保留其它已存在的 settings 字段，不覆盖）。"""
    p = _settings_path(data_dir)
    try:
        raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except (json.JSONDecodeError, OSError):
        raw = {}
    raw.setdefault("device", {})["preferred"] = preferred
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(raw, indent=2, ensure_ascii=False), encoding="utf-8")

