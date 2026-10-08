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
- **支持档降噪（2026-10-08 续63 补九）**：asyncio proactor 的「客户端强关连接」噪声
  （``_call_connection_lost`` + WinError 10053/10054/10058）降级为 DEBUG —— 真实支持档
  492 条 ERROR 里 485 条是它（信噪比 1.4%），客服会被淹。见
  :class:`BenignConnectionNoiseFilter`；调试档（``SVL_LOG_DEBUG=1``）仍逐条保留。
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
DEBUG_FILENAME = "debug.log"
MAX_BYTES = 10 * 1024 * 1024   # 10MB
BACKUP_COUNT = 5
DEBUG_MAX_BYTES = 20 * 1024 * 1024
DEBUG_BACKUP_COUNT = 3

_FMT = "%(asctime)s %(levelname)s module=%(name)s session=%(session_id)s %(message)s"

# ---------------------------------------------------------------- 脱敏
_SECRET_QUERY = re.compile(r"([?&](?:token|session|svl_session|api_key)=)[^&\s\"']*", re.I)
_WIN_PATH = re.compile(r"\b[A-Za-z]:[\\/][^\s\"'<>|]*")
_UNC_PATH = re.compile(r"\\\\[^/\s\"'<>|]+(?:/[^\s\"'<>|]*)?")
_POSIX_PATH = re.compile(r"/(?:Users|home|var|opt|mnt|media|srv)/[^\s\"'<>|]*")
_URL = re.compile(r"\b(?:file|https?|ftp)://[^\s\"'<>|]+", re.I)
_TRAILING = ".,;:)]}\"'"
# 售后三件·脱敏补强（2026-10-02）：
# ① 百分号编码的盘符路径（URL query 里最常见：video_path=D%3A%5CUsers%5C...）；
# ② 相对 API 路径里 `*path=` 参数的值（我方请求日志只打 path 不打 query，但异常回显
#    可能带全 URL 残段；token 类参数已由 _SECRET_QUERY 覆盖，这里只补文件路径参数）。
_PCT_WIN_PATH = re.compile(r"\b[A-Za-z](?:%3a)(?:%5c)(?:[^&\s\"'<>])*", re.I)
_API_PATH_QUERY = re.compile(r"(/api/\S*?\?[^\s\"'<>]*?path=)(?!<)[^\s&\"'<>]*", re.I)


def _pct_basename(m: re.Match) -> str:
    tail = m.group(0)
    name = re.split(r"%5c", tail, flags=re.I)[-1] or "%"
    return "<PATH:%s>" % name


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
    text = _PCT_WIN_PATH.sub(_pct_basename, text)
    text = _API_PATH_QUERY.sub(lambda m: m.group(1) + "<REDACTED>", text)
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

# ---------------------------------------------------------------- 支持档降噪
# 2026-10-08 续63 补九 ②。真实支持档实测 492 条 ERROR 里 **485 条**是同一种形态
# （`review_packaged_support_log.py` D 面统计，占 98.6% ⇒ 信噪比 1.4%）：
#
#   ERROR module=asyncio Exception in callback _ProactorBasePipeTransport._call_connection_lost()
#   handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>
#   Traceback ... ConnectionResetError: [WinError 10054] 远程主机强迫关闭了一个现有的连接。
#
# 成因 = Windows proactor 事件循环在**客户端先挂断**时，transport 关闭回调里 send 抛
# ConnectionReset。谁在挂断：Electron 预览播放器取消 Range 请求、UI 轮询 `/api/tasks/*`
# 超时/关页、下载中断。这些都是**正常网络行为**，不是后端故障，却以 ERROR + 五行 traceback
# 落进支持档；客服拿到档第一眼看到几百条「远程主机强迫关闭」就会误判为链路坏了。
#
# 处理：判定为噪声的记录**降级为 DEBUG**（不是 drop）⇒ 支持档（INFO+）不再收，
# 调试档（env SVL_LOG_DEBUG=1）仍逐条保留，真出问题时支持人员能要求用户开着复现。
# 判据三条**同时**成立才动手，宁可放过不可误杀：
#   ① logger 名以 ``asyncio`` 开头——我方模块（media/app/api）的同类异常照旧 ERROR，
#      连接重置若发生在我方代码里就是真问题；
#   ② 回调是 proactor 的 pipe transport 关闭路径（``_call_connection_lost``）；
#   ③ 异常类型 ∈ {ConnectionResetError, BrokenPipeError} 且 ``winerror``（缺省时退到
#      ``errno``）属于「连接被对端关掉」那族（10053 中止 / 10054 强制关闭 / 10058 不再需要）。
_BENIGN_CONNECTION_CALLBACK = "_call_connection_lost"
_BENIGN_CONNECTION_EXC = (ConnectionResetError, BrokenPipeError)
_BENIGN_CONNECTION_WINERRORS = (10053, 10054, 10058)


def _exc_from(record: logging.LogRecord):
    """从 record 取异常实例（兼容 exc_info 的三元组 / 实例两种形态）。取不到返回 None。"""
    ei = getattr(record, "exc_info", None)
    if ei is None:
        return None
    if isinstance(ei, BaseException):
        return ei
    if isinstance(ei, tuple) and len(ei) == 3:
        return ei[1]
    return None


def is_benign_connection_noise(record: logging.LogRecord) -> bool:
    """True = asyncio proactor「客户端强关连接」噪声（见上）。"""
    name = getattr(record, "name", "") or ""
    if not (name == "asyncio" or name.startswith("asyncio.")):
        return False
    exc = _exc_from(record)
    if not isinstance(exc, _BENIGN_CONNECTION_EXC):
        return False
    # Windows 真机会给 winerror；**mac/Linux 上 OSError 没有 winerror 这个属性**（CPython 忽略该
    # 入参，2026-10-08 mac CI 实测 AttributeError）⇒ 必须 getattr 取，取不到再退 errno。
    # 两条腿缺一不可：Windows 靠 winerror、跨平台/手工构造靠 errno。
    code = getattr(exc, "winerror", None)
    if code is None:
        code = getattr(exc, "errno", None)
    if code not in _BENIGN_CONNECTION_WINERRORS:
        return False
    return _BENIGN_CONNECTION_CALLBACK in record.getMessage()


class BenignConnectionNoiseFilter(logging.Filter):
    """把 :func:`is_benign_connection_noise` 认定的记录降级为 DEBUG（支持档不收录）。

    只挂在 ``asyncio`` logger 上（logger 级 filter 不对传播来的记录生效，挂在 root
    等于没挂）；返回 True 不丢记录，只是级别变了——调试档开着时仍会进 ``debug.log``。
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.levelno >= logging.WARNING and is_benign_connection_noise(record):
                record.levelno = logging.DEBUG
                record.levelname = "DEBUG"
                record._svl_benign_connection_noise = True
        except Exception:  # noqa: BLE001 - 降噪判定失败绝不能影响日志本身
            pass
        return True


def noise_filter_enabled() -> bool:
    """降噪开关（env ``SVL_LOG_NOISE_FILTER=off`` 关闭）。默认开。

    留这个口子有两个理由：① 支持人员远程指导时可以临时看全量连接错误；
    ② 真机双臂对照（`work/r17_noise/probe_proactor.py`）需要在**同一台机、同一份
    真实 proactor 代码路径**上跑「开/关」两臂，否则「降噪有效」只能靠手工构造的
    record 自证。
    """
    return str(os.environ.get("SVL_LOG_NOISE_FILTER", "")).strip().lower() not in (
        "off", "0", "false", "no")


def _ensure_asyncio_noise_filter() -> None:
    """幂等地给 ``asyncio`` logger 挂降噪 filter（由 configure_logging 调用）。

    开关关闭时**主动摘掉**已挂的 filter：``configure_logging`` 是幂等的，同一进程里
    后调用一次也必须生效（两臂对照靠这点，否则第二个臂还带着第一个臂的 filter）。
    """
    lg = logging.getLogger("asyncio")
    lg.filters = [f for f in lg.filters if not isinstance(f, BenignConnectionNoiseFilter)]
    if noise_filter_enabled():
        lg.addFilter(BenignConnectionNoiseFilter())

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
    # 门槛与支持档一致（INFO）：调试行只进 debug.log，stdout/stderr 也与支持档同构
    # ——否则腿边界埋点/降噪降级的记录会以 DEBUG 混进包内 stdout，accept 断言读的是它。
    h.setLevel(logging.INFO)
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
    fh.setLevel(logging.INFO)      # 支持档：INFO+（调试行只进 debug.log，两档互不重复）
    setattr(fh, "_svl_file", True)
    root.addHandler(fh)


def debug_tier_enabled() -> bool:
    """调试档开关（env ``SVL_LOG_DEBUG=1``）。默认关——磁盘与隐私都只给支持档。"""
    return str(os.environ.get("SVL_LOG_DEBUG", "")).strip().lower() in (
        "1", "true", "yes", "on")


def _ensure_debug_handler(log_dir: str | Path | None, root: logging.Logger) -> bool:
    """按开关挂/摘 DEBUG 级 ``debug.log``。返回调试档是否生效。"""
    want = debug_tier_enabled()
    existing = [h for h in root.handlers if getattr(h, "_svl_debug", False)]
    if not want:
        for h in existing:
            root.removeHandler(h)
            h.close()
        return False
    target = (_log_path(log_dir).parent / DEBUG_FILENAME).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if existing and Path(existing[0].baseFilename).resolve() == target:
        return True
    for h in existing:
        root.removeHandler(h)
        h.close()
    dh = RotatingFileHandler(str(target), maxBytes=DEBUG_MAX_BYTES,
                             backupCount=DEBUG_BACKUP_COUNT, encoding="utf-8")
    dh.setLevel(logging.DEBUG)
    dh.setFormatter(_make_formatter())
    dh.addFilter(RedactingFilter())
    setattr(dh, "_svl_debug", True)
    root.addHandler(dh)
    return True


def configure_logging(level: int = logging.INFO, *, stream=None,
                      log_dir: str | Path | None = None) -> None:
    """幂等地配置 root logger：stderr（默认 stderr，GUI 不污染 stdout）+ 文件（自动轮转）。

    可重复调用：级别更新；文件 handler 会在 ``log_dir`` 变化时切换到新路径
    （测试可在临时目录里隔离验证）。

    三级日志（2026-10-02 售后三件，对齐竞品 wp.diagnostics 客户/支持/调试分层，
    不抄其加密形态）：
    - **客户档** = UI 错误条幅话术 + LOC 稳定码（errors.public_error，已存在）；
    - **支持档** = ``video_locator.log``，INFO+，落盘前脱敏，「下载日志」给客服的就是它；
    - **调试档** = ``debug.log``，DEBUG 全量（同样脱敏），默认**关**，
      env ``SVL_LOG_DEBUG=1`` 开启——支持人员指导用户排障时才让开。
    """
    root = logging.getLogger()
    debug_on = _ensure_debug_handler(log_dir, root)
    root.setLevel(logging.DEBUG if debug_on else level)
    _ensure_stream_handler(stream, root)
    _ensure_file_handler(log_dir, root)
    # 支持档降噪（2026-10-08 续63 补九 ②）：asyncio proactor 的「客户端强关连接」
    # 在真实档里占 ERROR 的 98.6%，降到 DEBUG 只留调试档。隔离子进程也调本函数
    # （续63 补二 的「子进程自配日志」），所以父/子两侧都生效。
    _ensure_asyncio_noise_filter()


def get_logger(name: str) -> logging.Logger:
    """统一获取 logger。``name`` 建议传 ``__name__``（自动化 ``module=`` 字段）。"""
    return logging.getLogger(name)
