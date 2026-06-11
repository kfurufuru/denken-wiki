#!/usr/bin/env python3
"""U+FFFD（UTF-8 置換文字 �）混入ゲート.

走査対象（既定・引数なし時）:
  - ``docs/**/*.md`` / ``docs/**/*.yml`` / ``docs/**/*.yaml``
  - ``_data/*.yml`` / ``_data/*.yaml``

除外:
  - ``docs/javascripts/`` … vendored ライブラリ（mermaid.min.js が正当な
                            U+FFFD リテラルを含むため。.js は元々対象外だが
                            将来 md/yml が置かれても誤検出しないよう除外）
  - ``docs/assets/``      … 画像等バイナリ

検出（いずれかがあれば exit 1）:
  1. 文字としての U+FFFD（バイト列 EF BF BD）→ file:line:col で列挙
  2. UTF-8 として decode できないバイト列 → file:line と byte offset で列挙

盲目0件ガード（exit 2）:
  既定走査でファイル数が SCAN_FLOOR 未満の場合、「健全な0件」ではなく
  パス構成変更などで走査自体が空転している疑いとして exit 2 で落とす
  （docs/ の md は 240+。CI の無音死モード封じ・PR #70 と同じ思想）。

背景:
  docs/kakomon/by-field.md に初回コミット(700a708)から U+FFFD 12 行が潜伏し、
  問番号セルが壊れた 3 行は全監査スクリプトの正規表現（``R0N問NN`` 等の
  アンカー）にマッチせず不可視だった（PR #74 で修復）。文字化けは
  データ破損に加えて「壊れた行が他ゲートのパターンから外れて監査の
  盲点になる」二次被害を生むため、混入時点（pre-commit / PR CI）で止める。

使い方:
    python scripts/check_mojibake.py              # 既定走査（exit 0/1/2）
    python scripts/check_mojibake.py <path>...    # 指定パスのみ（floor 無効）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FFFD = b"\xef\xbf\xbd"  # U+FFFD の UTF-8 バイト列
EXCLUDE_PREFIXES = ("docs/javascripts/", "docs/assets/")
SCAN_PATTERNS = ("*.md", "*.yml", "*.yaml")
SCAN_FLOOR = 100  # docs/ の md だけで 240+。これ未満は走査が壊れている疑い
SNIPPET_RADIUS = 15  # 検出箇所の前後に表示する文字数


def rel_posix(path: Path) -> str:
    """ROOT 相対の posix 表記（ROOT 外ならそのまま posix）."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def is_excluded(path: Path) -> bool:
    return rel_posix(path).startswith(EXCLUDE_PREFIXES)


def iter_default_targets():
    docs = ROOT / "docs"
    for pattern in SCAN_PATTERNS:
        yield from docs.rglob(pattern)
    data = ROOT / "_data"
    for pattern in SCAN_PATTERNS:
        yield from data.glob(pattern)


def iter_arg_targets(args: list[str]):
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            for pattern in SCAN_PATTERNS:
                yield from p.rglob(pattern)
        else:
            yield p


def snippet_around(line: bytes) -> str:
    """U+FFFD 周辺の文脈を console-safe（FFFD は <FFFD> マーカー化）で返す."""
    text = line.decode("utf-8", "replace")
    i = text.index("�")
    start = max(0, i - SNIPPET_RADIUS)
    end = min(len(text), i + SNIPPET_RADIUS)
    return text[start:end].replace("�", "<FFFD>").strip()


def scan_file(path: Path) -> list[str]:
    rel = rel_posix(path)
    findings: list[str] = []
    data = path.read_bytes()

    # 1. 文字としての U+FFFD（EF BF BD）
    if FFFD in data:
        for lineno, line in enumerate(data.split(b"\n"), 1):
            n = line.count(FFFD)
            if n:
                col = len(line[: line.index(FFFD)].decode("utf-8", "replace")) + 1
                findings.append(
                    f"{rel}:{lineno}: U+FFFD x{n} (col {col}) | {snippet_around(line)}"
                )

    # 2. UTF-8 として不正なバイト列（decode 不能 = 別形態の文字化け）
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as e:
        lineno = data[: e.start].count(b"\n") + 1
        findings.append(
            f"{rel}:{lineno}: invalid UTF-8 byte 0x{data[e.start]:02x}"
            f" at offset {e.start} ({e.reason})"
        )

    return findings


def main() -> int:
    # cp932 コンソールでも UnicodeEncodeError で自壊しない（自壊=無音化の防止）
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")

    args = sys.argv[1:]
    if args:
        targets = sorted(set(iter_arg_targets(args)))
        floor = 0  # 明示指定時は floor 無効
    else:
        targets = sorted(set(t for t in iter_default_targets() if not is_excluded(t)))
        floor = SCAN_FLOOR

    findings: list[str] = []
    for path in targets:
        findings.extend(scan_file(path))

    # サマリ sentinel: 「盲目0件」と「健全0件」を区別できるよう必ず件数を出す
    print(f"[check_mojibake] scanned {len(targets)} files: {len(findings)} findings")

    if not args and len(targets) < floor:
        print(
            f"[ERROR] scanned only {len(targets)} files (< floor {floor})."
            " docs/ のパス構成が変わって走査が空転している疑いがあります。",
            file=sys.stderr,
        )
        return 2

    if findings:
        print("[ERROR] U+FFFD 置換文字 or 不正な UTF-8 バイト列を検出しました:")
        for f in findings:
            print(f"  {f}")
        print()
        print("  → 化け前の文字を前後の文脈・git 履歴から特定して復元してください。")
        print("    位置特定: git grep -n \"$(printf '\\xef\\xbf\\xbd')\" -- docs/ _data/")
        print("    背景: PR #74（by-field.md 問番号セル破損の盲点化）")
        return 1

    print("OK check_mojibake: U+FFFD・不正バイト列なし")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
