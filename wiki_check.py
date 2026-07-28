#!/usr/bin/env python3
"""wiki_check.py — denken-wiki Markdown 品質チェッカ

検出項目:
  [§]  §X記号残存（CLAUDE.mdで明示禁止、「第X条」推奨）
  [簡]  簡体字混入（風→风 のような誤字）
  [?]  [要確認] / [要確認: 理由] プレースホルダー残存（PLACEHOLDER_ALLOWLIST 超過分）
  [許]  allowlist 登録済みプレースホルダ（WARN・exit code に影響しない）
  [空]  空タグ・空リンク・空 admonition
  [壊]  壊れた相対 .md リンク／停滞TODO（「未作成」と書いた先が既に存在）

Usage:
  python wiki_check.py                       # docs/ 全体（検出のみ）
  python wiki_check.py docs/articles/jigyoho # ディレクトリ指定
  python wiki_check.py docs/articles/jigyoho/38.md  # 単ファイル
  python wiki_check.py --fix-section --dry-run     # § 修正 dry-run
  python wiki_check.py --fix-section                # § 自動修正

Exit code: 0=OK, 1=issues found
"""
import argparse
import io
import re
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

SECTION_PATTERN = re.compile(r"§(\d+)")
# [要確認] だけでなく [要確認: 理由] / [要確認：理由] 形式も検出する。
# 事故: 旧パターン r"\[要確認\]" は閉じ括弧が直後に来る形しか拾わず、実際に残存していた
# `> [要確認: e-Gov公式の本文をここに転記]`（条文原文の未転記）を1件も検出できていなかった。
# その結果、条文原文が空のページが採点器で 100 点超（kaishaku/224.md=107点・全体3位）を
# 取り、「ゲート緑＝安全」という誤った信号を出していた。
# 閉じ括弧を任意にしているのは意図的: `[要確認: 理由` と書き掛けで閉じ忘れた行を
# 素通りさせないため。本文中で「言及」したい場合はバックティックで囲む
# （コードスパン／コードフェンス内は検査対象外なので誤検知しない）。
PLACEHOLDER_PATTERN = re.compile(r"\[要確認[^\]]*\]?")

# 未解消の [要確認:…] プレースホルダの既知残存数（docs/ からの相対パス → 件数）。
# ここに載っている件数ちょうどなら WARN（exit 0）、増えたら ERROR、減ったら
# 「allowlist が古い」として ERROR にする（ratchet: 潰したら必ずここも減らす）。
# 最終的に空 dict にするのがゴール。プレースホルダを本文で「言及」したいときは
# バックティックで囲む（`[要確認: …]`）— コードスパンは検査対象外になる。
PLACEHOLDER_ALLOWLIST = {
    # 解消済み（原典から逐語転記・2026-07-28）: kaishaku/22.md・kaishaku/224.md・
    # kijun/7.md・kijun/63.md の4件（16 → 11 件）。
    "docs/articles/kaishaku/45.md": 1,
    "docs/articles/kijun/11.md": 2,
    "docs/articles/other/pse-2.md": 1,
    "docs/articles/other/pse-10.md": 1,
    "docs/themes/hatsuhendenjo.md": 3,
    "docs/themes/pse-anzen-ho.md": 1,
    "docs/themes/setsuchi.md": 1,
    "docs/themes/shiyo-basho.md": 1,
}

# 停滞 TODO: <!-- TODO: 148.md は未作成 --> と書いてあるがリンク先が既に存在するもの。
# HTML コメントなので壊れリンク検査にも掛からず、機械的に見えない欠落になっていた。
STALE_TODO_PATTERN = re.compile(r"<!--\s*TODO:\s*(\S+\.md)\s+は未作成")

# 空タグ（中身が空白のみも対象）
EMPTY_TAG_PATTERN = re.compile(
    r"<(div|span|svg|p|details)>\s*</\1>",
    re.IGNORECASE,
)

# 空リンク: []() / [text]() / [](url)
# - URLが空: [text]() （[text](path) のような正常リンクと区別するため "()" を末尾チェック）
# - ラベルが空: [](url)
EMPTY_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")

# admonition 開始行: !!! note "..." または !!! warning など
ADMONITION_OPEN_PATTERN = re.compile(r"^\s*!!!\s+\S")

# 相対 .md リンク（ローカル参照のみ。http(s) や trailing slash は除外）
RELATIVE_MD_LINK_PATTERN = re.compile(r"\]\(([^)]+\.md)(?:#[^)]*)?\)")

# 簡体字 → 日本字（よく混入する文字に限定）
SIMP_TO_JP = {
    "风": "風", "电": "電", "规": "規", "务": "務", "约": "約",
    "级": "級", "单": "単", "时": "時", "间": "間", "问": "問",
    "题": "題", "应": "応", "计": "計", "设": "設", "业": "業",
    "产": "産", "让": "譲", "见": "見", "长": "長", "经": "経",
    "联": "聯", "节": "節", "给": "給", "实": "実", "边": "辺",
    "选": "選", "远": "遠", "进": "進", "还": "還",
}

EXCLUDE_DIRS = {"_data", "site", "overrides", "includes", ".git"}


def _repo_rel(path: Path) -> str:
    """リポジトリルート起点の posix パス（allowlist 照合キー）。"""
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _docs_root(path: Path):
    """path が含む docs/ ディレクトリ。見つからなければ None。"""
    parts = path.parts
    if "docs" in parts:
        return Path(*parts[: parts.index("docs") + 1])
    return None


def _strip_code_spans(line: str) -> str:
    """インラインコードスパン（`...`）を非空白プレースホルダに置換し、リンタの誤検知を防ぐ。
    空白で埋めると `[`x`](y)` のリンクが「空ラベル」と誤検知されるため X 埋めにする。"""
    return re.sub(r"`[^`]*`", lambda m: "X" * len(m.group(0)), line)


def check_file(path: Path):
    issues = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [(path, 0, "?", f"読込失敗: {e}")]

    lines = text.splitlines()
    placeholder_hits = []  # (lineno, 検出文字列)
    in_fence = False
    fence_is_code = False
    for lineno, line in enumerate(lines, 1):
        # フェンスの扱い:
        #   言語タグ付き（```python / ```mermaid 等）＝本物のコード → 全検査をスキップ
        #   タグ無しの ``` ＝「法的根拠ピラミッド」等の**学習コンテンツ**（学習者にはそのまま
        #     表示される）→ **本文系の検査（§記号・簡体字・プレースホルダ・停滞TODO）は行う**。
        #     一方、空タグ／空リンク／壊れ相対リンクは**マークアップの検査**であり、
        #     フェンス内はリンクとして描画されないので適用しない。
        # 事案: check_theme_article_numbers.py が同じフェンススキップで条番号誤帰属10件を
        #   見逃していた（2026-07-28 監査・PR #173）。同型の穴を本スクリプトでも塞ぐ。
        #   本 PR 時点でのタグ無しフェンス内の検出は §0 / 簡0 / プレースホルダ0 / 停滞TODO0
        #   ＝実害ゼロのうちに構造だけ固定する。
        m_fence = re.match(r"^\s*(```|~~~)(.*)$", line)
        if m_fence:
            if not in_fence:
                in_fence = True
                fence_is_code = bool(m_fence.group(2).strip())
            else:
                in_fence = False
                fence_is_code = False
            continue
        if in_fence and fence_is_code:
            continue
        in_prose_fence = in_fence  # タグ無しフェンス内（本文系の検査だけ行う）
        # インラインコードスパン内の文字列は誤検知の元なので空白化
        line = _strip_code_spans(line)
        for m in SECTION_PATTERN.finditer(line):
            issues.append((path, lineno, "§", f"§{m.group(1)} → 「第{m.group(1)}条」を推奨"))
        for ch in line:
            if ch in SIMP_TO_JP:
                issues.append((path, lineno, "簡", f"{ch} → 「{SIMP_TO_JP[ch]}」を推奨"))
        for m in PLACEHOLDER_PATTERN.finditer(line):
            placeholder_hits.append((lineno, m.group(0)))

        # E. 停滞 TODO: 「未作成」と書いてあるがリンク先が既に存在する
        for m in STALE_TODO_PATTERN.finditer(line):
            target = m.group(1)
            candidates = [path.parent / target]
            droot = _docs_root(path)
            if droot is not None:
                candidates.append(droot / target)
            if any(c.exists() for c in candidates):
                issues.append(
                    (
                        path,
                        lineno,
                        "壊",
                        f"停滞TODO: {target} は既に存在する（TODOを消してリンクに置き換える）",
                    )
                )

        # 以下 A/B/D は**マークアップの検査**。フェンス内はリンク・タグとして描画されない
        # （リテラル文字として表示される）ので適用しない。
        if in_prose_fence:
            continue

        # A. 空タグ
        for m in EMPTY_TAG_PATTERN.finditer(line):
            tag = m.group(1).lower()
            issues.append(
                (path, lineno, "空", f"空タグ <{tag}></{tag}> （内容を入れるか削除）")
            )

        # B. 空リンク
        for m in EMPTY_LINK_PATTERN.finditer(line):
            label = m.group(1).strip()
            url = m.group(2).strip()
            if not label and not url:
                issues.append((path, lineno, "空", "空リンク []() （URLとラベルを補完）"))
            elif not url:
                issues.append(
                    (path, lineno, "空", f"空リンク [{m.group(1)}]() （URLを補完）")
                )
            elif not label:
                issues.append(
                    (path, lineno, "空", f"空リンク []({url}) （ラベルを補完）")
                )

        # D. 壊れた相対 .md リンク
        for m in RELATIVE_MD_LINK_PATTERN.finditer(line):
            target = m.group(1).strip()
            # http(s)://, mailto:, 絶対パス（/から）はスキップ
            if target.startswith(("http://", "https://", "mailto:", "/")):
                continue
            # trailing-slash MkDocs変換形式は対象外（このパターンは .md 必須なので該当しないが念のため）
            if target.endswith("/"):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                issues.append(
                    (path, lineno, "壊", f"相対リンク先が存在しない: {target}")
                )

    # C. 空 admonition: !!! 行の直後に空行が2連続したら検出
    for idx, line in enumerate(lines):
        if ADMONITION_OPEN_PATTERN.match(line):
            # 直後の2行が両方とも空白行ならフラグ
            next1 = lines[idx + 1] if idx + 1 < len(lines) else ""
            next2 = lines[idx + 2] if idx + 2 < len(lines) else ""
            if next1.strip() == "" and next2.strip() == "":
                issues.append(
                    (path, idx + 1, "空", "空 admonition （本文を追加）")
                )

    # プレースホルダは allowlist と件数突合（ratchet）
    allowed = PLACEHOLDER_ALLOWLIST.get(_repo_rel(path), 0)
    found = len(placeholder_hits)
    if found > allowed:
        note = f"（allowlist 登録{allowed}件 → 実残存{found}件に増加）" if allowed else ""
        for lineno, hit in placeholder_hits:
            issues.append((path, lineno, "?", f"{hit} が残存{note}"))
    elif found < allowed:
        issues.append(
            (
                path,
                0,
                "?",
                f"allowlist が古い: 登録{allowed}件に対し実残存{found}件。"
                f"PLACEHOLDER_ALLOWLIST を {found} に減らす（0なら行ごと削除）",
            )
        )
    else:
        for lineno, hit in placeholder_hits:
            issues.append(
                (path, lineno, "許", f"{hit} が残存（allowlist 登録済み・要解消）")
            )

    return issues


def collect_files(target: Path):
    if target.is_file():
        return [target]
    files = []
    for md in target.rglob("*.md"):
        if any(d in md.parts for d in EXCLUDE_DIRS):
            continue
        files.append(md)
    return sorted(files)


def fix_section_in_file(path: Path, dry_run: bool):
    """§\\d+ → 第\\d+条 を自動置換。戻り値: (変更件数, ファイル変更されたか)"""
    text = path.read_text(encoding="utf-8")
    new_text, n = SECTION_PATTERN.subn(r"第\1条", text)
    if n == 0:
        return 0, False
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return n, True


# --self-test: 正規表現の回帰ガード。
# 旧パターン r"\[要確認\]" は「コロン+理由」形式を1件も拾えず、条文原文が未転記の
# ページを CI 全緑のまま通していた。同じ壊れ方を再発させないため、検出すべき形と
# 検出してはいけない形の両方を固定する。
PLACEHOLDER_SELF_TEST = [
    ("[要確認]", True),                      # 旧形式（裸）
    ("[要確認: e-Gov公式の本文をここに転記]", True),  # 半角コロン
    ("[要確認：全角コロンの理由]", True),          # 全角コロン
    ("> [要確認: 引用ブロック内]", True),          # blockquote
    ("[要確認: 閉じ括弧を書き忘れた", True),        # 閉じ忘れ
    ("A [要確認: 甲] と B [要確認: 乙]", True),    # 1行2件
    ("`[要確認: これは言及]`", False),            # コードスパン＝検査対象外
    ("要確認事項をまとめる", False),               # 角括弧なしの通常文
]

# フェンスの扱いの回帰ガード（2026-07-28・PR #173 と同型の穴を塞いだ際に制定）。
# (本文, 期待する検出種別の集合) — 空集合なら「何も検出しない」ことを固定する。
FENCE_SELF_TEST = [
    # 言語タグ付き＝本物のコード → 全検査スキップ
    ("```python\n# §5 と [要確認: x]\n```", set()),
    # タグ無し＝学習コンテンツ → 本文系（§・プレースホルダ）は検出する
    ("```\n🟩 解釈§5（電路の絶縁）\n```", {"§"}),
    ("```\n[要確認: ピラミッド内の宿題]\n```", {"?"}),
    # タグ無しでも**マークアップ検査**は適用しない（リンクとして描画されないため）
    ("```\n[ラベル]()\n```", set()),
    ("```\n<div></div>\n```", set()),
    # フェンスを閉じた後は通常どおり全検査に戻る（状態リークしない）
    ("```python\nx\n```\n§5 は本文", {"§"}),
]

STALE_TODO_SELF_TEST = [
    ("<!-- TODO: 148.md は未作成 -->", "148.md"),
    ("<!-- TODO: ../kijun/12.md は未作成 -->", "../kijun/12.md"),
    ("<!-- TODO: 158.md は未作成・優先度高 -->", "158.md"),
    ("<!-- TODO: kijun/56.md に本条への言及を追加検討 -->", None),  # 別動詞は対象外
]


def self_test() -> int:
    failures = []
    for text, expected in PLACEHOLDER_SELF_TEST:
        got = bool(PLACEHOLDER_PATTERN.search(_strip_code_spans(text)))
        if got != expected:
            failures.append(f"placeholder: {text!r} → 期待 {expected} / 実測 {got}")
    for text, expected in STALE_TODO_SELF_TEST:
        m = STALE_TODO_PATTERN.search(text)
        got = m.group(1) if m else None
        if got != expected:
            failures.append(f"stale-todo: {text!r} → 期待 {expected!r} / 実測 {got!r}")
    # フェンス扱いの回帰テスト（実ファイルに書き出して check_file を通す）
    import tempfile

    for body, expected in FENCE_SELF_TEST:
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "t.md"
            f.write_text(body, encoding="utf-8")
            kinds = {k for _, _, k, _ in check_file(f)}
        if kinds != expected:
            failures.append(
                f"fence: {body!r} → 期待 {sorted(expected)} / 実測 {sorted(kinds)}"
            )

    for line in failures:
        print(f"[FAIL] {line}")
    total = (
        len(PLACEHOLDER_SELF_TEST) + len(STALE_TODO_SELF_TEST) + len(FENCE_SELF_TEST)
    )
    print(f"self-test: {total - len(failures)}/{total} passed")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description="denken-wiki Markdown 品質チェッカ")
    parser.add_argument("target", nargs="?", default="docs", help="対象パス（省略時 docs/）")
    parser.add_argument("--fix-section", action="store_true", help="§記号を「第X条」に自動置換")
    parser.add_argument("--dry-run", action="store_true", help="--fix-section と併用で変更内容のみ表示")
    parser.add_argument("--self-test", action="store_true", help="検出パターンの回帰テスト")
    args = parser.parse_args()

    if args.self_test:
        sys.exit(self_test())

    target = Path(args.target)
    if not target.exists():
        print(f"対象が存在しない: {target}", file=sys.stderr)
        sys.exit(2)

    files = collect_files(target)

    if args.fix_section:
        total_replaced = 0
        modified_files = []
        for f in files:
            n, modified = fix_section_in_file(f, args.dry_run)
            if n > 0:
                try:
                    rel = f.relative_to(Path.cwd())
                except ValueError:
                    rel = f
                print(f"[FIX] {rel}: {n} 箇所{'（dry-run）' if args.dry_run else '修正'}")
                total_replaced += n
                if modified:
                    modified_files.append(f)
        print()
        verb = "would replace" if args.dry_run else "replaced"
        print(f"{verb}: {total_replaced} § symbols across {len(modified_files)} files")
        sys.exit(0)

    all_issues = []
    for f in files:
        all_issues.extend(check_file(f))

    # 「許」= allowlist 登録済みプレースホルダ。表示するが exit code には影響させない。
    errors = [i for i in all_issues if i[2] != "許"]
    allowlisted = [i for i in all_issues if i[2] == "許"]

    counts = {"§": 0, "簡": 0, "?": 0, "空": 0, "壊": 0}
    affected_files = set()
    for path, lineno, kind, msg in errors:
        try:
            rel = path.relative_to(Path.cwd())
        except ValueError:
            rel = path
        print(f"[{kind}] {rel}:{lineno} {msg}")
        if kind in counts:
            counts[kind] += 1
        affected_files.add(path)

    for path, lineno, kind, msg in allowlisted:
        try:
            rel = path.relative_to(Path.cwd())
        except ValueError:
            rel = path
        print(f"[許] {rel}:{lineno} {msg}")

    print()
    print(
        f"Found: {counts['§']} § symbols, {counts['簡']} simplified chars, "
        f"{counts['?']} placeholders, {counts['空']} empty elements, "
        f"{counts['壊']} broken relative links"
    )
    print(f"across {len(affected_files)}/{len(files)} files")
    # 件数合算（verify_suite の _detail_wiki）に混ざらないよう別行に出す
    print(f"Allowlisted placeholders (WARN, not counted): {len(allowlisted)}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
