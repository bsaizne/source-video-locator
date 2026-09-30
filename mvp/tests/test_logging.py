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


if __name__ == "__main__":
    unittest.main(verbosity=2)
