"""infrastructure.errors — 产品级统一错误模型。

UI 层可 catch 顶层 ``LocatorError`` 获得可展示的错误信息；具体子类承载语义。
media 层的 ``MediaError`` 是本模型的子类（见 media/ffmpeg/_runner.py），因此
"任何视频/FFmpeg 失败"都能被 ``except LocatorError`` 捕获。
"""
from __future__ import annotations


class LocatorError(RuntimeError):
    """产品运行时所有失败的基础异常。"""


class ConfigError(LocatorError):
    """配置缺失 / 非法 / 无法加载。"""


class DeviceError(LocatorError):
    """设备后端（CPU/GPU/MPS）初始化或推理失败，如模型权重缺失。"""


class IndexError(LocatorError):
    """原片特征索引建立 / 加载 / 校验失败（FeatureStore 层）。"""


class FeatureExtractionError(LocatorError):
    """编辑侧视频抽帧或特征提取失败（FFmpegIO / embed_frames 层）。"""


class LocalizationError(LocatorError):
    """候选检索 / 精定位 / 置信度环节失败（Engine 层，非段级隔离时）。"""


class ApplicationError(LocatorError):
    """应用服务编排 / 取消 / 其它未归类失败。GUI 可干净处理，不解析原始 exception。"""
