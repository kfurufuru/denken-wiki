#!/usr/bin/env python3
"""条文原文ブロックの「※ N-M表 は本ページの解説表を参照」が実在の解説表を指すかを検査する。

背景:
    条文原文を逐語転記する際、原典の表（罫線つき）は markdown に落とせないため
    「※ 59-3表 は本ページの解説表を参照（原文の表は未転記）」というマーカーで
    ページ本文の解説表へ読者を送る運用にしている。
    ところが**送り先の解説表が無いページ**が実測 15 件あり、読者は原文で
    「表を見よ」と言われたまま値に到達できない状態だった（2026-09-07 監査）。

検査:
    マーカーが指す `<N-M>表` が、そのページの**原文引用行（"> " 始まり）以外**に
    1 回でも出現するかを見る。0 回なら DANGLING。

    「解説表」の形は 33.md の `**33-1表（…）**` 型、17.md の
    `#### 原典の 17-1表（…）` 型、65.md のようにマーカー行自体へ内容を書く型など
    複数あるため、**見出しの書式ではなく言及の有無**で判定する。
    書式で判定すると 17.md が偽陽性になる（実測済み）。

解消のしかたは3通りとも可:
    1. 解説表を本文に転記する（59.md・16.md・231.md で採った）
    2. 表が小さければマーカー行に内容を直接書く（65.md で採った）
    3. ページの射程外ならマーカーを「本ページに対応する解説表は無い」に書き換える
       （10.md で採った。231.md の 231-2表 が先行例）
"""
from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
# 「解説表を参照せよ」と読める行を広めに拾う（文言を少し変えただけで検査を外れる
# のを防ぐため）。ただし「解説表は無い」と明示した行は解消済みなので除外する。
MARK = re.compile(r"※\s*(\d+-\d+)表[^\n]*解説表")
RESOLVED = re.compile(r"解説表は無い")


def scan(root: pathlib.Path | None = None) -> tuple[list[tuple[str, str]], int, int]:
    root = root or ROOT / "docs" / "articles"
    findings: list[tuple[str, str]] = []
    markers = 0
    pages = 0
    for path in sorted(root.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        ids = list(dict.fromkeys(
            tid
            for line in text.split("\n")
            if not RESOLVED.search(line)
            for tid in MARK.findall(line)
        ))
        if not ids:
            continue
        pages += 1
        body = "\n".join(
            line for line in text.split("\n") if not line.lstrip().startswith(">")
        )
        for tid in ids:
            markers += 1
            # 左境界が要る: "9-1表" は "19-1表" の部分文字列になる
            if not re.search(r"(?<!\d)" + re.escape(tid) + "表", body):
                try:
                    name = str(path.relative_to(ROOT))
                except ValueError:
                    name = str(path)
                findings.append((name, tid + "表"))
    return findings, markers, pages


def self_test() -> int:
    import tempfile

    cases = [
        # (本文, 期待する DANGLING 件数, 説明)
        ("    > ※ 9-1表 は本ページの解説表を参照（原文の表は未転記）\n", 1, "送り先なし"),
        ("**9-1表（x）**\n\n    > ※ 9-1表 は本ページの解説表を参照（原文の表は未転記）\n",
         0, "bold キャプション型"),
        ("#### 原典の 9-1表（x）\n\n    > ※ 9-1表 は本ページの解説表を参照（原文の表は未転記）\n",
         0, "見出し型（17.md）— 書式判定だと偽陽性になる形"),
        ("    > ※ 9-1表 は未転記。本ページに対応する解説表は無い。\n", 0, "解消済みの文言"),
        ("    > ※ 9-1表（原文の表は未転記・2行のため内容をここに示す）: 単心＝…\n",
         0, "マーカー行に内容を書く型（65.md）"),
        ("本文で 9-1表 に言及\n\n    > ※ 9-1表 は本ページの解説表を参照（原文の表は未転記）\n"
         "    > 9-1表 は原文引用行なので数えない\n", 0, "原文行以外に言及あり"),
        ("    > 9-1表 は原文引用行\n    > ※ 9-1表 は本ページの解説表を参照（原文の表は未転記）\n",
         1, "言及が原文引用行だけ＝送り先にならない"),
        ("    > ※ 9-1表 は本ページの解説表を参照（原文の表は未転記）\n"
         "    > ※ 9-2表 は本ページの解説表を参照（原文の表は未転記）\n"
         "**9-2表（x）**\n", 1, "同一ページで片方だけ解消"),
        ("**19-1表（x）**\n\n    > ※ 9-1表 は本ページの解説表を参照（原文の表は未転記）\n",
         1, "部分一致で誤って ok にしない（19-1表 は 9-1表 ではない）"),
        ("マーカーなし。9-1表 とだけ書いてある。\n", 0, "マーカーが無いページは対象外"),
        ("    > ※ 9-1表 は本ページの解説表をご覧ください\n", 1,
         "文言を変えても拾う（『参照』でなく『ご覧ください』）"),
        ("    > ※ 9-1表 は未転記。本ページに対応する解説表は無い。原典を参照すること。\n",
         0, "『解説表は無い』は解消済み扱い（『参照』の語があっても拾わない）"),
    ]
    failed = 0
    for i, (body, want, label) in enumerate(cases, 1):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d)
            (p / "t.md").write_text(body, encoding="utf-8")
            got = len(scan(p)[0])
        ok = got == want
        failed += not ok
        print(f"  [{i:2d}] {'PASS' if ok else 'FAIL'} want={want} got={got}  {label}")
    print(f"self-test: {len(cases) - failed}/{len(cases)}")
    return 1 if failed else 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    findings, markers, pages = scan()
    for path, tid in findings:
        print(f"{path}: {tid} のマーカーが指す解説表がページ内に無い（DANGLING）")
    print(
        f"check_hyou_pointer: {len(findings)}件"
        f"（マーカー {markers}件／{pages}ページを照合）"
    )
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
