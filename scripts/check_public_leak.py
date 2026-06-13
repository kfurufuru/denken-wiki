#!/usr/bin/env python3
"""公開ビルド成果物（site/）の私的情報漏えい検査（denken-wiki 版・正対照つき）。

denken-wiki は公開 GitHub Pages（https://kfurufuru.github.io/denken-wiki/）で、
リポジトリも public。実名・勤務先・ローカル環境情報が build 出力（site/）に混入
すると全世界へ配信される。本スクリプトは mkdocs build 後の site/ を機械検査し、
PR Build Check と deploy.yml の両方で漏えいを fail-closed に止める。

導入の発端（2026-06-13）:
  制御盤撤去ガイドラインを ei-wiki へ移設した際（denken 撤去 PR #116）、ei-wiki の
  check_public_leak.py が記入例の実名「古舘・佐藤」を検出した。同じ実名は検査の無い
  denken-wiki 側では未検出のまま公開され続けていた。源流側（denken-wiki）にも同等の
  検査を導入するのが本スクリプト（ei-wiki 版を移植・FORBIDDEN を denken-wiki 用に調整）。

使い方:
  python scripts/check_public_leak.py              # site/ を検査（mkdocs build 後）
  python scripts/check_public_leak.py --site DIR   # 検査対象ディレクトリ指定
  python scripts/check_public_leak.py --self-test  # 検出器の生存証明（正対照）のみ

終了コード:
  0 = 漏えい 0 件かつ正対照すべて検出
  1 = 漏えい検出 / 正対照の検出失敗（=検出器または build の故障）
  2 = 引数・IO エラー（site/ が無い等）

設計（ei-wiki 版 2026-06-11 search_index.json 空振りPASS事故の再発防止を継承）:
  - 生バイト grep はしない。HTML 実体参照・URL エンコード・\\uXXXX（JSON
    ensure_ascii 形）を復号した「復号ビュー」と、NFKC 正規化＋ゼロ幅除去の
    シャドーも走査する（エンコード形に隠れた語を見落とさない）
  - sitemap.xml.gz は gzip 展開してから走査する（コンテナをスキップしない）。
    .gz 以外のコンテナ（zip/pdf）は site/ に存在した時点で NG（中身を検査できない）
  - 正対照（positive control）を 3 層で同梱:
      1) --self-test: 各 FORBIDDEN パターンが自分のサンプルを検出できるか＋
         エンコード形プローブ（\\uXXXX・HTML実体・URL%・全角・ゼロ幅・gzip）
      2) site 検査時: 「確実に存在するはずの公開語」（電験 等）が
         search_index.json / sitemap.xml.gz / index.html から検出できるか
      3) 1)2) のどちらが欠けても exit 1 ＝「漏えい 0 件」を空振りで報告しない
  - 「三菱電機」等の機器メーカー用途は FORBIDDEN に入れない（kaishaku/149 等で正当用途）。
    勤務先を特定する「三菱ケミカル」のみ FORBIDDEN（2026-06-13 docs 全数調査で峻別）。

関連: ei-wiki scripts/check_public_leak.py（移植元）／
      memory: feedback_absence_check_positive_control / feedback_cross_wiki_content_move /
      feedback_public_pages_repo_exposure_audit
"""

import argparse
import gzip
import html
import io
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

# Windows cp932 で日本語エンコード失敗を回避
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# 禁止パターン（site/ に 1 件でもあれば公開不可）
# 2026-06-13 に docs/ 全数調査で各語の正当用途 0 件を確認してから採用。
# 第3列は正対照サンプル: そのパターンが「必ず検出できなければならない」最小文字列。
# --self-test が毎回スキャンし、検出失敗＝検出器故障として exit 1 にする
# （パターン追加時はサンプルも必須＝検証器と fixture のドリフトを構造的に防ぐ）。
# 正当用途が将来できた場合は、このテーブルを意識的に編集する（黙認エスケープ無し）。
# ---------------------------------------------------------------------------
FORBIDDEN = [
    (r"古[舘館]", "実名（姓・舘/館 異体字とも）", "古舘"),
    (r"舘", "実名の単漢字指紋（タグ/ゼロ幅分断対策。常用『館』は別字で対象外）", "<b>舘</b>"),
    (r"主寿", "実名（名）", "主寿"),
    (r"(?i)furuta(?:te|chi|n)|furudate", "実名ローマ字", "Furutachi"),
    (r"(?i)kazutoshi", "実名ローマ字（名）", "Kazutoshi"),
    (r"(?i)furu3291", "メールアドレス（ローカル部指紋）", "k.furu3291@gmail.com"),
    (r"(?i)kfuru(?!furu)", "ローカルユーザー名（kfurufuru=公開GitHubアカウントは許容）", "kfuru"),
    (r"(?i)C:[/\\]+Users", "ローカル Windows パス", r"C:\Users"),
    (r"(?i)AppData", "ローカル Windows パス", "AppData"),
    (r"三菱ケミカル", "勤務先（社名。三菱電機等の機器メーカー用途は対象外）", "三菱ケミカル"),
    (r"鶴見", "勤務地", "鶴見"),
]

# site/ に「確実に存在するはずの公開語」。検出できなければ検出器か build の故障
# （＝「漏えい 0 件」が空振りの疑い）として exit 1。
# (相対パス, パターン, 説明)。パスは mkdocs build の固定出力。
SITE_POSITIVE_CONTROLS = [
    ("search/search_index.json", r"電験", "検索インデックス復号後に本文語が見えること"),
    ("sitemap.xml.gz", r"articles/kaishaku", "gzip 展開後に公開 URL パスが見えること"),
    ("index.html", r"電験", "トップページ本文が見えること"),
]

# エンコード形プローブ（--self-test 用）: 復号・正規化・gzip 展開の各層の生存証明
_ENCODED_PROBES = [
    ("JSON \\uXXXX 形（ensure_ascii・search_index 事故と同型）", "\\u53e4\\u8218"),
    ("HTML 10進実体", "&#21476;&#33304;"),
    ("HTML 16進実体", "&#x53e4;&#x8218;"),
    ("URL エンコード", "%E5%8F%A4%E8%88%98"),
    ("NFKC 全角英字", "ＫＦＵＲＵ"),
    ("ゼロ幅挿入", "古​舘"),
]

# テキスト走査しない拡張子（画像・フォント）。コンテナ（zip/pdf）は走査除外では
# なく「存在自体を NG」。gz はここに含めず gzip 展開して走査する。
BINARY_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".svg",
               ".woff", ".woff2", ".ttf", ".eot"}
CONTAINER_EXTS = {".zip", ".pdf"}

# 意図的に公開している、走査不能だが PII を含まないと確認済みのコンテナ（site/ 相対パス）。
# ここに無いコンテナ（zip/pdf）は「中身を検査できない」として一律 NG（fail-closed）。
# 追加は必ず一次調査つきで（黙認エスケープ無し）。
#   denken-kaishaku-r07-11.pdf … 経産省告示「電気設備の技術基準の解釈」R7-11 版の
#     公的法令 PDF（239 頁・36.7 万字）。2026-06-13 に PyMuPDF で全文抽出し
#     FORBIDDEN 全パターンを照合 → ヒット 0 件を確認のうえ allowlist 化。
ALLOWED_CONTAINERS = {
    "assets/pdf/denken-kaishaku-r07-11.pdf",
}

# 走査対象から外す「自作ではない上流ベンダーバンドル」（site/ 相対パス・正規表現）。
# これらは手打ちの実名・ローカルパスを構造的に含み得ない一方、巨大な minify 済み
# Unicode 文字クラス（例: CJK 互換漢字の範囲端点 `豈-舘`）を含むため、単漢字指紋
# パターン（舘）が誤検出する。上流コードを自分の PII で grep しても雑音にしかならない
# ため、ファイルごとスキップする。自作 JS/CSS（javascripts/self-check.js 等）は
# assets/ 配下ではなく上記2バンドルにも該当しないため、引き続き全走査される。
#   - assets/ … Material テーマ生成物＋lunr 検索辞書（content-hash 付き・全て上流）
#   - mermaid.min.js / tex-mml-svg.js … self-host した mermaid / MathJax（各 2〜3 MB）
VENDORED_SKIP = [
    re.compile(r"^assets/"),
    re.compile(r"^javascripts/mermaid\.min\.js$"),
    re.compile(r"^javascripts/tex-mml-svg\.js$"),
]

CONTEXT_CHARS = 35
MAX_SHOW = 8

# ZWSP / ZWNJ / ZWJ / WORD JOINER / ZWNBSP(BOM) — 不可視のため必ず明示エスケープで書く
_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))


def shadow_normalize(text: str) -> str:
    """ゼロ幅文字を除去し NFKC 正規化したシャドーコピー。"""
    return unicodedata.normalize("NFKC", text.translate(_ZERO_WIDTH))


def decoded_view(text: str) -> str:
    """HTML 実体参照・URL エンコード・\\uXXXX を素朴に復号した検査用ビュー。"""
    t = html.unescape(text)
    try:
        t = unquote(t)
    except Exception:
        pass
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m.group(1), 16)), t)


def scan_text(text: str) -> list[tuple[str, str, str]]:
    """生・NFKC シャドー・復号ビュー（とその NFKC）を走査し
    (パターン, ラベル+検出層, context) を返す。"""
    seen: set[tuple[str, int]] = set()
    out = []
    sources = [("", text)]
    shadow = shadow_normalize(text)
    if shadow != text:
        sources.append(("・正規化後検出", shadow))
    dec = decoded_view(text)
    if dec != text:
        sources.append(("・復号後検出", dec))
        dec_shadow = shadow_normalize(dec)
        if dec_shadow != dec:
            sources.append(("・復号+正規化後検出", dec_shadow))
    for suffix, t in sources:
        for pat, label, _sample in FORBIDDEN:
            for m in re.finditer(pat, t):
                key = (pat, m.start())
                if key in seen:
                    continue
                seen.add(key)
                s, e = m.start(), m.end()
                ctx = t[max(0, s - CONTEXT_CHARS): e + CONTEXT_CHARS].replace("\n", "⏎")
                out.append((pat, label + suffix, ctx))
    return out


def read_artifact(path: Path) -> str | None:
    """検査用テキストを返す。gz は展開、バイナリ拡張子は None（スキップ）。
    UTF-8 で読めないテキスト系ファイルは例外を上げる（呼び出し側で NG 扱い）。"""
    suffix = path.suffix.lower()
    if suffix in BINARY_EXTS:
        return None
    if suffix == ".gz":
        data = gzip.decompress(path.read_bytes())
        return data.decode("utf-8")
    return path.read_text(encoding="utf-8")


def self_test() -> int:
    """正対照スキャンで検出器自体の生存を証明する（--self-test）。"""
    failures = []
    for pat, label, sample in FORBIDDEN:
        if not any(h[0] == pat for h in scan_text(sample)):
            failures.append(f"{pat!r} ({label}) が正対照 {sample!r} を検出できない")
    for name, probe in _ENCODED_PROBES:
        if not scan_text(probe):
            failures.append(f"エンコード形 {name} の正対照 {probe!r} が全層で未検出")
    # gzip 展開層の生存証明（sitemap.xml.gz と同経路）
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        gz = Path(td) / "probe.xml.gz"
        gz.write_bytes(gzip.compress("<url>古舘</url>".encode("utf-8")))
        text = read_artifact(gz)
        if not (text and scan_text(text)):
            failures.append("gzip 展開層の正対照が未検出（sitemap.xml.gz 経路の故障）")
    if failures:
        for msg in failures:
            print(f"[FAIL] {msg}")
        print(f"[NG] self-test: 検出器故障 {len(failures)} 件。"
              "この状態の『漏えい 0 件』は信頼できません。")
        return 1
    print(f"[OK] self-test: 正対照 {len(FORBIDDEN)} パターン＋エンコード形 "
          f"{len(_ENCODED_PROBES)} 種＋gzip 展開層を全て検出（検出器は生きています）")
    return 0


def scan_site(site: Path, quiet: bool) -> int:
    if not site.is_dir():
        print(f"[ERROR] site ディレクトリがありません: {site}（先に mkdocs build）",
              file=sys.stderr)
        return 2

    # 検出器の生存証明を内蔵実行（CI の独立 step だけに頼らない）。
    # これが無いと scan_text の沈黙故障時に「漏えい 0 件＋site 正対照 PASS」の
    # 空振りが成立してしまう（site 正対照は re.search 直叩きで scan_text 非依存のため）
    if self_test() != 0:
        return 1

    violations: list[tuple[str, str, str, str]] = []  # (rel, pat, label, ctx)
    n_files = 0
    for p in sorted(site.rglob("*")):
        if not p.is_file():
            continue
        rel = str(p.relative_to(site)).replace("\\", "/")
        if any(rx.search(rel) for rx in VENDORED_SKIP):
            continue  # 上流ベンダーバンドル（自作 PII を含み得ない・誤検出源）
        if p.suffix.lower() in CONTAINER_EXTS:
            if rel in ALLOWED_CONTAINERS:
                continue  # 一次調査済みの公開コンテナ（PII 0 件確認・allowlist）
            print(f"[FAIL] 走査不能なコンテナ形式が site/ に存在: {rel}（中身を検査できない）")
            return 1
        try:
            text = read_artifact(p)
        except Exception as e:
            print(f"[FAIL] 読込/展開できないファイル: {rel} ({e})")
            return 1
        if text is None:
            continue
        n_files += 1
        for pat, label, ctx in scan_text(text):
            violations.append((rel, pat, label, ctx))

    if violations:
        for rel, pat, label, ctx in violations[:MAX_SHOW]:
            print(f"[FAIL] {rel}: {pat} ({label})")
            if not quiet:
                print(f"    …{ctx}…")
        if len(violations) > MAX_SHOW:
            print(f"    …他 {len(violations) - MAX_SHOW} 件")
        print(f"[NG] 漏えい {len(violations)} 件。公開不可（deploy を中止してください）。")
        return 1

    # site 正対照: 「確実にあるはずの公開語」が見えること（空振り PASS 防止）
    pc_failures = []
    for rel, pat, why in SITE_POSITIVE_CONTROLS:
        p = site / rel
        try:
            text = read_artifact(p) if p.is_file() else None
        except Exception:
            text = None
        if text is None or not re.search(pat, decoded_view(text)):
            pc_failures.append(f"{rel}: {pat!r} が未検出（{why}）")
    if pc_failures:
        for msg in pc_failures:
            print(f"[FAIL] site 正対照: {msg}")
        print("[NG] 正対照が見えない＝検出器か build の故障。"
              "『漏えい 0 件』は空振りの疑いがあり信頼できません。")
        return 1

    print(f"[OK] {n_files} ファイル走査・漏えい 0 件・site 正対照 "
          f"{len(SITE_POSITIVE_CONTROLS)}/{len(SITE_POSITIVE_CONTROLS)} 検出（公開可能な状態）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="公開ビルド成果物（site/）の私的情報漏えい検査（正対照つき）")
    ap.add_argument("--site", default="site", help="検査対象ディレクトリ（既定: site）")
    ap.add_argument("--self-test", action="store_true",
                    help="検出器の生存証明（正対照スキャン）のみ実行")
    ap.add_argument("--quiet", action="store_true", help="context 表示を抑制（CI 用）")
    args = ap.parse_args()

    if args.self_test:
        return self_test()
    return scan_site(Path(args.site), args.quiet)


if __name__ == "__main__":
    sys.exit(main())
