"""infrastructure — 跨切面基础层（配置 / 日志 / 错误模型 / 路径）。

下层（media / device / engine）可依赖 infrastructure；infrastructure 不依赖
上层。domain 是纯数据模型，无 infrastructure 依赖。
"""
from .config import (AppConfig, ConfidenceConfig, DeviceConfig, MediaConfig,
                     PipelineConfig, load_config)
from .errors import (ApplicationError, ConfigError, DeviceError, FeatureExtractionError,
                      IndexError, LocalizationError, LocatorError, public_error)
from .logging import (configure_logging, get_logger, get_session_id, new_session_id,
                      redact_text, set_session_id)
from .paths import app_data_dir, ensure_dir, export_root, index_root

__all__ = [
    "AppConfig",
    "ConfidenceConfig",
    "DeviceConfig",
    "MediaConfig",
    "PipelineConfig",
    "load_config",
    "ApplicationError",
    "ConfigError",
    "DeviceError",
    "FeatureExtractionError",
    "IndexError",
    "LocalizationError",
    "LocatorError",
    "public_error",
    "redact_text",
    "configure_logging",
    "get_logger",
    "get_session_id",
    "new_session_id",
    "set_session_id",
    "app_data_dir",
    "ensure_dir",
    "export_root",
    "index_root",
]
