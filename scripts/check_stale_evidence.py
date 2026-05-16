#!/usr/bin/env python3
"""
照合日（verified_on）からの経過監視と stale 記事検出。

監査周期（デフォルト）:
  - kaishaku/  : 180日（解釈・告示は改正頻度高）
  - kijun/     : 365日（省令本文は年単位の改正）
  - jigyoho/   : 365日
  - other/     : 365日

next_audit 行が記事メタに明示されていればそちらを優先する。
メタ未設定の記事は WARN として一覧化する。

usage:
  python scripts/check_stale_evidence.py
  python scripts/check_stale_evidence.py --fail-on-stale   # CI 用（stale 検出時 exit 1）
  python scripts/check_stale_evidence.py --include-warn    # メタ未設定もstale扱いで集計
  python scripts/check_stale_evidence.py --today 2026-05-16  # テスト用に基準日固定

メタ表記（denken-wiki 標準）:
  | **照合日** | 2026-05-02（補足コメント） |
  | **次回監査** | 2026-11-02 |          ← 任意

依存: 標準ライブラリのみ。
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).parent.parent
ARTICLES_DIR = ROOT / "docs" / "articles"

PERIOD_DAYS = {
    "kaishaku": 180,
    "kijun": 365,
    "jigyoho": 365,
    "other": 365,
}
DEFAULT_PERIOD = 365

VERIFIED_RE = re.compile(
    r"\|\s*\*\*照合日\*\*\s*\|\s*(\d{4}-\d{2}-\d{2})"
)
NEXT_AUDIT_RE = re.compile(
    r"\|\s*\*\*次回監査\*\*\s*\|\s*(\d{4}-\d{2}-\d{2})"
)


@dataclass
class Record:
    path: Path
    verified_on: date | None
    next_audit: date | None
    next_audit_inferred: bool
    category: str

    @property
    def relative(self) -> str:
        return str(self.path.relative_to(ROOT)).replace("\\", "/")


def parse_date(s: str) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_article(path: Path) -> Record:
    text = path.read_text(encoding="utf-8")
    v = VERIFIED_RE.search(text)
    n = NEXT_AUDIT_RE.search(text)
    verified = parse_date(v.group(1)) if v else None
    next_audit = parse_date(n.group(1)) if n else None
    inferred = False
    category = path.parent.name
    period = PERIOD_DAYS.get(category, DEFAULT_PERIOD)
    if next_audit is None and verified is not None:
        next_audit = verified + timedelta(days=period)
        inferred = True
    return Record(
        path=path,
        verified_on=verified,
        next_audit=next_audit,
        next_audit_inferred=inferred,
        category=category,
    )


def classify(record: Record, today: date) -> str:
    if record.verified_on is None:
        return "WARN"  # メタ未設定
    if record.next_audit is None:
        return "WARN"
    if record.next_audit < today:
        return "STALE"
    days = (record.next_audit - today).days
    if days <= 30:
        return "DUE_SOON"
    return "OK"


def iter_articles(target_root: Path) -> list[Path]:
    if not target_root.exists():
        return []
    out = []
    for p in sorted(target_root.rglob("*.md")):
        if p.name == "index.md":
            continue
        out.append(p)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fail-on-stale", action="store_true",
                        help="STALE記事1件以上で exit 1")
    parser.add_argument("--include-warn", action="store_true",
                        help="WARN（メタ未設定）も失敗扱い")
    parser.add_argument("--today", default=None,
                        help="基準日固定（テスト用・YYYY-MM-DD）")
    parser.add_argument("--root", default=str(ARTICLES_DIR),
                        help="スキャン対象ルート（デフォルト docs/articles）")
    args = parser.parse_args(argv)

    today = parse_date(args.today) if args.today else date.today()
    if today is None:
        print(f"ERROR: invalid --today: {args.today}", file=sys.stderr)
        return 2

    target_root = Path(args.root)
    paths = iter_articles(target_root)
    if not paths:
        print(f"WARN: 対象記事が見つかりません: {target_root}")
        return 0

    counts = {"OK": 0, "DUE_SOON": 0, "STALE": 0, "WARN": 0}
    rows: list[tuple[str, Record, str]] = []
    for p in paths:
        rec = parse_article(p)
        verdict = classify(rec, today)
        counts[verdict] += 1
        rows.append((verdict, rec, _format_row(rec, verdict, today)))

    # 表示順: STALE → WARN → DUE_SOON → OK
    order = {"STALE": 0, "WARN": 1, "DUE_SOON": 2, "OK": 3}
    rows.sort(key=lambda r: (order[r[0]], r[1].relative))

    print(f"基準日: {today.isoformat()}  対象: {target_root}")
    print(f"{'verdict':<9} | {'category':<8} | {'verified':<12} | {'next_audit':<12} | path")
    print("-" * 100)
    for _, _, formatted in rows:
        print(formatted)
    print()
    print(f"[SUMMARY] OK: {counts['OK']}  DUE_SOON: {counts['DUE_SOON']}  STALE: {counts['STALE']}  WARN: {counts['WARN']}")

    fail = counts["STALE"] > 0 and args.fail_on_stale
    if args.include_warn and counts["WARN"] > 0:
        fail = True
    return 1 if fail else 0


def _format_row(rec: Record, verdict: str, today: date) -> str:
    cat = rec.category
    v = rec.verified_on.isoformat() if rec.verified_on else "(none)"
    if rec.next_audit:
        suffix = "*" if rec.next_audit_inferred else " "
        n = rec.next_audit.isoformat() + suffix
    else:
        n = "(none)  "
    return f"{verdict:<9} | {cat:<8} | {v:<12} | {n:<12} | {rec.relative}"


if __name__ == "__main__":
    sys.exit(main())
