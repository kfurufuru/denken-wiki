"""kaishaku/*.md の H1 タイトルと ファイル名（条番号）の整合をチェック。

電技解釈は告示で e-Gov に載らないため、audit_titles.py（省令側）と異なり
外部正本との照合は出来ない。代わりに以下の内部整合のみ検査する:

1. ファイル名 (NN.md) と H1「電技解釈 第NN条 — タイトル」の条番号が一致するか
2. kaishaku/index.md の表記と H1 タイトルが一致するか

使い方:
    python scripts/audit_kaishaku_titles.py
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
KAISHAKU = ROOT / "docs" / "articles" / "kaishaku"
INDEX_MD = KAISHAKU / "index.md"


def parse_h1(path: Path) -> tuple[int | None, str | None]:
    text = path.read_text(encoding="utf-8")
    first_line = text.split("\n", 1)[0]
    m = re.match(r"^#\s*電技解釈\s*第(\d+)条\s*[—\-‐–]\s*(.+?)\s*$", first_line)
    if not m:
        return None, None
    return int(m.group(1)), m.group(2).strip()


def parse_index_titles() -> dict[int, str]:
    """kaishaku/index.md の表から 条番号→タイトル のマップを抽出"""
    if not INDEX_MD.exists():
        return {}
    text = INDEX_MD.read_text(encoding="utf-8")
    titles: dict[int, str] = {}
    # | 第NN条 | [タイトル](NN.md) | ... |  または  | 第NN条 | タイトル | ...
    for m in re.finditer(r"\|\s*第(\d+)条\s*\|\s*(?:\[([^\]]+)\]\([^)]+\)|([^|]+?))\s*\|", text):
        n = int(m.group(1))
        t = (m.group(2) or m.group(3) or "").strip()
        titles[n] = t
    return titles


def main() -> int:
    results: list[tuple[str, str, str]] = []
    index_titles = parse_index_titles()

    for md in sorted(KAISHAKU.glob("*.md"), key=lambda p: p.name):
        if md.name == "index.md":
            continue
        try:
            file_n = int(md.stem)
        except ValueError:
            continue
        h1_n, h1_title = parse_h1(md)
        if h1_n is None:
            results.append(("NO_H1", md.name, "H1 が解釈タイトル形式でない"))
            continue
        if file_n != h1_n:
            results.append((
                "MISMATCH_FILE",
                md.name,
                f"ファイル名=第{file_n}条 / H1=第{h1_n}条 ({h1_title})",
            ))
            continue
        idx_title = index_titles.get(file_n)
        if idx_title and idx_title != h1_title:
            # 軽微: index は短縮表記の場合がある → warning のみ
            results.append((
                "INDEX_DIFF",
                md.name,
                f"H1='{h1_title}' / index='{idx_title}'",
            ))
        else:
            results.append(("OK", md.name, f"第{file_n}条 {h1_title}"))

    ok = [r for r in results if r[0] == "OK"]
    issues = [r for r in results if r[0] != "OK"]

    for r in ok:
        print(f"  [OK] {r[1]} - {r[2]}")
    if issues:
        print()
        print("=== 異常 ===")
        for r in issues:
            print(f"  [{r[0]}] {r[1]} - {r[2]}")
    print()
    print(f"Total: {len(results)} / OK: {len(ok)} / 異常: {len(issues)}")

    # MISMATCH_FILE/NO_H1 のみ非0で返す（INDEX_DIFF は warning）
    serious = [r for r in issues if r[0] in ("MISMATCH_FILE", "NO_H1")]
    return 0 if not serious else 2


if __name__ == "__main__":
    sys.exit(main())
