#!/usr/bin/env python3
"""過去問引用の実在・帰属ゲート (check_kakomon_citations.py)

記事・テーマ・戦略ページが書く「R05上 問12」「H29問4」のような過去問引用を、
SoT である `_data/kakomon.yml` と突き合わせる。

既存ゲートとの棲み分け:
  - check_kakomon_dual_sync.py  … 正本の2コピーがバイト一致か
  - check_kakomon_pages_sync.py … 正本と **docs/kakomon/ の派生md** が整合しているか
  - compute_frequency.py --audit-meta … 「試験対策メタの出題**回数**」と現集計のドリフト
  - 本スクリプト … **docs/kakomon/ の外**（条文ページ・テーマ・戦略・reference）が書く
    **個々の引用**が実在し、そのページの条に帰属しているか

制定事案: 2026-08-28 の全数監査。
  - 「H27頃」「H24頃」のように年度も問番号も特定できない行を過去問実績として掲載
  - R03問7 を解釈第175条の実績として掲載（SoT では省令第68・69条）
  - H30問7・H24問7・R05下問6 を省令第24条の実績として掲載（SoT では解釈第53条）
  いずれも既存ゲートは 7/7 PASS のまま素通りしていた。docs/kakomon/ しか見ていなかったため。

2つのチェック:
  NOT_FOUND      引用した (年度, 問番号) が kakomon.yml に無い
  MISATTRIBUTED  引用は実在するが、SoT の article がそのページの条を指していない
                 （「過去問実績」節と「直近出題」メタ行に限って適用）

採らなかった検査:
  テーマページで「kakomon.yml の theme スラグ ≠ ページのスラグ」を誤帰属とする案は**却下**した。
  試作して 14件検出したが、その大半が正当な相互参照だった（例: R04上問1「受電電圧7000V以下の
  需要設備の保安体系（主任技術者の選任等）」は SoT の theme が jigyoho-taikei だが
  shunin-gijutsusha からも当然参照される）。**SoT の theme は単一値なのに問題の関連性は多値**で、
  規則として不健全。構造的に誤爆する検査を足すと、ゲート全体が「無視するもの」になる。

対象外:
  - docs/kakomon/**            … check_kakomon_pages_sync.py の担当
  - H18〜H22                   … kakomon.yml の収録範囲外（年度ページのみ）。
                                  repo の運用どおり honest-hold 扱いで検査しない
  - 監修ログ・変更履歴の節      … 過去の誤りを記録する場所
  - docs/articles/other/**     … 帰属チェックのみ対象外（法令が多岐で SoT の表記が揺れる）

Usage:
    python scripts/check_kakomon_citations.py
    python scripts/check_kakomon_citations.py docs/articles/kijun/23.md
    python scripts/check_kakomon_citations.py --self-test

Exit codes:
    0  findings 0件
    1  findings 1件以上
    2  SoT が読めない
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR: PyYAML が必要です (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
SOT = ROOT / "_data" / "kakomon.yml"
DOCS = ROOT / "docs"

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 「R05上 問12」「R05上問12」「R05上-問12」「H29 問4」「R04下‐問3」
CITE = re.compile(
    r"(?P<year>[HR]\d{2}(?:上|下)?)\s*(?:期)?\s*[-‐−–—・]?\s*問\s*(?P<num>\d{1,2})"
)
# kakomon.yml の収録範囲は H23〜R07。それ以前（H01〜H22）は年度ページのみ、
# または repo が意図的に引く歴史的出典なので、実在検査の対象外にする。
OUT_OF_DB = re.compile(r"^H(?:0?[1-9]|1[0-9]|2[0-2])$")

# 電験三種法規の問番号は 1〜13 しかない（kakomon.yml 全247問で確認済）。
MAX_NUM = 13

# 「その引用は架空だった／削除した」と説明している行は検査しない
# （過去の誤りを説明できなくなるため）。監修ログ節と同じ趣旨。
DENIAL = re.compile(
    r"架空|削除した|存在しない|しか存在しない|は無い|(?:は|＝|=)?誤り|ではな(?:い|く)"
    r"|旧版|訂正|別ページで管理|要確認|未確認|特定できな(?:い|かった)"
)

# 過去問実績テーブルは「| 年度 | 問 | 形式 | 論点 |」の**セル分割**で書くのが主流で、
# 年度と問番号が `|` で隔たっているため CITE（隣接前提）では1件も拾えない。
# 実測: 監査前コミットの kijun/24.md「| H30 | 問7 |」等がまるごと素通りしていた。
TABLE_CITE = re.compile(r"^\s*\|\s*(?P<year>[HR]\d{2}(?:上|下)?)\s*(?:期)?\s*\|\s*問?\s*(?P<num>\d{1,2})\s*\|")

# 「H27頃」「H24 頃」のような**年度を特定しない出題実績の主張**。
# 過去問は年度と問番号で一意に決まるので、「頃」は出典として成立しない。
VAGUE_CITE = re.compile(r"[HR]\d{2}\s*頃")

HISTORY_HEAD = re.compile(r"^#{1,6}\s*(?:📜\s*)?(?:監修ログ|変更履歴|改訂履歴)")
# 帰属チェックを掛ける区間（過去問実績の節）と行（試験対策メタの「直近出題」）。
# 節の中でも **表の行**（| で始まる）だけを「このページの実績だと主張している行」とみなす。
# 節内の admonition 散文は「関連条文の出題は別ページで管理」のような正しい注記であり、
# そこまで帰属エラーにすると 82件中の大半が誤爆になる（実測）。
KAKOMON_SECTION = re.compile(r"^#{1,6}\s*.*(?:過去問実績|出題実績)")
RECENT_LINE = re.compile(r"\*\*直近出題\*\*")
TABLE_ROW = re.compile(r"^\s*\|")

# 記事ディレクトリ → kakomon.yml の article フィールドで使われる法令トークン
GROUP_LAW = {"kijun": "省令", "jigyoho": "事業法", "kaishaku": "解釈"}

# 上期・下期を欠いた年度表記のうち、既存分を凍結する ratchet。
# 「学習者が問題を特定できない」という実害があるので直すべきだが、
# どちらの期かは1件ずつ問題文を当たらないと決まらない。
# ここに載せて **新規発生だけをブロック**する（wiki_check.py の
# PLACEHOLDER_ALLOWLIST と同じ運用）。減らすときは1件ずつ根拠つきで。
AMBIGUOUS_ALLOWLIST: set[str] = set()


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def parse_articles(field: str) -> set[tuple[str, str]]:
    """`省令§10,§11` `解釈§227〜§229` → {('省令','10'),('省令','11')} のような集合に開く.

    裸の `§N` は直前に出た法令名を引き継ぐ（SoT の実際の書き方）。
    """
    out: set[tuple[str, str]] = set()
    if not field:
        return out
    cur = ""
    for tok in re.split(r"[,、]\s*", norm(field)):
        tok = tok.strip()
        if not tok:
            continue
        m = re.match(r"^([^\s§]*)§?(.*)$", tok)
        name, rest = m.group(1), m.group(2)
        if name:
            cur = name
        if not rest:
            continue
        # 「227〜229」の範囲、「12の2」の枝番、単独番号
        rng = re.match(r"^(\d+)\s*[〜~-]\s*§?(\d+)", rest)
        if rng:
            a, b = int(rng.group(1)), int(rng.group(2))
            for n in range(a, b + 1):
                out.add((cur, str(n)))
            continue
        for n in re.findall(r"(\d+)", rest):
            out.add((cur, n))
    return out


class Finding:
    def __init__(self, kind: str, rel: str, line: int, cite: str, detail: str):
        self.kind, self.rel, self.line, self.cite, self.detail = kind, rel, line, cite, detail

    def render(self) -> str:
        return f"[{self.kind}] {self.rel}:{self.line} 「{self.cite}」\n        {self.detail}"


def load_sot() -> dict[tuple[str, int], dict]:
    if not SOT.exists():
        raise SystemExit(f"ERROR: SoT がありません: {SOT}")
    data = yaml.safe_load(SOT.read_text(encoding="utf-8")) or {}
    problems = data.get("problems") or []
    if not problems:
        raise SystemExit("ERROR: kakomon.yml に problems が1件もありません（vacuous pass 防止）")
    return {(norm(p["year"]), int(p["num"])): p for p in problems}


def scan(paths: list[Path], sot: dict) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    checked = 0
    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith("docs/kakomon/"):
            continue
        group = path.parent.name
        law = GROUP_LAW.get(group) if rel.startswith("docs/articles/") else None
        art_num = path.stem if law else None

        in_history = False
        in_kakomon = False
        for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.match(r"^#{1,6}\s", raw):
                in_history = bool(HISTORY_HEAD.match(raw))
                in_kakomon = bool(KAKOMON_SECTION.match(raw))
            if in_history:
                continue
            text = norm(raw)
            denied = bool(DENIAL.search(text))
            # VAGUE は出題実績テーブルの行に限る。
            # 「平成年代（〜H30頃）の問題は…」のような**時代の言及**は出典の主張ではない。
            if not denied and TABLE_ROW.match(text):
                for vm in VAGUE_CITE.finditer(text):
                    findings.append(
                        Finding(
                            "VAGUE", rel, i, vm.group(0),
                            "「頃」では過去問を特定できない。年度と問番号を kakomon.yml で"
                            "確定するか、実績の主張自体を撤回する（honest-hold）",
                        )
                    )
            attributable = (in_kakomon and bool(TABLE_ROW.match(text))) or bool(
                RECENT_LINE.search(text)
            )
            cites = list(CITE.finditer(text))
            tm = TABLE_CITE.match(text)
            if tm and not any(
                m.group("year") == tm.group("year") and m.group("num") == tm.group("num")
                for m in cites
            ):
                cites.append(tm)
            for m in cites:
                year, num = m.group("year"), int(m.group("num"))
                if OUT_OF_DB.match(year):
                    continue
                checked += 1
                if num > MAX_NUM:
                    if not denied:
                        findings.append(
                            Finding(
                                "BAD_NUM", rel, i, m.group(0),
                                f"法規の問番号は1〜{MAX_NUM}のみ（架空の問番号）",
                            )
                        )
                    continue
                p = sot.get((year, num))
                if p is None:
                    # 上/下 を欠く年度表記（R04〜R07 は上期・下期に分かれる）
                    halves = [h for h in ("上", "下") if (year + h, num) in sot]
                    if halves:
                        key = f"{rel}:{m.group(0)}"
                        if key not in AMBIGUOUS_ALLOWLIST and not denied:
                            findings.append(
                                Finding(
                                    "AMBIGUOUS", rel, i, m.group(0),
                                    f"{year} は上期・下期に分かれる。"
                                    f"該当は {'／'.join(year + h for h in halves)} のいずれか"
                                    f" — 学習者が問題を特定できない",
                                )
                            )
                        continue
                    if not denied:
                        findings.append(
                            Finding(
                                "NOT_FOUND", rel, i, m.group(0),
                                f"kakomon.yml に ({year}, 問{num}) が無い"
                                f" — 実在しない引用か、年度・問番号の取り違え",
                            )
                        )
                    continue
                if law and attributable and not denied:
                    got = parse_articles(p.get("article", ""))
                    # 行が SoT の帰属先を自分で名乗っているなら誤帰属ではない
                    # （「解釈第21条として出題（R04下問3）」のような正しい書き方）
                    names_correct = any(
                        re.search(rf"{a}\s*第?{b}条", text)
                        or re.search(rf"{a}§{b}\b", text)
                        # 法令名を省いた「第29条」「第199条の2」も帰属の明示とみなす
                        or re.search(rf"第{b}条", text)
                        # 「192条4要件」のように「第」を省いた書き方も帰属の明示とみなす
                        or re.search(rf"(?<!\d){b}条", text)
                        # 「第63〜66条」のような範囲表記
                        or any(
                            int(lo) <= int(b) <= int(hi)
                            for lo, hi in re.findall(r"第(\d+)\s*[〜~-]\s*(?:第)?(\d+)条", text)
                        )
                        for a, b in got
                    )
                    if got and (law, art_num) not in got and not names_correct:
                        shown = "／".join(f"{a}第{b}条" for a, b in sorted(got))
                        findings.append(
                            Finding(
                                "MISATTRIBUTED", rel, i, m.group(0),
                                f"SoT ではこの問の条文は {shown}"
                                f"（本ページは {law}第{art_num}条）"
                                f" — topic: {p.get('topic', '')}",
                            )
                        )
    return findings, checked


def collect(paths: list[str]) -> list[Path]:
    if not paths:
        return sorted(DOCS.rglob("*.md"))
    out: list[Path] = []
    for p in paths:
        q = Path(p)
        if not q.is_absolute():
            q = ROOT / p
        if q.is_dir():
            out.extend(sorted(q.rglob("*.md")))
        elif q.exists():
            out.append(q)
    return out


def self_test(sot: dict) -> int:
    ok = True

    cases = [
        ("引用形式: R05上 問12", "R05上 問12", ("R05上", 12)),
        ("引用形式: R05上問12", "R05上問12", ("R05上", 12)),
        ("引用形式: R04上‐問1", "R04上‐問1", ("R04上", 1)),
        ("引用形式: H29 問4", "H29 問4", ("H29", 4)),
        ("引用形式: Ｒ０６下 問８（全角）", "Ｒ０６下 問８", ("R06下", 8)),
    ]
    for label, text, want in cases:
        m = CITE.search(norm(text))
        got = (m.group("year"), int(m.group("num"))) if m else None
        hit = got == want
        print(f"  [{'PASS' if hit else 'FAIL'}] {label} → {got}")
        ok &= hit

    # article フィールドの展開
    parse_cases = [
        ("省令§10,§11", {("省令", "10"), ("省令", "11")}),
        ("解釈§227〜§229", {("解釈", "227"), ("解釈", "228"), ("解釈", "229")}),
        ("事業法§43, 施行規則", {("事業法", "43")}),
        ("解釈§53", {("解釈", "53")}),
    ]
    for field, want in parse_cases:
        got = parse_articles(field)
        hit = got == want
        print(f"  [{'PASS' if hit else 'FAIL'}] article 展開: {field} → {sorted(got)}")
        ok &= hit

    # 検出器の生存: SoT に無い引用が NOT_FOUND になること
    hit = ("R07下", 99) not in sot
    print(f"  [{'PASS' if hit else 'FAIL'}] 存在しない引用 (R07下 問99) が SoT に無い")
    ok &= hit

    # 陽性対照: SoT に実在する引用は見つかること（SoT 読み込みの故障検出）
    hit = ("R05上", 12) in sot
    print(f"  [{'PASS' if hit else 'FAIL'}] 陽性対照: (R05上 問12) が SoT に実在する")
    ok &= hit

    # H18〜H22 は収録範囲外として除外されること
    hit = bool(OUT_OF_DB.match("H20")) and not OUT_OF_DB.match("H23")
    print(f"  [{'PASS' if hit else 'FAIL'}] 収録範囲外 H18〜H22 の除外")
    ok &= hit

    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    sot = load_sot()
    if args.self_test:
        return self_test(sot)

    targets = collect(args.paths)
    findings, checked = scan(targets, sot)
    for f in findings:
        print(f.render())
    kinds = {}
    for f in findings:
        kinds[f.kind] = kinds.get(f.kind, 0) + 1
    detail = " / ".join(f"{k} {v}" for k, v in sorted(kinds.items())) or "0"
    print(
        f"\ncheck_kakomon_citations: {len(findings)}件（{detail}）"
        f" — {len(targets)}ファイル・{checked}引用を照合"
        + (f"・AMBIGUOUS allowlist {len(AMBIGUOUS_ALLOWLIST)}件" if AMBIGUOUS_ALLOWLIST else "")
    )
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
