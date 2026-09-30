"""infrastructure.errors — 产品级统一错误模型 + 稳定对外错误码。

UI 层可 catch 顶层 ``LocatorError`` 获得可展示的错误信息；具体子类承载语义。
media 层的 ``MediaError`` 是本模型的子类（见 media/ffmpeg/_runner.py），因此
"任何视频/FFmpeg 失败"都能被 ``except LocatorError`` 捕获。

对外码（2026-09-28 续19, T1-2）：借鉴竞品 ``diagnostics.public_messages`` 的
「稳定编号 + 用户话术」结构（不抄它的码）。规则：
- ``LOC-1xxx`` = 异常类可归类；``LOC-2xxx`` = 非阻断告警；``LOC-9999`` = 未归类兜底。
- 码一旦发布即**只增不改**（客服/文档按码定位），``user_message`` 是可给用户的中文话术，
  ``str(exc)`` 是给工程师的技术细节，两者分开返回。
"""
from __future__ import annotations


class LocatorError(RuntimeError):
    """产品运行时所有失败的基础异常。"""

    code = "LOC-1000"
    user_message = "处理失败，请把日志（设置页「下载日志」）发给支持人员定位。"


class ConfigError(LocatorError):
    """配置缺失 / 非法 / 无法加载。"""

    code = "LOC-1101"
    user_message = "软件配置缺失或不合法，请检查配置文件后重试。"


class DeviceError(LocatorError):
    """设备后端（CPU/GPU/MPS）初始化或推理失败，如模型权重缺失。"""

    code = "LOC-1102"
    user_message = "显卡/推理后端不可用或模型文件缺失，请在设置页改用 CPU 后重试。"


class IndexError(LocatorError):
    """原片特征索引建立 / 加载 / 校验失败（FeatureStore 层）。"""

    code = "LOC-1103"
    user_message = "原片索引损坏或与当前版本不匹配，请删除该原片索引后重新建立。"


class FeatureExtractionError(LocatorError):
    """编辑侧视频抽帧或特征提取失败（FFmpegIO / embed_frames 层）。"""

    code = "LOC-1104"
    user_message = "视频画面读取失败，请确认文件完整且能正常播放。"


class LocalizationError(LocatorError):
    """候选检索 / 精定位 / 置信度环节失败（Engine 层，非段级隔离时）。"""

    code = "LOC-1105"
    user_message = "定位计算未完成，请重试或缩小本次分析范围。"


class ApplicationError(LocatorError):
    """应用服务编排 / 取消 / 其它未归类失败。GUI 可干净处理，不解析原始 exception。"""

    code = "LOC-1106"
    user_message = "任务未能完成，请重试；若反复出现请下载日志发给支持人员。"


def public_error(exc: BaseException) -> dict:
    """把任意异常转成对外错误体：稳定码 + 用户话术 + 技术细节。"""
    code = str(getattr(exc, "code", "") or "") or "LOC-9999"
    message = str(getattr(exc, "user_message", "") or "")
    if not message:
        code = "LOC-9999"
        message = LocatorError.user_message
    return {"code": code, "message": message,
            "error": type(exc).__name__, "detail": str(exc)}
