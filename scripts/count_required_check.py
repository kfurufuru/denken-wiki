#!/usr/bin/env python3
"""
[要確認]フラグ集計レポート

denken-wiki 全条文ファイルから `[要確認]` フラグを抽出し、
- ファイル別件数
- 内容カテゴリ（条文原文 / 数値 / 条番号 / リンク先 / その他）
- 全体サマリ
を出力する。

使い方:
  python scripts/count_required_check.py

CI連携時:
  python scripts/count_required_check.py --threshold 30
  → 件数が threshold を超えたら exit code 1
"""
import re
import sys
import io
import argparse
from pathlib import Path
from collections import defaultdict

# Windows コンソール対策
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# カテゴリ判定キーワード
CATEGORIES = {
    "条文原文": ["e-Gov公式の本文", "e-Gov", "eGov", "本文をここに転記"],
    "条番号": ["条番号", "§", "解釈第", "省令第", "kakomon.yml", "kaishaku"],
    "数値": ["数値", "Ω", "kV", "%", "MΩ", "回/14年"],
    "リンク先未作成": ["は未作成", "未作成", "作成予定"],
    "地域別規定": ["地域別", "北日本", "凍結"],
}


def categorize(line: str) -> str:
    """[要確認]フラグの内容を5カテゴリに分類"""
    for cat, keywords in CATEGORIES.items():
        if any(kw in line for kw in keywords):
            return cat
    return "その他"


def scan(root: Path):
    """全 .md ファイルから [要確認] を抽出"""
    results = defaultdict(list)  # file_path -> [(line_no, line, category), ...]
    total = 0
    for md_path in root.rglob("*.md"):
        if "site/" in str(md_path) or ".claude/" in str(md_path):
            continue
        try:
            with open(md_path, encoding="utf-8") as f:
                for i, line in enumerate(f, 1):
                    if "[要確認" in line:
                        cat = categorize(line)
                        results[md_path].append((i, line.strip(), cat))
                        total += 1
        except Exception as e:
            print(f"WARN: {md_path}: {e}", file=sys.stderr)
    return results, total


def report(results, total):
    """レポート出力"""
    print(f"# [要確認]フラグ集計レポート")
    print(f"\n**全件数: {total}件**\n")

    # カテゴリ別集計
    cat_count = defaultdict(int)
    for entries in results.values():
        for _, _, cat in entries:
            cat_count[cat] += 1

    print("## カテゴリ別内訳\n")
    print("| カテゴリ | 件数 | 自動解消可否 |")
    print("|---------|------|------------|")
    auto_ok = {"リンク先未作成"}  # 放置可
    for cat in sorted(cat_count.keys(), key=lambda k: -cat_count[k]):
        marker = "✅放置可" if cat in auto_ok else "❌人手必須"
        print(f"| {cat} | {cat_count[cat]} | {marker} |")

    # ファイル別トップ
    print("\n## ファイル別件数（多い順 トップ10）\n")
    sorted_files = sorted(results.items(), key=lambda kv: -len(kv[1]))[:10]
    print("| ファイル | 件数 |")
    print("|---------|------|")
    for path, entries in sorted_files:
        rel = path.relative_to(path.parents[2]) if len(path.parents) >= 3 else path.name
        print(f"| {rel} | {len(entries)} |")


def export_tasks(results, out_path: Path):
    """人手必須カテゴリのみ抽出して朝のタスクリスト形式で出力"""
    AUTO_OK = {"リンク先未作成"}
    by_category = defaultdict(list)  # category -> [(file, line_no, line)]
    for path, entries in results.items():
        for line_no, line, cat in entries:
            if cat in AUTO_OK:
                continue
            by_category[cat].append((path, line_no, line))

    total_manual = sum(len(v) for v in by_category.values())

    lines = [
        "---",
        "date: 2026-05-03",
        "type: morning-tasks",
        "title: denken-wiki [要確認]フラグ朝タスクリスト",
        "---",
        "",
        "# denken-wiki [要確認]フラグ朝タスクリスト",
        "",
        f"**人手対応必須: {total_manual}件**（リンク先未作成カテゴリは除外）",
        "",
        "出典: `python scripts/count_required_check.py` 実行結果",
        "",
        "## 優先順位",
        "",
        "1. **条文原文**（eGov公式照合）— wiki信頼性の核心",
        "2. **条番号**（2013年改正マッピング）— wiki誤誘導防止",
        "3. **数値**（地域別規定含む）— 試験対策の正確性",
        "4. **その他** — 個別判断",
        "",
    ]

    # カテゴリ別に出力（優先順位順）
    priority = ["条文原文", "条番号", "数値", "地域別規定", "その他"]
    for cat in priority:
        if cat not in by_category:
            continue
        lines.append(f"## {cat}（{len(by_category[cat])}件）")
        lines.append("")
        for path, line_no, line in sorted(by_category[cat]):
            rel = path.relative_to(path.parents[2]) if len(path.parents) >= 3 else path.name
            short = line[:80] + ("..." if len(line) > 80 else "")
            lines.append(f"- [ ] `{rel}:{line_no}` — {short}")
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✅ {total_manual}件の朝タスクを {out_path} に出力", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="docs/articles", help="走査ルート")
    ap.add_argument("--threshold", type=int, default=None,
                    help="件数がこの値を超えたら exit 1")
    ap.add_argument("--export", type=str, default=None,
                    help="人手必須項目をMarkdownタスクリストとして出力するパス")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"ERROR: {root} not found", file=sys.stderr)
        sys.exit(2)

    results, total = scan(root)
    report(results, total)

    if args.export:
        export_tasks(results, Path(args.export))

    if args.threshold is not None and total > args.threshold:
        print(f"\n❌ {total}件 > 閾値{args.threshold}件", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
