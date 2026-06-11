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

# ヘッダ列名の同義語（ヘッダ駆動の列マッピング用）。
# 過去問テーブルは記事ごと・分野ごとに列構成が違う（例: 記事側は
# `年度|問|形式|論点` だが kijun/11.md は `年度|問|論点|登録条文`、by-field の
# 配線工事表は `年度|問|形式|論点|法令`）。固定位置で読むと「登録条文」や
# 「形式（穴埋/論説）」を論点と取り違える（false positive）か、列ズレが偶然
# 一致して実誤記を見逃す（false negative）。ヘッダ名で列を解決して根治する。
YEAR_HEADERS = ("年度",)
PROB_HEADERS = ("問", "問番", "問番号")
TOPIC_HEADERS = ("論点", "出題内容", "内容", "テーマ")  # 比較対象（キーワード突合する列）


def normalize_cell(s: str) -> str:
    return s.strip().replace("　", " ")


def resolve_col_index(header: list[str], names: tuple[str, ...]) -> int | None:
    """ヘッダ行から列名（同義語のいずれか）に一致する列indexを返す。無ければ None.

    完全一致を優先し、無ければ部分一致（ヘッダが名前を含む）でフォールバック。
    """
    norm = [normalize_cell(h) for h in header]
    for name in names:
        for idx, h in enumerate(norm):
            if h == name:
                return idx
    for name in names:
        for idx, h in enumerate(norm):
            if name and name in h:
                return idx
    return None


def parse_table_rows(lines: list[str], start_idx: int) -> tuple[list[str], list[list[str]], int]:
    """`start_idx` 行目以降のMarkdownテーブルを解析。

    戻り値: (ヘッダ列リスト, データ行リスト, テーブル末端のインデックス)。
    ヘッダはヘッダ駆動の列マッピングに使う（呼び出し側で列名→indexを解決）。
    """
    i = start_idx
    rows: list[list[str]] = []
    # ヘッダ行
    while i < len(lines) and not lines[i].lstrip().startswith("|"):
        i += 1
    if i >= len(lines):
        return [], rows, i
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
            rows.append(cells)
        i += 1
    return header, rows, i


def parse_by_field(path: Path) -> tuple[dict[tuple[str, str], dict[str, str]], list[str]]:
    """by-field.md を解析して ({ (year, prob): {topic, category} }, warnings) を返す.

    列マッピングはヘッダ行駆動。「年度」「問」「論点」をヘッダ名で解決し、
    無ければ位置フォールバック（年度=0 / 問=1 / 論点=2）。配線工事表のように
    `年度|問|形式|論点|法令` と「形式」列が割り込む構成でも論点列を正しく拾う。
    比較対象（論点）列がヘッダ名でも位置でも特定できない構成は WARN として報告。
    """
    warnings: list[str] = []
    if not path.exists():
        print(f"[ERROR] by-field.md not found: {path}", file=sys.stderr)
        return {}, warnings
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
            header, rows, end = parse_table_rows(lines, i)
            year_idx = resolve_col_index(header, YEAR_HEADERS)
            prob_idx = resolve_col_index(header, PROB_HEADERS)
            topic_idx = resolve_col_index(header, TOPIC_HEADERS)
            # 位置フォールバック（後方互換）: 旧実装は 0/1/2 固定だった
            if year_idx is None:
                year_idx = 0
            if prob_idx is None:
                prob_idx = 1
            topic_resolved_by_name = topic_idx is not None
            if topic_idx is None:
                topic_idx = 2  # フォールバック
            # 論点列がヘッダ名で特定できず、フォールバック位置にも論点らしき
            # 見出しが無い構成は黙ってスキップせず WARN（盲目化回避）
            if not topic_resolved_by_name and (
                len(header) <= topic_idx or normalize_cell(header[topic_idx]) not in TOPIC_HEADERS
            ):
                hdr_disp = " | ".join(header) if header else "(ヘッダ不明)"
                warnings.append(
                    f"by-field.md [{current_category}] 論点列を特定できず位置 "
                    f"{topic_idx} で代用（ヘッダ: {hdr_disp}）"
                )
            for row in rows:
                if len(row) < 2:
                    continue
                year = row[year_idx] if year_idx < len(row) else ""
                prob = row[prob_idx] if prob_idx < len(row) else ""
                if not YEAR_RE.match(year):
                    continue
                m = PROB_RE.match(prob)
                if not m:
                    continue
                topic = row[topic_idx] if topic_idx < len(row) else ""
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
    return db, warnings


def parse_kijun_page(path: Path) -> tuple[list[dict[str, str]], int, list[str]]:
    """kijun/N.md の過去問実績テーブルを解析.

    戻り値: (claims, section_start+1, warnings)。
    列マッピングはヘッダ行駆動。「論点」列をヘッダ名で解決し、無ければ
    位置フォールバック（4列以上=index3 / それ未満=index2）。これにより
    `年度|問|論点|登録条文`（形式列なし・kijun/11.md 型）では「登録条文」を
    論点と取り違えず、`年度|問|形式|論点`（標準型）では形式を除いて論点を拾う。
    """
    warnings: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    # 過去問実績セクションを見つける
    section_start = None
    for i, line in enumerate(lines):
        if line.startswith("## ") and "過去問実績" in line:
            section_start = i
            break
    if section_start is None:
        return [], -1, warnings
    # テーブル開始行を探す
    j = section_start + 1
    while j < len(lines) and not lines[j].lstrip().startswith("|"):
        # 次のセクションに到達したら終わり
        if lines[j].startswith("## "):
            return [], section_start, warnings
        j += 1
    header, rows, _ = parse_table_rows(lines, j)

    year_idx = resolve_col_index(header, YEAR_HEADERS)
    prob_idx = resolve_col_index(header, PROB_HEADERS)
    topic_idx = resolve_col_index(header, TOPIC_HEADERS)
    fmt_idx = resolve_col_index(header, ("形式",))
    if year_idx is None:
        year_idx = 0
    if prob_idx is None:
        prob_idx = 1
    topic_resolved_by_name = topic_idx is not None
    if topic_idx is None:
        # 位置フォールバック（後方互換）: 旧実装は 4列以上で index3、未満で index2
        topic_idx = 3 if len(header) > 3 else 2
    # 論点列が名前で特定できず、フォールバック位置にも論点見出しが無い構成は WARN
    if not topic_resolved_by_name and (
        len(header) <= topic_idx or normalize_cell(header[topic_idx]) not in TOPIC_HEADERS
    ):
        hdr_disp = " | ".join(header) if header else "(ヘッダ不明)"
        warnings.append(
            f"{path.name} 過去問実績の論点列を特定できず位置 {topic_idx} で代用"
            f"（ヘッダ: {hdr_disp}）"
        )

    parsed: list[dict[str, str]] = []
    for row in rows:
        if len(row) < 2:
            continue
        year = row[year_idx] if year_idx < len(row) else ""
        prob = row[prob_idx] if prob_idx < len(row) else ""
        topic = row[topic_idx] if topic_idx < len(row) else ""
        format_col = row[fmt_idx] if (fmt_idx is not None and fmt_idx < len(row)) else ""
        if APPROX_RE.search(year) or APPROX_RE.search(prob):
            parsed.append({"year": year, "prob": prob, "approx": True, "topic": topic})
            continue
        if not YEAR_RE.match(year):
            continue
        m = PROB_RE.match(prob)
        if not m:
            continue
        parsed.append({
            "year": year,
            "prob": f"問{m.group(1)}",
            "format": format_col,
            "topic": topic,
            "approx": False,
        })
    return parsed, section_start + 1, warnings


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
    claims, _, warnings = parse_kijun_page(path)
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
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="kijun ページの過去問実績を by-field.md と突合")
    parser.add_argument("--page", help="特定ページのみ（例: 5 → kijun/5.md）")
    parser.add_argument("--json", help="JSON出力先")
    parser.add_argument("--strict", action="store_true", help="MISSING/MISMATCHが1件でもあれば exit 1")
    args = parser.parse_args()

    db, bf_warnings = parse_by_field(BY_FIELD_MD)
    if not db:
        print("[ERROR] by-field.md を解析できませんでした", file=sys.stderr)
        return 2
    print(f"[INFO] by-field.md から {len(db)} 件の出題実績を読み込み")

    # 列構成が解決できず比較対象（論点）列を位置で代用したケースを集約。
    # 黙ってスキップせず件数報告する（列マッピング限界の盲目化を回避）。
    col_warnings: list[str] = list(bf_warnings)

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
        col_warnings.extend(r.get("warnings", []))
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

    if col_warnings:
        print()
        print(f"[WARN] 列構成を解決できず位置フォールバックしたテーブル {len(col_warnings)} 件:")
        for w in col_warnings:
            print(f"  - {w}")

    print()
    print(f"[SUMMARY] {len(targets)} ページ中、不整合 {total_issues} 件 / 列構成WARN {len(col_warnings)} 件")

    if args.json:
        out = {"results": results, "column_warnings": col_warnings}
        Path(args.json).write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[INFO] JSON出力: {args.json}")

    if args.strict and total_issues > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
