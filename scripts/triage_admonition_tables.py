#!/usr/bin/env python3
"""admonition 内 table を「行数」「種別」で重要度分類する精緻 triage。

分類:
  CRITICAL: 行数>=8 で admonition のメインコンテンツ（外出し推奨）
  WARNING : 行数>=6 で admonition のメインコンテンツ（外出し検討）
  ACCEPTABLE: ≤5行・解答表（??? success/question）・小さな比較表（許容）

Usage: python scripts/triage_admonition_tables.py docs/articles/
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ADM_OPEN = re.compile(r"^(\s*)(!!!|\?\?\?)\s+(\w+)(?:\s+\"([^\"]*)\")?")


def scan_file(path):
    text = path.read_text(encoding="utf-8")
    lines = text.split("\n")
    issues = []

    in_adm = False
    adm_start_line = 0
    adm_indent = 0
    adm_kind = ""
    adm_title = ""
    max_table_rows = 0   # adm 内の **単一の最大テーブル** の行数
    cur_table_rows = 0   # 連続中のテーブル行数
    non_table_lines_in_adm = 0

    def flush():
        nonlocal in_adm, max_table_rows, cur_table_rows, non_table_lines_in_adm
        # 最後の連続テーブルを記録
        if cur_table_rows > max_table_rows:
            max_table_rows = cur_table_rows
        if in_adm and max_table_rows > 0:
            is_answer = adm_kind in ("success", "question")
            if is_answer:
                severity = "ACCEPTABLE"
            elif max_table_rows >= 10:
                severity = "CRITICAL"
            elif max_table_rows >= 7:
                severity = "WARNING"
            else:
                severity = "ACCEPTABLE"
            if severity in ("CRITICAL", "WARNING"):
                issues.append((adm_start_line, severity, adm_kind, adm_title or "(no title)", max_table_rows))
        in_adm = False
        max_table_rows = 0
        cur_table_rows = 0
        non_table_lines_in_adm = 0

    for i, line in enumerate(lines, 1):
        m = ADM_OPEN.match(line)
        if m:
            flush()
            in_adm = True
            adm_indent = len(m.group(1))
            adm_kind = m.group(3)
            adm_title = m.group(4) or ""
            adm_start_line = i
            continue
        if in_adm:
            stripped = line.rstrip()
            if not stripped:
                continue
            # admonition 終了判定: インデント不足
            min_indent = adm_indent + 4
            actual_indent = len(line) - len(line.lstrip())
            if line.strip() and actual_indent < min_indent:
                flush()
                continue
            # admonition 内
            content = line[min_indent:] if len(line) > min_indent else ""
            if content.startswith("|") and content.rstrip().endswith("|"):
                if not (content.startswith("|---") or content.startswith("|:")):
                    cur_table_rows += 1
            else:
                # テーブル中断 → 最大値更新
                if cur_table_rows > max_table_rows:
                    max_table_rows = cur_table_rows
                cur_table_rows = 0
                if content.strip():
                    non_table_lines_in_adm += 1
    flush()

    return issues


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/articles/")
    files = sorted(root.rglob("*.md"))

    rows = []
    for f in files:
        if f.name == "index.md":
            continue
        issues = scan_file(f)
        if not issues:
            continue
        try:
            rel = f.relative_to(Path.cwd())
        except ValueError:
            rel = f
        for line, sev, kind, title, n in issues:
            rows.append((sev, str(rel), line, kind, title, n))

    # severity でソート
    sev_order = {"CRITICAL": 0, "WARNING": 1, "ACCEPTABLE": 2}
    rows.sort(key=lambda r: (sev_order[r[0]], r[1], r[2]))

    print(f"{'重要度':<10s}\t{'ファイル:行':<55s}\t{'種別':<10s}\t行数\tタイトル")
    print("-" * 130)
    for sev, rel, line, kind, title, n in rows:
        print(f"{sev:<10s}\t{rel}:{line:<5d}\t{kind:<10s}\t{n}行\t{title[:40]}")

    crit = sum(1 for r in rows if r[0] == "CRITICAL")
    warn = sum(1 for r in rows if r[0] == "WARNING")
    print(f"\nCRITICAL: {crit}件 / WARNING: {warn}件 / 合計: {len(rows)}件")


if __name__ == "__main__":
    main()
