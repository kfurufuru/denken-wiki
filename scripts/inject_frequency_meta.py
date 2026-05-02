#!/usr/bin/env python3
"""
全条文 Markdown に「📊 試験対策メタ」 admonition を注入し、
docs/articles/index.md の各条文リンク行に頻度バッジ＋ランクを追記する。

頻度ランク:
  5回以上  : 🔥🔥🔥 / A
  2〜4回   : 🔥🔥   / B
  1回      : 🔥     / C
  0回      : (バッジなし) / C

挿入位置:
  h1 (# 第X条 ...) の直後・空行を挟み、最初の本文ブロックの前。
  既に "試験対策メタ" admonition があれば skip。
"""
from __future__ import annotations
import io
import re
import sys
from pathlib import Path

# 既存スクリプトの集計関数を import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compute_frequency import (  # noqa: E402
    parse_article_field,
    to_filepath,
    ARTICLES,
    KAKOMON,
)

import yaml  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
INDEX_MD = ARTICLES / "index.md"


def freq_to_rank(n: int):
    """出題回数 -> (badge, rank, rank_label)"""
    if n >= 5:
        return ("🔥🔥🔥", "A", "重要必須")
    if n >= 2:
        return ("🔥🔥", "B", "重要")
    if n >= 1:
        return ("🔥", "C", "基本")
    return ("", "C", "基本")


def build_admonition(n: int) -> str:
    badge, rank, label = freq_to_rank(n)
    if n == 0:
        badge_disp = "—"
        count_phrase = "過去14年で出題なし"
    else:
        badge_disp = badge
        count_phrase = f"過去14年で {n} 回出題"
    return (
        '!!! abstract "📊 試験対策メタ"\n'
        f'    - **出題頻度**: {badge_disp}（{count_phrase}）\n'
        f'    - **重要度**: {rank}（{label}）\n'
        f'    - **直近出題**: \n'
    )


# h1 行（"# ..." で始まる、ただし "## " ではない）
H1_RE = re.compile(r"^# [^#].*$", re.M)


# 手書きの standalone「**出題頻度**: ...」行を検出
# - h1直後の行頭から始まるもの（インデント無し）が対象
# - メタブロック内の `    - **出題頻度**: ...` は4スペース字下げのため対象外
# - フォーマット多様（"N回/14年 ★..."、"N〜M回/14年"、"高 ★..."、"R01, H30(N回) ★..."、
#   "1回/22年 ★..." など）に対応するため、行頭 `**出題頻度**` 全体を貪欲削除
HANDWRITTEN_FREQ_RE = re.compile(
    r"^\*\*出題頻度\*\*[:：][^\n]*\n", re.MULTILINE
)


def inject_into_article(path: Path, n: int) -> tuple[bool, str]:
    """条文 Markdown に admonition を注入し、手書きの出題頻度行があれば削除する。
    戻り値: (変更したか, 理由)
    """
    text = path.read_text(encoding="utf-8")
    original_text = text
    actions = []

    # 1. 手書きの「**出題頻度**: N回/14年 ★...」行を削除（矛盾の温床）
    text_after_strip = HANDWRITTEN_FREQ_RE.sub("", text)
    if text_after_strip != text:
        text = text_after_strip
        actions.append("stripped-handwritten-freq")

    # 2. メタ未注入なら admonition を注入
    if "試験対策メタ" not in text:
        m = H1_RE.search(text)
        if m:
            h1_end = m.end()
            insert = "\n\n" + build_admonition(n) + "\n"
            text = text[:h1_end] + insert + text[h1_end:]
            actions.append("injected-meta")
        else:
            if not actions:
                return False, "skip:no-h1"

    # 3. 空行の重複を整理
    text = re.sub(r"\n{3,}", "\n\n", text)

    if text != original_text:
        path.write_text(text, encoding="utf-8")
        return True, "+".join(actions) if actions else "normalized"
    return False, "skip:already-has-meta"


def update_index(counts: dict[Path, int]) -> int:
    """docs/articles/index.md の各条文リンク行に頻度バッジ＋ランクを追記する。"""
    text = INDEX_MD.read_text(encoding="utf-8")

    # リンク行のパターン: "[第X条（...）](path/)" を含む行
    # path は kijun/{N}/, kaishaku/{N}/, jigyoho/{N}/, other/{slug-N}/
    link_re = re.compile(
        r"\(\s*(?P<sub>kijun|kaishaku|jigyoho|other)/(?P<slug>[a-z\-]*\d+)/\s*\)"
    )

    updated_count = 0

    def slug_to_filename(sub: str, slug: str) -> str:
        # slug例: "5", "koji-shi-2", "pse-10", "jiko-3"
        return slug + ".md"

    # 既にバッジが付いた直後の `(...)` をスキップするための判定
    badge_after_re = re.compile(r"\)\s+(?:🔥+|—)\s+[A-C]\b")

    def replace_in_line(line: str) -> str:
        nonlocal updated_count

        def repl(mm: re.Match) -> str:
            nonlocal updated_count
            # 直後にすでにバッジが付いているならスキップ
            tail = line[mm.end():mm.end() + 12]
            if re.match(r"\s+(?:🔥+|—)\s+[A-C]\b", tail):
                return mm.group(0)
            sub = mm.group("sub")
            slug = mm.group("slug")
            path = ARTICLES / sub / slug_to_filename(sub, slug)
            n = counts.get(path, 0)
            badge, rank, _ = freq_to_rank(n)
            badge_disp = badge if badge else "—"
            updated_count += 1
            return mm.group(0) + f" {badge_disp} {rank}"

        return link_re.sub(repl, line)

    new_lines = [replace_in_line(line) for line in text.splitlines(keepends=True)]
    new_text = "".join(new_lines)
    if new_text != text:
        INDEX_MD.write_text(new_text, encoding="utf-8")
    return updated_count


def collect_counts() -> dict[Path, int]:
    data = yaml.safe_load(KAKOMON.read_text(encoding="utf-8"))
    problems = data.get("problems", [])
    counts: dict[Path, int] = {}
    # 全条文ファイルを 0 で初期化
    for sub in ("kijun", "kaishaku", "jigyoho", "other"):
        for f in (ARTICLES / sub).glob("*.md"):
            if f.name == "index.md":
                continue
            counts[f] = 0
    # 集計
    for p in problems:
        field = p.get("article", "") or ""
        for law, num in parse_article_field(field):
            path = to_filepath(law, num)
            if path is None or not path.exists():
                continue
            counts[path] = counts.get(path, 0) + 1
    return counts


def main():
    counts = collect_counts()
    print(f"[INFO] 集計対象ファイル数: {len(counts)}")

    injected = 0
    skipped = 0
    skip_reasons: dict[str, int] = {}
    for path in sorted(counts.keys()):
        n = counts[path]
        ok, reason = inject_into_article(path, n)
        if ok:
            injected += 1
        else:
            skipped += 1
            skip_reasons[reason] = skip_reasons.get(reason, 0) + 1
    print(f"[INFO] 注入: {injected} ファイル / スキップ: {skipped} ファイル")
    for r, c in skip_reasons.items():
        print(f"        - {r}: {c}")

    idx_updated = update_index(counts)
    print(f"[INFO] index.md リンク行更新: {idx_updated} 行")


if __name__ == "__main__":
    main()
