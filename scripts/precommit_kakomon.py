"""kakomon.yml の article 変更を キャッシュと照合する pre-commit フック.

`_data/denken-ou-cache.yml` （audit_kakomon.py --cache で生成）に
記録された検証済みエントリの article が変更されていたら commit を拒否する。

設計思想:
- AIトークン 0：urllib も使わない、ローカルyaml読込のみ
- 実行時間 0.1秒未満：キャッシュは事前に外部照合済み
- 法令改正への耐性：cache を月次更新すれば改正検出 → 警告

Exit codes:
    0  問題なし、または cache が無い（スキップ）
    1  キャッシュと不一致あり → commit 拒否
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import yaml

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
KAKOMON_YML = ROOT / "_data" / "kakomon.yml"
CACHE_YML = ROOT / "_data" / "denken-ou-cache.yml"


def main() -> int:
    if not CACHE_YML.exists():
        # キャッシュ未構築：初回 setup として警告のみで通過
        print(
            "[precommit_kakomon] キャッシュ未構築のためスキップ。"
            "初回は: python scripts/audit_kakomon.py --all --cache _data/denken-ou-cache.yml",
            file=sys.stderr,
        )
        return 0

    if not KAKOMON_YML.exists():
        return 0

    cache_doc = yaml.safe_load(CACHE_YML.read_text(encoding="utf-8")) or {}
    verified: dict = cache_doc.get("verified", {})
    if not verified:
        return 0

    kakomon_doc = yaml.safe_load(KAKOMON_YML.read_text(encoding="utf-8")) or {}
    problems = kakomon_doc.get("problems", [])

    errors: list[str] = []
    for p in problems:
        key = f"{p.get('year')}-{p.get('num')}"
        if key not in verified:
            continue
        cached_article = verified[key].get("article", "")
        current_article = p.get("article", "")
        if cached_article and current_article != cached_article:
            errors.append(
                f"  {key}（{p.get('topic','')}）: "
                f"キャッシュ={cached_article} ≠ kakomon.yml={current_article}"
            )

    if not errors:
        return 0

    print(
        "❌ kakomon.yml の article がキャッシュと不一致（外部照合で検証済みエントリ）:",
        file=sys.stderr,
    )
    for e in errors:
        print(e, file=sys.stderr)
    print(
        "\n対処法:\n"
        "  (a) kakomon.yml を正しい article に戻す\n"
        "  (b) 法令改正で正当な変更なら、キャッシュを再生成して再コミット:\n"
        "      python scripts/audit_kakomon.py --all --cache _data/denken-ou-cache.yml\n"
        "  (c) 緊急バイパス（非推奨）: git commit --no-verify",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
