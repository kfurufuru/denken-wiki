"""jigyoho/*.md の条番号↔条見出しを e-Gov（電気事業法）と突合する。

## なぜ必要か（2026-07-26 制定）

`articles/jigyoho/` には**条見出しのゲートが1つも無かった**。省令は audit_titles.py、
解釈は audit_kaishaku_titles.py が見ているのに、事業法だけ素通しだった。
条番号の取り違えは PR #154/#156/#157/#158 で繰り返し起きているクラスの事故で、
「まだ起きていない」ことは「起きない」ことを意味しない。**現時点で誤帰属 0 件のうちに
ゲートを入れる**（赤の状態で入れると allowlist 運用のコストがかかる）。

## 附則を混ぜない（重要）

e-Gov の法令 XML は本則（MainProvision）と附則（SupplProvision）で**条番号が重複する**。
素朴に全体を走査すると、電気事業法第38条が附則の「罰則の適用に関する経過措置」、
第48条が「政令への委任」として抽出され、正本が壊れる（実測）。**MainProvision に
限定して抽出する**。

## 見出しの無い条は fail-open

事業法には ArticleCaption を持たない条がある（第38条・第48条など）。正本に無い条は
MASTER_MISSING として判定しない。

## 使い方

    python scripts/audit_jigyoho_titles.py            # 記事 H1 + index + nav
    python scripts/audit_jigyoho_titles.py --strict   # ERROR で exit 2（CI用）
    python scripts/audit_jigyoho_titles.py --all      # WARN も表示
    python scripts/audit_jigyoho_titles.py --refresh  # e-Gov を再取得
    python scripts/audit_jigyoho_titles.py --self-test
"""
from __future__ import annotations

import io
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import article_title_match as M  # noqa: E402

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
JIGYOHO = ROOT / "docs" / "articles" / "jigyoho"
INDEX_MD = JIGYOHO / "index.md"
MKDOCS_YML = ROOT / "mkdocs.yml"
CACHE_PATH = ROOT / "scripts" / "cache" / "egov-339AC0000000170.xml"
EGOV_URL = "https://laws.e-gov.go.jp/api/1/lawdata/339AC0000000170"  # 電気事業法

H1_RE = re.compile(r"^#\s*電気事業法\s*第(\d+)条\s*[—\-‐–]\s*(.+?)\s*$")
ARTICLE_CAPTION = re.compile(
    r'<Article\s[^>]*Num="([0-9_]+)"[^>]*>\s*<ArticleCaption>（([^）]+)）</ArticleCaption>'
)


def fetch_xml(refresh: bool = False) -> str:
    if not refresh and CACHE_PATH.exists():
        return CACHE_PATH.read_text(encoding="utf-8")
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(EGOV_URL, timeout=30) as resp:
        xml = resp.read().decode("utf-8")
    CACHE_PATH.write_text(xml, encoding="utf-8")
    return xml


def parse_main_provision(xml: str) -> dict[int, str]:
    """本則（MainProvision）の 条番号→条見出し。附則は条番号が重複するため除外する。"""
    try:
        start = xml.index("<MainProvision")
        end = xml.index("</MainProvision>")
    except ValueError:
        return {}
    body = xml[start:end]
    out: dict[int, str] = {}
    for m in ARTICLE_CAPTION.finditer(body):
        num = m.group(1)
        if num.isdigit() and int(num) not in out:
            out[int(num)] = m.group(2).strip()
    return out


def parse_h1(text: str) -> tuple[int | None, str | None]:
    body = text
    if body.startswith("---\n"):
        e = body.find("\n---\n", 3)
        if e != -1:
            body = body[e + 5:]
    first = next((ln for ln in body.split("\n") if ln.startswith("# ")), "")
    m = H1_RE.match(first)
    return (int(m.group(1)), m.group(2).strip()) if m else (None, None)


def scan(official: dict[int, str]) -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []

    for md in sorted(JIGYOHO.glob("*.md"), key=lambda p: p.name):
        if md.name == "index.md" or not md.stem.isdigit():
            continue
        n, title = parse_h1(md.read_text(encoding="utf-8"))
        if n is None:
            out.append(("ERROR", md.name, "H1 が「電気事業法 第N条 — タイトル」形式でない"))
            continue
        if n != int(md.stem):
            out.append(("ERROR", md.name, f"ファイル名=第{md.stem}条 / H1=第{n}条（{title}）"))
            continue
        v = M.classify(n, title, official)
        if v:
            out.append((v[0], md.name, v[1]))

    if INDEX_MD.exists():
        for n, t in sorted(M.parse_index_titles(INDEX_MD.read_text(encoding="utf-8")).items()):
            v = M.classify(n, t, official)
            if v:
                out.append((v[0], "index.md", v[1]))

    if MKDOCS_YML.exists():
        nav = MKDOCS_YML.read_text(encoding="utf-8")
        for n, label in sorted(M.parse_nav_titles(nav, "jigyoho").items()):
            v = M.classify(n, label, official)
            if v:
                out.append((v[0], "mkdocs.yml", v[1]))
        for ln, fn, label in M.nav_number_mismatches(nav, "jigyoho"):
            out.append((
                "ERROR", "mkdocs.yml",
                f"nav ラベル「第{ln}条（{label}）」のリンク先が articles/jigyoho/{fn}.md",
            ))
    return out


def self_test() -> int:
    print("--- 共有判定ロジック (article_title_match) ---")
    rc = M.self_test()
    print("--- jigyoho 固有 ---")
    cases: list[tuple[str, bool]] = []

    # 附則を混ぜると正本が壊れる（実測した退行テスト）
    xml = (
        '<Law><MainProvision>'
        '<Article Num="38"><ArticleCaption>（事業用電気工作物）</ArticleCaption></Article>'
        '<Article Num="40"><ArticleCaption>（技術基準適合命令）</ArticleCaption></Article>'
        '</MainProvision><SupplProvision>'
        '<Article Num="38"><ArticleCaption>（罰則の適用に関する経過措置）</ArticleCaption></Article>'
        '</SupplProvision></Law>'
    )
    got = parse_main_provision(xml)
    cases.append(("附則の同番号条を混ぜない", got == {38: "事業用電気工作物", 40: "技術基準適合命令"}))
    cases.append(("MainProvision が無ければ空", parse_main_provision("<Law/>") == {}))

    cases.append(("H1 を読む", parse_h1("# 電気事業法 第42条 — 保安規程\n") == (42, "保安規程")))
    cases.append(("frontmatter 付きでも読む",
                  parse_h1("---\na: b\n---\n\n# 電気事業法 第42条 — 保安規程\n") == (42, "保安規程")))
    cases.append(("H2 は拾わない", parse_h1("## 電気事業法 第42条 — 保安規程\n")[0] is None))

    # 本文の見出しが同一の条が複数あっても誤検出しない（第40条・第56条＝技術基準適合命令）
    m = {40: "技術基準適合命令", 56: "技術基準適合命令", 57: "調査の義務", 92: "調査の義務"}
    cases.append(("同一見出しの条が併存しても自条一致は OK",
                  M.classify(40, "技術基準適合命令", m) is None
                  and M.classify(56, "技術基準適合命令（一般用）", m) is None))

    ok = rc == 0
    for name, passed in cases:
        print(("  PASS " if passed else "  FAIL ") + name)
        ok = ok and passed
    print("self-test:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()
    strict = "--strict" in argv
    show_all = "--all" in argv

    official = parse_main_provision(fetch_xml(refresh="--refresh" in argv))
    if not official:
        print("[ERROR] e-Gov XML（電気事業法）から本則の条見出しを抽出できませんでした",
              file=sys.stderr)
        return 3

    findings = scan(official)
    errors = [x for x in findings if x[0] == "ERROR"]
    warns = [x for x in findings if x[0] == "WARN"]
    missing = [x for x in findings if x[0] == "MASTER_MISSING"]

    print(f"=== 電気事業法 条番号↔条見出し（e-Gov 本則 {len(official)} 条と突合）===")
    if errors:
        print(f"NG ERROR {len(errors)} 件（条番号の取り違えの疑い）")
        for _, where, detail in errors:
            print(f"  [ERROR] {where} - {detail}")
    else:
        print("OK ERROR 0 件")
    for label, items in (("WARN", warns), ("MASTER_MISSING", missing)):
        if items:
            print(f"  （{label} {len(items)} 件 — --all で表示）")
            if show_all:
                for _, where, detail in items:
                    print(f"  [{label}] {where} - {detail}")
    return 2 if (errors and strict) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
