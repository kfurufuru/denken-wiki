#!/usr/bin/env python3
"""kakomon.yml デュアルファイル同期ガード.

このリポジトリには過去問DBが 2 箇所にある:

  - ``_data/kakomon.yml``       … **正本（source of truth）**。
                                   mkdocs-macros (mkdocs.yml の include_yaml)・
                                   scripts/precommit_kakomon.py・compute_frequency.py が読む。
  - ``docs/_data/kakomon.yml``  … 上記の同期コピー。``exclude_docs`` でビルド対象外。
                                   audit_kakomon_article.py が両方を照合する。

両者は **バイト単位で一致** していなければならない。過去に片方だけ編集されて
静かにズレる事故（PR #35 で 7 件同期）が起きたため、commit / CI 時に機械検出する。

使い方:
    python scripts/check_kakomon_dual_sync.py          # 照合のみ（ズレたら exit 1）
    python scripts/check_kakomon_dual_sync.py --fix    # 正本 -> コピー へ再同期

pre-commit / CI への組み込みは PR 説明・.github/workflows/quality-check.yml 参照。
"""
import difflib
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "_data" / "kakomon.yml"          # 正本（ビルドが読む）
COPY = ROOT / "docs" / "_data" / "kakomon.yml"      # 同期コピー


def main() -> int:
    fix = "--fix" in sys.argv[1:]

    for p in (CANONICAL, COPY):
        if not p.exists():
            print(f"[ERROR] not found: {p}", file=sys.stderr)
            return 2

    a = CANONICAL.read_bytes()
    b = COPY.read_bytes()

    if a == b:
        print("OK check_kakomon_dual_sync: _data/ と docs/_data/ は一致しています")
        return 0

    if fix:
        shutil.copyfile(CANONICAL, COPY)
        print(f"FIXED: {CANONICAL.relative_to(ROOT)} -> {COPY.relative_to(ROOT)} に再同期しました")
        return 0

    # 差分を見やすく提示
    diff = difflib.unified_diff(
        a.decode("utf-8", "replace").splitlines(),
        b.decode("utf-8", "replace").splitlines(),
        fromfile=str(CANONICAL.relative_to(ROOT)),
        tofile=str(COPY.relative_to(ROOT)),
        lineterm="",
        n=1,
    )
    shown = 0
    print("[ERROR] kakomon.yml の 2 ファイルがズレています（正本=_data/, コピー=docs/_data/）:")
    for line in diff:
        print("  " + line)
        shown += 1
        if shown >= 40:
            print("  ... (以降省略)")
            break
    print("\n  修正: python scripts/check_kakomon_dual_sync.py --fix")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
