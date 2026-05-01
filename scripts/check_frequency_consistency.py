#!/usr/bin/env python3
"""
出題頻度の矛盾検知スクリプト。

検証対象:
  - 各条文 md の `!!! abstract "📊 試験対策メタ"` の自動値（kakomon.yml集計）
  - 同じファイルの本文手書き「**出題頻度**: N回/14年 ★...」

矛盾パターン:
  - メタが「過去14年で出題なし」なのに本文に「N回/14年」（N≧1）が書かれている
  - メタの「N回出題」と本文の「M回/14年」が乖離（|N-M| >= 2）
  - 本文に手書き★評価があるが kakomon.yml では出題0件

使い方:
  python scripts/check_frequency_consistency.py        # 矛盾を一覧表示
  python scripts/check_frequency_consistency.py --fix  # 本文の手書き行を削除（オプション）
"""
from __future__ import annotations
import argparse
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES = ROOT / "docs" / "articles"

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

META_RE = re.compile(
    r'!!! abstract "📊 試験対策メタ".*?\*\*出題頻度\*\*:\s*([^（]+)（([^）]+)）',
    re.S,
)
HANDWRITTEN_RE = re.compile(r"\*\*出題頻度\*\*:\s*(\d+)回/14年(?:\s*([★☆]+))?")
NO_OUTPUT_RE = re.compile(r"過去14年で(?:省令|解釈|事業法|工事士法|電気用品安全法|報告規則)?[§\s\d]*直接の?出題なし|過去14年で出題なし")
COUNT_RE = re.compile(r"過去14年で\s*(\d+)\s*回出題")


def check_file(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    issues: list[tuple[str, str]] = []

    meta_match = META_RE.search(text)
    if not meta_match:
        return issues  # メタなし＝対象外

    meta_freq = meta_match.group(1).strip()
    meta_phrase = meta_match.group(2).strip()

    auto_count = 0
    if NO_OUTPUT_RE.search(meta_phrase):
        auto_count = 0
    else:
        m = COUNT_RE.search(meta_phrase)
        if m:
            auto_count = int(m.group(1))

    hand_match = HANDWRITTEN_RE.search(text)
    if not hand_match:
        return issues  # 手書きなし＝矛盾なし

    hand_count = int(hand_match.group(1))
    hand_stars = hand_match.group(2) or ""

    if auto_count == 0 and hand_count >= 1:
        issues.append((
            "ZERO_VS_HANDWRITTEN",
            f"メタ='出題なし' / 手書き='{hand_count}回/14年 {hand_stars}' → 矛盾",
        ))
    elif abs(auto_count - hand_count) >= 2:
        issues.append((
            "DIVERGENCE",
            f"メタ={auto_count}回 / 手書き={hand_count}回 → 乖離≧2",
        ))

    return issues


def remove_handwritten(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    new_text = HANDWRITTEN_RE.sub("", text)
    # 残った空行を整理
    new_text = re.sub(r"\n{3,}", "\n\n", new_text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="手書き出題頻度行を削除する")
    args = parser.parse_args()

    files = []
    for sub in ("kijun", "kaishaku", "jigyoho", "other"):
        for f in sorted((ARTICLES / sub).glob("*.md")):
            if f.name == "index.md":
                continue
            files.append(f)

    total_issues = 0
    fixed_files = 0

    for f in files:
        issues = check_file(f)
        if issues:
            rel = f.relative_to(ROOT).as_posix()
            for kind, msg in issues:
                print(f"[{kind}] {rel}: {msg}")
                total_issues += 1
            if args.fix:
                if remove_handwritten(f):
                    fixed_files += 1
                    print(f"        → 手書き行を削除: {rel}")

    print(f"\n[INFO] 検査ファイル数: {len(files)}")
    print(f"[INFO] 矛盾検出: {total_issues}件")
    if args.fix:
        print(f"[INFO] 自動修正: {fixed_files}ファイル")
    return 1 if total_issues > 0 and not args.fix else 0


if __name__ == "__main__":
    sys.exit(main())
