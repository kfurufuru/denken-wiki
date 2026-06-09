#!/usr/bin/env python3
"""
check_stale_evidence.py のセルフテスト（pytest不要・標準ライブラリのみ）。

usage:
  python scripts/tests/check_stale_evidence/test_check_stale_evidence.py

判定:
  OK→exit 0  ／ 1件以上失敗→exit 1
"""
from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
SCRIPTS_ROOT = HERE.parent.parent
sys.path.insert(0, str(SCRIPTS_ROOT))

spec = importlib.util.spec_from_file_location(
    "check_stale_evidence",
    SCRIPTS_ROOT / "check_stale_evidence.py",
)
mod = importlib.util.module_from_spec(spec)
sys.modules["check_stale_evidence"] = mod  # Python 3.13: dataclass module lookup 対応
spec.loader.exec_module(mod)  # type: ignore[union-attr]


class StaleEvidenceTest(unittest.TestCase):

    TODAY = date(2026, 5, 16)

    def _classify(self, sample_name: str) -> str:
        rec = mod.parse_article(HERE / sample_name)
        return mod.classify(rec, self.TODAY)

    def test_pass_fresh(self):
        self.assertEqual(self._classify("sample_pass_fresh.md"), "OK")

    def test_fail_stale(self):
        self.assertEqual(self._classify("sample_fail_stale.md"), "STALE")

    def test_warn_no_meta(self):
        self.assertEqual(self._classify("sample_warn_no_meta.md"), "WARN")

    def test_due_soon(self):
        self.assertEqual(self._classify("sample_due_soon.md"), "DUE_SOON")

    def test_footer_format(self):
        # 照合日テーブルが無く「*最終確認: YYYY-MM-DD ...*」フッターだけの記事も拾う
        rec = mod.parse_article(HERE / "sample_footer_format.md")
        self.assertEqual(rec.verified_on, date(2026, 3, 1))
        self.assertEqual(mod.classify(rec, self.TODAY), "OK")

    def test_inline_format(self):
        # 箇条書きインライン「- **照合日**: YYYY-MM-DD」形式も拾う（kaishaku/165.md 実例）
        rec = mod.parse_article(HERE / "sample_inline_format.md")
        self.assertEqual(rec.verified_on, date(2026, 3, 1))
        self.assertEqual(mod.classify(rec, self.TODAY), "OK")

    def test_inferred_next_audit(self):
        rec = mod.parse_article(HERE / "sample_inferred.md")
        self.assertIsNotNone(rec.next_audit)
        self.assertTrue(rec.next_audit_inferred)
        # 照合日 2025-10-01 + 365日 (other category) = 2026-10-01 → 2026-05-16 時点で OK
        self.assertEqual(rec.next_audit, date(2026, 10, 1))
        self.assertEqual(mod.classify(rec, self.TODAY), "OK")

    def test_cli_exit_code_with_fail_on_stale(self):
        # tests/ ディレクトリ自体をルートに指定して main() を呼び、stale 1件で exit 1
        argv = [
            "--root", str(HERE),
            "--today", "2026-05-16",
            "--fail-on-stale",
        ]
        # stdout 抑止
        buf = io.StringIO()
        old = sys.stdout
        # main() は sys.stdout を utf-8 reconfigure で上書きしているので、
        # bufferを持つ StringIO 代替として devnull を使う
        try:
            sys.stdout = open(__import__("os").devnull, "w", encoding="utf-8")
            code = mod.main(argv)
        finally:
            sys.stdout.close()
            sys.stdout = old
        self.assertEqual(code, 1, "stale 1件以上で exit 1 を期待")


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(unittest.TestLoader().loadTestsFromTestCase(StaleEvidenceTest))
    sys.exit(0 if result.wasSuccessful() else 1)
