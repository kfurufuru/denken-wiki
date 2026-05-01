#!/usr/bin/env python3
"""wiki_check.py — denken-wiki Markdown 品質チェッカ

検出項目:
  [§]  §X記号残存（CLAUDE.mdで明示禁止、「第X条」推奨）
  [簡]  簡体字混入（風→风 のような誤字）
  [?]  [要確認] プレースホルダー残存

Usage:
  python wiki_check.py                       # docs/ 全体（検出のみ）
  python wiki_check.py docs/articles/jigyoho # ディレクトリ指定
  python wiki_check.py docs/articles/jigyoho/38.md  # 単ファイル
  python wiki_check.py --fix-section --dry-run     # § 修正 dry-run
  python wiki_check.py --fix-section                # § 自動修正

Exit code: 0=OK, 1=issues found
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SECTION_PATTERN = re.compile(r"§(\d+)")
PLACEHOLDER_PATTERN = re.compile(r"\[要確認\]")

# 簡体字 → 日本字（よく混入する文字に限定）
SIMP_TO_JP = {
    "风": "風", "电": "電", "规": "規", "务": "務", "约": "約",
    "级": "級", "单": "単", "时": "時", "间": "間", "问": "問",
    "题": "題", "应": "応", "计": "計", "设": "設", "业": "業",
    "产": "産", "让": "譲", "见": "見", "长": "長", "经": "経",
    "联": "聯", "节": "節", "给": "給", "实": "実", "边": "辺",
    "选": "選", "远": "遠", "进": "進", "还": "還",
}

EXCLUDE_DIRS = {"_data", "site", "overrides", "includes", ".git"}


def check_file(path: Path):
    issues = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [(path, 0, "?", f"読込失敗: {e}")]

    for lineno, line in enumerate(text.splitlines(), 1):
        for m in SECTION_PATTERN.finditer(line):
            issues.append((path, lineno, "§", f"§{m.group(1)} → 「第{m.group(1)}条」を推奨"))
        for ch in line:
            if ch in SIMP_TO_JP:
                issues.append((path, lineno, "簡", f"{ch} → 「{SIMP_TO_JP[ch]}」を推奨"))
        if PLACEHOLDER_PATTERN.search(line):
            issues.append((path, lineno, "?", "[要確認] が残存"))
    return issues


def collect_files(target: Path):
    if target.is_file():
        return [target]
    files = []
    for md in target.rglob("*.md"):
        if any(d in md.parts for d in EXCLUDE_DIRS):
            continue
        files.append(md)
    return sorted(files)


def fix_section_in_file(path: Path, dry_run: bool):
    """§\\d+ → 第\\d+条 を自動置換。戻り値: (変更件数, ファイル変更されたか)"""
    text = path.read_text(encoding="utf-8")
    new_text, n = SECTION_PATTERN.subn(r"第\1条", text)
    if n == 0:
        return 0, False
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return n, True


def main():
    parser = argparse.ArgumentParser(description="denken-wiki Markdown 品質チェッカ")
    parser.add_argument("target", nargs="?", default="docs", help="対象パス（省略時 docs/）")
    parser.add_argument("--fix-section", action="store_true", help="§記号を「第X条」に自動置換")
    parser.add_argument("--dry-run", action="store_true", help="--fix-section と併用で変更内容のみ表示")
    args = parser.parse_args()

    target = Path(args.target)
    if not target.exists():
        print(f"対象が存在しない: {target}", file=sys.stderr)
        sys.exit(2)

    files = collect_files(target)

    if args.fix_section:
        total_replaced = 0
        modified_files = []
        for f in files:
            n, modified = fix_section_in_file(f, args.dry_run)
            if n > 0:
                try:
                    rel = f.relative_to(Path.cwd())
                except ValueError:
                    rel = f
                print(f"[FIX] {rel}: {n} 箇所{'（dry-run）' if args.dry_run else '修正'}")
                total_replaced += n
                if modified:
                    modified_files.append(f)
        print()
        verb = "would replace" if args.dry_run else "replaced"
        print(f"{verb}: {total_replaced} § symbols across {len(modified_files)} files")
        sys.exit(0)

    all_issues = []
    for f in files:
        all_issues.extend(check_file(f))

    counts = {"§": 0, "簡": 0, "?": 0}
    affected_files = set()
    for path, lineno, kind, msg in all_issues:
        try:
            rel = path.relative_to(Path.cwd())
        except ValueError:
            rel = path
        print(f"[{kind}] {rel}:{lineno} {msg}")
        if kind in counts:
            counts[kind] += 1
        affected_files.add(path)

    print()
    print(
        f"Found: {counts['§']} § symbols, {counts['簡']} simplified chars, "
        f"{counts['?']} placeholders"
    )
    print(f"across {len(affected_files)}/{len(files)} files")
    sys.exit(1 if all_issues else 0)


if __name__ == "__main__":
    main()
