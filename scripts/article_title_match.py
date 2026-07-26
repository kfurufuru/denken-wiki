"""条番号↔条見出し の突合ロジック（省令・解釈・事業法で共有）。

## なぜ共通化したか（2026-07-26）

同じ「条番号と条見出しの対応」を検査するコードが法令ごとに独立して育った結果、
判定規則が法令ごとにズレた。実際 `audit_kaishaku_titles.py` にだけ入れた
「他条の見出しと逐語一致なら ERROR」規則が `audit_titles.py`（省令）には無く、
**kijun/index.md に第7条・第47条・第39条の見出しがそのまま別の条に付いている誤り
3件が検出されないまま残っていた**。判定規則は1箇所に置き、法令側は「正本 dict」
だけを差し替える。

## 判定

`classify(num, claimed, master)` は以下を返す:

- `None`            … 逐語一致（末尾の補足「（…）」は除去して比較）
- `("ERROR", ...)`  … 条番号の取り違え。次のいずれか
                      (a) 主張が**他の条の見出しと逐語一致**（margin 不問）
                      (b) 他条への類似が SIM_OK 以上、かつ当該条より SIM_MARGIN 以上近い
- `("WARN", ...)`   … 単なる乖離（短縮表記・改正前見出し・言い換え）
- `("MASTER_MISSING", ...)` … 正本に当該条が無い（判定不能・fail-open）

(a) を (b) より先に評価するのが要点。(b) だけだと隣接条で語彙が重なる事案を取り逃す
（実測: 解釈第68条「低高圧架空電線の高さ」を第65条「低高圧架空電線路に使用する電線」に
差し替えても margin 0.45 に届かなかった）。

なお **同じ見出しを持つ条が正本内に複数あっても誤検出しない**。逐語一致の判定は
「まず当該条と一致するか」を先に見て `None` を返すため、(a) には到達しない
（例: 解釈第64条と第83条はどちらも「適用範囲」／電気事業法第40条と第56条はどちらも
「技術基準適合命令」）。
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

SIM_OK = 0.60      # これ以上なら「その条の見出しの言い換え」とみなす
SIM_MARGIN = 0.45  # ERROR に必要な「他条の方が近い」差

# 末尾の補足括弧を落とす。
#   「電路の対地電圧の制限（住宅の屋内電路 150V）」→「電路の対地電圧の制限」
# 見出しの**途中**にある括弧は原典見出しの一部でありうるので触らない。
TRAILING_PAREN = re.compile(r"(?:[（(][^（()）]*[）)])+\s*$")


def strip_supplement(title: str) -> str:
    """末尾の補足「（…）」を除去（連続していれば全部）。"""
    prev = None
    s = title.strip()
    while prev != s:
        prev = s
        s = TRAILING_PAREN.sub("", s).strip()
        if not s:  # 括弧だけのタイトルは元に戻す（除去しすぎない）
            return title.strip()
    return s


def norm_exact(s: str) -> str:
    """逐語一致の判定用。空白のみ吸収し、字句は変えない。"""
    return re.sub(r"[\s　]", "", s)


def norm_fuzzy(s: str) -> str:
    """類似度計算用の正規化（記号・定型語尾を落とす）。"""
    s = re.sub(r"[\s　、，,・（）()「」【】]", "", s)
    return s.replace("等", "").replace("の防止", "").replace("防止", "")


def sim(a: str, b: str) -> float:
    """0..1 の類似度。包含は 1.0 にせず長さ比で減点する。

    「電路の絶縁」は「電路の絶縁性能」の部分文字列だが別概念（絶縁の原則 vs 絶縁性能）で、
    1.0 にすると隣接条を誤って同一視する。
    """
    na, nb = norm_fuzzy(a), norm_fuzzy(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 0.6 + 0.4 * (min(len(na), len(nb)) / max(len(na), len(nb)))
    return SequenceMatcher(None, na, nb).ratio()


def classify(num: int, claimed: str, master: dict[int, str]) -> tuple[str, str] | None:
    """(status, detail) を返す。一致していれば None。詳細はモジュール docstring 参照。"""
    truth = master.get(num)
    if truth is None:
        return ("MASTER_MISSING", f"第{num}条 は正本に無い（判定不能・fail-open）: 「{claimed}」")

    base = strip_supplement(claimed)
    if norm_exact(base) == norm_exact(truth):
        return None

    # (a) 他の条の見出しと逐語一致 → margin を問わず ERROR。
    # 公式見出しと1文字違わず一致するのは偶然ではないので cry-wolf にならない。
    for n2, t2 in master.items():
        if n2 != num and norm_exact(base) == norm_exact(t2):
            return (
                "ERROR",
                f"第{num}条「{base}」… 正本は「{truth}」"
                f" → その表記は**第{n2}条**の見出しと逐語一致（条番号の取り違え）",
            )

    # (b) 他条への類似が当該条より明確に高い
    truth_s = sim(base, truth)
    best_n, best_s = None, 0.0
    for n2, t2 in master.items():
        if n2 == num:
            continue
        s2 = sim(base, t2)
        if s2 > best_s:
            best_n, best_s = n2, s2

    if best_n is not None and best_s >= SIM_OK and (best_s - truth_s) >= SIM_MARGIN:
        return (
            "ERROR",
            f"第{num}条「{base}」… 正本は「{truth}」"
            f" → **第{best_n}条**（{master[best_n]}）では？",
        )
    return ("WARN", f"第{num}条「{base}」… 正本は「{truth}」（短縮表記・改正前見出し等なら問題なし）")


# ---------------------------------------------------------------------------
# index.md / mkdocs.yml nav のパース（法令ディレクトリ名を差し替えて使う）
# ---------------------------------------------------------------------------
INDEX_ROW = re.compile(
    r"\|\s*(?:\[)?第(\d+)条(?:\]\([^)]*\))?\s*\|\s*(?:\[([^\]]+)\]\([^)]+\)|([^|]+?))\s*\|"
)


def parse_index_titles(text: str) -> dict[int, str]:
    """一覧表 index.md から 条番号→タイトル を抽出。

    1 列目は `第N条` でも `[第N条](N.md)` でも拾う（両形式が混在している）。
    """
    titles: dict[int, str] = {}
    for m in INDEX_ROW.finditer(text):
        t = (m.group(2) or m.group(3) or "").strip()
        if t:
            titles[int(m.group(1))] = t
    return titles


def nav_entry_re(subdir: str) -> re.Pattern:
    """mkdocs.yml の「- 第N条（ラベル）: articles/<subdir>/N.md」にマッチする正規表現。"""
    return re.compile(
        r"^\s*-\s*第(\d+)条[（(]([^）)]*)[）)]\s*:\s*articles/"
        + re.escape(subdir)
        + r"/(\d+)\.md\s*$",
        re.MULTILINE,
    )


def parse_nav_titles(text: str, subdir: str) -> dict[int, str]:
    """mkdocs.yml から 条番号→nav ラベル を抽出（条番号とリンク先が一致する行のみ）。"""
    titles: dict[int, str] = {}
    for m in nav_entry_re(subdir).finditer(text):
        if m.group(1) == m.group(3):
            titles[int(m.group(1))] = m.group(2).strip()
    return titles


def nav_number_mismatches(text: str, subdir: str) -> list[tuple[int, int, str]]:
    """nav ラベルの条番号とリンク先 N.md が食い違う行を (ラベル条番号, ファイル条番号, ラベル) で返す。"""
    return [
        (int(m.group(1)), int(m.group(3)), m.group(2).strip())
        for m in nav_entry_re(subdir).finditer(text)
        if m.group(1) != m.group(3)
    ]


# ---------------------------------------------------------------------------
def self_test() -> int:
    """共有ロジック単体の退行テスト。各 audit スクリプトの --self-test から呼ばれる。"""
    cases: list[tuple[str, bool]] = []
    m = {
        13: "電路の絶縁", 14: "低圧電路の絶縁性能",
        36: "地絡遮断装置の施設", 37: "避雷器等の施設",
        64: "適用範囲", 83: "適用範囲",          # 正本内に重複見出しがある実例
        65: "低高圧架空電線路に使用する電線", 68: "低高圧架空電線の高さ",
        143: "電路の対地電圧の制限", 226: "低圧連系時の施設要件",
    }
    c = lambda n, s: classify(n, s, m)

    cases.append(("逐語一致は None", c(226, "低圧連系時の施設要件") is None))
    cases.append(("末尾補足を strip して一致", c(143, "電路の対地電圧の制限（住宅の屋内電路 150V）") is None))
    cases.append(("連続する末尾補足も strip", c(226, "低圧連系時の施設要件（第1項）（要点）") is None))
    cases.append(("全角空白差は吸収", c(226, "低圧　連系時の施設要件") is None))

    r = c(37, "地絡遮断装置の施設")
    cases.append(("他条見出しと逐語一致 → ERROR", r is not None and r[0] == "ERROR" and "第36条" in r[1]))
    r = c(68, "低高圧架空電線路に使用する電線")
    cases.append(("margin に届かない隣接条も逐語一致で ERROR",
                  r is not None and r[0] == "ERROR" and "第65条" in r[1]))

    # 正本内に同じ見出しの条が複数あっても、当該条と一致していれば OK
    cases.append(("重複見出しでも自条一致なら None（第64条↔第83条）", c(64, "適用範囲") is None))
    cases.append(("重複見出しの他方も None", c(83, "適用範囲") is None))

    r = c(14, "低圧電路の絶縁抵抗")
    cases.append(("包含による誤 ERROR を出さない", r is not None and r[0] == "WARN"))
    r = c(143, "住宅の屋内電路の対地電圧の制限")
    cases.append(("短縮/言い換えは WARN 止まり", r is not None and r[0] == "WARN"))
    r = c(999, "何らかの見出し")
    cases.append(("正本に無い条は MASTER_MISSING", r is not None and r[0] == "MASTER_MISSING"))

    cases.append(("括弧だけのタイトルは strip しすぎない", strip_supplement("（注記）") == "（注記）"))
    cases.append(("見出し途中の括弧は残す",
                  strip_supplement("35,000V（特高）を超える電線と建造物")
                  == "35,000V（特高）を超える電線と建造物"))

    idx = (
        "| 第226条 | [低圧連系時の施設要件](226.md) | — | 作成済み |\n"
        "| [第45条](45.md) | 燃料電池等の施設 | — | 作成済み |\n"
    )
    cases.append(("index の両形式を抽出",
                  parse_index_titles(idx) == {226: "低圧連系時の施設要件", 45: "燃料電池等の施設"}))

    nav = (
        "      - 第37条（避雷器等の施設）: articles/kaishaku/37.md\n"
        "      - 一覧: articles/kaishaku/index.md\n"
        "      - 第99条（ずれ）: articles/kaishaku/98.md\n"
        "      - 第5条（電路の絶縁）: articles/kijun/5.md\n"
    )
    cases.append(("nav は subdir で絞る",
                  parse_nav_titles(nav, "kaishaku") == {37: "避雷器等の施設"}))
    cases.append(("nav は他法令を混ぜない",
                  parse_nav_titles(nav, "kijun") == {5: "電路の絶縁"}))
    cases.append(("nav の条番号↔リンク先ズレを検出",
                  nav_number_mismatches(nav, "kaishaku") == [(99, 98, "ずれ")]))

    ok = True
    for name, passed in cases:
        print(("  PASS " if passed else "  FAIL ") + name)
        ok = ok and passed
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_test())
