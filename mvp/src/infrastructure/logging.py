"""infrastructure.logging — 统一日志基础设施（stderr + 文件，自动轮转，**落盘前脱敏**）。

设计：
- 纯 stdlib ``logging``，无第三方依赖。
- ``get_logger(name)``：任意模块拿 logger，统一格式。
- ``configure_logging(level, stream=None, log_dir=None)``：幂等；stderr + 文件双输出，
  文件用 ``RotatingFileHandler``（默认 10MB × 5 备份，写入就近 ``mvp/logs/``
  的 ``video_locator.log``，路径可由 ``log_dir``/env ``SVL_LOG_DIR`` 覆盖）。
- 结构化文本格式：``时间 级别 module=<name> session=<sid> <message>``。
- ``session_id``：轻量 ``contextvars``（uuid4 hex 前 8 位），无需数据库；供未来
  FastAPI 每请求 / 多任务并发时区分日志行。
- **脱敏（2026-09-28 续19, T1-2）**：日志里的本机绝对路径只保留文件名、URL 只保留
  scheme+host、``?token=``/``?session=`` 之类查询参数一律打码。理由 = 日志是售后
  唯一要发给外人的产物（``/api/logs/download`` 打 zip），而客户素材路径属隐私。
  本地排查可用 env ``SVL_LOG_REDACTION=off`` 关闭。
"""
from __future__ import annotations

import logging
import os
import re
import sys
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path
from uuid import uuid4

LOG_FILENAME = "video_locator.log"
MAX_BYTES = 10 * 1024 * 1024   # 10MB
BACKUP_COUNT = 5

_FMT = "%(asctime)s %(levelname)s module=%(name)s session=%(session_id)s %(message)s"

# ---------------------------------------------------------------- 脱敏
_SECRET_QUERY = re.compile(r"([?&](?:token|session|svl_session|api_key)=)[^&\s\"']*", re.I)
_WIN_PATH = re.compile(r"\b[A-Za-z]:[\\/][^\s\"'<>|]*")
_UNC_PATH = re.compile(r"\\\\[^/\s\"'<>|]+(?:/[^\s\"'<>|]*)?")
_POSIX_PATH = re.compile(r"/(?:Users|home|var|opt|mnt|media|srv)/[^\s\"'<>|]*")
_URL = re.compile(r"\b(?:file|https?|ftp)://[^\s\"'<>|]+", re.I)
_TRAILING = ".,;:)]}\"'"


def _basename(p: str) -> str:
    tail = p.rstrip(_TRAILING)
    keep = p[len(tail):]          # 匹配吃掉的收尾标点要还回去
    name = tail.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
    return (("<PATH:%s>" % name) if name else "<PATH>") + keep


def _redact_url(m: re.Match) -> str:
    """file:// 只留文件名；http(s)/ftp 保留 host+path（诊断需要），只打码查询串
    （令牌/密钥都在 query 里）。"""
    raw = m.group(0)
    url = raw.rstrip(_TRAILING)
    keep = raw[len(url):]
    scheme, rest = url.split("://", 1)
    if scheme.lower() == "file":
        return _basename(rest) + keep
    head, _, query = rest.partition("?")
    masked = head if not query else head + "?<REDACTED>"
    return "%s://%s%s" % (scheme.lower(), masked, keep)


def redaction_enabled() -> bool:
    return str(os.environ.get("SVL_LOG_REDACTION", "")).strip().lower() not in (
        "off", "0", "false", "no")


def redact_text(text: str) -> str:
    """打码顺序：查询参数 → URL → 绝对路径（Win 先于 UNC，避免 repr 的双反斜杠被
    UNC 规则截断留下盘符）。相对路径不动。``SVL_LOG_REDACTION=off`` 时原样返回。"""
    if not text or not redaction_enabled():
        return text
    text = _SECRET_QUERY.sub(lambda m: m.group(1) + "<REDACTED>", text)
    text = _URL.sub(_redact_url, text)
    text = _WIN_PATH.sub(lambda m: _basename(m.group(0)), text)
    text = _UNC_PATH.sub(lambda m: _basename(m.group(0)), text)
    text = _POSIX_PATH.sub(lambda m: _basename(m.group(0)), text)
    return text


class RedactingFilter(logging.Filter):
    """在格式化前改写 record：脱敏 msg 与异常文本。返回 True（只脱敏不丢弃）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_text(record.getMessage())
            record.args = ()
        except Exception:  # noqa: BLE001 - 脱敏失败不能吞掉日志
            pass
        return True

# ---------------------------------------------------------------- session id
_session: ContextVar[str] = ContextVar("svl_session", default="")


def get_session_id() -> str:
    return _session.get()


def set_session_id(sid: str | None = None) -> str:
    """设置当前上下文的 session id。

    - ``None``：生成新的 uuid4 hex 前 8 位。
    - 空串 ``""``：清空（等价回默认无 session）。
    - 其它：按给定值设置（strip 后）。
    返回生效值。
    """
    if sid is None:
        value = uuid4().hex[:8]
    else:
        value = str(sid).strip()
    _session.set(value)
    return value


def new_session_id() -> str:
    """生成并设置一个新的 session id，返回它。"""
    return set_session_id(None)


# ---------------------------------------------------------------- formatter
class _SvlFormatter(logging.Formatter):
    """注入 ``session_id``（缺省 "-"），保证含 ``%(session_id)s`` 的格式永不 KeyError。"""

    def format(self, record: logging.LogRecord) -> str:
        if not getattr(record, "session_id", ""):
            record.session_id = get_session_id() or "-"
        return super().format(record)

    def formatException(self, ei) -> str:
        """traceback 里同样可能带素材绝对路径（FFmpeg stderr / open(path) 异常）。"""
        return redact_text(super().formatException(ei))


def _make_formatter() -> logging.Formatter:
    return _SvlFormatter(_FMT)


# ---------------------------------------------------------------- paths
def _log_path(log_dir: str | Path | None = None) -> Path:
    if log_dir is not None:
        return Path(log_dir) / LOG_FILENAME
    env = os.environ.get("SVL_LOG_DIR")
    base = Path(env) if env else Path(__file__).resolve().parents[2] / "logs"  # -> mvp/logs
    return base / LOG_FILENAME


def log_dir() -> Path:
    """当前日志目录（与文件 handler 同源；供 API 层日志快照/打包用）。"""
    return _log_path(None).parent


# ---------------------------------------------------------------- configure
def _ensure_stream_handler(stream, root: logging.Logger) -> None:
    for h in root.handlers:
        if getattr(h, "_svl_stream", False):
            return
    h = logging.StreamHandler(stream or sys.stderr)
    h.setFormatter(_make_formatter())
    h.addFilter(RedactingFilter())
    setattr(h, "_svl_stream", True)
    root.addHandler(h)


def _ensure_file_handler(log_dir: str | Path | None, root: logging.Logger) -> None:
    target = _log_path(log_dir).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    for h in list(root.handlers):
        if getattr(h, "_svl_file", False):
            if Path(h.baseFilename).resolve() == target:
                return
            root.removeHandler(h)
            h.close()
    fh = RotatingFileHandler(str(target), maxBytes=MAX_BYTES,
                             backupCount=BACKUP_COUNT, encoding="utf-8")
    fh.setFormatter(_make_formatter())
    fh.addFilter(RedactingFilter())
    setattr(fh, "_svl_file", True)
    root.addHandler(fh)


def configure_logging(level: int = logging.INFO, *, stream=None,
                      log_dir: str | Path | None = None) -> None:
    """幂等地配置 root logger：stderr（默认 stderr，GUI 不污染 stdout）+ 文件（自动轮转）。

    可重复调用：级别更新；文件 handler 会在 ``log_dir`` 变化时切换到新路径
    （测试可在临时目录里隔离验证）。
    """
    root = logging.getLogger()
    root.setLevel(level)
    _ensure_stream_handler(stream, root)
    _ensure_file_handler(log_dir, root)


def get_logger(name: str) -> logging.Logger:
    """统一获取 logger。``name`` 建议传 ``__name__``（自动化 ``module=`` 字段）。"""
    return logging.getLogger(name)
