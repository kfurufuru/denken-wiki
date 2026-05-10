#!/usr/bin/env python3
"""頻出ひっかけセクションの番号付きリストを 致命/注意/軽度 3段表化する。

検出パターン: `1. 🔴 ...`, `2. 🟡 ...` 等の番号付き行
出力パターン: 3段の小見出し＋「誤った主張 / 正しくは」2列表

Usage: python scripts/fix_pitfall_format.py <file1.md> [<file2.md> ...]
"""
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

PITFALL_HEADER_RE = re.compile(r"^(##\s*\d+\.\s*頻出ひっかけ.*)$", re.M)
NUMBERED_LINE_RE = re.compile(r"^\s*(\d+)\.\s*([🔴🟡🟢])\s*(.+)$")


def split_claim_and_correction(body):
    """「**主張** — 説明」または「**主張** → 説明」を (claim, correction) に分解"""
    # パターン1: `**X** — Y` または `**X** ＝ Y`
    m = re.match(r"\*\*([^*]+)\*\*\s*[—\-–→](.+)", body)
    if m:
        claim = m.group(1).strip()
        correction = m.group(2).strip()
        return claim, correction
    # パターン2: `**X**:Y`
    m = re.match(r"\*\*([^*]+)\*\*[：:](.+)", body)
    if m:
        claim = m.group(1).strip()
        correction = m.group(2).strip()
        return claim, correction
    # パターン3: 単純なテキスト（claim と correction を分けられない場合）
    return None, body


def convert_pitfalls(text):
    """ひっかけセクションを3段表化する"""
    m_header = PITFALL_HEADER_RE.search(text)
    if not m_header:
        return text, "no_section"

    section_start = m_header.start()
    # 次の ## までを取得
    rest = text[m_header.end():]
    next_section = re.search(r"^##\s+", rest, re.M)
    section_end = m_header.end() + (next_section.start() if next_section else len(rest))

    section = text[section_start:section_end]
    section_lines = section.split("\n")

    # 番号付きリストを抽出
    numbered = {"🔴": [], "🟡": [], "🟢": []}
    other_lines_pre = []  # ヘッダ後・リスト前の行
    other_lines_post = []  # リスト後の行
    in_list = False
    list_done = False
    header_consumed = False

    for line in section_lines:
        if not header_consumed and line.startswith("##"):
            header_consumed = True
            other_lines_pre.append(line)
            continue
        m = NUMBERED_LINE_RE.match(line)
        if m:
            in_list = True
            num, emoji, body = m.group(1), m.group(2), m.group(3).strip()
            claim, correction = split_claim_and_correction(body)
            numbered[emoji].append((claim, correction))
            continue
        if in_list and line.strip() == "":
            # リスト内の空行
            continue
        if in_list and not list_done:
            list_done = True
            other_lines_post.append(line)
            continue
        if not in_list:
            other_lines_pre.append(line)
        else:
            other_lines_post.append(line)

    if not any(numbered.values()):
        return text, "no_numbered_list"

    if sum(len(v) for v in numbered.values()) < 3:
        return text, "too_few_items"

    # 新しいセクション構築
    new_lines = []
    new_lines.extend(other_lines_pre)
    new_lines.append("")

    sections_def = [
        ("🔴", "致命的ひっかけ", "必ず即答できる必修事項"),
        ("🟡", "注意ひっかけ", "細部の表現に注意"),
        ("🟢", "軽度ひっかけ", "用語の確認"),
    ]
    for emoji, title, sub in sections_def:
        items = numbered[emoji]
        if not items:
            continue
        new_lines.append(f"### {emoji} {title}（{sub}）")
        new_lines.append("")
        new_lines.append("| 誤った主張 | 正しくは |")
        new_lines.append("|---|---|")
        for claim, correction in items:
            if claim is None:
                # 分解失敗時は1セルに全文
                new_lines.append(f"| — | {correction} |")
            else:
                # セル内 pipe をエスケープ
                claim_safe = claim.replace("|", "\\|")
                correction_safe = correction.replace("|", "\\|")
                new_lines.append(f"| {claim_safe} | {correction_safe} |")
        new_lines.append("")

    # 末尾の他要素（??? question など）を保持
    # 空行重複を避ける
    if other_lines_post:
        # 先頭空行除去
        while other_lines_post and other_lines_post[0].strip() == "":
            other_lines_post.pop(0)
        new_lines.extend(other_lines_post)

    new_section = "\n".join(new_lines)
    # セクション末尾と次セクションの境界保護（改行担保）
    if not new_section.endswith("\n"):
        new_section += "\n"
    new_text = text[:section_start] + new_section + text[section_end:]
    return new_text, "fixed"


def main():
    for path in sys.argv[1:]:
        p = Path(path)
        if not p.exists():
            print(f"[SKIP] not found: {path}")
            continue
        text = p.read_text(encoding="utf-8")
        new_text, status = convert_pitfalls(text)
        if status == "fixed" and new_text != text:
            p.write_text(new_text, encoding="utf-8")
            print(f"[FIX] {path}")
        else:
            print(f"[{status.upper()}] {path}")


if __name__ == "__main__":
    main()
