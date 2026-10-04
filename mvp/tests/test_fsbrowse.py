"""Unit tests for mvp.infrastructure.fsbrowse（入库层四件，2026-10-02）。

Run: "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_fsbrowse -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from infrastructure import fsbrowse
from infrastructure.errors import DiskSpaceError


class NaturalSortTest(unittest.TestCase):
    def test_digits_compare_numerically(self):
        names = ["clip10.mp4", "clip2.mp4", "clip1.mp4", "Clip20.mkv"]
        self.assertEqual(list(fsbrowse.sort_natural(names)),
                         ["clip1.mp4", "clip2.mp4", "clip10.mp4", "Clip20.mkv"])

    def test_case_insensitive_text(self):
        self.assertEqual(list(fsbrowse.sort_natural(["b", "a", "C"])), ["a", "b", "C"])

    def test_natural_key_mixed(self):
        self.assertLess(fsbrowse.natural_key("ep2"), fsbrowse.natural_key("ep10"))


class WhitelistTest(unittest.TestCase):
    def test_common_containers_accepted(self):
        for n in ("a.mp4", "b.MKV", "c.mov", "d.avi", "e.webm", "f.mts"):
            self.assertTrue(fsbrowse.is_video(n), n)

    def test_non_video_rejected(self):
        for n in ("a.txt", "b.srt", "c.jpg", "d", "e.pdf"):
            self.assertFalse(fsbrowse.is_video(n), n)


class BrowseTest(unittest.TestCase):
    def test_root_lists_drives(self):
        out = fsbrowse.browse(None)
        self.assertEqual(out["kind"], "root")
        self.assertTrue(out["drives"])
        d = out["drives"][0]
        for k in ("name", "path", "total_bytes", "free_bytes"):
            self.assertIn(k, d)
        if sys.platform == "win32":
            self.assertTrue(any(x["path"].upper().startswith("C:") for x in out["drives"]))

    def test_dir_entries_sorted_and_filtered(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "subB").mkdir()
            (Path(td) / "subA").mkdir()
            for f in ("clip10.mp4", "clip2.mp4", "notes.txt", "cover.jpg"):
                (Path(td) / f).write_bytes(b"x")
            out = fsbrowse.browse(td)
            self.assertEqual(out["kind"], "dir")
            names = [e["name"] for e in out["entries"]]
            self.assertEqual(names, ["subA", "subB", "clip2.mp4", "clip10.mp4"])
            self.assertTrue(all(e["is_video"] for e in out["entries"]
                                if not Path(e["path"]).is_dir()))
            self.assertGreater(out["free_bytes"], 0)
            self.assertEqual(out["parent"], str(Path(td).parent))

    def test_hidden_and_unreadable_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / ".secret.mp4").write_bytes(b"x")
            (Path(td) / "ok.mp4").write_bytes(b"x")
            out = fsbrowse.browse(td)
            self.assertEqual([e["name"] for e in out["entries"]], ["ok.mp4"])

    def test_error_paths(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                fsbrowse.browse(Path(td) / "nope")
            f = Path(td) / "v.mp4"
            f.write_bytes(b"x")
            with self.assertRaises(NotADirectoryError):
                fsbrowse.browse(f)


class DriveSpaceTest(unittest.TestCase):
    def test_require_free_passes_for_small_need(self):
        with tempfile.TemporaryDirectory() as td:
            fsbrowse.require_free_space(td, 1024, what="test")  # 不抛即过

    def test_require_free_raises_with_loc_code(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(DiskSpaceError) as cm:
                fsbrowse.require_free_space(td, 10 ** 18, what="test")
            self.assertEqual(cm.exception.code, "LOC-1108")

    def test_free_bytes_walks_up_for_missing_dir(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertGreater(fsbrowse.free_bytes(Path(td) / "not" / "yet"), 0)

    def test_parent_of_drive_root(self):
        if sys.platform == "win32":
            # 盘符根的上一级 = ''（前端据此回「此电脑」）
            self.assertEqual(fsbrowse.parent_of("C:\\"), "")
        else:
            self.assertIsNone(fsbrowse.parent_of("/"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
