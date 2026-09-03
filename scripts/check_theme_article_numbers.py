#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""themes/strategy 等のページが書く「省令第N条（見出し）」を articles/ の正本と突合する

## なぜ必要か（2026-07-26 制定・PR #154）

`themes/hoan-gensoku.md` と `strategy/trap-patterns.md` が **「保安原則＝省令第1条〜第4条」**
として第1条=人体・物件／第2条=電路の絶縁／第3条=機器の熱／第4条=他への損傷 と教えていた。
原典逐語照合の結果すべて誤りで、正しくは **第1条=用語の定義／第2条=電圧の種別等／
第3条=適用除外**、保安原則は **第三節（第4条〜第18条）** だった。

この誤りは長期間 CI 全緑のまま残存した。理由は既存チェッカーの守備範囲:

- `audit_titles.py`        … **articles/kijun/*.md の H1** が省令の条見出しと一致するか（記事側）
- `audit_kaishaku_titles.py` … kaishaku のファイル名↔H1↔index の整合（記事側）
- `check_law_citations.py` … 事業法等の**手続語**（認可/届出）整合（別軸）
- `wiki_check.py` / `mkdocs build` … §記号・リンク・構文（条番号は見ない）

→ **themes/strategy/reference など「記事以外のページ」が書く条番号は誰も検査していなかった。**
本スクリプトがその穴を埋める。正本は `articles/kijun/N.md`・`articles/kaishaku/N.md` の H1
（省令側は audit_titles.py が原典と照合済みなので、正本として使える）。

## 検出するもの

`省令第N条（見出し）` / `解釈第N条（見出し）` の**括弧内が正本タイトルと乖離**している箇所。
- 乖離が大きい → **ERROR**（他の条の見出しに一致するなら「第M条では？」と提案）
- 判定できない（正本記事が無い等） → skip（fail-open）

## 使い方

    python scripts/check_theme_article_numbers.py            # docs/ 全体（articles/ 以外）
    python scripts/check_theme_article_numbers.py --strict   # 検出時 exit 1（CI 用）
    python scripts/check_theme_article_numbers.py --self-test
"""
from __future__ import annotations

import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

# 「省令第5条（電路の絶縁）」「省令 第5条（…）」「解釈第218条（…）」
CITE = re.compile(r"(省令|解釈)\s*第\s*(\d+)\s*条(の\d+)?\s*[（(]([^）)]{2,40})[）)]")

# 「省令」「解釈」の直前に別法令の名が付いているものは、電技省令／電技解釈ではないので
# 突合対象から外す。CITE の「省令」は部分一致するため、そのままだと
# 「風技省令第5条（自動停止）」を電技省令第5条「電路の絶縁」と比べて必ず WARN になる
# （実測: themes/fusha.md:82,89・kakomon/wave-analysis.md:112 の3件。うち fusha.md:89 は
# 「電技省令第15条 vs 風技省令第5条 の区別」と、まさに両者を区別する正しい記述だった）。
OTHER_LAW_PREFIX = ("風技", "風力", "施行", "工事士", "用品", "報告", "内線", "太陽電池")

# 括弧内がタイトルでない（説明・注記）と分かるものは対象外
NON_TITLE_HINTS = ("参照", "抜粋", "再掲", "後述", "前述", "詳細", "以下", "上記", "同上",
                   "根拠", "関連", "旧", "新", "例", "注", "実在せず", "のみ")

# **是正記録の行**は旧誤記を意図的に引用するため対象外にする
# （例: 「旧記述は本条を『省令第4条（…）』としていたが誤り」）
CORRECTION_HINTS = ("旧記述", "としていた", "は誤り", "誤りだった", "是正", "訂正")

# 乖離とみなす類似度のしきい値
SIM_ERROR = 0.35      # これ未満は明確な不一致
SIM_OK = 0.60         # これ以上なら一致とみなす（略称・省略を許容）


def norm(s: str) -> str:
    """比較用に正規化（記号・空白・接頭辞を落とす）。"""
    s = re.sub(r"[\s　、，,・（）()「」【】]", "", s)
    s = s.replace("等", "").replace("の防止", "").replace("防止", "")
    return s


def sim(a: str, b: str) -> float:
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def load_master() -> dict[tuple[str, int], str]:
    """{(法令, 条番号): 見出し} を articles/ の H1 から作る。

    「省令」は電技省令だけでなく**風技省令（発電用風力設備）**も指しうるため、
    `articles/furyoku/N.md` を別キー ("省令風力", N) として持ち、判定時の
    代替候補にする（風車ページの「省令第5条」を電技省令と誤突合しないため）。
    """
    master: dict[tuple[str, int], str] = {}
    for law, sub in (("省令", "kijun"), ("解釈", "kaishaku"), ("省令風力", "furyoku")):
        d = DOCS / "articles" / sub
        if not d.is_dir():
            continue
        for f in d.glob("*.md"):
            if not f.stem.isdigit():
                continue
            try:
                text = f.read_text(encoding="utf-8")
            except Exception:
                continue
            m = re.search(r"^#\s+.*?第\s*(\d+)\s*条\s*[—\-–]\s*(.+?)\s*$", text, re.M)
            if not m:
                continue
            if int(m.group(1)) != int(f.stem):
                continue  # ファイル名と H1 の条番号が不一致＝audit_*_titles.py の担当
            master[(law, int(f.stem))] = m.group(2).strip()

    # 記事ファイルが無い解釈条は、原典由来マスタ（令和7年11月版告示PDFから抽出した
    # 233条の条番号↔条見出し）で埋める。
    # 事故: 正本を「存在する記事の H1」だけに頼っていたため、記事が無い条（第34条・
    # 第61条・第153条・第181条 等）を引用した誤りが truth is None で fail-open になり、
    # CI 全緑のまま残っていた（2026-07-28 監査で4件検出）。
    # 記事 H1 は audit_kaishaku_titles.py --external が原典照合済みなので優先する。
    for num_s, title in _load_kaishaku_master().items():
        if not num_s.isdigit() or not title:
            continue
        master.setdefault(("解釈", int(num_s)), title)
    return master


def _load_kaishaku_master() -> dict[str, str]:
    """_data/kaishaku_article_titles.json の {条番号: 条見出し}（読めなければ空）。"""
    path = ROOT / "_data" / "kaishaku_article_titles.json"
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8")).get("解釈", {}) or {}
    except Exception:
        return {}  # fail-open（従来どおり記事 H1 だけで判定）


def scan(master: dict[tuple[str, int], str], targets: list[Path]) -> list[str]:
    findings: list[str] = []
    for f in targets:
        rel = f.relative_to(ROOT).as_posix()
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
        except Exception:
            continue
        # フェンスの扱い: 言語タグ付き（```python / ```mermaid 等）は本物のコードなので
        # 従来どおりスキップする。一方、**タグ無しの ``` フェンス**は本 repo では
        # 「法的根拠ピラミッド」等の**学習コンテンツ**（学習者にはそのまま表示される）
        # なので検査対象にする。
        # 事故: themes/hogo-sochi.md・shijimono.md・shiyo-basho.md のピラミッドが
        # タグ無しフェンス内にあり、条番号の誤帰属が丸ごと検査対象外になっていた
        # （2026-07-28 監査で検出）。
        fence = False
        fence_is_code = False
        for ln, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```"):
                if not fence:
                    fence = True
                    fence_is_code = bool(stripped[3:].strip())  # 言語タグの有無
                else:
                    fence = False
                    fence_is_code = False
                continue
            if fence and fence_is_code:
                continue
            if any(h in line for h in CORRECTION_HINTS):
                continue  # 是正記録の行（旧誤記の引用）
            for m in CITE.finditer(line):
                law, num_s, branch, claimed = (
                    m.group(1), m.group(2), m.group(3), m.group(4).strip()
                )
                # 枝番（第34条の2 等）は正本マスタに見出しが無く、本条の見出しと
                # 突合すると必ず誤検出になる（例: 解釈第34条の2「高圧受電設備の保護装置」を
                # 第34条「…過電流遮断器の性能等」と比較）。判定不能として skip（fail-open）。
                if branch:
                    continue
                if any(h in claimed for h in NON_TITLE_HINTS):
                    continue
                # 直前が別法令名なら電技省令／電技解釈ではない（他法令混同の誤検出を防ぐ）
                if any(line[max(0, m.start() - len(x)):m.start()] == x
                       for x in OTHER_LAW_PREFIX):
                    continue
                num = int(num_s)
                truth = master.get((law, num))
                if truth is None:
                    continue  # 正本記事なし＝判定不能（fail-open）
                if sim(claimed, truth) >= SIM_OK:
                    continue
                # 「省令」が**風技省令**を指している可能性（風車ページ等）は誤検出なので除外
                if law == "省令":
                    alt = master.get(("省令風力", num))
                    if alt and sim(claimed, alt) >= SIM_OK:
                        continue
                # 他の条の見出しに強く一致する＝**高確信の誤り**（ERROR）
                best_num, best_s = None, 0.0
                for (l2, n2), t2 in master.items():
                    if l2 != law or n2 == num:
                        continue
                    s2 = sim(claimed, t2)
                    if s2 > best_s:
                        best_num, best_s = n2, s2
                if best_num is not None and best_s >= SIM_OK:
                    findings.append(
                        f"ERROR {rel}:{ln}: {law}第{num}条（{claimed}）… 正本は「{truth}」"
                        f" → **第{best_num}条**（{master[(law, best_num)]}）では？"
                    )
                elif sim(claimed, truth) < SIM_ERROR:
                    # 括弧内が内容説明（例: 解釈第14条（絶縁抵抗））のことも多い＝WARN 止まり
                    if warn_suppressed(rel):
                        continue
                    findings.append(
                        f"WARN  {rel}:{ln}: {law}第{num}条（{claimed}）… 正本は「{truth}」"
                        f"（見出しでなく内容説明なら問題なし）"
                    )
    return findings


def targets_under_docs() -> list[Path]:
    """docs/ 全体。articles/ も含む。

    当初は articles/ を除外していた（「記事側の H1 は audit_titles.py が原典と照合済み
    だから正本として信頼できる」）。しかしそれが守るのは**そのページ自身の見出し**だけで、
    **記事ページが他の条を引用する記述**は誰も検査していなかった。実測 2026-08-30 で
    ERROR 11件が出た（省令第4条を「電気設備の損傷防止」と書く4箇所・解釈第65条を
    「架空電線の高さ」と書く3箇所・解釈第220条を「低圧/高圧の定義」とする2箇所ほか）。

    ただし articles/ を入れると WARN は 13→108 に増え、実害のある1件が埋もれる。
    WARN は「括弧内が内容説明なら問題なし」の弱い信号なので、**articles/ では
    ERROR だけを出す**（下記 emit 側で抑制）。
    """
    return sorted(DOCS.rglob("*.md"))


def warn_suppressed(rel: str) -> bool:
    """articles/ の WARN は出さない（ERROR は出す）。上記 docstring の理由による。"""
    return rel.startswith("articles/") or "/articles/" in rel


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    cases = []
    master = {("省令", 1): "用語の定義", ("省令", 5): "電路の絶縁",
              ("省令", 18): "電気設備による供給支障の防止",
              ("省令", 20): "電線路等の感電又は火災の防止",
              ("解釈", 218): "IEC60364規格の適用"}

    import tempfile
    import os

    def run(body: str):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "t.md"
            p.write_text(body, encoding="utf-8")
            global ROOT
            old = ROOT
            ROOT = Path(td)
            try:
                return scan(master, [p])
            finally:
                ROOT = old

    # 1) 正しい引用は通す
    cases.append(("正しい引用はPASS", run("省令第5条（電路の絶縁）は…") == []))

    # 2) hoan-gensoku 事案: 第2条（電路の絶縁）→ 第5条を提案
    r = run("保安原則の省令第1条（電路の絶縁）を覚える")
    cases.append(("誤った条番号をERROR検出",
                  len(r) == 1 and r[0].startswith("ERROR") and "第5条" in r[0]))

    # 3) 章名を条見出しと取り違えた事案（第20条）
    r3 = run("省令第20条（電気供給のための電気設備の施設）は供給の確実性")
    cases.append(("章名との取り違えを検出", len(r3) == 1))
    # 是正記録の行（旧誤記の引用）は対象外
    cases.append(("是正記録は無視",
                  run("旧記述は本条を「省令第1条（電路の絶縁）」としていたが誤り") == []))
    # 風技省令の条を電技省令と誤突合しない
    master["省令風力", 5] = "風車の安全な状態の確保"
    cases.append(("風技省令は誤検出しない", run("省令第5条（風車の安全な状態の確保）") == []))

    # 4) 略称・省略は許容（誤検出しない）
    cases.append(("略称はPASS", run("省令第18条（供給支障の防止）") == []))

    # 5) 言語タグ付きフェンス（本物のコード）は対象外
    cases.append(("タグ付きフェンスは無視",
                  run("```python\n# 省令第1条（電路の絶縁）\n```") == []))

    # 6) タグ無しフェンス（法的根拠ピラミッド等の学習コンテンツ）は検査する
    #    2026-07-28: themes の条番号誤帰属がここに隠れて CI 全緑だった事案
    cases.append(("タグ無しフェンスは検査する",
                  len(run("```\n🟩 省令第1条（電路の絶縁）\n```")) == 1))

    # 7) タグ無しフェンスを抜けた後も検査が継続する（状態リークしない）
    cases.append(("フェンス閉じ後も検査継続",
                  len(run("```\nx\n```\n省令第1条（電路の絶縁）")) == 1))

    # 8) 枝番（第N条のM）は正本に見出しが無いので判定しない（誤検出防止）
    cases.append(("枝番は判定しない",
                  run("解釈第218条の2（何らかの見出し）") == []))

    # 6) 注記系の括弧は対象外
    cases.append(("注記括弧は無視", run("省令第1条（詳細は後述）") == []))

    # 7) 正本記事が無い条は fail-open
    cases.append(("正本なしはskip", run("省令第999条（架空の見出し）") == []))

    # 8) 解釈も検査対象
    r8 = run("解釈第218条（電路の絶縁）")
    cases.append(("解釈も検査", len(r8) == 1))

    ok = True
    for name, passed in cases:
        print(("  PASS " if passed else "  FAIL ") + name)
        ok = ok and passed
    print("self-test:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    strict = "--strict" in argv
    files = [Path(a) for a in argv[1:] if not a.startswith("-")]
    targets = files or targets_under_docs()
    master = load_master()
    if not master:
        print("OK check_theme_article_numbers: 正本（articles/）が読めないため skip")
        return 0
    findings = scan(master, targets)
    errors = [x for x in findings if x.startswith("ERROR")]
    warns = [x for x in findings if x.startswith("WARN")]
    show_warn = "--all" in argv
    if errors:
        print("NG check_theme_article_numbers: ERROR %d 件（条番号↔見出しの明確な不一致）"
              % len(errors))
        for x in errors:
            print("  " + x)
    else:
        print("OK check_theme_article_numbers: ERROR 0 件（正本 %d 条・対象 %d ファイル）"
              % (len(master), len(targets)))
    if warns:
        print("  （WARN %d 件 — 括弧内が内容説明なら問題なし。--all で表示）" % len(warns))
        if show_warn:
            for x in warns:
                print("  " + x)
    return 1 if (errors and strict) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
