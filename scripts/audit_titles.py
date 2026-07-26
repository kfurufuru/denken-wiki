"""denken-wiki kijun/*.md の H1 タイトルが省令の条見出しと一致するかを検証する。

事故記録：2026-05-03 旧 20.md の H1 が「第20条 発電所等への取扱者以外の者の立入の防止」
だったが、本来の第20条は「電線路等の感電又は火災の防止」。条文番号と内容の不一致が
三段監修の数値照合だけでは検出できなかった。

denken-hoki-style.md §7.3 R6「条文番号・タイトル・本文の三点照合」の機械化版。

検査対象は記事 H1 だけでなく、**一覧表 kijun/index.md と mkdocs.yml の nav ラベル**も含む
（2026-07-26 追加）。記事本文が正しくても、一覧・サイドバーが誤った条番号↔主題を教えて
いれば学習者はそちらを覚える。実際 index.md には第7条・第39条・第47条の見出しがそのまま
別の条に付いている誤りが3件残っていた（解釈側 PR #159/#161 と同型）。
判定ロジックは `scripts/article_title_match.py` に集約している（法令ごとの規則ドリフト防止）。

使い方：
  python scripts/audit_titles.py                       # 全 kijun/*.md スキャン
  python scripts/audit_titles.py --self-test           # 判定ロジックの退行テスト
  python scripts/audit_titles.py --strict              # MISMATCH があれば exit 2（pre-commit用）
  python scripts/audit_titles.py --json                # JSON出力
  python scripts/audit_titles.py --refresh             # e-Gov XML を再取得（キャッシュ無視）
  python scripts/audit_titles.py --staged              # staged 変更ファイルのみ検査（pre-commit高速化）

データソース：
  - 電気設備に関する技術基準を定める省令（lawid=409M50000400052）
  - e-Gov 法令検索 API: https://laws.e-gov.go.jp/api/1/lawdata/{lawid}
  - キャッシュ: scripts/cache/egov-409M50000400052.xml
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import article_title_match as M  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
WIKI_KIJUN = REPO_ROOT / "docs" / "articles" / "kijun"
KIJUN_INDEX = WIKI_KIJUN / "index.md"
MKDOCS_YML = REPO_ROOT / "mkdocs.yml"
CACHE_PATH = REPO_ROOT / "scripts" / "cache" / "egov-409M50000400052.xml"
EGOV_URL = "https://laws.e-gov.go.jp/api/1/lawdata/409M50000400052"

KANSUJI = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def kanji_to_int(s: str) -> int | None:
    if not s:
        return None
    if s == "百":
        return 100
    if "十" in s:
        head, _, tail = s.partition("十")
        n = (KANSUJI.get(head, 1) if head else 1) * 10
        if tail:
            n += KANSUJI.get(tail, 0)
        return n
    if len(s) == 1 and s in KANSUJI:
        return KANSUJI[s]
    return None


@dataclass
class Finding:
    file_path: str
    article_num: int | None
    h1_title: str
    expected_title: str | None
    status: str


def fetch_egov_xml(refresh: bool = False) -> str:
    if not refresh and CACHE_PATH.exists():
        return CACHE_PATH.read_text(encoding="utf-8")
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(EGOV_URL, timeout=20) as resp:
        xml = resp.read().decode("utf-8")
    CACHE_PATH.write_text(xml, encoding="utf-8")
    return xml


def parse_egov_articles(xml: str) -> dict[int, str]:
    pattern = re.compile(
        r"<Article\s[^>]*Num=\"(\d+)\"[^>]*>\s*<ArticleCaption>（([^）]+)）</ArticleCaption>",
        re.DOTALL,
    )
    result: dict[int, str] = {}
    for m in pattern.finditer(xml):
        num = int(m.group(1))
        caption = m.group(2).strip()
        if num not in result:
            result[num] = caption
    return result


H1_PATTERN = re.compile(
    r"^#\s*(?:電気設備技術基準|電技省令)\s*第([一二三四五六七八九十百〇\d]+)条\s*[—\-]\s*(.+?)\s*$",
    re.MULTILINE,
)


def parse_h1(text: str) -> tuple[int | None, str | None]:
    m = H1_PATTERN.search(text)
    if not m:
        return None, None
    num_str = m.group(1)
    title = m.group(2).strip()
    num = int(num_str) if num_str.isdigit() else kanji_to_int(num_str)
    return num, title


def normalize_title(s: str) -> str:
    return s.strip().replace("　", "").replace(" ", "")


def audit_file(path: Path, official_map: dict[int, str]) -> Finding:
    text = path.read_text(encoding="utf-8")
    rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    num, h1_title = parse_h1(text)
    if num is None or h1_title is None:
        return Finding(rel, num, h1_title or "", None, "NO_H1")
    expected = official_map.get(num)
    if expected is None:
        return Finding(rel, num, h1_title, None, "NOT_IN_SHOREI")
    if normalize_title(h1_title) == normalize_title(expected):
        return Finding(rel, num, h1_title, expected, "OK")
    return Finding(rel, num, h1_title, expected, "MISMATCH")


def get_staged_kijun_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []
    files = []
    for line in result.stdout.splitlines():
        if line.startswith("docs/articles/kijun/") and line.endswith(".md") and not line.endswith("index.md"):
            p = REPO_ROOT / line
            if p.exists():
                files.append(p)
    return files


def format_human(findings: list[Finding]) -> str:
    out = []
    counts = {"OK": 0, "MISMATCH": 0, "NOT_IN_SHOREI": 0, "NO_H1": 0}
    for f in findings:
        counts[f.status] = counts.get(f.status, 0) + 1
        if f.status == "OK":
            out.append(f"  [OK] {f.file_path} 第{f.article_num}条 {f.h1_title}")
        elif f.status == "MISMATCH":
            out.append(
                f"  [NG] {f.file_path} 第{f.article_num}条\n"
                f"        H1: {f.h1_title}\n"
                f"        正: {f.expected_title}"
            )
        elif f.status == "NOT_IN_SHOREI":
            out.append(f"  [WARN] {f.file_path} 第{f.article_num}条 は省令に存在しない")
        elif f.status == "NO_H1":
            out.append(f"  [SKIP] {f.file_path} H1 パース失敗")
    out.append("\n=== Summary ===")
    out.append(f"  OK: {counts['OK']}")
    out.append(f"  MISMATCH: {counts['MISMATCH']}")
    out.append(f"  NOT_IN_SHOREI: {counts['NOT_IN_SHOREI']}")
    out.append(f"  NO_H1: {counts['NO_H1']}")
    return "\n".join(out)


def scan_index_and_nav(official: dict[int, str]) -> list[tuple[str, str, str]]:
    """kijun/index.md と mkdocs.yml nav を e-Gov 正本と突合する。"""
    out: list[tuple[str, str, str]] = []

    if KIJUN_INDEX.exists():
        for num, title in sorted(
            M.parse_index_titles(KIJUN_INDEX.read_text(encoding="utf-8")).items()
        ):
            v = M.classify(num, title, official)
            if v:
                out.append((v[0], "kijun/index.md", v[1]))

    if MKDOCS_YML.exists():
        nav = MKDOCS_YML.read_text(encoding="utf-8")
        for num, label in sorted(M.parse_nav_titles(nav, "kijun").items()):
            v = M.classify(num, label, official)
            if v:
                out.append((v[0], "mkdocs.yml", v[1]))
        for label_n, file_n, label in M.nav_number_mismatches(nav, "kijun"):
            out.append((
                "ERROR", "mkdocs.yml",
                f"nav ラベル「第{label_n}条（{label}）」のリンク先が articles/kijun/{file_n}.md",
            ))
    return out


def self_test() -> int:
    print("--- 共有判定ロジック (article_title_match) ---")
    rc = M.self_test()
    print("self-test:", "ALL PASS" if rc == 0 else "FAILED")
    return rc


def main(argv: list[str]) -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    if "--self-test" in argv:
        return self_test()

    output_json = "--json" in argv
    strict = "--strict" in argv
    refresh = "--refresh" in argv
    staged_only = "--staged" in argv

    xml = fetch_egov_xml(refresh=refresh)
    official_map = parse_egov_articles(xml)
    if not official_map:
        print("[ERROR] e-Gov XML から条見出しを抽出できませんでした", file=sys.stderr)
        return 3

    if staged_only:
        files = get_staged_kijun_files()
        if not files:
            return 0
    else:
        files = sorted(p for p in WIKI_KIJUN.glob("*.md") if p.name != "index.md")

    findings = [audit_file(f, official_map) for f in files]

    if output_json:
        print(json.dumps([asdict(f) for f in findings], ensure_ascii=False, indent=2))
    else:
        print(format_human(findings))

    rc = 0
    if strict and sum(1 for f in findings if f.status == "MISMATCH") > 0:
        rc = 2

    # staged モードは記事ファイル限定の高速パスなので index/nav は見ない
    if staged_only or output_json:
        return rc

    ext = scan_index_and_nav(official_map)
    errors = [x for x in ext if x[0] == "ERROR"]
    warns = [x for x in ext if x[0] == "WARN"]
    print()
    print("=== 一覧・nav の条番号↔条見出し（e-Gov 正本と突合）===")
    if errors:
        print(f"NG ERROR {len(errors)} 件（条番号の取り違えの疑い）")
        for s, where, detail in errors:
            print(f"  [ERROR] {where} - {detail}")
    else:
        print("OK ERROR 0 件")
    if warns:
        print(f"  （WARN {len(warns)} 件 — 短縮表記・言い換えなら問題なし。--all で表示）")
        if "--all" in argv:
            for s, where, detail in warns:
                print(f"  [WARN] {where} - {detail}")
    if strict and errors:
        rc = 2
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
