#!/usr/bin/env python3
"""法令数値整合性チェッカー (check_law_facts.py)

2026-05-31 セッションで発生した3類型のハルシネーションを機械検出する。
ChatGPT・古舘さん指摘なしには Claude 自身が検出できなかった構造的盲点を補う。

検出ルール:
  H01: 解釈第14条の根拠として「1/2000」を引用
       正しくは「漏えい電流1mA以下」(解釈第14条第1項第二号)
       「1/2000」は省令第22条(低圧電線路)の規定。電路とは別概念。
  H02: 第15条を低圧電路の活線代替根拠とする誤り
       第15条は高圧・特別高圧電路の耐圧試験規定(1.5倍×10分)。
       低圧電路の活線代替は解釈第14条第1項第二号。
  H03: 三相3線式200VをB種接地のみで0.1MΩと断定する誤り
       日本の低圧三相配電はΔ-Δ結線主流(対地200V→0.2MΩ)。
       Y結線中性点接地のみ115V→0.1MΩ(レアケース)。

Usage:
    python scripts/check_law_facts.py                    # docs/ 全体
    python scripts/check_law_facts.py docs/articles/kaishaku/14.md
    python scripts/check_law_facts.py --staged           # staged ファイルのみ (pre-commit用)

Exit codes:
    0  ERROR 0件（WARNING のみなら pass）
    1  ERROR 1件以上
"""
from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"

CONTEXT_WINDOW = 6  # パターン前後N行をexclude_context判定に使う


@dataclass
class Rule:
    id: str
    description: str
    patterns: list[str]
    exclude_contexts: list[str]
    severity: str  # "ERROR" | "WARNING"
    note: str = ""


RULES: list[Rule] = [
    Rule(
        id="H01",
        description="解釈第14条の根拠として「1/2000」を引用（正しくは漏えい電流1mA以下）",
        patterns=[
            r"第14条.{0,40}1[/／]2000",
            r"1[/／]2000.{0,40}第14条",
            r"解釈.{0,15}1[/／]2000.{0,30}代替",
            r"漏[洩えい]電流.{0,15}1[/／]2000.{0,40}第14",
        ],
        exclude_contexts=[
            "警告", "warning", "誤り", "❌", "別概念", "混同注意",
            "第22条", "電線路", "ではない", "not", "誤", "✗",
        ],
        severity="ERROR",
        note=(
            "解釈第14条の代替確認は「漏えい電流1mA以下」(第14条第1項第二号)。"
            "「1/2000」は省令第22条(低圧電線路)の規定。電路と電線路は別概念。"
        ),
    ),
    Rule(
        id="H02",
        description="第15条を低圧電路の活線代替根拠とする誤り（第15条は高圧・特高の耐圧試験）",
        patterns=[
            r"第15条.{0,40}代替.{0,20}確認",
            r"活線.{0,40}第15条.{0,30}漏[洩えい]",
            r"漏[洩えい]電流.{0,25}第15条.{0,25}以下",
            r"第15条.{0,40}低圧.{0,30}漏[洩えい]",
            r"停電.{0,20}第15条.{0,20}漏[洩えい]",
        ],
        exclude_contexts=[
            "警告", "warning", "誤り", "❌", "高圧", "特別高圧",
            "耐圧試験", "倍率", "1.5倍", "1.25倍", "ではない", "✗",
        ],
        severity="ERROR",
        note=(
            "第15条は高圧・特別高圧電路の絶縁性能（耐圧試験 1.5倍×10分等）。"
            "低圧電路の活線代替は解釈第14条第1項第二号「漏えい電流1mA以下」。"
        ),
    ),
    Rule(
        id="H03",
        description="三相3線式200VをB種接地のみで0.1MΩと断定（主流Δ結線は対地200V→0.2MΩ）",
        patterns=[
            r"三相.{0,20}200V?.{0,40}B種接地.{0,40}0\.1\s*MΩ",
            r"B種接地.{0,40}三相.{0,20}200V?.{0,40}0\.1\s*MΩ",
            r"三相3線式.{0,20}200V?.{0,30}115V.{0,30}0\.1\s*MΩ",
        ],
        exclude_contexts=[
            "警告", "warning", "誤り", "❌", "Y結線", "スター",
            "中性点接地", "ではない", "Δ結線", "デルタ", "✗", "誤",
        ],
        severity="WARNING",
        note=(
            "三相3線式200VはΔ-Δ結線が主流（対地200V→0.2MΩ）。"
            "Y結線中性点接地のみ対地115V→0.1MΩ（レアケース）。"
            "接地方式を明示せず断定しない。"
        ),
    ),
]


def get_staged_files() -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=ROOT, timeout=10,
        )
        return [
            ROOT / p for p in result.stdout.splitlines()
            if p.endswith(".md") and p.startswith("docs/") and (ROOT / p).exists()
        ]
    except Exception:
        return []


def get_context_block(lines: list[str], idx: int) -> str:
    start = max(0, idx - CONTEXT_WINDOW)
    end = min(len(lines), idx + CONTEXT_WINDOW + 1)
    return "\n".join(lines[start:end])


def check_file(path: Path) -> list[tuple[str, int, str, Rule]]:
    """Returns list of (filepath_rel, lineno, matched_text, rule)"""
    issues: list[tuple[str, int, str, Rule]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return issues

    lines = text.splitlines()
    seen: set[tuple[str, int]] = set()  # dedup (rule_id, lineno)

    for rule in RULES:
        for pattern in rule.patterns:
            for idx, line in enumerate(lines):
                if not re.search(pattern, line, re.IGNORECASE):
                    continue
                key = (rule.id, idx + 1)
                if key in seen:
                    continue
                ctx = get_context_block(lines, idx)
                if any(exc.lower() in ctx.lower() for exc in rule.exclude_contexts):
                    continue
                seen.add(key)
                rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
                issues.append((rel, idx + 1, line.strip()[:100], rule))

    return issues


def collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix == ".md" else []
    return sorted(target.rglob("*.md"))


def main(argv: list[str]) -> int:
    staged_mode = "--staged" in argv
    args = [a for a in argv if not a.startswith("-")]

    if staged_mode:
        files = get_staged_files()
    elif args:
        files = []
        for a in args:
            files.extend(collect_files(ROOT / a if not Path(a).is_absolute() else Path(a)))
    else:
        files = collect_files(DOCS_DIR)

    if not files:
        print("check_law_facts: 対象ファイルなし (skip)")
        return 0

    all_issues: list[tuple[str, int, str, Rule]] = []
    for f in files:
        all_issues.extend(check_file(f))

    if not all_issues:
        print(f"✅ check_law_facts: 0件 — {len(files)} ファイル検査済")
        return 0

    error_count = sum(1 for *_, r in all_issues if r.severity == "ERROR")
    warn_count = sum(1 for *_, r in all_issues if r.severity == "WARNING")

    for filepath, lineno, text, rule in all_issues:
        icon = "❌" if rule.severity == "ERROR" else "⚠️"
        print(f"{icon} [{rule.id}] {filepath}:{lineno}")
        print(f"   検出: {text}")
        print(f"   問題: {rule.description}")
        if rule.note:
            print(f"   正解: {rule.note}")
        print()

    print(f"合計: ERROR {error_count}件 / WARNING {warn_count}件 (対象 {len(files)} ファイル)")
    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
