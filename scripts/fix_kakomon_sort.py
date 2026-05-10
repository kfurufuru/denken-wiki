#!/usr/bin/env python3
"""過去問実績セクションのテーブル行を「新しい→古い順」に並べ替える。

Usage: python scripts/fix_kakomon_sort.py <file1.md> [<file2.md> ...]
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

YEAR_ORDER = {}
for i, y in enumerate([
    "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20",
    "H21", "H22", "H23", "H24", "H25", "H26", "H27", "H28", "H29", "H30",
    "R01", "R02", "R03", "R04下", "R04上", "R04",
    "R05下", "R05上", "R06下", "R06上", "R07下", "R07上",
]):
    YEAR_ORDER[y] = i


def year_sort_key(row_first_cell):
    """テーブル行の最初のセルから年度を抽出してソートキーを返す（大きいほど新しい）"""
    s = row_first_cell.strip("*").strip()
    if s in YEAR_ORDER:
        return YEAR_ORDER[s]
    return -1  # 不明は古い扱い


def reverse_kakomon_table(text):
    """過去問実績セクション内の最初のテーブル行を逆順にする"""
    # セクション特定
    m = re.search(r"(##\s*\d+\.\s*過去問実績.*?)(?=^##\s|\Z)", text, re.S | re.M)
    if not m:
        return text, "no_section"
    section = m.group(1)
    section_start = m.start()
    section_end = m.end()

    # テーブル抽出（最初のテーブル）
    lines = section.split("\n")
    table_start = None
    table_end = None
    header_line = None
    sep_line = None
    body_lines = []

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped.startswith("|"):
            if table_start is not None and table_end is None:
                table_end = i
                break
            continue
        if table_start is None:
            table_start = i
            header_line = line
            continue
        if stripped.startswith("|---") or stripped.startswith("|:"):
            sep_line = line
            continue
        body_lines.append((i, line))

    if table_start is None or len(body_lines) < 2:
        return text, "no_table"

    if table_end is None:
        table_end = len(lines)

    # body_lines をソート（新しい→古い順、降順）
    def sort_key(t):
        i, line = t
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not cells:
            return -1
        return year_sort_key(cells[0])

    sorted_body = sorted(body_lines, key=sort_key, reverse=True)

    # 元の位置に並べ替えた行を再配置
    new_lines = lines[:]
    for orig_pos, _ in body_lines:
        # 該当位置に新順序の行を入れる
        idx = body_lines.index([(orig_pos, _) for orig_pos, _ in body_lines if (orig_pos, _) == body_lines[body_lines.index([(orig_pos, _)][0])]][0])
    # 単純に行入替: body_lines の元位置に sorted_body の順序で詰める
    new_section_lines = lines[:]
    for new_idx, (orig_pos, _) in enumerate(body_lines):
        new_section_lines[orig_pos] = sorted_body[new_idx][1]

    new_section = "\n".join(new_section_lines)
    new_text = text[:section_start] + new_section + text[section_end:]
    return new_text, "fixed"


def main():
    for path in sys.argv[1:]:
        p = Path(path)
        if not p.exists():
            print(f"[SKIP] not found: {path}")
            continue
        text = p.read_text(encoding="utf-8")
        new_text, status = reverse_kakomon_table(text)
        if status == "fixed" and new_text != text:
            p.write_text(new_text, encoding="utf-8")
            print(f"[FIX] {path}")
        else:
            print(f"[{status.upper()}] {path}")


if __name__ == "__main__":
    main()
