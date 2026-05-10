#!/usr/bin/env python3
"""denken-wiki 全条文記事を triage して書式ルール違反を検出する。

検出項目:
  R1: 過去問実績表が古い→新しい順（最新年度が下にある）
  R2: admonition (!!! / ???) 内に table がある
  R3: 頻出ひっかけセクションが番号付きリスト（1. 2. 3.）形式
  R4: 「具体的施設要件は解釈第33条」のような単独委任記述（ヒント）
  R6: OCR を過電流遮断器として混入

Output: triage report to stdout (TSV)
Usage: python scripts/triage_format_rules.py docs/articles/
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

# 年度コードを「相対値」に変換（大きいほど新しい）
YEAR_ORDER = {}
for i, y in enumerate([
    "H13", "H14", "H15", "H16", "H17", "H18", "H19", "H20",
    "H21", "H22", "H23", "H24", "H25", "H26", "H27", "H28", "H29", "H30",
    "R01", "R02", "R03", "R04下", "R04上", "R04",
    "R05下", "R05上", "R06下", "R06上", "R07下", "R07上",
]):
    YEAR_ORDER[y] = i


def extract_kakomon_years(text):
    """過去問実績セクションのテーブルから年度カラムを抽出（出現順）。"""
    m = re.search(r"##\s*\d+\.\s*過去問実績(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    if not m:
        return None
    section = m.group(1)
    # テーブル行から最初のカラム（年度）を抽出
    rows = []
    for line in section.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        if line.startswith("|---") or line.startswith("|:"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        first = cells[0].strip("*").strip()  # 太字マーカー除去
        # ヘッダ行スキップ
        if first in ("年度", "Year"):
            continue
        # 年度っぽい文字列か？
        if re.match(r"^[HR]\d", first):
            rows.append(first)
    return rows


def is_sorted_old_to_new(years):
    """古い→新しい順か（昇順）"""
    if len(years) < 2:
        return None  # 1件以下は対象外
    indices = []
    for y in years:
        # 「H30」「R05上」などのバリエーション吸収
        normalized = y.replace("年", "").strip()
        if normalized in YEAR_ORDER:
            indices.append(YEAR_ORDER[normalized])
        else:
            return None  # 不明
    if indices == sorted(indices):
        return "OLD_TO_NEW"  # 古い→新しい順（要修正）
    elif indices == sorted(indices, reverse=True):
        return "NEW_TO_OLD"  # 新しい→古い順（OK）
    return "MIXED"


def detect_admonition_table(text):
    """admonition 内に「外出し検討」レベルのテーブルがあるか検出（単一テーブル7行以上）。

    許容ケース（検出対象外）：
      - 解答表（??? success/question 内）
      - 小さな比較表（連続テーブル行 ≤ 6 行）
      - 典型ひっかけ表（≤ 6 行で example ラベル）
    """
    issues = []
    in_adm = False
    adm_indent = 0
    adm_kind = ""
    adm_start_line = 0
    max_table_rows = 0
    cur_table_rows = 0

    def check_emit():
        nonlocal max_table_rows, cur_table_rows, issues, adm_start_line, adm_kind, in_adm
        if cur_table_rows > max_table_rows:
            max_table_rows = cur_table_rows
        is_answer = adm_kind in ("success", "question")
        if not is_answer and max_table_rows >= 7:
            issues.append((adm_start_line, max_table_rows))
        max_table_rows = 0
        cur_table_rows = 0

    for i, line in enumerate(text.split("\n"), 1):
        m = re.match(r"^(\s*)(!!!|\?\?\?)\s+(\w+)", line)
        if m:
            if in_adm:
                check_emit()
            in_adm = True
            adm_indent = len(m.group(1))
            adm_kind = m.group(3)
            adm_start_line = i
            continue
        if in_adm:
            min_indent = adm_indent + 4
            if line.strip() and (len(line) - len(line.lstrip())) < min_indent:
                check_emit()
                in_adm = False
                continue
            content = line[min_indent:] if len(line) > min_indent else ""
            if content.startswith("|") and content.rstrip().endswith("|"):
                if not (content.startswith("|---") or content.startswith("|:")):
                    cur_table_rows += 1
            else:
                if cur_table_rows > max_table_rows:
                    max_table_rows = cur_table_rows
                cur_table_rows = 0
    if in_adm:
        check_emit()
    return [line_no for line_no, _ in issues]


def detect_numbered_pitfalls(text):
    """頻出ひっかけセクションが番号リスト形式か"""
    m = re.search(r"##\s*\d+\.\s*頻出ひっかけ(.*?)(?=^##\s|\Z)", text, re.S | re.M)
    if not m:
        return False
    section = m.group(1)
    # 番号付きリストの行（"1. 🔴..." など）が3個以上あるか
    numbered_lines = re.findall(r"^\s*\d+\.\s+[🔴🟡🟢]", section, re.M)
    return len(numbered_lines) >= 3


def detect_single_delegation(text):
    """「具体的施設要件は解釈第N条」のような単独委任記述"""
    matches = re.findall(r"具体的(?:施設要件|な施設要件).*解釈第(\d+)条", text)
    return matches[:3]  # 最大3件


def detect_ocr_in_breaker(text):
    """OCR を過電流遮断器として混入"""
    issues = []
    for line_no, line in enumerate(text.split("\n"), 1):
        if re.search(r"(ヒューズ・MCCB・OCR|MCCB・OCR|過電流遮断器（ヒューズ.*OCR|過電流遮断器：ヒューズ.*OCR)", line):
            issues.append((line_no, line.strip()[:80]))
    return issues


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/articles/")
    files = sorted(root.rglob("*.md"))

    rows = []
    for f in files:
        if f.name == "index.md":
            continue
        text = f.read_text(encoding="utf-8")
        try:
            rel = f.relative_to(Path.cwd())
        except ValueError:
            rel = f

        years = extract_kakomon_years(text)
        sort_result = is_sorted_old_to_new(years) if years else None
        adm_issues = detect_admonition_table(text)
        numbered = detect_numbered_pitfalls(text)
        single_deleg = detect_single_delegation(text)
        ocr_issues = detect_ocr_in_breaker(text)

        flags = []
        if sort_result == "OLD_TO_NEW":
            flags.append(f"R1:{','.join(years)}")
        if adm_issues:
            flags.append(f"R2:{len(adm_issues)}件")
        if numbered:
            flags.append("R3")
        if single_deleg:
            flags.append(f"R4:解釈{','.join(single_deleg)}条")
        if ocr_issues:
            flags.append(f"R6:{len(ocr_issues)}件")

        if flags:
            rows.append((str(rel), "  ".join(flags)))

    print(f"{'ファイル':<55s}\t違反")
    print("-" * 100)
    for rel, flags in rows:
        print(f"{rel:<55s}\t{flags}")
    print(f"\n合計: {len(rows)} files / {len(files)} scanned")


if __name__ == "__main__":
    main()
