#!/usr/bin/env python3
"""全機械ゲートを 1 コマンドで一括実行し、各 1 行サマリ＋総合判定を出す.

PR 出荷前の検証で各ゲートを個別に叩くと毎回多ターンを消費するため、定型を
1 コマンドに畳む。ゲート系（dual_sync / pages_sync / mojibake / value_consist /
wiki_check）のいずれかが非 0 なら最後に exit 1。audit_frequency は非ゲート
（WARN 扱い・exit に影響させない）。

各サブプロセスは PYTHONIOENCODING=utf-8 を env に注入して呼ぶ（Windows の
cp932 端末で mojibake / UnicodeEncodeError になる事故を防止）。自身も stdout を
UTF-8 へ reconfigure する。

使い方:
  python scripts/verify_suite.py
  python scripts/verify_suite.py --v3 docs/articles/kaishaku/45.md
  python scripts/verify_suite.py --v3 docs/articles/kijun/58.md --v3 docs/articles/kaishaku/226.md

  --v3 <path> は wiki_quality_check.py <path> --v3 を実行し
  「<path>: 92/100 S・cap無し」形式の 1 行を情報として追加出力する
  （ゲート扱いせず・exit に影響しない）。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def utf8_env() -> dict:
    """PYTHONIOENCODING=utf-8 を注入した環境（子プロセスの mojibake 防止）."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def run_step(cmd: list[str]) -> tuple[int, str]:
    """サブプロセスを実行し (returncode, 結合出力) を返す."""
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        env=utf8_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout or ""


def extract(pattern: str, text: str, default: str = "") -> str:
    m = re.search(pattern, text)
    return m.group(1) if m else default


# (ラベル, コマンド, 出力から件数等の補足を取り出す関数) のゲート定義
def _detail_mojibake(out: str) -> str:
    n = extract(r"scanned \d+ files: (\d+) findings", out, "?")
    return f"({n} findings)"


def _detail_value(out: str) -> str:
    n = extract(r"(\d+)件", out, "?")
    return f"({n}件)"


def _detail_wiki(out: str) -> str:
    files = extract(r"across \d+/(\d+) files", out, "?")
    # 「Found: 0 § symbols, ...」の各 0 を合算して findings 件数にする
    counts = re.findall(r"Found:\s*(.+)", out)
    total = "?"
    if counts:
        nums = re.findall(r"(\d+)\s+\S", counts[0])
        if nums:
            total = str(sum(int(x) for x in nums))
    return f"({total} findings/{files} files)"


def _detail_law_facts(out: str) -> str:
    n = extract(r"check_law_facts:\s*(\d+)件", out, "?")
    return f"({n}件)"


GATES = [
    ("dual_sync", [sys.executable, "scripts/check_kakomon_dual_sync.py"], None),
    ("pages_sync", [sys.executable, "scripts/check_kakomon_pages_sync.py"], None),
    ("mojibake", [sys.executable, "scripts/check_mojibake.py"], _detail_mojibake),
    (
        "value_consist",
        [sys.executable, "scripts/check_value_consistency.py", "docs"],
        _detail_value,
    ),
    ("wiki_check", [sys.executable, "wiki_check.py"], _detail_wiki),
    # 法令事実・法令引用の2ゲートは実装済みだが verify_suite にも CI にも
    # 配線されておらず孤児化していた（両方とも実測 0 件 clean）。緑のうちに
    # 固定して、以後の退行を検出できるようにする。
    (
        "law_facts",
        [sys.executable, "scripts/check_law_facts.py", "docs"],
        _detail_law_facts,
    ),
    (
        "law_citations",
        [sys.executable, "scripts/check_law_citations.py", "docs"],
        None,
    ),
]

# 非ゲート（WARN 扱い・exit に影響させない）
AUDIT = ("audit_freq", [sys.executable, "scripts/audit_frequency.py"])

# 非ゲート2: 注入済み「試験対策メタ」の出題回数 vs kakomon.yml 現集計のドリフト。
# inject_frequency_meta.py は既存メタを skip する一度きりの注入なので、kakomon.yml が
# 増えてもメタは更新されない（＝学習者に見える優先度が静かに古くなる）。
# どちらが正かは再帰属の経緯を個別に見ないと決まらないため、**検出のみ**に留める。
AUDIT_META = (
    "freq_meta_drift",
    [sys.executable, "scripts/compute_frequency.py", "--audit-meta"],
)


def tail(text: str, n: int = 5) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--v3",
        action="append",
        default=[],
        dest="v3_paths",
        metavar="PATH",
        help="wiki_quality_check.py <PATH> --v3 を実行（情報のみ・複数指定可）",
    )
    args = ap.parse_args()

    total = len(GATES) + 2  # ゲート + audit_freq + freq_meta_drift
    failures: list[tuple[str, str]] = []  # (ラベル, 末尾出力)
    gates_passed = 0

    # ゲート系（順次）
    for i, (label, cmd, detail_fn) in enumerate(GATES, start=1):
        rc, out = run_step(cmd)
        if rc == 0:
            gates_passed += 1
            suffix = f" {detail_fn(out)}" if detail_fn else ""
            print(f"[{i}/{total}] {label:<13} PASS{suffix}")
        else:
            failures.append((label, tail(out)))
            print(f"[{i}/{total}] {label:<13} FAIL (exit {rc})")

    # audit_frequency（非ゲート＝WARN）
    rc, out = run_step(AUDIT[1])
    cnt = extract(r"頻度不整合:\s*(\d+)件", out, "?")
    if cnt == "0":
        print(f"[{total - 1}/{total}] {AUDIT[0]:<13} PASS (0件)")
        warnings = 0
    else:
        print(f"[{total - 1}/{total}] {AUDIT[0]:<13} WARN {cnt}件（非ゲート）")
        warnings = 1

    # 頻度メタのドリフト（非ゲート＝WARN）
    rc, out = run_step(AUDIT_META[1])
    dcnt = extract(r"頻度メタのドリフト:\s*(\d+)件", out, "?")
    if dcnt == "0":
        print(f"[{total}/{total}] {AUDIT_META[0]:<13} PASS (0件)")
    else:
        print(f"[{total}/{total}] {AUDIT_META[0]:<13} WARN {dcnt}件（非ゲート・要個別照合）")
        warnings += 1

    # --v3 情報行（ゲート扱いしない）
    for path in args.v3_paths:
        rc, out = run_step([sys.executable, "wiki_quality_check.py", path, "--v3"])
        score = extract(r"v3\.1総合スコア:\s*(\d+/100)", out, "?/100")
        verdict = extract(r"Verdict:\s*(\S+)", out, "?")
        cap = "cap無し" if "cap発火なし" in out else "cap発火あり"
        print(f"  v3 {path}: {score} {verdict}・{cap}")

    gate_total = len(GATES)
    ok = not failures
    verdict = "PASS" if ok else "FAIL"
    print(
        f"==== RESULT: {verdict} (gates {gates_passed}/{gate_total}, "
        f"warnings {warnings}) ===="
    )

    if failures:
        print("\n--- 失敗ステップの末尾出力 ---")
        for label, last in failures:
            print(f"[{label}]")
            print(last)
            print()
        sys.exit(1)


if __name__ == "__main__":
    main()
