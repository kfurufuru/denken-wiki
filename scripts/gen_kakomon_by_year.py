#!/usr/bin/env python3
"""docs/kakomon/by-year.md を _data/kakomon.yml から再生成するジェネレータ.

## 背景

`docs/kakomon/by-year.md` は元々 generator を持たない **手動メンテ** ページだった。
そのため正本 `_data/kakomon.yml`（H23–R07・247問）と静かにドリフトし、
特に R06上/下・R07上/下 が **丸ごと別問題** に化けていた（topic 58 件・article 54 件・
form 10 件 不整合）。`docs/kakomon/index.md` は by-year.md を
「kakomon.yml のデータから自動生成」と説明しており、本来は生成物であるべきだった。

本スクリプトで by-year.md を **単一ソースから決定論的に再生成** できるようにし、
`--check` モードで CI / pre-commit からドリフトを検出する。

## データソース（2 系統）

- **H23–R07（247問）** … `_data/kakomon.yml`（正本）の射影。
  - `topic` `form` … yml をそのまま転記
  - `関連条文` … yml の `article`（`§N` 表記）を `第N条` 表記へ正規化
  - `分類`（法令カテゴリ）… `theme` + `article` から決定論的に導出（yml に専用フィールド無し）
- **H18–H22（65問）** … yml 非収録。年度ページ `H18.md`–`H22.md` のテーブルを正とする。
  - `topic` `分類` `form` `関連条文` … 年度ページから転記

## 導出ルール（yml に無い 2 列）

- **分類（法令カテゴリ）**: `derive_category()` 参照。`shisetsu-kanri` テーマは
  「電気施設管理」で確定。それ以外は `article` の法令種別キーワードで判定し、
  事業法ファミリーの細分（電気工事業法・電気関係報告規則・電気用品安全法・
  電気工事士法・風力設備技術基準）も拾う。
- **再出題（🔁）**: `compute_reuse()` 参照。「同一論点（topic 正規化一致）が
  時系列で **より前の試験回** に出題済み」を 🔁 とする。各論点の初出は付かない。
  H18–H22 も再出題判定の母集合に含める（時系列の正確性のため）。

## 使い方

    python scripts/gen_kakomon_by_year.py          # by-year.md を再生成（書き込み）
    python scripts/gen_kakomon_by_year.py --check   # 現ファイルと照合（差分あれば exit 1・非書き込み）

CI 連携は `.github/workflows/quality-check.yml`、横断整合は
`scripts/check_kakomon_pages_sync.py`（年度ページも含めた突合）を参照。
"""
import difflib
import re
import sys
from collections import defaultdict
from pathlib import Path

# Windows cp932 環境での stdout encoding 対策
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, TypeError):
        pass

try:
    import yaml
except ImportError:  # import 時点では落とさない（checker から import されるため）
    yaml = None

ROOT = Path(__file__).resolve().parents[1]
YML = ROOT / "_data" / "kakomon.yml"
KAKOMON_DIR = ROOT / "docs" / "kakomon"
BY_YEAR = KAKOMON_DIR / "by-year.md"

# H18–H22 は yml 非収録。年度ページを正とする（時系列順）
PRE_DB_PAGES = ["H18", "H19", "H20", "H21", "H22"]

# ---------------------------------------------------------------------------
# 正規化ヘルパ
# ---------------------------------------------------------------------------
_ART_RE = re.compile(r"§(\d+)(の\d+)?")


def normalize_article(art: str) -> str:
    """yml の `§N` / `§Nの2` 表記を `第N条` / `第N条の2` 表記へ。コンマ空白も統一。

    例: '事業法§39, §40'  -> '事業法第39条, 第40条'
        '省令§1〜§4'       -> '省令第1条〜第4条'
        '事業法§28の40'     -> '事業法第28条の40'   (枝番は「第N条の<sub>」)
        '解釈§37, §37の2'   -> '解釈第37条, 第37条の2'
        '−' / '報告規則'    -> そのまま
    """
    art = (art or "").strip()
    art = _ART_RE.sub(lambda m: f"第{m.group(1)}条{m.group(2) or ''}", art)
    art = re.sub(r"\s*,\s*", ", ", art)  # コンマ空白を ', ' に統一
    return art


def normalize_topic(t: str) -> str:
    """論点の表記揺れを吸収（Markdownリンク・括弧書き・記号・空白を除去）。再出題判定・突合に使う。"""
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", "", t)  # [→解法パターン](url) 等のリンクを除去
    t = re.sub(r"[（(][^）)]*[)）]", "", t)  # 括弧書き（計算）等を除去
    t = re.sub(r"[\s，、・。,.\-―—–~〜＝=/／]", "", t)
    return t.strip()


def derive_category(theme: str, article: str) -> str:
    """yml の theme + article から by-year.md の「分類（法令カテゴリ）」を決定論的に導出。

    優先順位:
      1. theme == 'shisetsu-kanri' → 電気施設管理（管理・計算系は条文があっても施設管理）
      2. article の法令種別キーワード（事業法ファミリーの細分を含む）
      3. theme フォールバック（jigyoho-taikei / shunin-gijutsusha → 電気事業法、他 → 電気設備技術基準）
    """
    if theme == "shisetsu-kanri":
        return "電気施設管理"
    a = article or ""
    if "工事業法" in a:
        return "電気工事業法"
    if "報告規則" in a:
        return "電気関係報告規則"
    if "PSE" in a or "用品安全" in a:
        return "電気用品安全法"
    if "工事士" in a:
        return "電気工事士法"
    if "風力" in a:
        return "風力設備技術基準"
    if "事業法" in a or "施行規則" in a:
        return "電気事業法"
    if "省令" in a or "解釈" in a:
        return "電気設備技術基準"
    if theme in ("jigyoho-taikei", "shunin-gijutsusha"):
        return "電気事業法"
    return "電気設備技術基準"


def chrono_key(year_label: str):
    """year_label を時系列ソート可能な (西暦, 期) タプルへ。上期=0 / 下期=1。"""
    half = 1 if "下期" in year_label else 0
    if "令和元年" in year_label:
        yr = 2019
    else:
        m = re.search(r"平成(\d+)年", year_label)
        if m:
            yr = 1988 + int(m.group(1))
        else:
            m = re.search(r"令和(\d+)年", year_label)
            yr = 2018 + int(m.group(1)) if m else 9999
    return (yr, half)


# ---------------------------------------------------------------------------
# データロード
# ---------------------------------------------------------------------------
_TABLE_ROW_RE = re.compile(
    r"^\|\s*問(\d+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|"
)


def parse_year_page(slug: str):
    """年度ページ（H18–H22 用・6 列テーブル）から行を抽出。year_label はタイトルから。"""
    path = KAKOMON_DIR / f"{slug}.md"
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^#\s*(.+?)\s*法規", text, re.M)
    year_label = m.group(1).strip() if m else slug
    rows = []
    for line in text.splitlines():
        m = _TABLE_ROW_RE.match(line)
        if m:
            rows.append(
                {
                    "year_label": year_label,
                    "num": int(m.group(1)),
                    "topic": m.group(2).strip(),
                    "category": m.group(3).strip(),
                    "form": m.group(4).strip(),
                    "article": normalize_article(m.group(6).strip()),
                }
            )
    return rows


def load_yml_rows():
    """_data/kakomon.yml（H23–R07）から行を生成。分類は導出・article は正規化。"""
    if yaml is None:
        print("[ERROR] gen_kakomon_by_year: PyYAML が必要です（pip install pyyaml）", file=sys.stderr)
        raise SystemExit(2)
    data = yaml.safe_load(YML.read_text(encoding="utf-8")) or {}
    rows = []
    for p in data.get("problems", []) or []:
        rows.append(
            {
                "year_label": p["year_label"],
                "num": p["num"],
                "topic": p["topic"],
                "category": derive_category(p.get("theme", ""), p.get("article", "")),
                "form": p["form"],
                "article": normalize_article(p.get("article", "")),
            }
        )
    return rows


def compute_reuse(rows):
    """各行に reuse(bool) を付与。同一論点が「より前の試験回」に出題済みなら True。"""
    for r in rows:
        r["key"] = chrono_key(r["year_label"])
    topic_keys = defaultdict(list)
    for r in rows:
        topic_keys[normalize_topic(r["topic"])].append(r["key"])
    for r in rows:
        keys = topic_keys[normalize_topic(r["topic"])]
        r["reuse"] = any(k < r["key"] for k in keys)


# ---------------------------------------------------------------------------
# 生成
# ---------------------------------------------------------------------------
def build() -> str:
    """by-year.md の全文を生成して返す（決定論的・タイムスタンプ無し）。"""
    rows = []
    for slug in PRE_DB_PAGES:
        rows.extend(parse_year_page(slug))
    rows.extend(load_yml_rows())
    compute_reuse(rows)

    by_label = defaultdict(list)
    for r in rows:
        by_label[r["year_label"]].append(r)
    ordered = sorted(by_label, key=chrono_key)

    out = []
    out.append("# 📅 年度別 過去問一覧")
    out.append("")
    out.append("> H18〜R07（312問）の出題を年度別に整理")
    out.append("")
    for label in ordered:
        out.append(f"## {label}")
        out.append("")
        out.append("| 問 | 論点 | 分類 | 形式 | 再出題 | 関連条文 |")
        out.append("|----|------|------|------|--------|----------|")
        for r in sorted(by_label[label], key=lambda x: x["num"]):
            reuse = "🔁 再出題" if r["reuse"] else "-"
            art = r["article"] if r["article"] else "−"
            out.append(
                f"| 問{r['num']} | {r['topic']} | {r['category']} | {r['form']} | {reuse} | {art} |"
            )
        out.append("")
    out.append("---")
    out.append("")
    out.append('!!! note "自動生成ファイル（手動編集禁止）"')
    out.append(
        "    このページは `_data/kakomon.yml`（H23–R07・正本247問）と年度ページ "
        "`H18.md`–`H22.md`（H18–H22・65問）から `scripts/gen_kakomon_by_year.py` で自動生成しています。"
    )
    out.append(
        "    **直接編集せず**、データ元（kakomon.yml もしくは該当年度ページ）を修正して再生成してください。"
    )
    out.append(
        "    再生成: `python scripts/gen_kakomon_by_year.py` ／ "
        "整合確認: `python scripts/gen_kakomon_by_year.py --check`"
    )
    out.append("    関連条文の一部は推定を含みます。")
    return "\n".join(out) + "\n"


def check() -> int:
    """生成結果と現ファイルを照合（改行コードは正規化して比較）。差分あれば 1。"""
    expected = build()
    if not BY_YEAR.exists():
        print(f"[ERROR] {BY_YEAR.relative_to(ROOT)} が存在しません", file=sys.stderr)
        return 1
    actual = BY_YEAR.read_text(encoding="utf-8").replace("\r\n", "\n")
    if actual == expected:
        print("OK gen_kakomon_by_year --check: by-year.md は kakomon.yml と同期しています")
        return 0
    print("[ERROR] by-year.md が kakomon.yml（+H18–H22 年度ページ）とズレています。")
    print("  修正: python scripts/gen_kakomon_by_year.py")
    diff = difflib.unified_diff(
        actual.splitlines(),
        expected.splitlines(),
        fromfile="by-year.md (現状)",
        tofile="by-year.md (期待=再生成結果)",
        lineterm="",
        n=1,
    )
    for i, line in enumerate(diff):
        print("  " + line)
        if i >= 60:
            print("  ...(以降省略)")
            break
    return 1


def main() -> int:
    if "--check" in sys.argv[1:]:
        return check()
    content = build()
    with open(BY_YEAR, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    n_rows = len(re.findall(r"^\| 問\d", content, re.M))
    print(f"WROTE {BY_YEAR.relative_to(ROOT)}  ({n_rows} problems)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
