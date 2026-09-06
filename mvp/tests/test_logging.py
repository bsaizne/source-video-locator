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
                                    new_session_id, set_session_id)


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


if __name__ == "__main__":
    unittest.main(verbosity=2)
