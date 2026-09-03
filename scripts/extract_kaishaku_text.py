#!/usr/bin/env python3
"""電技解釈PDF → 逐語照合用テキストキャッシュを生成する（オフライン専用）.

`docs/assets/pdf/denken-kaishaku-r07-11.pdf` は電技解釈の唯一の原典だが、
電技解釈は e-Gov 法令API に無いため、条文原文の逐語照合には PDF を読むしかない。
PDF 解析には PyMuPDF が要るが CI には入れたくない（重い・照合のたびに解析するのも無駄）ので、
**抽出結果を gzip テキストとして repo にコミットし、CI 側はそれを読むだけ**にする。

生成物: scripts/cache/kaishaku-r07-11.txt.gz
  1行目に `# source-sha256: <PDFのSHA256>` を書き込む。
  check_law_verbatim.py がこのハッシュを PDF と突き合わせ、
  **PDF を差し替えたのにキャッシュを再生成していない**状態を検出する
  （派生物ドリフトの3段防御と同じ思想）。

使い方（PyMuPDF がある環境で・年次改訂で PDF を差し替えたときだけ）:
    pip install pymupdf
    python scripts/extract_kaishaku_text.py
"""
from __future__ import annotations

import gzip
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PDF = ROOT / "docs" / "assets" / "pdf" / "denken-kaishaku-r07-11.pdf"
OUT = ROOT / "scripts" / "cache" / "kaishaku-r07-11.txt.gz"


def main() -> int:
    if not PDF.exists():
        print(f"ERROR: PDF がありません: {PDF}", file=sys.stderr)
        return 2
    try:
        try:
            import pymupdf as fitz
        except ImportError:
            import fitz  # PyMuPDF (旧API)
    except ImportError:
        print(
            "ERROR: PyMuPDF が必要です（pip install pymupdf）。\n"
            "本スクリプトはオフライン専用で、CI では実行しません。",
            file=sys.stderr,
        )
        return 2

    digest = hashlib.sha256(PDF.read_bytes()).hexdigest()
    doc = fitz.open(PDF)
    parts = [f"# source-sha256: {digest}"]
    for i, page in enumerate(doc, start=1):
        parts.append(f"===== PDF_PAGE {i} =====")
        parts.append(page.get_text())
    text = "\n".join(parts)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as fh:
        fh.write(text)
    print(f"OK: {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes) / {len(doc)} pages")
    print(f"    source-sha256: {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
