"""客服错误编号对照表防漂移断言（2026-10-02 售后三件）。

规则：源码里出现的每个 ``LOC-xxxx`` 对外码 **必须**在
``mvp/docs/SUPPORT_ERROR_CODES.md`` 表格里有一行归口；反向亦然（表里不许挂死码）。
码只增不改 ⇒ 新增码忘了登记，本测试即红。

Run: "D:/claudework/video-dedup-tool/.venv/Scripts/python.exe" -m unittest mvp.tests.test_support_codes_doc
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

MVP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MVP / "src"))

_CODE = re.compile(r"LOC-(\d{4})")


def _source_codes() -> set[str]:
    found: set[str] = set()
    for root in (MVP / "src", MVP / "api"):
        for py in root.rglob("*.py"):
            if "tests" in py.parts:
                continue
            found.update(_CODE.findall(py.read_text(encoding="utf-8", errors="replace")))
    return {"LOC-" + c for c in found}


def _doc_codes() -> set[str]:
    doc = MVP / "docs" / "SUPPORT_ERROR_CODES.md"
    return {"LOC-" + c for c in _CODE.findall(doc.read_text(encoding="utf-8"))}


class SupportCodesDocTest(unittest.TestCase):
    def test_every_source_code_is_documented(self):
        missing = _source_codes() - _doc_codes()
        self.assertFalse(missing, f"新增对外码未登记客服对照表: {sorted(missing)}")

    def test_doc_has_no_dead_codes(self):
        dead = _doc_codes() - _source_codes()
        self.assertFalse(dead, f"对照表挂了源码已不存在的码: {sorted(dead)}")

    def test_core_error_classes_have_unique_codes(self):
        from infrastructure.errors import (ApplicationError, ConfigError, DeviceError,
                                            FeatureExtractionError, IndexError,
                                            LocalizationError, LocatorError)
        codes = [c.code for c in (LocatorError, ConfigError, DeviceError, IndexError,
                                  FeatureExtractionError, LocalizationError,
                                  ApplicationError)]
        self.assertEqual(len(codes), len(set(codes)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
