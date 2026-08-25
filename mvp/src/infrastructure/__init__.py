"""infrastructure — 跨切面基础层（配置 / 日志 / 错误模型 / 路径）。

下层（media / device / engine）可依赖 infrastructure；infrastructure 不依赖
上层。domain 是纯数据模型，无 infrastructure 依赖。
"""
from .config import (AppConfig, ConfidenceConfig, DeviceConfig, MediaConfig,
                     PipelineConfig, load_config)
from .errors import ConfigError, LocatorError
from .logging import configure_logging, get_logger
from .paths import app_data_dir, ensure_dir, export_root, index_root

__all__ = [
    "AppConfig",
    "ConfidenceConfig",
    "DeviceConfig",
    "MediaConfig",
    "PipelineConfig",
    "load_config",
    "ConfigError",
    "LocatorError",
    "configure_logging",
    "get_logger",
    "app_data_dir",
    "ensure_dir",
    "export_root",
    "index_root",
]
