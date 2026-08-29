#!/usr/bin/env python3
"""照合宣言の裏付けゲート (check_verification_claims.py)

「一次照合済」「逐語照合」「照合日 …」という**宣言**が、機械で確かめられる
**条文原文ブロック**に裏打ちされているかを見る。

制定事案: 2026-08-28 の全数監査。
`kijun/11.md`（B種の 50/Ig）・`kijun/23.md`（柵1.8m）・`kijun/32.md`（安全率1.5）は
いずれも監修ログに「解釈第17/38/59条と照合済・公式値と一致」と書いてあったが、
**その数値は条文に存在しなかった**。宣言はコストゼロで書ける。
宣言 × 実際の条文の機械突合が無いと、監修ログは品質の証拠にならない。

本ゲートは宣言の**内容**が正しいかは見ない（それは check_law_verbatim.py の仕事）。
見るのは **「照合したと書いてあるページに、機械が照合できる条文原文があるか」** だけ。
無ければ、その宣言は誰にも検証できない＝品質の根拠として使えない。

検出:
  UNBACKED   照合宣言があるのに、逐語照合できる条文原文ブロックが1件も無い
  EMPTY_GENBUN
             「条文原文」という名前の節があるのに、その中に blockquote が1件も無い
             （例: kaishaku/17.md の「2. 条文原文（17-1表・17-3表の要旨）」は
               要旨と学習用再構成表だけで、原文が1行も無い）

運用:
  現状分を ALLOWLIST に凍結し、**新規発生だけをブロック**する ratchet
  （wiki_check.py の PLACEHOLDER_ALLOWLIST と同じ運用）。
  減らすときは、そのページに条文原文ブロックを起こして allowlist から外す。
  外すと check_law_verbatim.py の照合対象にもなるので、二重に効く。

Usage:
    python scripts/check_verification_claims.py
    python scripts/check_verification_claims.py --list-allowlist
    python scripts/check_verification_claims.py --no-allowlist   # 全件（債務の棚卸し）
    python scripts/check_verification_claims.py --self-test

Exit codes:
    0  allowlist 外の findings 0件
    1  findings 1件以上
    2  依存モジュールが読めない
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def _load_verbatim():
    """check_law_verbatim.py を読み込んで抽出ロジックを共有する.

    条文原文ブロックの切り出しは1箇所に置く（別実装を持つと、片方だけ直して
    もう片方が盲点を持ち続ける）。
    """
    path = ROOT / "scripts" / "check_law_verbatim.py"
    if not path.exists():
        print(f"ERROR: {path} がありません", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("check_law_verbatim", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


CLAIM = re.compile(r"一次照合|逐語照合|原典照合|照合済|照合日|一次ソース照合")
GENBUN_HEAD = re.compile(r"^#{1,6}\s*.*条文原文")

# 現状の債務を凍結する ratchet。新規発生だけをブロックする。
# 減らすときは「そのページに条文原文ブロックを起こして1行ずつ原典と照合する」こと。
ALLOWLIST: set[str] = {
    "docs/articles/other/jiko-4.md",
    "docs/articles/other/jiko-5.md",
    "docs/articles/other/koji-shi-3.md",
    "docs/articles/other/koji-shi-5.md",
    "docs/articles/other/pse-2.md",
    "docs/articles/other/pse-27.md",
    "docs/articles/other/pse-28.md",
}


class Finding:
    def __init__(self, kind: str, rel: str, detail: str):
        self.kind, self.rel, self.detail = kind, rel, detail

    def render(self) -> str:
        return f"[{self.kind}] {self.rel}\n        {self.detail}"


def scan(paths: list[Path], verbatim) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        quotes = verbatim.genbun_quotes(path)
        has_genbun_head = any(
            GENBUN_HEAD.match(l.strip()) for l in text.splitlines()
        )
        if CLAIM.search(text) and not quotes:
            findings.append(
                Finding(
                    "UNBACKED", rel,
                    "照合したと書いてあるが、機械が逐語照合できる条文原文ブロックが1件も無い"
                    " — この宣言は誰にも検証できない",
                )
            )
        elif has_genbun_head and not quotes:
            findings.append(
                Finding(
                    "EMPTY_GENBUN", rel,
                    "「条文原文」という名前の節があるのに、その中に引用（blockquote）が無い",
                )
            )
    return findings


def collect(paths: list[str]) -> list[Path]:
    if not paths:
        return sorted(
            p
            for g in ("kijun", "jigyoho", "kaishaku", "other")
            for p in (ROOT / "docs" / "articles" / g).glob("*.md")
            if p.stem != "index"
        )
    out: list[Path] = []
    for p in paths:
        q = Path(p)
        if not q.is_absolute():
            q = ROOT / p
        if q.is_dir():
            out.extend(sorted(q.rglob("*.md")))
        elif q.exists():
            out.append(q)
    return out


def self_test(verbatim) -> int:
    ok = True
    hit = bool(CLAIM.search("2026-05-10 一次照合済"))
    print(f"  [{'PASS' if hit else 'FAIL'}] 宣言検出: 「一次照合済」")
    ok &= hit
    hit = bool(CLAIM.search("| **照合日** | 2026-05-05（kakomon.yml 照合）|"))
    print(f"  [{'PASS' if hit else 'FAIL'}] 宣言検出: 「照合日」")
    ok &= hit
    hit = not CLAIM.search("本条の要点は接地抵抗値である。")
    print(f"  [{'PASS' if hit else 'FAIL'}] 陰性対照: 宣言の無い文で発火しない")
    ok &= hit
    hit = bool(GENBUN_HEAD.match("## 2. 条文原文（17-1表・17-3表の要旨）"))
    print(f"  [{'PASS' if hit else 'FAIL'}] 節検出: 「条文原文（…要旨）」")
    ok &= hit
    hit = not GENBUN_HEAD.match("## 3. 原文解析（ブロック分解）")
    print(f"  [{'PASS' if hit else 'FAIL'}] 陰性対照: 「原文解析」を条文原文節としない")
    ok &= hit
    # 抽出ロジックの共有先が生きていること（import 事故の検出）
    hit = callable(getattr(verbatim, "genbun_quotes", None))
    print(f"  [{'PASS' if hit else 'FAIL'}] check_law_verbatim.genbun_quotes を共有できている")
    ok &= hit
    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--list-allowlist", action="store_true")
    ap.add_argument("--no-allowlist", action="store_true", help="allowlist を無視して全件表示")
    args = ap.parse_args()

    verbatim = _load_verbatim()
    if args.self_test:
        return self_test(verbatim)
    if args.list_allowlist:
        for k in sorted(ALLOWLIST):
            print(k)
        print(f"-- allowlist {len(ALLOWLIST)}件")
        return 0

    targets = collect(args.paths)
    findings = scan(targets, verbatim)
    shown = [f for f in findings if args.no_allowlist or f.rel not in ALLOWLIST]
    for f in shown:
        print(f.render())
    allowed = len(findings) - len(shown)
    print(
        f"\ncheck_verification_claims: {len(shown)}件"
        f" — {len(targets)}ファイルを検査"
        + (f"・allowlist {allowed}件（債務）" if allowed else "")
    )
    return 1 if shown else 0


if __name__ == "__main__":
    sys.exit(main())
