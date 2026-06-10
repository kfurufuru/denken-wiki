#!/usr/bin/env python3
"""数値クロス整合チェッカー (check_value_consistency.py)

article 内で同一の数値情報が「本文／テーブル／SVG <tspan>／Mermaid／折り畳み原文」
に分散して書かれているとき、一部だけ訂正して他を取り残す
"value-correction sweep" 事故（memory: feedback-value-correction-sweep-all-instances・
kijun/58 単相3線式200V→0.1MΩ 事案）を機械検出する。

手動デバッグループの「回帰検証税（manually verifies nothing else broke）」を
人手の grep から pre-commit / CI の機械ゲートへ移すことが目的。

検出ルール:
  V01 [MΩ太字バグ]  Ω(U+03A9) を太字(**...**)の内側に置くと、MkDocs 環境で
       フォント依存によりキリル文字に化ける（CLAUDE.md「MΩ表記ルール（Ω太字バグ回避）」）。
       正: **0.1**MΩ（数値だけ太字・MΩ は太字の外）。誤: **0.1MΩ**。 severity=ERROR。
       ※ `0.4**MΩ**`（太字を一旦閉じ MΩ は素・直後にまた太字開始）のような
         "並置" は誤検出しない（** の左右ペアリングで内部判定するため）。
  V02 [MΩ三段値の自己不整合]  同一ファイル内に複数回登場する「A／B／C MΩ」三段組のうち、
       多数派と1値だけ食い違う positional near-miss を検出（sweep 訂正漏れの疑い）。
       例: 多数派 0.1／0.2／0.4 に対し1箇所だけ 0.1／0.2／0.2。 severity=WARNING。

Usage:
    python scripts/check_value_consistency.py                       # docs/ 全体
    python scripts/check_value_consistency.py docs/articles/kijun/58.md
    python scripts/check_value_consistency.py docs/articles          # ディレクトリ可
    python scripts/check_value_consistency.py --staged              # staged のみ (pre-commit用)

Exit codes:
    0  ERROR 0件（WARNING のみなら pass）
    1  ERROR 1件以上
"""
from __future__ import annotations

import io
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"

# Ω は U+03A9（ギリシャ大文字オメガ）／ U+2126（OHM SIGN）の両方を拾う
_OHM = "[ΩΩ]"
_MOHM = re.compile(_OHM)  # "MΩ" の Ω 部分だけ判定すれば十分
_MOHM_UNIT = re.compile(r"M[ΩΩ]")  # 単位が MΩ か（ERROR）／単なる Ω か（WARNING）の判別
_NUM = r"\d+(?:\.\d+)?"

# V01: 「太字スパン全体が “数値＋Ω単位” そのもの」の形だけを bug とみなす。
#   ✅ flag:   **0.1MΩ** / **0.4MΩ以上** / **10Ω以下** / **0.1／0.2／0.4 MΩ** / **883 Ω**
#   ✗ 除外:   **なぜ10Ω以下か？** / **R ≦ 50/200 = 0.25Ω** / **C種=10Ω、D種=100Ω**
#             （文・式まるごとの強調にΩが紛れただけのもの = 別事象・過検出を避ける）
_VALUE_CHARS = r"\s\d.．,，/／×÷()（）=＝<>＜＞≦≧≤≥+\-~〜"
_VALUE_BOLD = re.compile(
    rf"^[{_VALUE_CHARS}]*\d[{_VALUE_CHARS}]*M?[ΩΩ](?:\s*(?:以上|以下|未満|超|程度))?\s*$"
)
# --fix 用: 数値部と単位部を分離（数値だけ太字に残し、単位は太字の外へ）
_VALUE_BOLD_SPLIT = re.compile(
    rf"^([{_VALUE_CHARS}]*\d[{_VALUE_CHARS}]*?)(M?[ΩΩ](?:\s*(?:以上|以下|未満|超|程度))?)\s*$"
)

# V02: 三段値（出現順を保持） — 2形式に対応
#   形式A: 「0.1／0.2／0.4MΩ」 （数値3つ→末尾にMΩ）
#   形式B: 「0.1MΩ／0.2MΩ／0.4MΩ」（各値にMΩ）
_TRIPLE_A = re.compile(
    rf"({_NUM})\s*[／/]\s*({_NUM})\s*[／/]\s*({_NUM})\s*M{_OHM}"
)
_TRIPLE_B = re.compile(
    rf"({_NUM})\s*M{_OHM}\s*[／/]\s*({_NUM})\s*M{_OHM}\s*[／/]\s*({_NUM})\s*M{_OHM}"
)

# 監修ログ以降は「過去の誤りを記録した文脈」を含むため V02 の対象外にする
_SUPERVISE_LOG = re.compile(r"^##\s*監修ログ", re.MULTILINE)


def bold_inside_segments(line: str) -> list[str]:
    """行を `**` で分割し、太字スパンの *内側* セグメントだけ返す。

    `**` を左から順にペアリングする。マーカーが奇数（閉じ忘れ）の場合、
    最後の開きっぱなしは太字とみなさない（誤検出抑制）。
    """
    parts = line.split("**")
    n_markers = len(parts) - 1
    n_spans = n_markers // 2
    return [parts[2 * k + 1] for k in range(n_spans)]


def check_bold_omega(lines: list[str]) -> list[tuple[int, str]]:
    """V01: 太字スパン *全体* が「数値＋Ω単位」になっている行を検出。

    文・式まるごとの強調にΩが紛れただけのもの（**なぜ10Ω以下か？** 等）は
    _VALUE_BOLD にマッチしないため拾わない。
    戻り値: (行番号, 該当する太字セグメント) のリスト
    """
    hits: list[tuple[int, str, str]] = []
    for idx, line in enumerate(lines):
        if "**" not in line or not _MOHM.search(line):
            continue
        for seg in bold_inside_segments(line):
            s = seg.strip()
            if _MOHM.search(s) and _VALUE_BOLD.match(s):
                # 単位が MΩ なら ERROR（ブロック対象）、単なる Ω なら WARNING（report-only）
                sev = "ERROR" if _MOHM_UNIT.search(s) else "WARNING"
                hits.append((idx + 1, s[:60], sev))
    return hits


def fix_line_bold(line: str, mohm_only: bool = False) -> str:
    """V01 を機械修正: **0.1MΩ** → **0.1**MΩ（数値だけ太字・単位は外）。

    数値値そのものの太字スパンのみ変換。文・式の強調は変えない。
    mohm_only=True のとき単位が MΩ のものだけ修正（単なる Ω は据え置く）。
    """
    def repl(m: re.Match) -> str:
        inner = m.group(1).strip()
        sm = _VALUE_BOLD_SPLIT.match(inner)
        if not sm:
            return m.group(0)
        num = sm.group(1).strip()
        unit = sm.group(2).strip()
        if not num:
            return m.group(0)
        if mohm_only and not _MOHM_UNIT.search(unit):
            return m.group(0)
        return f"**{num}**{unit}"

    return re.sub(r"\*\*([^*]+?)\*\*", repl, line)


def _fmt_triple(t: tuple[float, ...]) -> str:
    def one(v: float) -> str:
        return str(int(v)) if v == int(v) else str(v)
    return "／".join(one(v) for v in t)


def extract_triples(text: str) -> list[tuple[int, tuple[float, float, float]]]:
    out: list[tuple[int, tuple[float, float, float]]] = []
    for idx, line in enumerate(text.splitlines()):
        for pat in (_TRIPLE_A, _TRIPLE_B):
            for m in pat.finditer(line):
                try:
                    triple = (float(m.group(1)), float(m.group(2)), float(m.group(3)))
                except ValueError:
                    continue
                out.append((idx + 1, triple))
    return out


def check_triple_consistency(text: str) -> list[tuple[int, tuple, tuple]]:
    """V02: ファイル内の多数派三段値に対する positional near-miss を検出。

    戻り値: (行番号, 検出した三段値, 多数派三段値) のリスト
    """
    m = _SUPERVISE_LOG.search(text)
    if m:
        text = text[: m.start()]  # 監修ログ以降を除外

    triples = extract_triples(text)
    if len(triples) < 3:
        return []  # 母数が少なく多数派を確定できない → 判定しない

    counts = Counter(t for _, t in triples)
    majority, maj_count = counts.most_common(1)[0]
    if maj_count < 2:
        return []  # 同点ばらけ → どれが正か機械判定できない

    hits: list[tuple[int, tuple, tuple]] = []
    for lineno, t in triples:
        if t == majority:
            continue
        # 位置ごとに2/3一致 = 1値だけ食い違う「訂正漏れの形」のときだけ拾う。
        # 値が全く違う三段組は「別概念」とみなし誤検出を避ける。
        same = sum(1 for a, b in zip(t, majority) if a == b)
        if same == 2:
            hits.append((lineno, t, majority))
    return hits


def collect_files(target: Path) -> list[Path]:
    if target.is_file():
        return [target] if target.suffix == ".md" else []
    if target.is_dir():
        return sorted(target.rglob("*.md"))
    return []


def get_staged_files() -> list[Path]:
    try:
        r = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, cwd=ROOT, timeout=10,
        )
        return [
            ROOT / p for p in r.stdout.splitlines()
            if p.endswith(".md") and p.startswith("docs/") and (ROOT / p).exists()
        ]
    except Exception:
        return []


def main(argv: list[str]) -> int:
    staged = "--staged" in argv
    fix = "--fix" in argv
    mohm_only = "--mohm-only" in argv
    args = [a for a in argv if not a.startswith("-")]

    if staged:
        files = get_staged_files()
    elif args:
        files = []
        for a in args:
            p = Path(a)
            files.extend(collect_files(p if p.is_absolute() else ROOT / a))
    else:
        files = collect_files(DOCS_DIR)

    if not files:
        print("check_value_consistency: 対象ファイルなし (skip)")
        return 0

    if fix:
        fixed_files = 0
        fixed_lines = 0
        for f in files:
            try:
                content = f.read_text(encoding="utf-8")
            except Exception:
                continue
            src = content.split("\n")
            dst = [fix_line_bold(ln, mohm_only=mohm_only) for ln in src]
            n = sum(1 for a, b in zip(src, dst) if a != b)
            if n:
                f.write_text("\n".join(dst), encoding="utf-8")
                rel = str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f)
                print(f"🔧 {rel}: {n} 行を修正（V01 太字バグ）")
                fixed_files += 1
                fixed_lines += n
        scope = "MΩのみ" if mohm_only else "MΩ＋Ω"
        print(f"\n--fix 完了（{scope}）: {fixed_lines} 行 / {fixed_files} ファイルを修正"
              f"（V02・H04/H05 は手動確認が必要）")
        return 0

    errors = 0
    warns = 0
    for f in files:
        try:
            text = f.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f)
        lines = text.splitlines()

        for lineno, seg, sev in check_bold_omega(lines):
            if sev == "ERROR":
                errors += 1
                print(f"❌ [V01] {rel}:{lineno}  MΩ太字バグ（MΩが **...** の内側）")
                print(f"   検出: **{seg}** → 数値だけ太字に（例: **0.1**MΩ）")
            else:
                warns += 1
                print(f"⚠️  [V01] {rel}:{lineno}  Ω太字（接地抵抗等・plain Ω・report-only）")
                print(f"   検出: **{seg}** → 数値だけ太字に（例: **10**Ω以下）")
            print()

        for lineno, t, maj in check_triple_consistency(text):
            warns += 1
            print(f"⚠️  [V02] {rel}:{lineno}  三段値の自己不整合の疑い（sweep訂正漏れ）")
            print(f"   検出: {_fmt_triple(t)} MΩ  /  多数派: {_fmt_triple(maj)} MΩ")
            print()

    total = len(files)
    if errors == 0 and warns == 0:
        print(f"✅ check_value_consistency: 0件 — {total} ファイル検査済")
        return 0

    print(f"合計: ERROR {errors}件 / WARNING {warns}件 (対象 {total} ファイル)")
    return 1 if errors > 0 else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
