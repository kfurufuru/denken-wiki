"""
sync_quiz_to_wiki.py
quiz.html のテスト記録を解析して theory/index.md を自動更新し git push する。

使い方:
  python scripts/sync_quiz_to_wiki.py [quiz.htmlのパス]

デフォルトの quiz.html パス:
  C:/Users/kfuru/.secretary/denken3-study-dashboard/quiz.html
"""

import re
import sys
from pathlib import Path
from datetime import date
import subprocess

# ---- 設定 ----------------------------------------------------------------
QUIZ_HTML_DEFAULT = Path(r"C:/Users/kfuru/.secretary/denken3-study-dashboard/quiz.html")
WIKI_ROOT = Path(__file__).parent.parent          # denken-wiki/
THEORY_INDEX = WIKI_ROOT / "docs/theory/index.md"

SUBJECT_FILTER = "理論"   # theory/index.md に反映する科目
# denken-wiki-riron 側で管理するテーマはスキップ
SKIP_THEMES = {"三相交流"}
# -------------------------------------------------------------------------


def parse_quiz_records(html: str) -> list[dict]:
    """tbody の <tr> を解析してレコードリストを返す。"""
    # テーブル行をざっくり抽出（HTML が1行に収まっているため tr 単位で処理）
    rows = re.findall(r"<tr>(.*?)</tr>", html, re.DOTALL)
    records = []
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL)
        if len(cells) < 5:
            continue
        # 日付
        date_raw = re.sub(r"<[^>]+>", "", cells[0]).strip()
        if not re.match(r"\d{4}-\d{2}-\d{2}", date_raw):
            continue
        # 科目
        subject = re.sub(r"<[^>]+>", "", cells[1]).strip()
        # テーマ
        theme = re.sub(r"<[^>]+>", "", cells[2]).strip()
        # 結果 (OK / Risky / NG)
        result_match = re.search(r"(OL|OK|Risky|NG)", cells[4])
        raw = result_match.group(1) if result_match else "?"
        result = "OK" if raw == "OL" else raw
        records.append({"date": date_raw, "subject": subject, "theme": theme, "result": result})
    return records


def latest_by_theme(records: list[dict], subject: str) -> dict[str, dict]:
    """科目でフィルタし、テーマごとに最新レコードを返す。"""
    filtered = [r for r in records if r["subject"] == subject]
    latest: dict[str, dict] = {}
    for r in filtered:
        if r["theme"] not in latest or r["date"] > latest[r["theme"]]["date"]:
            latest[r["theme"]] = r
    return latest


def build_table_rows(theme_map: dict[str, dict], existing_rows: list[dict]) -> str:
    """既存テーブル行をベースに status と最終テスト日を更新した Markdown 行を生成。"""
    lines = []
    # 既存テーマ順を維持しつつ更新
    seen = set()
    for row in existing_rows:
        theme = row["theme"]
        seen.add(theme)
        if theme in theme_map:
            info = theme_map[theme]
            lines.append(
                f"| [{theme}]({row['link']}) | {row['hint']} | {info['result']} | {info['date']} |"
            )
        else:
            # quiz に記録なし → 既存情報を保持
            lines.append(
                f"| [{theme}]({row['link']}) | {row['hint']} | {row['status']} | {row.get('last_test', '—')} |"
            )
    # quiz にあるが既存テーブルにないテーマを末尾に追記
    for theme, info in theme_map.items():
        if theme not in seen:
            lines.append(f"| {theme} | — | {info['result']} | {info['date']} |")
    return "\n".join(lines)


def parse_existing_table(md: str) -> list[dict]:
    """index.md の収録テーマテーブルを解析して辞書リストを返す。"""
    rows = []
    in_table = False
    header_skipped = False
    for line in md.splitlines():
        if line.strip().startswith("| テーマ"):
            in_table = True
            continue
        if in_table and line.strip().startswith("|---"):
            header_skipped = True
            continue
        if in_table and header_skipped and line.strip().startswith("|"):
            parts = [p.strip() for p in line.strip().strip("|").split("|")]
            if len(parts) < 3:
                break
            # テーマセル: "[テキスト](link)"
            m = re.match(r"\[(.+?)\]\((.+?)\)", parts[0])
            if not m:
                break
            theme_text = m.group(1)
            link = m.group(2)
            hint = parts[1]
            status = parts[2]
            last_test = parts[3] if len(parts) > 3 else "—"
            rows.append({"theme": theme_text, "link": link, "hint": hint,
                         "status": status, "last_test": last_test})
        elif in_table and header_skipped and not line.strip().startswith("|"):
            break
    return rows


def update_index_md(md: str, theme_map: dict[str, dict], today: str) -> str:
    """index.md の収録テーマテーブルと最終更新日を書き換えて返す。"""
    existing_rows = parse_existing_table(md)
    new_table_header = "| テーマ | 主なひっかかり | ステータス | 最終テスト |\n|--------|--------------|-----------|-----------|"
    new_rows = build_table_rows(theme_map, existing_rows)
    new_table = new_table_header + "\n" + new_rows

    # テーブル全体を置換（ヘッダ行〜最後の "|" 行）
    md = re.sub(
        r"\| テーマ \|.*?\n(?:\|[-| ]+\n)?(?:\|.*\n)*",
        new_table + "\n",
        md,
        flags=re.DOTALL,
    )
    # 最終更新日を更新
    md = re.sub(
        r"\*最終更新: [\d-]+.*\*",
        f"*最終更新: {today} | quiz.html より自動同期*",
        md,
    )
    return md


def git_commit_push(repo: Path, message: str) -> None:
    def run(cmd):
        result = subprocess.run(cmd, cwd=repo, capture_output=True,
                                encoding="utf-8", errors="replace")
        if result.returncode != 0 and result.stderr:
            print(f"[warn] {' '.join(cmd)}: {result.stderr.strip()}")
        return result

    run(["git", "add", "docs/theory/index.md"])
    result = run(["git", "commit", "-m", message])
    if "nothing to commit" in (result.stdout or "") + (result.stderr or ""):
        print("[info] 変更なし。push をスキップします。")
        return
    run(["git", "push"])
    print("[ok] git push 完了")


def main():
    quiz_path = Path(sys.argv[1]) if len(sys.argv) > 1 else QUIZ_HTML_DEFAULT
    if not quiz_path.exists():
        print(f"[error] quiz.html が見つかりません: {quiz_path}")
        sys.exit(1)

    html = quiz_path.read_text(encoding="utf-8")
    records = parse_quiz_records(html)
    print(f"[info] {len(records)} 件のレコードを読み込みました")

    theme_map = latest_by_theme(records, SUBJECT_FILTER)
    theme_map = {k: v for k, v in theme_map.items() if k not in SKIP_THEMES}
    print(f"[info] 理論テーマ: {list(theme_map.keys())}")

    md = THEORY_INDEX.read_text(encoding="utf-8")
    today = str(date.today())
    new_md = update_index_md(md, theme_map, today)

    if new_md == md:
        print("[info] 差分なし。ファイルは変更しません。")
    else:
        THEORY_INDEX.write_text(new_md, encoding="utf-8")
        print(f"[ok] {THEORY_INDEX} を更新しました")

    git_commit_push(WIKI_ROOT, f"theory: sync quiz {today} - auto update status and last-test date")


if __name__ == "__main__":
    main()
