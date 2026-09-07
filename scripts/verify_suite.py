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


def _detail_verbatim(out: str) -> str:
    n = extract(r"check_law_verbatim:\s*(\d+)件", out, "?")
    q = extract(r"・(\d+)引用を照合", out, "?")
    return f"({n}件/{q}引用)"


def _detail_facts(out: str) -> str:
    n = extract(r"check_verified_facts:\s*(\d+)件", out, "?")
    k = extract(r"・(\d+)事実を照合", out, "?")
    return f"({n}件/{k}事実)"


def _detail_cites(out: str) -> str:
    n = extract(r"check_kakomon_citations:\s*(\d+)件", out, "?")
    q = extract(r"・(\d+)引用を照合", out, "?")
    return f"({n}件/{q}引用)"


def _detail_claims(out: str) -> str:
    n = extract(r"check_verification_claims:\s*(\d+)件", out, "?")
    debt = extract(r"allowlist (\d+)件（債務）", out, "0")
    return f"({n}件/債務 {debt}件)"


def _detail_omission(out: str) -> str:
    n = extract(r"check_genbun_omission:\s*(\d+)件", out, "?")
    pages = extract(r"（(\d+)ページを照合", out, "?")
    return f"({n}件/{pages}ページ)"


def _detail_law_facts(out: str) -> str:
    n = extract(r"check_law_facts:\s*(\d+)件", out, "?")
    return f"({n}件)"


# CI が回す検出器の生存証明。verify_suite が self-test を回していなかったため、
# 「ゲートは 0件で緑・CI の self-test だけ赤」という乖離が起きた（実測 2026-08-29:
# verified-facts に事実を1件足して self-test の陽性サンプルを付け忘れ、
# ローカル gates 11/11 PASS のまま CI の wiki-check が落ちた）。
# ローカルで CI と同じ検査を通すため、ゲート本体より先に走らせる。
SELF_TESTS = [
    ("wiki_check", [sys.executable, "wiki_check.py", "--self-test"]),
    ("law_verbatim", [sys.executable, "scripts/check_law_verbatim.py", "--self-test"]),
    ("verified_facts", [sys.executable, "scripts/check_verified_facts.py", "--self-test"]),
    ("kakomon_cites", [sys.executable, "scripts/check_kakomon_citations.py", "--self-test"]),
    ("verif_claims", [sys.executable, "scripts/check_verification_claims.py", "--self-test"]),
    ("genbun_omission", [sys.executable, "scripts/check_genbun_omission.py", "--self-test"]),
    ("public_leak", [sys.executable, "scripts/check_public_leak.py", "--self-test"]),
    ("theme_article_no", [sys.executable, "scripts/check_theme_article_numbers.py", "--self-test"]),
    ("kaishaku_titles", [sys.executable, "scripts/audit_kaishaku_titles.py", "--self-test"]),
    ("jigyoho_titles", [sys.executable, "scripts/audit_jigyoho_titles.py", "--self-test"]),
    ("stale_evidence", [sys.executable, "scripts/tests/check_stale_evidence/test_check_stale_evidence.py"]),
]

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
    # 条文原文 blockquote と原典（e-Gov XML / 解釈PDF抽出）の逐語 diff。
    # 2026-08-28 の全数監査で、既存ゲート 7/7 PASS のまま条文原文の逐語ズレが
    # 29 箇所残っていたのが制定事案（本ゲートを監査前コミットに当てて実測）。
    (
        "law_verbatim",
        [sys.executable, "scripts/check_law_verbatim.py"],
        _detail_verbatim,
    ),
    # 解説・要約・暗記表に書かれた数値と判定軸を _data/verified-facts.yml に固定する。
    # 条文原文が正しくても、その下の表が別の値を書いていれば学習者はそちらを覚える。
    # 監査前コミットに当てると 29件（B種の 50/Ig・支持物の安全率1.5・第131条の罰則・
    # 径間60/120m・低圧耐圧1分間・「発生から24時間」・60点満点 など）。
    (
        "verified_facts",
        [sys.executable, "scripts/check_verified_facts.py"],
        _detail_facts,
    ),
    # docs/kakomon/ の外が書く個々の過去問引用を SoT と突合する。
    # 既存の kakomon 系ゲートは docs/kakomon/ しか見ておらず、条文ページ・テーマページの
    # 「過去問実績」は誰も検査していなかった（監査前コミットに当てると 27件）。
    (
        "kakomon_cites",
        [sys.executable, "scripts/check_kakomon_citations.py"],
        _detail_cites,
    ),
    # 「照合済」と書いてあるページに、機械が逐語照合できる条文原文があるか。
    # 宣言はコストゼロで書ける。kijun/11・23・32 はいずれも監修ログに
    # 「解釈第17/38/59条と照合済・公式値と一致」と書いてあったが、
    # その数値は条文に存在しなかった（2026-08-28 監査）。
    (
        "verif_claims",
        [sys.executable, "scripts/check_verification_claims.py"],
        _detail_claims,
    ),
    # 条文原文の**引用漏れ**（原典にある項・号をページが持たない）と、本文の号数主張
    # （「3つの号」）が第1項の号数と食い違うもの。逐語ゲートは引用した文しか見ないので、
    # 引用しなかった項・号は素通りしていた（PR #184 13〜15章: 117/150/227/229/149。
    # 是正前コミット ada8467 に当てると 6件、HEAD 0件・allowlist 1件）。
    (
        "genbun_omission",
        [sys.executable, "scripts/check_genbun_omission.py"],
        _detail_omission,
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

    # 検出器の生存証明を先に回す（vacuous pass 防止・CI と同じ検査をローカルでも通す）
    st_failed: list[str] = []
    for label, cmd in SELF_TESTS:
        rc, out = run_step(cmd)
        if rc != 0:
            st_failed.append(label)
            print(f"[self-test] {label:<17} FAIL (exit {rc})\n{tail(out)}")
    if st_failed:
        print(f"\n==== RESULT: FAIL (self-test {len(st_failed)}件: {', '.join(st_failed)}) ====")
        print("検出器が壊れている状態でゲートを回しても「0件で緑」は意味を持たない。")
        # 本ファイルは main() の戻り値を捨てる（末尾が `main()`）。既存の失敗パスと
        # 同じく sys.exit で抜ける。return 1 だと FAIL 表示のまま exit 0 になる。
        sys.exit(1)
    print(f"[self-test] {len(SELF_TESTS)}件 ALL PASS")

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
