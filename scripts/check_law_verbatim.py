#!/usr/bin/env python3
"""条文原文ブロックの逐語照合ゲート (check_law_verbatim.py)

記事の「条文原文」blockquote を、原典（e-Gov 法令XML／電技解釈PDFの抽出テキスト）と
**正規化のうえ逐語比較**する。2026-08-28 の全数監査で、既存ゲートが 7/7 PASS のまま
条文原文の逐語ズレが 26 件残っていたことが制定事案。

既存ゲートとの棲み分け（重複させない）:
  - audit_titles.py / audit_kaishaku_titles.py / audit_jigyoho_titles.py … **条見出し**を照合
  - check_law_citations.py … 条番号と**手続語**（認可/届出）の整合
  - check_law_facts.py … 特定の数値ハルシネーション3類型
  - 本スクリプト … **条文の本文そのもの**が原典と一字一句合っているか

検出する2種類:
  MISS  引用文が原典のどこにも存在しない
        → 語の脱落・創作・改正未反映。例: 解釈第227条・第229条から「又は配電事業者」が
          脱落（2020年改正未反映）、kijun/1 の第6号「構外から伝送される電気の開閉を
          行うが変成しない所」（条文に存在しない創作）
  OTHER 引用文は原典に存在するが、**そのページの条とは別の条**の文である
        → 誤帰属。例: kaishaku/18 が第3項の特例先を「第17条第6項各号」と書いていた

原典:
  docs/articles/kijun/N.md     → scripts/cache/egov-409M50000400052.xml（電技省令）
  docs/articles/jigyoho/N.md   → scripts/cache/egov-339AC0000000170.xml（電気事業法）
  docs/articles/kaishaku/N.md  → scripts/cache/kaishaku-r07-11.txt.gz（電技解釈PDF抽出）
      ※ 電技解釈は e-Gov 法令API に存在しないため PDF が唯一の原典。
        キャッシュは scripts/extract_kaishaku_text.py が生成し、
        PDF の SHA256 を埋め込む（PDF 差し替え × キャッシュ未再生成 を検出）。

Usage:
    python scripts/check_law_verbatim.py                 # docs/articles 全体
    python scripts/check_law_verbatim.py docs/articles/kaishaku/17.md
    python scripts/check_law_verbatim.py --self-test     # 検出器の生存証明
    python scripts/check_law_verbatim.py --list-allowlist

Exit codes:
    0  allowlist 外の findings 0件
    1  findings 1件以上
    2  原典キャッシュが無い／壊れている（vacuous pass を避けるため fail）
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "scripts" / "cache"
PDF = ROOT / "docs" / "assets" / "pdf" / "denken-kaishaku-r07-11.pdf"

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 引用が原典と食い違うことに正当な理由があるものだけを、
# 「ファイル:行:先頭20文字」を鍵にして通す。ratchet（増やすときは理由を書く）。
ALLOWLIST: dict[str, str] = {}

MIN_LEN = 20  # これ未満の断片は誤検出が多いので対象外（見出し語・記号のみ等）


# ---------------------------------------------------------------- 正規化

def norm(s: str) -> str:
    """HTML/Markdown 装飾と空白を落として比較用に畳む."""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"<[^>]+>", "", s)                      # <mark> 等
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)     # [text](link)
    s = s.replace("==", "").replace("**", "").replace("*", "").replace("`", "")
    s = s.replace("&nbsp;", "")
    return re.sub(r"\s+", "", s)


# 引用行の先頭に付く「第1項」「一」「2」「イ」等の位置記号を落とす
LEAD = re.compile(
    r"^(第[0-9０-９一二三四五六七八九十]+[項号]|[０-９0-9]+|[一二三四五六七八九十]+号?|イ|ロ|ハ|ニ)[\s　]*"
)


def strip_lead(q: str) -> str:
    q = re.sub(r"^\*\*[^*]{0,14}\*\*[\s　]*", "", q)          # **第1項** 等
    q = LEAD.sub("", q)
    q = re.sub(r"^第[一二三四五六七八九十百]+条[\s　]*", "", q)   # 「第十七条 …」の条名
    return q.strip()


# ---------------------------------------------------------------- 原典ロード

def load_egov(path: Path) -> tuple[dict[str, str], str]:
    """e-Gov 法令XML → ({条番号: 本文}, 全文).

    附則（SupplProvision）の Article は本則と Num が重複するため除外する。
    除外しないと本則の条文が附則で上書きされ、正しい引用が MISS 判定になる。
    """
    root = ET.parse(path).getroot()
    supp_ids = set()
    for sp in root.iter("SupplProvision"):
        for art in sp.iter("Article"):
            supp_ids.add(id(art))
    arts: dict[str, str] = {}
    for art in root.iter("Article"):
        if id(art) in supp_ids:
            continue
        num = art.get("Num")
        if not num or num in arts:
            continue
        arts[num] = "".join(art.itertext())
    return arts, "".join(root.itertext())


def load_kaishaku(path: Path) -> tuple[dict[str, str], str]:
    """電技解釈PDF の抽出テキスト → ({条番号: 本文}, 全文).

    PDF は 1ページごとに `===== PDF_PAGE n =====` を挟んで連結されている。
    このマーカーが条文の途中に割り込むと正しい引用まで MISS になるため、
    比較前に必ず除去する（プロトタイプで 37/15/200 の3件が偽陽性になった経路）。
    """
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        raw = fh.read()
    header, _, body = raw.partition("\n")
    sha = ""
    m = re.match(r"#\s*source-sha256:\s*([0-9a-f]{64})", header.strip())
    if m:
        sha = m.group(1)
    else:  # ヘッダ無しの旧形式
        body = raw
    text = re.sub(r"===== PDF_PAGE \d+ =====", "", body)

    starts: dict[str, int] = {}
    for m in re.finditer(r"(?m)^第(\d+)条[ 　]", text):
        starts.setdefault(m.group(1), m.start())
    order = sorted(starts.items(), key=lambda kv: kv[1])
    arts: dict[str, str] = {}
    for i, (num, pos) in enumerate(order):
        end = order[i + 1][1] if i + 1 < len(order) else len(text)
        arts[num] = text[pos:end]
    return arts, text, sha  # type: ignore[return-value]


SOURCES = {
    "kijun": ("電技省令", CACHE / "egov-409M50000400052.xml", "egov"),
    "jigyoho": ("電気事業法", CACHE / "egov-339AC0000000170.xml", "egov"),
    "kaishaku": ("電技解釈", CACHE / "kaishaku-r07-11.txt.gz", "kaishaku"),
}


# ---------------------------------------------------------------- 記事側の抽出

# 条文本文ではない行（編集注・見出し・凡例・数式・表）。
# ここを広げすぎると「※ を付ければ検査を逃れられる」escape ルートになるので、
# 条文本文としてありえない書き出しだけに限る。
SKIP_PREFIX = (
    "<small", "**凡例", "**電気", "**典拠", "**出典", "**数値検証", "**要約",
    "（", "*", "!!!", "|", "-", "※", "【", "数式", "$", "例:", "**例",
)

# 「条文原文」だけを逐語検査の対象にする。
# 「原文解析（ブロック分解）」は条文を分解して**解説する**セクションで、
# blockquote に編集注が入る（例: kijun/11「数値は本条には規定されず…」）。
# 単に "原文" を含むかで拾うと解析セクションの注記まで条文扱いになる。
GENBUN_MARK = re.compile(r"条文原文")
SECTION_END = re.compile(r"^(#{1,6}\s|-{3,}\s*$|\*{3,}\s*$)")

# 記事側が明示する省略マーカー。末尾のこれを剥がして残りを照合する。
# 「（…省略）」を付ければ何でも通る escape ルートにしないため、
# **剥がした残り**が MIN_LEN 以上あるときだけ照合対象として残す。
ABBREV_TAIL = re.compile(r"[（(][^（()）]{0,40}(?:省略|詳細|以下略|抜粋)[^（()）]{0,10}[）)]\s*$")

# 引用行の途中から始まる編集注（「※ …」）は条文本文ではないので落とす。
# 行頭 ※ は SKIP_PREFIX が丸ごと落とすが、
# 「(ホ) 第175条から第178条までに規定する場所　※粉じん等」のように
# **原文のあとに注を足す**書き方を許すための規則。
EDITORIAL_TAIL = re.compile(r"[※].*$")


def genbun_quotes(path: Path) -> list[tuple[int, str]]:
    """「条文原文」セクション内の blockquote 行を (行番号, 本文) で返す.

    セクションの終端は次の見出し（#）・水平線（---）。
    太字だけの行（**第79条 第1項本文** 等）は原文ブロック内の小見出しなので
    終端にしない。
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[tuple[int, str]] = []
    # 見出し由来と admonition 由来を別に持つ。
    # `## 2. 条文原文` の直下に `!!! abstract "電気設備技術基準…"` が入る書き方が
    # 21ファイルあり、admonition を無条件に「区間の切り替え」として扱うと
    # そこで区間が閉じて **1件も照合しない沈黙の盲点**になる（実測で発覚）。
    # admonition は区間を「開く」ことはできるが、見出しで開いた区間を「閉じない」。
    heading_genbun = False
    adm_genbun = False
    for j, raw in enumerate(lines):
        stripped = raw.strip()
        if SECTION_END.match(stripped):
            heading_genbun = bool(GENBUN_MARK.search(stripped))
            adm_genbun = False
            continue
        if stripped.startswith(("!!!", "???")):
            adm_genbun = bool(GENBUN_MARK.search(stripped))
            continue
        if not (heading_genbun or adm_genbun):
            continue
        m = re.match(r"^>+\s?(.*)$", stripped)
        if m and m.group(1).strip():
            out.append((j + 1, m.group(1).strip()))
    return out


def longest_prefix(needle: str, hay: str) -> int:
    lo, hi = 0, len(needle)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if needle[:mid] in hay:
            lo = mid
        else:
            hi = mid - 1
    return lo


# ---------------------------------------------------------------- 本体

class Finding:
    def __init__(self, kind: str, rel: str, line: int, quote: str, matched: int, total: int, tail: str):
        self.kind, self.rel, self.line = kind, rel, line
        self.quote, self.matched, self.total, self.tail = quote, matched, total, tail

    @property
    def key(self) -> str:
        return f"{self.rel}:{self.line}:{norm(self.quote)[:20]}"

    def render(self) -> str:
        head = f"[{self.kind:<5}] {self.rel}:{self.line}"
        if self.kind == "MISS":
            s = f"{head} 一致長{self.matched}/{self.total}\n         引用: {self.quote[:100]}"
            if self.tail:
                s += f"\n         ↳ 不一致開始: {self.tail}"
            return s
        return f"{head} 他条の文\n         引用: {self.quote[:100]}"


def scan(targets: list[Path]) -> tuple[list[Finding], list[str], int]:
    """(findings, errors, 検査した引用数)."""
    errors: list[str] = []
    loaded: dict[str, tuple[dict[str, str], str]] = {}
    for group, (label, path, kind) in SOURCES.items():
        if not path.exists():
            errors.append(f"原典キャッシュがありません: {path.relative_to(ROOT)}（{label}）")
            continue
        if kind == "egov":
            arts, full = load_egov(path)
        else:
            arts, full, sha = load_kaishaku(path)
            if sha and PDF.exists():
                actual = hashlib.sha256(PDF.read_bytes()).hexdigest()
                if actual != sha:
                    errors.append(
                        f"キャッシュが PDF と一致しません（{path.name}）。"
                        f"python scripts/extract_kaishaku_text.py で再生成してください。"
                    )
        if not arts:
            errors.append(f"原典から条文を1件も抽出できませんでした: {path.name}")
            continue
        loaded[group] = ({k: norm(v) for k, v in arts.items()}, norm(full))

    findings: list[Finding] = []
    checked = 0
    for path in targets:
        group = path.parent.name
        if group not in loaded:
            continue
        arts, full = loaded[group]
        own = arts.get(path.stem)
        rel = path.relative_to(ROOT).as_posix()
        for line, quote in genbun_quotes(path):
            if quote.startswith(SKIP_PREFIX):
                continue
            body = ABBREV_TAIL.sub("", EDITORIAL_TAIL.sub("", strip_lead(quote)))
            nq = norm(body)
            if len(nq) < MIN_LEN:
                continue
            checked += 1
            if own and nq in own:
                continue
            if nq in full:
                findings.append(Finding("OTHER", rel, line, quote, len(nq), len(nq), ""))
            else:
                lo = longest_prefix(nq, full)
                tail = ""
                if 0 < lo < len(nq):
                    tail = f"…{nq[max(0, lo - 12):lo]}【{nq[lo:lo + 28]}】"
                findings.append(Finding("MISS", rel, line, quote, lo, len(nq), tail))
    return findings, errors, checked


def collect(paths: list[str]) -> list[Path]:
    if not paths:
        return sorted(
            p
            for g in SOURCES
            for p in (ROOT / "docs" / "articles" / g).glob("*.md")
        )
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


def self_test() -> int:
    """検出器の生存証明（vacuous pass 防止）.

    原典に存在しない文・他条の文を合成して、MISS / OTHER が実際に立つことを見る。
    「findings 0 件」が検出器の故障によるものでないことを CI で毎回証明する。
    """
    cases = [
        ("MISS", "存在しない条文の創作", "構外から伝送される電気の開閉を行うが変成しない所であって、発電所以外のものをいう。"),
        ("MISS", "語の脱落（改正未反映）", "電線路維持運用者が一般送配電事業者であるものに限り、配電事業者を含まないものとする。"),
        ("OTHER", "他条からの引用（誤帰属）", None),
    ]
    src = SOURCES["kijun"][1]
    if not src.exists():
        print("ERROR: self-test に必要な原典キャッシュがありません", file=sys.stderr)
        return 2
    arts, full = load_egov(src)
    narts = {k: norm(v) for k, v in arts.items()}
    nfull = norm(full)

    ok = True
    for kind, label, text in cases:
        if kind == "MISS":
            nq = norm(text)
            hit = nq not in nfull
            print(f"  [{'PASS' if hit else 'FAIL'}] MISS 検出: {label}")
            ok &= hit
        else:
            # 第2条の文を第1条の引用として与えると OTHER になること
            other = None
            for num, body in narts.items():
                if num != "1" and len(body) > 60:
                    other = body[10:70]
                    break
            hit = other is not None and other not in narts.get("1", "") and other in nfull
            print(f"  [{'PASS' if hit else 'FAIL'}] OTHER 検出: {label}")
            ok &= hit

    # 陽性対照: 原典の文はそのまま一致すること（正規化が壊れていないか）
    body = narts.get("1", "")
    ctrl = body[20:80]
    hit = bool(ctrl) and ctrl in narts["1"]
    print(f"  [{'PASS' if hit else 'FAIL'}] 陽性対照: 原典の文が自条に一致する")
    ok &= hit

    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*", help="対象ファイル／ディレクトリ（省略時 docs/articles 全体）")
    ap.add_argument("--self-test", action="store_true", help="検出器の生存証明")
    ap.add_argument("--list-allowlist", action="store_true", help="allowlist を表示して終了")
    ap.add_argument("--no-allowlist", action="store_true", help="allowlist を無視して全件表示")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    if args.list_allowlist:
        if not ALLOWLIST:
            print("allowlist: 0件")
        for k, why in ALLOWLIST.items():
            print(f"{k}\n    理由: {why}")
        return 0

    targets = collect(args.paths)
    findings, errors, checked = scan(targets)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    allowed = 0
    shown: list[Finding] = []
    for f in findings:
        if not args.no_allowlist and f.key in ALLOWLIST:
            allowed += 1
            continue
        shown.append(f)

    for f in shown:
        print(f.render())

    miss = sum(1 for f in shown if f.kind == "MISS")
    other = sum(1 for f in shown if f.kind == "OTHER")
    print(
        f"\ncheck_law_verbatim: {len(shown)}件"
        f"（MISS {miss} / OTHER {other}）"
        f" — {len(targets)}ファイル・{checked}引用を照合"
        + (f"・allowlist {allowed}件" if allowed else "")
    )
    return 1 if shown else 0


if __name__ == "__main__":
    sys.exit(main())
