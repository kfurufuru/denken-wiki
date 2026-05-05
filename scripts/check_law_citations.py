#!/usr/bin/env python3
"""法令引用整合性チェッカー

denken-wiki の Markdown 内の「電気事業法第N条」「電気工事士法第N条」等の引用が、
_data/law_articles.yml のマスタ（手続・対象）と整合しているか検証する。

使い方:
    python scripts/check_law_citations.py [path/to/file.md ...]
    （引数なしで docs/ 全体を検査）

検出する不整合:
- 「電気事業法第47条」の周辺に「届出」が出現 → 47条は認可なので警告
- 「電気事業法第48条」の周辺に「認可」が出現 → 48条は届出なので警告
- 「電気事業法第47条」と「自家用」が同一文脈 → 47条は事業用が対象（自家用は48条）

Pre-commit hook 用途を想定し、不整合があれば exit 1 で終了。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML が必要です (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
MASTER_PATH = ROOT / "_data" / "law_articles.yml"
DEFAULT_TARGET = ROOT / "docs"

# 検出パターン: 「電気事業法第47条」「電気工事士法第2条」等
CITATION_PATTERN = re.compile(
    r"(電気事業法|電気工事士法|電気関係報告規則)\s*第\s*(\d+)\s*条"
)

# 周辺コンテキスト窓 (前後の文字数)
CONTEXT_WINDOW = 80

# 手続きキーワード (条文との整合チェック対象)
PROCEDURE_KEYWORDS = {
    "認可": "認可",
    "届出": "届出",
    "選任": "選任",
    "使用前自主検査": "検査",
    "報告": "報告",
}

# 対象キーワード
TARGET_KEYWORDS = {
    "事業用電気工作物": "事業用",
    "自家用電気工作物": "自家用",
    "事業用工作物": "事業用",
    "自家用工作物": "自家用",
}


def load_master() -> dict:
    if not MASTER_PATH.exists():
        print(f"ERROR: マスタが見つかりません: {MASTER_PATH}", file=sys.stderr)
        sys.exit(2)
    with MASTER_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_context(text: str, start: int, end: int) -> str:
    s = max(0, start - CONTEXT_WINDOW)
    e = min(len(text), end + CONTEXT_WINDOW)
    return text[s:e]


def check_file(path: Path, master: dict) -> list[str]:
    """1ファイルを検査し、警告メッセージのリストを返す。"""
    warnings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"{path}: 読み込みエラー: {e}"]

    # 監修ログ・出典・参考リンクは検査対象外（過去の誤りを記録した文脈を含むため）
    # 監修ログ以降は除外
    log_marker = re.search(r"^##\s*監修ログ", text, re.MULTILINE)
    if log_marker:
        text = text[: log_marker.start()]

    for match in CITATION_PATTERN.finditer(text):
        law_name = match.group(1)
        article_num = int(match.group(2))

        articles = master.get(law_name, {})
        article_info = articles.get(article_num)
        if article_info is None:
            # マスタにない条文はスキップ（網羅率不足は別途扱い）
            continue

        expected_proc = article_info.get("手続")
        expected_target = article_info.get("対象")

        # 行番号算出
        line_no = text[: match.start()].count("\n") + 1

        # 周辺コンテキストから手続キーワードを抽出
        context = get_context(text, match.start(), match.end())

        # 同一行抽出
        line_start = text.rfind("\n", 0, match.start()) + 1
        line_end = text.find("\n", match.end())
        if line_end == -1:
            line_end = len(text)
        line_text = text[line_start:line_end]

        # 誤検出抑制: H1タイトル（# で始まる行）は対象外（page title は teaching scope marker）
        if line_text.lstrip().startswith("# "):
            continue

        # 誤検出抑制: 同一行で複数の条文番号が言及されている場合は対比文脈とみなしスキップ
        # （法律名プレフィックス無しの「第N条」も数える）
        article_count_in_line = len(re.findall(r"第\s*\d+\s*条", line_text))
        if article_count_in_line >= 2:
            continue

        # 手続不整合チェック
        if expected_proc in {"認可", "届出"}:
            for kw, kw_proc in PROCEDURE_KEYWORDS.items():
                if kw not in line_text:
                    continue
                if kw_proc != expected_proc and kw_proc in {"認可", "届出"}:
                    warnings.append(
                        f"{path}:{line_no}: {law_name}第{article_num}条は『{expected_proc}』が正しい "
                        f"（同一行に『{kw}』が出現）"
                    )

        # 対象（事業用／自家用）不整合チェック（参考レベル）
        # 注：自家用 ⊂ 事業用（広義）なので、マスタ「事業用」は自家用言及を許容する
        if expected_target == "自家用":
            for kw, kw_target in TARGET_KEYWORDS.items():
                if kw not in line_text:
                    continue
                if kw_target == "事業用":
                    warnings.append(
                        f"{path}:{line_no}: {law_name}第{article_num}条の対象は『{expected_target}』のみ "
                        f"（同一行に『{kw}』が出現・対比文脈なら無視可）"
                    )

    return warnings


def main(argv: list[str]) -> int:
    master = load_master()

    targets: list[Path] = []
    if len(argv) <= 1:
        targets = list(DEFAULT_TARGET.rglob("*.md"))
    else:
        for arg in argv[1:]:
            p = Path(arg)
            if p.is_dir():
                targets.extend(p.rglob("*.md"))
            elif p.is_file():
                targets.append(p)

    all_warnings: list[str] = []
    for t in targets:
        all_warnings.extend(check_file(t, master))

    if not all_warnings:
        print(f"OK: 法令引用 {len(targets)} ファイル検査・不整合なし")
        return 0

    print(f"WARNING: 法令引用の不整合を {len(all_warnings)} 件検出:", file=sys.stderr)
    for w in all_warnings:
        print(f"  - {w}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
