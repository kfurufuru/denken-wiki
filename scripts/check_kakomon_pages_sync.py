#!/usr/bin/env python3
"""kakomon.yml ↔ by-year.md ＋ 年度ページ 横断整合チェック（CI / pre-commit ガード）.

`scripts/check_kakomon_dual_sync.py`（_data/ と docs/_data/ のバイト一致ガード）の
姉妹スクリプト。あちらが「正本の 2 コピーが一致しているか」を見るのに対し、
本スクリプトは「正本 kakomon.yml と **派生 Markdown**（by-year.md・各年度ページ）が
内容整合しているか」を見る。

## 背景

by-year.md は手動メンテ時代に R06/R07 が丸ごと別問題へドリフトしていた
（topic 58・article 54・form 10 件不整合）。さらに年度ページ R06.md なども
一部の問で yml と食い違っていた（例: R06下問3 yml「電路の絶縁の原則と例外/省令5条」
↔ ページ「保安原則/省令1-4条」）。派生 md が静かにズレるのを機械検出する。

## 2 つのチェック

- **Check A: by-year.md 同期** … `gen_kakomon_by_year.py` で再生成した内容と一致するか
  （= yml + H18–H22 年度ページの射影と一致するか）。ズレたら ERROR。
- **Check B: 年度ページ（H23–R07）content 突合** … 各年度ページのテーブル行を
  yml の (year_label, num) と突き合わせる。
    - topic … **文字 bigram の Jaccard 類似度**で判定（しきい値は TOPIC_THRESHOLD）。
      単一 bigram 一致（「電気」等の頻出語のみ）では一致と見なさない設計。
      別問題に化けていれば Jaccard が落ちて ERROR。
    - article … 正規化（§N→第N条）後に比較。違えば WARNING（年度ページは
      代表条文のみ載せる運用差があるため非致命）。

## 使い方

    python scripts/check_kakomon_pages_sync.py            # 全チェック（ズレたら exit 1）
    python scripts/check_kakomon_pages_sync.py --list      # 不整合を一覧表示（exit 0・調査用）

CI 連携は `.github/workflows/quality-check.yml`。再生成は
`python scripts/gen_kakomon_by_year.py`。
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

# 同ディレクトリの generator を共有ロジックとして読む
sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_kakomon_by_year as gen  # noqa: E402

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, TypeError):
        pass

try:
    import yaml
except ImportError:
    print("[WARN] check_kakomon_pages_sync: PyYAML 未導入のため skip", file=sys.stderr)
    raise SystemExit(0)

ROOT = gen.ROOT
KAKOMON_DIR = gen.KAKOMON_DIR

# topic Jaccard しきい値。別問題への化けは 0.2 未満、言い換えは 0.6 以上に出る
# 典型分布を見て中間の 0.45 を採用（誤マッチ防止のため単一 bigram 一致では通さない）。
TOPIC_THRESHOLD = 0.45


# ---------------------------------------------------------------------------
# topic 類似度（厳しめ：文字 bigram Jaccard）
# ---------------------------------------------------------------------------
def char_bigrams(s: str):
    return {s[i : i + 2] for i in range(len(s) - 1)}


def topic_jaccard(a: str, b: str) -> float:
    na, nb = gen.normalize_topic(a), gen.normalize_topic(b)
    A, B = char_bigrams(na), char_bigrams(nb)
    if not A or not B:  # 1 文字以下に正規化された場合は完全一致のみ
        return 1.0 if na == nb else 0.0
    return len(A & B) / len(A | B)


def topics_consistent(a: str, b: str) -> bool:
    if gen.normalize_topic(a) == gen.normalize_topic(b):
        return True
    return topic_jaccard(a, b) >= TOPIC_THRESHOLD


def article_for_compare(art: str) -> str:
    """article 比較用の正規化：括弧注記（背景）等を除去。

    年度ページは「解釈第34条（背景）」のように代表条文へ注記を付ける運用があり、
    これは yml との不整合ではないので比較時に剥がす。
    """
    return re.sub(r"（[^）]*）", "", art).strip()


# ---------------------------------------------------------------------------
# 年度ページのパース（H23–R07）
# ---------------------------------------------------------------------------
# yml に収録のある DB 範囲のみ対象（H18–H22 は yml 非収録なので突合対象外）
DB_PAGE_RE = re.compile(r"^(H2[3-9]|H30|R0[1-7])\.md$")


def parse_table_row(line: str):
    """テーブル行を列数非依存でパースし (num, topic, article) を返す。非該当は None。

    年度ページは 6 列（問|論点|分類|形式|再出題|関連条文）と
    5 列（問|論点|分類|形式|関連条文＝R06/R07）が混在する。
    **先頭セル=topic、末尾セル=article** として両形式を吸収する
    （これが無いと 5 列の R06/R07 が突合対象から漏れる）。
    """
    s = line.strip()
    if not s.startswith("|"):
        return None
    cells = [c.strip() for c in s.strip("|").split("|")]
    if len(cells) < 3:
        return None
    m = re.match(r"問(\d+)$", cells[0])
    if not m:  # ヘッダ行「問」・区切り行「----」を弾く
        return None
    return int(m.group(1)), cells[1], gen.normalize_article(cells[-1])


def parse_db_year_page(path: Path):
    """年度ページから (year_label, num) -> {'topic','article'} を抽出。

    上期/下期 split ページは base ラベルに「上期/下期」を挿入してラベル化する。
    """
    text = path.read_text(encoding="utf-8")
    m = re.search(r"^#\s*(.+?)\s*法規", text, re.M)
    base_label = m.group(1).strip() if m else path.stem
    has_split = ("上期" in text) or ("下期" in text)
    out = {}
    cur_half = None
    for line in text.splitlines():
        hm = re.match(r"^##\s*(上期|下期)", line)
        if hm:
            cur_half = hm.group(1)
            continue
        row = parse_table_row(line)
        if row:
            num, topic, article = row
            if has_split and cur_half:
                label = base_label.replace("（", f"{cur_half}（", 1)
            else:
                label = base_label
            out[(label, num)] = {"topic": topic, "article": article}
    return out


# ---------------------------------------------------------------------------
# Check A / Check B
# ---------------------------------------------------------------------------
def load_yml_map():
    data = yaml.safe_load(gen.YML.read_text(encoding="utf-8")) or {}
    out = {}
    for p in data.get("problems", []) or []:
        out[(p["year_label"], p["num"])] = {
            "topic": p["topic"],
            "article": gen.normalize_article(p.get("article", "")),
        }
    return out


def run(list_only: bool = False) -> int:
    ymlmap = load_yml_map()

    # ---- Check A: by-year.md 同期（generator と一致するか） ----
    a_rc = gen.check()  # OK/ERROR を自前で print する

    # ---- Check B: 年度ページ content 突合 ----
    topic_errors = []
    article_warnings = []
    missing = []
    pages = sorted(p for p in KAKOMON_DIR.glob("*.md") if DB_PAGE_RE.match(p.name))
    checked = 0
    for path in pages:
        page = parse_db_year_page(path)
        for key, row in page.items():
            y = ymlmap.get(key)
            if y is None:
                missing.append((path.name, key))
                continue
            checked += 1
            if not topics_consistent(row["topic"], y["topic"]):
                topic_errors.append(
                    {
                        "file": path.name,
                        "label": key[0],
                        "num": key[1],
                        "page_topic": row["topic"],
                        "yml_topic": y["topic"],
                        "jac": topic_jaccard(row["topic"], y["topic"]),
                    }
                )
            elif article_for_compare(row["article"]) != article_for_compare(y["article"]):
                article_warnings.append(
                    {
                        "file": path.name,
                        "label": key[0],
                        "num": key[1],
                        "page_article": row["article"],
                        "yml_article": y["article"],
                    }
                )

    print("")
    print(
        f"[Check B] 年度ページ {len(pages)} 冊 / {checked} 問を yml と突合"
        f"（topic Jaccard しきい値 {TOPIC_THRESHOLD}）"
    )
    if topic_errors:
        print(f"  [ERROR] topic ドリフト {len(topic_errors)} 件（別問題に化けている）:")
        for e in topic_errors:
            print(f"    {e['file']} {e['label']} 問{e['num']}  (Jaccard {e['jac']:.2f})")
            print(f"        page: {e['page_topic']}")
            print(f"        yml : {e['yml_topic']}")
    else:
        print("  topic: OK（全問 yml と整合）")
    if article_warnings:
        print(f"  [WARN] article 表記差 {len(article_warnings)} 件（非致命・代表条文運用差）:")
        for w in article_warnings:
            print(
                f"    {w['file']} {w['label']} 問{w['num']}: "
                f"page='{w['page_article']}' / yml='{w['yml_article']}'"
            )
    if missing:
        print(f"  [WARN] yml に対応が無い行 {len(missing)} 件: {missing[:5]}")

    b_rc = 1 if topic_errors else 0

    print("")
    if list_only:
        print("(--list モード: exit 0)")
        return 0
    rc = 1 if (a_rc or b_rc) else 0
    if rc == 0:
        print("OK check_kakomon_pages_sync: by-year.md・年度ページとも kakomon.yml と整合")
    else:
        print("[FAIL] 不整合あり。gen_kakomon_by_year.py で再生成、または年度ページを yml に合わせて是正してください")
    return rc


def main() -> int:
    return run(list_only="--list" in sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
