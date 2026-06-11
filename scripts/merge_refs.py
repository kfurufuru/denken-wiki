"""役に立った参考文献を `_data/refs-pending.yml` から `docs/reference/links.md` に統合する.

設計思想:
- append-only ログ（pending）→ links.md 末尾に追記 → merged に移動 の3段運用
- URL重複はスキップ（人間は重複を気にせず append OK）
- カテゴリは links.md の H2 見出しと部分一致で照合（柔軟マッチ）
- マッチしないカテゴリは pending に残す（要セクション作成）
- ADD 候補の URL は死活確認（HEAD→GET フォールバック）し、4xx/5xx・接続不可は
  pending に残す（404 の JEAC9701 が links.md にマージされ PR #77 で除去した事案の再発防止）
- refs-pending.yml の書き戻しは先頭に PENDING_HEADER を必ず付与する
  （yaml.safe_dump はコメントを保持しないため、ヘッダの運用ルール説明が毎回消えていた）

Exit codes:
    0  正常終了（merged が 0件でもエラーではない）
    1  YAML 構文エラー / links.md 読込失敗 など致命的エラー

CLI:
    python scripts/merge_refs.py                  # 実行（実反映）
    python scripts/merge_refs.py --dry-run        # 何が追加されるか確認のみ（書き込みなし）
    python scripts/merge_refs.py --verbose        # 詳細ログ（--dry-run なしだと実反映される点に注意）
    python scripts/merge_refs.py --skip-url-check # URL 死活確認を省略（オフライン環境等）
"""
from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

import yaml

# Windows shell の cp932 で日本語が壊れるのを防ぐ
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PENDING_YML = ROOT / "_data" / "refs-pending.yml"
LINKS_MD = ROOT / "docs" / "reference" / "links.md"

# refs-pending.yml の先頭ヘッダコメント。yaml.safe_dump はコメントを保持できないため、
# 書き戻し時に必ずこの定数を先頭へ付与する（2026-06-11 に2回手動復元した消失事案の再発防止）。
# ヘッダ文言の正本はこの定数。yml 側だけ直接編集しても次回マージで本定数の内容に戻る。
PENDING_HEADER = """\
# 役に立った参考文献の追加ログ
# 編集セッションで新規参照したURLをここに append すること。
# scripts/merge_refs.py が定期的に docs/reference/links.md にマージする。
#
# 運用ルール: .claude/rules/refs-auto-reflect.md
# - pending は append-only（直接削除しない・merge スクリプトのみが移動可）
# - カテゴリは links.md のセクション見出し（H2 / `## …`）と部分一致で照合される
# - 重複URLはスクリプトがスキップするので、人間は重複を気にせず append OK

"""

URL_CHECK_TIMEOUT = 10  # 秒
URL_CHECK_UA = (
    "Mozilla/5.0 (compatible; denken-wiki-merge-refs/1.0; "
    "+https://github.com/kfurufuru/denken-wiki)"
)


def load_pending() -> dict:
    if not PENDING_YML.exists():
        print(f"[merge_refs] pending yml not found: {PENDING_YML}", file=sys.stderr)
        sys.exit(1)
    try:
        doc = yaml.safe_load(PENDING_YML.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        print(f"[merge_refs] YAML 構文エラー: {e}", file=sys.stderr)
        sys.exit(1)
    doc.setdefault("pending", [])
    doc.setdefault("merged", [])
    return doc


def load_links_md() -> str:
    if not LINKS_MD.exists():
        print(f"[merge_refs] links.md not found: {LINKS_MD}", file=sys.stderr)
        sys.exit(1)
    return LINKS_MD.read_text(encoding="utf-8")


def find_section_headings(md_text: str) -> list[tuple[int, str]]:
    """links.md の H2 見出し（`## …`）の (行番号, 見出しテキスト) を返す."""
    headings = []
    for i, line in enumerate(md_text.splitlines()):
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            headings.append((i, m.group(1).strip()))
    return headings


def url_already_in_links(url: str, md_text: str) -> bool:
    """links.md に既に同URLが記載されているか.

    Markdown の `[text](url)` 形式 / 素URL いずれもカバー。
    比較は前後空白除去のみ（厳密一致）。
    """
    return url in md_text


def check_url_alive(url: str) -> tuple[bool, str]:
    """ADD 候補 URL の死活確認. HEAD → 失敗時 GET フォールバックの2段で試す.

    Returns:
        (True, detail)  : 2xx/3xx 応答あり（リダイレクトは urllib が自動追従）
        (False, detail) : 4xx/5xx または接続不可（DNS失敗・タイムアウト等）

    接続不可はネットワーク不通と区別できないが、未検証 URL を links.md に
    公開しない安全側に倒して False を返す。オフライン環境で実マージしたい場合は
    --skip-url-check で明示的に省略する。
    """
    detail = ""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": URL_CHECK_UA})
        try:
            with urllib.request.urlopen(req, timeout=URL_CHECK_TIMEOUT) as resp:
                return True, f"{method} {resp.status}"
        except urllib.error.HTTPError as e:
            detail = f"{method} HTTP {e.code}"  # HEAD拒否(405等)の可能性があるためGETで再試行
        except OSError as e:  # URLError / TimeoutError / ConnectionError を包含
            detail = f"{method} 接続不可 ({getattr(e, 'reason', e)})"
        except ValueError as e:  # URL 形式不正（scheme 無し等）はリトライ不能
            return False, f"URL形式不正 ({e})"
    return False, detail


def find_section_end_line(md_text: str, heading_line: int) -> int:
    """指定 H2 見出しの直後セクションの「末尾行（次のH1/H2/水平線/EOFの直前）」を返す.

    `---` 区切りで分割している links.md 構造に対応：
    `---` を見つけたらその直前を末尾とみなす。
    """
    lines = md_text.splitlines()
    for j in range(heading_line + 1, len(lines)):
        line = lines[j]
        if re.match(r"^##\s+", line):
            return j - 1
        if line.strip() == "---":
            return j - 1
        if re.match(r"^#\s+", line):
            return j - 1
    return len(lines) - 1


def match_category(category: str, headings: list[tuple[int, str]]) -> tuple[int, str] | None:
    """category 文字列を H2 見出しと部分一致で照合.

    完全一致 > 見出しが category を含む > category が見出しを含む の優先順位。
    複数候補ある場合は最初に見つけた1件を返す。
    """
    cat_norm = category.strip()
    # 1. 完全一致
    for ln, h in headings:
        if h == cat_norm:
            return (ln, h)
    # 2. 見出しが category を含む（H2 が広い概念で category が部分指定）
    for ln, h in headings:
        if cat_norm in h:
            return (ln, h)
    # 3. category が見出しを含む（category が "1.3 電気工事士..." のように番号付きで詳細）
    for ln, h in headings:
        if h in cat_norm:
            return (ln, h)
    return None


def build_bullet(entry: dict) -> str:
    """pending entry から links.md に挿入する1行 bullet を生成."""
    title = entry.get("title", "(無題)")
    url = entry.get("url", "")
    rationale = entry.get("rationale", "")
    rationale_part = f" — {rationale}" if rationale else ""
    return f"- [{title}]({url}){rationale_part}"


def insert_bullets_into_md(
    md_text: str,
    insertions: list[tuple[int, str]],
) -> str:
    """insertions: [(insert_after_line_index, bullet_line), ...].

    後ろから挿入することで行番号のずれを回避。
    挿入位置の前行が空行でなければ空行を1つ追加してから bullet を入れる。
    挿入後、bullet が直後の '---'（区切り線）や見出しに密着している箇所には
    空行を1行補完する。密着すると Python-Markdown が bullet を setext 見出しと
    誤認し、hr が消えて bullet が <h2> 化するため（2026-06-11 修正）。
    """
    lines = md_text.splitlines()
    # 行番号が大きい順に挿入
    for line_idx, bullet in sorted(insertions, key=lambda x: -x[0]):
        # 直前が空行でなければ空行を入れる
        prev = lines[line_idx] if 0 <= line_idx < len(lines) else ""
        to_insert = []
        if prev.strip() != "":
            to_insert.append("")
        to_insert.append(bullet)
        # line_idx の「次」に挿入
        lines[line_idx + 1 : line_idx + 1] = to_insert
    # list item が直後の '---' / 見出しに密着していたら空行を補完（setext 誤認防止）
    normalized: list[str] = []
    for k, line in enumerate(lines):
        normalized.append(line)
        nxt = lines[k + 1] if k + 1 < len(lines) else ""
        if line.lstrip().startswith("- ") and (
            nxt.strip() == "---" or re.match(r"^#{1,6}\s+", nxt)
        ):
            normalized.append("")
    lines = normalized
    # 末尾の改行を保つ
    return "\n".join(lines) + ("\n" if md_text.endswith("\n") else "")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="実反映せずプレビューのみ")
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細ログ")
    parser.add_argument(
        "--skip-url-check",
        action="store_true",
        help="ADD 候補 URL の死活確認を省略（オフライン環境・bot 拒否サイトの誤検出回避用）",
    )
    args = parser.parse_args()

    doc = load_pending()
    md_text = load_links_md()
    headings = find_section_headings(md_text)

    if args.verbose:
        print(f"[merge_refs] links.md H2 セクション数: {len(headings)}")
        for _, h in headings:
            print(f"  - {h}")

    pending: list[dict] = doc["pending"]
    merged: list[dict] = doc["merged"]

    if not pending:
        print("[merge_refs] pending が空。何もすることがない。")
        return 0

    insertions: list[tuple[int, str]] = []  # (insert_after_line, bullet)
    new_pending: list[dict] = []
    new_merged: list[dict] = list(merged)

    today = date.today().isoformat()

    for entry in pending:
        url = entry.get("url", "").strip()
        title = entry.get("title", "(無題)")
        category = entry.get("category", "").strip()

        if not url:
            print(f"  [SKIP] URL未指定: {title}", file=sys.stderr)
            new_pending.append(entry)
            continue

        # 重複チェック
        if url_already_in_links(url, md_text):
            print(f"  [SKIP] already in links.md: {title} ({url})")
            # 既出は merged に移動（重複append防止）
            entry_done = dict(entry)
            entry_done["merged_at"] = today
            entry_done["merge_note"] = "already present in links.md (deduped)"
            new_merged.append(entry_done)
            continue

        # カテゴリ照合
        match = match_category(category, headings)
        if match is None:
            print(
                f"  [WARN] カテゴリ未マッチ・未マージ: {title}\n"
                f"         category='{category}' → links.md にセクション作成が必要",
                file=sys.stderr,
            )
            new_pending.append(entry)
            continue

        heading_line, heading_text = match

        # URL 死活確認（ADD 候補のみ）。NG はマージせず pending に残す
        if not args.skip_url_check:
            alive, detail = check_url_alive(url)
            if not alive:
                print(
                    f"  [WARN-URL] URL死活NG・未マージ: {title}\n"
                    f"             {url} → {detail}",
                    file=sys.stderr,
                )
                new_pending.append(entry)
                continue
            if args.verbose:
                print(f"  [URL-OK] {detail}: {url}")

        end_line = find_section_end_line(md_text, heading_line)
        bullet = build_bullet(entry)
        insertions.append((end_line, bullet))

        if args.verbose or args.dry_run:
            print(
                f"  [ADD] {title}\n"
                f"        category='{category}' → section='{heading_text}' (after L{end_line + 1})\n"
                f"        {bullet}"
            )
        else:
            print(f"  [ADD] {title} → '{heading_text}'")

        entry_done = dict(entry)
        entry_done["merged_at"] = today
        entry_done["merged_into_section"] = heading_text
        new_merged.append(entry_done)

    if args.dry_run:
        print(f"\n[DRY-RUN] 追記予定 {len(insertions)} 件 / pending残 {len(new_pending)} 件")
        return 0

    # --verbose 単独でもここに到達する（実マージ）。書き込み前に必ず可視化する
    print(
        "\n[merge_refs] ⚠ 実マージを実行します（links.md / refs-pending.yml に書き込み）。"
        "確認のみなら --dry-run を付けて再実行してください。",
        file=sys.stderr,
    )

    if not insertions:
        print("\n[merge_refs] 追記対象なし。pending YML のみ更新します。")
    else:
        new_md = insert_bullets_into_md(md_text, insertions)
        LINKS_MD.write_text(new_md, encoding="utf-8")
        print(f"\n[merge_refs] links.md に {len(insertions)} 件追記しました。")

    # pending YML 書き戻し
    doc["pending"] = new_pending
    doc["merged"] = new_merged
    PENDING_YML.write_text(
        PENDING_HEADER + yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    print(
        f"[merge_refs] refs-pending.yml 更新: pending={len(new_pending)} / merged={len(new_merged)}"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
