"""法規記事 (docs/articles/{kijun,kaishaku,jigyoho}/) の新規追加に対し、
メタテーブルに「典拠（一次ソース）」「照合日」行が含まれているかを検査する pre-commit フック.

設計思想:
- 新規追加 (git diff --diff-filter=A) のみチェック → 既存記事の部分編集は素通し
- 一次ソース照合の証跡が無い記事の公開を機械的に防ぐ
- denken-page-creation.md Step6 の補助（ユーザー先見せ後の本文段階で漏れを救う）

Exit codes:
    0  問題なし、または対象外
    1  必須行が不足 → commit 拒否
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
ARTICLE_DIRS = (
    "docs/articles/kijun/",
    "docs/articles/kaishaku/",
    "docs/articles/jigyoho/",
)

# 必須キーワード（いずれか1つでも含まれていれば OK の OR 条件）
EVIDENCE_KEYWORDS = ("**典拠（一次ソース）**", "**典拠**", "| **典拠**", "| **典拠（一次ソース）**")
DATE_KEYWORDS = ("**照合日**", "| **照合日**")


def main() -> int:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=A"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except FileNotFoundError:
        return 0

    if result.returncode != 0:
        return 0

    new_files = [f for f in result.stdout.strip().split("\n") if f]
    if not new_files:
        return 0

    errors: list[str] = []

    for f in new_files:
        # index.md は対象外（一覧ページ）
        if f.endswith("/index.md"):
            continue
        if not any(f.startswith(d) for d in ARTICLE_DIRS):
            continue
        if not f.endswith(".md"):
            continue

        path = ROOT / f
        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8")

        if not any(kw in content for kw in EVIDENCE_KEYWORDS):
            errors.append(f"{f}: メタテーブルに「典拠（一次ソース）」行がありません")
        if not any(kw in content for kw in DATE_KEYWORDS):
            errors.append(f"{f}: メタテーブルに「照合日」行がありません")

    if errors:
        print("[precommit_evidence_check] 法規記事に必須メタ行が不足:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print(
            "\n対応: メタテーブルに以下の行を追加してください（v2.3 ゴールド準拠）:",
            file=sys.stderr,
        )
        print("  | **典拠（一次ソース）** | <出典名・URL> |", file=sys.stderr)
        print("  | **照合日** | YYYY-MM-DD（<検証内容>） |", file=sys.stderr)
        print(
            "\n参考テンプレ: docs/articles/kijun/58.md (v2.3 ゴールドスタンダード)",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
