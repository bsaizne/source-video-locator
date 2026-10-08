"""Unit tests for mvp.infrastructure.logging.

Run with the venv python:
  "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_logging -v
"""
from __future__ import annotations

import logging
import sys
import tempfile
import unittest
from logging.handlers import RotatingFileHandler
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))  # -> mvp/src

from infrastructure.logging import (configure_logging, get_logger, get_session_id,
                                    new_session_id, redact_text, set_session_id)


class _RootIsolateMixin:
    """快照并恢复 root logger 的 level/handlers，避免测试污染其它测试模块。"""

    def _snapshot(self):
        root = logging.getLogger()
        return (root.level, list(root.handlers))

    def _restore(self, snap):
        root = logging.getLogger()
        root.setLevel(snap[0])
        for h in list(root.handlers):
            root.removeHandler(h)
            h.close()
        for h in snap[1]:
            root.addHandler(h)

    def _flush_files(self):
        for h in logging.getLogger().handlers:
            if isinstance(h, RotatingFileHandler):
                h.flush()


class GetLoggerTest(unittest.TestCase):
    def test_get_logger_returns_logger(self):
        lg = get_logger("svl.test")
        self.assertIsInstance(lg, logging.Logger)
        self.assertIs(lg, logging.getLogger("svl.test"))

    def test_no_session_by_default(self):
        # fresh context: session id empty
        self.assertEqual(get_session_id(), "")


class LevelWriteTest(unittest.TestCase):
    def test_info_warning_error_written(self):
        lg = get_logger("svl.levels")
        with self.assertLogs("svl.levels", level="INFO") as cm:
            lg.info("hello info")
            lg.warning("hello warning")
            lg.error("hello error")
        joined = "\n".join(cm.output)
        self.assertIn("hello info", joined)
        self.assertIn("hello warning", joined)
        self.assertIn("hello error", joined)
        self.assertIn("ERROR", joined)


class SessionTest(unittest.TestCase):
    def test_new_session_id_sets_and_get(self):
        sid = new_session_id()
        self.assertEqual(len(sid), 8)
        self.assertEqual(get_session_id(), sid)

    def test_set_session_id_given(self):
        self.assertEqual(set_session_id("a82f91"), "a82f91")
        self.assertEqual(get_session_id(), "a82f91")
        set_session_id("")  # clear

    def test_set_session_id_empty_clears(self):
        new_session_id()
        self.assertNotEqual(get_session_id(), "")
        set_session_id("")
        self.assertEqual(get_session_id(), "")


class ConfigureFileTest(unittest.TestCase, _RootIsolateMixin):
    def test_rotating_handler_installed(self):
        snap = self._snapshot()
        # 恢复必须在临时目录被清理（with 退出）之前执行，否则文件仍被 handler 占用无法删除。
        with tempfile.TemporaryDirectory() as td:
            try:
                configure_logging(level=logging.INFO, log_dir=td)
                fh = [h for h in logging.getLogger().handlers
                      if isinstance(h, RotatingFileHandler)]
                self.assertTrue(fh, "RotatingFileHandler should be installed")
                self.assertEqual(fh[0].maxBytes, 10 * 1024 * 1024)
                self.assertEqual(fh[0].backupCount, 5)
            finally:
                self._restore(snap)

    def test_file_written_structured_with_session(self):
        snap = self._snapshot()
        with tempfile.TemporaryDirectory() as td:
            try:
                configure_logging(level=logging.DEBUG, log_dir=td)
                sid = new_session_id()
                get_logger("svl.file").info("index started video=test.mkv")
                self._flush_files()
                text = (Path(td) / "video_locator.log").read_text(encoding="utf-8")
                self.assertIn("index started video=test.mkv", text)
                self.assertIn("INFO", text)
                self.assertIn("module=svl.file", text)
                self.assertIn(f"session={sid}", text)
            finally:
                set_session_id("")  # clear context
                self._restore(snap)


class RedactionTest(unittest.TestCase, _RootIsolateMixin):
    """T1-2：日志是售后唯一要发给外人的产物 ⇒ 绝对路径/URL/令牌必须落盘前打码。"""

    def test_windows_path_keeps_only_basename(self):
        out = redact_text(r"index failed opening D:\客户素材\2.mkv now")
        self.assertIn("<PATH:2.mkv>", out)
        self.assertNotIn("客户素材", out)

    def test_trailing_punctuation_preserved(self):
        self.assertEqual(redact_text("load C:/a/b.json)"), "load <PATH:b.json>)")

    def test_posix_and_unc_paths(self):
        self.assertIn("<PATH:movie.mp4>", redact_text("see /home/alex/movie.mp4"))
        self.assertNotIn("/home/alex", redact_text("see /home/alex/movie.mp4"))
        self.assertIn("<PATH:", redact_text(r"\\nas\share\clip.mov"))

    def test_url_keeps_path_drops_query(self):
        out = redact_text("license server https://api.example.com/v1/licenses/activate?k=secret")
        self.assertIn("https://api.example.com/v1/licenses/activate?<REDACTED>", out)
        self.assertNotIn("secret", out)

    def test_file_url_reduced_to_basename(self):
        self.assertIn("<PATH:a.mp4>", redact_text("src file:///D:/vid/a.mp4"))

    def test_secret_query_params_masked(self):
        out = redact_text("GET /api/preview?session=abc123&token=zzz tail")
        self.assertNotIn("abc123", out)
        self.assertNotIn("zzz", out)
        self.assertIn("session=<REDACTED>", out)

    def test_relative_paths_and_plain_text_untouched(self):
        for s in ("index started video=test.mkv", "wrote work/x.json",
                  "module=svl.file session=- ok", "batch 5/69 segs"):
            self.assertEqual(redact_text(s), s)

    def test_idempotent(self):
        once = redact_text(r"open D:\a\b\c.npy")
        self.assertEqual(redact_text(once), once)

    def test_off_switch(self):
        import os
        old = os.environ.get("SVL_LOG_REDACTION")
        os.environ["SVL_LOG_REDACTION"] = "off"
        try:
            self.assertEqual(redact_text(r"open D:\a\b.c"), r"open D:\a\b.c")
        finally:
            if old is None:
                del os.environ["SVL_LOG_REDACTION"]
            else:
                os.environ["SVL_LOG_REDACTION"] = old

    def test_traceback_is_redacted_too(self):
        snap = self._snapshot()
        with tempfile.TemporaryDirectory() as td:
            try:
                configure_logging(level=logging.INFO, log_dir=td)
                try:
                    open(r"D:\私密目录\不存在.mkv")
                except OSError:
                    get_logger("svl.tb").exception("read failed")
                self._flush_files()
                text = (Path(td) / "video_locator.log").read_text(encoding="utf-8")
                self.assertIn("read failed", text)
                self.assertNotIn("私密目录", text)
                self.assertIn("<PATH:", text)
            finally:
                self._restore(snap)


class RedactionV2Test(unittest.TestCase):
    """售后三件·脱敏补强（2026-10-02）：百分号编码盘符路径 + /api query 的 *path= 值。"""

    def test_percent_encoded_win_path(self):
        out = redact_text("GET /api/index/status?video_path=D%3A%5C%E7%B4%A0%E6%9D%90%5Ctest2.mkv")
        self.assertIn("<PATH:test2.mkv>", out)
        self.assertNotIn("%E7%B4%A0%E6%9D%90", out)   # 目录名（编码中文）不得残留

    def test_api_path_query_masked(self):
        out = redact_text("GET /api/index/status?video_path=D:/vid/x.mkv&n=3")
        self.assertNotIn("D:/vid", out)
        self.assertNotIn("x.mkv", out.replace("<PATH:x.mkv>", ""))  # 只允许脱敏形态出现

    def test_plain_api_query_untouched(self):
        # token 类走 _SECRET_QUERY；普通数值参数不误伤
        out = redact_text("GET /api/logs/recent?bytes_limit=49152")
        self.assertIn("bytes_limit=49152", out)


class DebugTierTest(unittest.TestCase, _RootIsolateMixin):
    """三级日志·调试档：默认关；SVL_LOG_DEBUG=1 时 DEBUG 只进 debug.log。"""

    def _run(self, monkey_env: str | None, td: str) -> tuple[str, str]:
        import os
        snap = self._snapshot()
        old = os.environ.get("SVL_LOG_DEBUG")
        try:
            if monkey_env is None:
                os.environ.pop("SVL_LOG_DEBUG", None)
            else:
                os.environ["SVL_LOG_DEBUG"] = monkey_env
            configure_logging(level=logging.INFO, log_dir=td)
            lg = get_logger("svl.tier")
            lg.debug("dbg-line")
            lg.info("info-line")
            self._flush_files()
            main = (Path(td) / "video_locator.log").read_text(encoding="utf-8")
            dbg_p = Path(td) / "debug.log"
            dbg = dbg_p.read_text(encoding="utf-8") if dbg_p.exists() else ""
            return main, dbg
        finally:
            if old is None:
                os.environ.pop("SVL_LOG_DEBUG", None)
            else:
                os.environ["SVL_LOG_DEBUG"] = old
            self._restore(snap)

    def test_debug_off_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            main, dbg = self._run(None, td)
            self.assertIn("info-line", main)
            self.assertNotIn("dbg-line", main)
            self.assertEqual(dbg, "")
            self.assertFalse((Path(td) / "debug.log").exists())

    def test_debug_on_writes_debug_log_only(self):
        with tempfile.TemporaryDirectory() as td:
            main, dbg = self._run("1", td)
            self.assertIn("dbg-line", dbg)
            self.assertIn("info-line", dbg)
            self.assertIn("info-line", main)
            self.assertNotIn("dbg-line", main)   # 两档互不重复

    def test_debug_env_off_string_disables(self):
        with tempfile.TemporaryDirectory() as td:
            self._run("0", td)
            self.assertFalse((Path(td) / "debug.log").exists())


class ProactorNoiseFilterTest(unittest.TestCase, _RootIsolateMixin):
    """支持档降噪（2026-10-08 续63 补九 ②）。

    真实支持档 492 条 ERROR 里 485 条（98.6%）= asyncio proactor
    `_call_connection_lost()` 里的 `ConnectionResetError [WinError 10054]`：客户端
    （Electron 预览播放器取消 Range 请求、UI 轮询关连接）先挂断，**不是故障**，
    却以 ERROR + 五行 traceback 淹没客服看到的档。⇒ 判定为噪声的记录降级 DEBUG：
    支持档（INFO+）与 stdout 都不再收录，调试档（SVL_LOG_DEBUG=1）逐条保留。

    这里同时锁「**不能误杀**」：asyncio 的其它异常、我方模块的连接异常都照旧 ERROR。
    """

    NOISE_MSG = ("Exception in callback _ProactorBasePipeTransport._call_connection_lost()\n"
                 "handle: <Handle _ProactorBasePipeTransport._call_connection_lost()>")

    def _emit(self, td: str, *, env: str | None, name: str = "asyncio",
              exc: Exception | None = None, msg: str = NOISE_MSG) -> tuple[str, str, str]:
        """按 asyncio 的真实形态发一条记录，回（支持档, 调试档, stderr 捕获）。

        stream 走 StringIO：既避免刷测试控制台，也顺带核「降噪对包内 stdout 同样生效」
        （打包验收脚本读的就是 stdout）。
        """
        import io
        import os
        snap = self._snapshot()
        old = os.environ.get("SVL_LOG_DEBUG")
        buf = io.StringIO()
        try:
            if env is None:
                os.environ.pop("SVL_LOG_DEBUG", None)
            else:
                os.environ["SVL_LOG_DEBUG"] = env
            configure_logging(log_dir=td, stream=buf)
            lg = get_logger(name)
            if exc is not None:
                try:
                    raise exc
                except type(exc):
                    lg.error(msg, exc_info=True)
            else:
                lg.error(msg)
            lg.info("support-log-alive")
            self._flush_files()
            main = (Path(td) / "video_locator.log").read_text(encoding="utf-8")
            dbg_p = Path(td) / "debug.log"
            dbg = dbg_p.read_text(encoding="utf-8") if dbg_p.exists() else ""
            return main, dbg, buf.getvalue()
        finally:
            if old is None:
                os.environ.pop("SVL_LOG_DEBUG", None)
            else:
                os.environ["SVL_LOG_DEBUG"] = old
            self._restore(snap)

    @staticmethod
    def _reset(code: int = 10054) -> Exception:
        """复刻「客户端强关连接」异常。

        Windows 上真实对象是 5 元组 `(errno, strerror, None, winerror, None)`，`str()` 渲染成
        `[WinError 10054]`；**非 Windows 平台 CPython 直接忽略 `winerror` 入参**（官方文档：
        "On other platforms, the winerror argument is ignored"），`exc.winerror` 恒为 None、
        `str()` 渲染成 `[Errno 10054]` ⇒ 这里按平台给形态，判定的「winerror 缺省退 errno」
        分支才是 mac/Linux 实际走的那条（2026-10-08 mac CI 唯一红点就出在这条渲染差异上）。
        """
        import os as _os
        msg = "远程主机强迫关闭了一个现有的连接。"
        if _os.name == "nt":
            return ConnectionResetError(code, msg, None, code, None)
        return ConnectionResetError(code, msg)

    @staticmethod
    def _code_token(code: int = 10054) -> str:
        """日志里错误码的**字面渲染分平台**：CPython 在 Windows 打 `[WinError 10054]`，
        其余平台打 `[Errno 10054]` ⇒ 断言取哪个字面量必须跟平台走。

        Windows 侧两种形态本机实测（2026-10-08）：5 元组 → `[WinError 10054] msg`，
        2 元组 → `[Errno 10054] msg`；mac 侧由上述文档 + 现役判定分支推出。
        （2026-10-08 mac CI 红点：`assertIn("WinError 10054")` 在 mac 上恒不成立 ——
        降噪判定其实是对的（走 errno 回退分支），是断言把 Windows 文案当成了跨平台事实。）
        """
        import os as _os
        return ("WinError %d" % code) if _os.name == "nt" else ("Errno %d" % code)

    def test_benign_noise_absent_from_support_log(self):
        with tempfile.TemporaryDirectory() as td:
            main, _dbg, err = self._emit(td, env=None, exc=self._reset())
            self.assertIn("support-log-alive", main)          # 档是活的，不是没落盘
            self.assertNotIn("_call_connection_lost", main)
            self.assertNotIn(self._code_token(), main)
            self.assertNotIn("ERROR", main)                   # 一条 ERROR 都不该留下
            self.assertNotIn("_call_connection_lost", err)    # stdout/stderr 同门槛

    def test_benign_noise_kept_in_debug_tier(self):
        with tempfile.TemporaryDirectory() as td:
            main, dbg, _ = self._emit(td, env="1", exc=self._reset())
            self.assertNotIn("_call_connection_lost", main)
            self.assertIn("_call_connection_lost", dbg)
            self.assertIn("DEBUG", dbg)                       # 降级而不是消失

    def test_errno_only_shape_still_downgraded(self):
        """**跨平台常驻锁**：非 Windows 的 OSError 没有 winerror（恒为 None），
        proactor 之外的 loop（mac/Linux 的 selector/kqueue）若报同类连接重置也只带 errno
        ⇒ 判定必须退到 errno 分支。这条在 Windows 上照样能构造（2 元组 = winerror None），
        把「mac 才会走的那半边」变成每平台都跑的测试，而不是等 mac CI 替我验。
        （2026-10-08 mac CI 红点的根因就是这半边从没被任何测试覆盖到。）
        """
        exc = ConnectionResetError(10054, "Connection reset by peer")
        self.assertIsNone(exc.winerror, "构造形态必须是「没有 winerror」的跨平台样")
        self.assertEqual(exc.errno, 10054)
        with tempfile.TemporaryDirectory() as td:
            main, _dbg, err = self._emit(td, env=None, exc=exc)
            self.assertIn("support-log-alive", main)
            self.assertNotIn("_call_connection_lost", main)
            self.assertNotIn("ERROR", main)
            self.assertNotIn("_call_connection_lost", err)

    def test_other_asyncio_error_still_error(self):
        """② 回调不是连接关闭路径 ⇒ 不降噪（真故障必须看得见）。"""
        with tempfile.TemporaryDirectory() as td:
            main, _dbg, _ = self._emit(
                td, env=None, msg="Exception in callback _AsyncTransport.close()",
                exc=self._reset())
            self.assertIn("ERROR", main)
            self.assertIn("_AsyncTransport.close", main)

    def test_other_exception_type_still_error(self):
        """③ 异常类型/错误码不在「客户端关连接」那族 ⇒ 不降噪。"""
        with tempfile.TemporaryDirectory() as td:
            main, _dbg, _ = self._emit(td, env=None, exc=ValueError("boom"))
            self.assertIn("ERROR", main)
            self.assertIn("ValueError", main)
        with tempfile.TemporaryDirectory() as td:
            main2, _d2, _ = self._emit(td, env=None, exc=self._reset(10061))  # 拒绝连接=真问题
            self.assertIn("ERROR", main2)

    def test_our_module_connection_reset_still_error(self):
        """① 只作用于 asyncio logger：我方模块抛同类异常 = 真问题，照旧 ERROR。"""
        with tempfile.TemporaryDirectory() as td:
            main, _dbg, _ = self._emit(td, env=None, name="media.ffmpeg",
                                       exc=self._reset())
            self.assertIn("ERROR", main)
            self.assertIn(self._code_token(), main)
            self.assertIn("_call_connection_lost", main)

    def test_filter_installed_idempotently(self):
        snap = self._snapshot()
        with tempfile.TemporaryDirectory() as td:
            try:
                configure_logging(log_dir=td)
                configure_logging(log_dir=td)
                from infrastructure.logging import BenignConnectionNoiseFilter
                n = [f for f in logging.getLogger("asyncio").filters
                     if isinstance(f, BenignConnectionNoiseFilter)]
                self.assertEqual(len(n), 1, "降噪 filter 必须幂等安装（挂多次=重复判定）")
            finally:
                self._restore(snap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
