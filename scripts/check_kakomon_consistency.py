"""
過去問実績テーブルの整合性チェッカー.

各 kijun/*.md ページの「過去問実績」セクションを抽出し、
by-field.md（一次ソース）と突合して以下を検出する：

- ❌ MISSING : kijun ページが主張する (年度・問番号) が by-field.md に存在しない
- ⚠️  MISMATCH: 存在するが論点キーワードが大きく食い違う

使い方:
    python scripts/check_kakomon_consistency.py
    python scripts/check_kakomon_consistency.py --json out.json
    python scripts/check_kakomon_consistency.py --page 5  # kijun/5.md のみチェック
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Windows コンソールのcp932で絵文字が落ちないようUTF-8強制
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
KIJUN_DIR = ROOT / "docs" / "articles" / "kijun"
BY_FIELD_MD = ROOT / "docs" / "kakomon" / "by-field.md"

# 年度パターン: H10, H29, R01, R04, R04上, R04下
YEAR_RE = re.compile(r"^(H[0-9]{1,2}|R[0-9]{1,2}(?:上|下)?)$")
PROB_RE = re.compile(r"^問\s*([0-9]+)$")
APPROX_RE = re.compile(r"頃|—|‐|–|\?")  # 「H27頃」「—」など曖昧表記


def normalize_cell(s: str) -> str:
    return s.strip().replace("　", " ")


def parse_table_rows(lines: list[str], start_idx: int) -> tuple[list[list[str]], int]:
    """`start_idx` 行目以降のMarkdownテーブルを解析。テーブル末端のインデックスも返す."""
    i = start_idx
    rows: list[list[str]] = []
    # ヘッダ行
    while i < len(lines) and not lines[i].lstrip().startswith("|"):
        i += 1
    if i >= len(lines):
        return rows, i
    header = [normalize_cell(c) for c in lines[i].strip().strip("|").split("|")]
    i += 1
    # セパレータ行
    if i < len(lines) and re.match(r"^\s*\|[\s\-:|]+\|", lines[i]):
        i += 1
    # データ行
    while i < len(lines):
        line = lines[i]
        if not line.lstrip().startswith("|"):
            break
        cells = [normalize_cell(c) for c in line.strip().strip("|").split("|")]
        if len(cells) >= 2:
            rows.append([header[j] if j < len(header) else f"col{j}" for j in range(len(cells))])
            rows[-1] = cells  # 上書き: cellsを格納
        i += 1
    return rows, i


def parse_by_field(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    """by-field.md を解析して { (year, prob): {topic, category} } を返す."""
    if not path.exists():
        print(f"[ERROR] by-field.md not found: {path}", file=sys.stderr)
        return {}
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    db: dict[tuple[str, str], dict[str, str]] = {}
    current_category = ""
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if line.startswith("###") or line.startswith("## "):
            current_category = line.lstrip("#").strip().split(" → ")[0].strip()
        # テーブル開始判定
        if line.lstrip().startswith("|") and "年度" in line and "問" in line:
            rows, end = parse_table_rows(lines, i)
            for row in rows:
                if len(row) < 2:
                    continue
                year = row[0]
                prob = row[1]
                if not YEAR_RE.match(year):
                    continue
                m = PROB_RE.match(prob)
                if not m:
                    continue
                topic = row[2] if len(row) > 2 else ""
                key = (year, f"問{m.group(1)}")
                if key not in db:
                    db[key] = {"topic": topic, "category": current_category}
                else:
                    # 同じ (年,問) が複数カテゴリに出るケース → カテゴリを連結
                    if current_category and current_category not in db[key]["category"]:
                        db[key]["category"] += f" / {current_category}"
            i = end
        else:
            i += 1
    return db


def parse_kijun_page(path: Path) -> tuple[list[dict[str, str]], int]:
    """kijun/N.md の過去問実績テーブルを解析."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    # 過去問実績セクションを見つける
    section_start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and "過去問実績" in line:
            section_start = i
            break
    if section_start is None:
        return [], -1
    # テーブル開始行を探す
    j = section_start + 1
    while j < len(lines) and not lines[j].lstrip().startswith("|"):
        # 次のセクションに到達したら終わり
        if lines[j].startswith("## "):
            return [], section_start
        j += 1
    rows, _ = parse_table_rows(lines, j)
    parsed: list[dict[str, str]] = []
    for row in rows:
        if len(row) < 2:
            continue
        year = row[0]
        prob = row[1]
        if APPROX_RE.search(year) or APPROX_RE.search(prob):
            parsed.append({"year": year, "prob": prob, "approx": True, "topic": row[3] if len(row) > 3 else ""})
            continue
        if not YEAR_RE.match(year):
            continue
        m = PROB_RE.match(prob)
        if not m:
            continue
        # 列順は通常: 年度 / 問 / 形式 / 論点 / 備考
        topic = row[3] if len(row) > 3 else (row[2] if len(row) > 2 else "")
        format_col = row[2] if len(row) > 3 else ""
        parsed.append({
            "year": year,
            "prob": f"問{m.group(1)}",
            "format": format_col,
            "topic": topic,
            "approx": False,
        })
    return parsed, section_start + 1


def keyword_overlap(a: str, b: str) -> bool:
    """日本語キーワードの重複を漢字2-gram で判定。語境界に依存せず緩く判定."""
    if not a or not b:
        return False
    # 漢字を抽出して連続2文字のbigramを作成
    pattern = re.compile(r"[一-龥々]+")
    a_kanji = "".join(pattern.findall(a))
    b_kanji = "".join(pattern.findall(b))
    if len(a_kanji) < 2 or len(b_kanji) < 2:
        return False
    a_bigrams = {a_kanji[i:i+2] for i in range(len(a_kanji) - 1)}
    b_bigrams = {b_kanji[i:i+2] for i in range(len(b_kanji) - 1)}
    return bool(a_bigrams & b_bigrams)


def check_page(path: Path, db: dict[tuple[str, str], dict[str, str]]) -> dict:
    claims, _ = parse_kijun_page(path)
    issues: list[dict] = []
    for c in claims:
        if c.get("approx"):
            continue
        key = (c["year"], c["prob"])
        if key not in db:
            issues.append({
                "level": "MISSING",
                "year": c["year"],
                "prob": c["prob"],
                "page_topic": c.get("topic", ""),
                "page_format": c.get("format", ""),
                "by_field_topic": None,
                "by_field_category": None,
            })
        else:
            entry = db[key]
            if not keyword_overlap(c.get("topic", ""), entry["topic"]):
                issues.append({
                    "level": "MISMATCH",
                    "year": c["year"],
                    "prob": c["prob"],
                    "page_topic": c.get("topic", ""),
                    "page_format": c.get("format", ""),
                    "by_field_topic": entry["topic"],
                    "by_field_category": entry["category"],
                })
    return {
        "page": path.name,
        "claims_count": len(claims),
        "issues": issues,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="kijun ページの過去問実績を by-field.md と突合")
    parser.add_argument("--page", help="特定ページのみ（例: 5 → kijun/5.md）")
    parser.add_argument("--json", help="JSON出力先")
    parser.add_argument("--strict", action="store_true", help="MISSING/MISMATCHが1件でもあれば exit 1")
    args = parser.parse_args()

    db = parse_by_field(BY_FIELD_MD)
    if not db:
        print("[ERROR] by-field.md を解析できませんでした", file=sys.stderr)
        return 2
    print(f"[INFO] by-field.md から {len(db)} 件の出題実績を読み込み")

    if args.page:
        targets = [KIJUN_DIR / f"{args.page}.md"]
    else:
        targets = sorted(KIJUN_DIR.glob("*.md"), key=lambda p: int(re.match(r"(\d+)", p.stem).group(1)) if re.match(r"\d", p.stem) else 999)

    results = []
    total_issues = 0
    for path in targets:
        if not path.exists():
            continue
        r = check_page(path, db)
        results.append(r)
        if r["issues"]:
            total_issues += len(r["issues"])
            print()
            print(f"=== {r['page']} （主張 {r['claims_count']} 件 / 問題 {len(r['issues'])} 件） ===")
            for issue in r["issues"]:
                tag = "❌ MISSING" if issue["level"] == "MISSING" else "⚠️  MISMATCH"
                print(f"  {tag}  {issue['year']} {issue['prob']}")
                print(f"      page  : {issue['page_format']} / {issue['page_topic']}")
                if issue["by_field_topic"]:
                    print(f"      actual: [{issue['by_field_category']}] {issue['by_field_topic']}")
                else:
                    print(f"      actual: (by-field.md に該当エントリなし)")

    print()
    print(f"[SUMMARY] {len(targets)} ページ中、不整合 {total_issues} 件")

    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INFO] JSON出力: {args.json}")

    if args.strict and total_issues > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
