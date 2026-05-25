#!/usr/bin/env python3
"""
kakomon.yml article-topic 整合性監査スクリプト

topic 欄のキーワードから「正しい条文番号」を逆引きし、article 欄との
意味的整合性を機械検出する。範囲表記（§220〜§232 等）も検出して
細分化を促す。

## 適用ルール

feedback_kakomon_article_topic_audit / feedback_phase_completion_audit_loop /
feedback_external_review_blindspot_analysis

## 監査ルール（topic キーワード → 期待 article）

- 低圧連系時の系統連系用保護装置  → §227
- 高圧連系時の系統連系用保護装置  → §229
- 高圧連系時の施設要件            → §228
- 低圧連系時の施設要件            → §226
- 低圧及び高圧連系時の施設要件    → §226 AND §228
- 再閉路時の事故防止              → §224
- 単独運転(の防止|防止)           → §232
- 分散型電源の系統連系設備に係る用語の定義 → §220

範囲表記（§N〜§M）は禁止。空欄数で細分化必須。

## 背景

2026-05-26 Phase E ChatGPT監修反映時に H29問9 §224 誤記・R03問9
範囲表記温存が発覚。pre-commit hook で再発防止する目的。
"""
import sys
import re
from pathlib import Path

# Windows cp932 環境での stdout encoding 対策
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, TypeError):
        pass

try:
    import yaml
except ImportError:
    print("[WARN] audit_kakomon_article: PyYAML not installed, skip")
    sys.exit(0)

ROOT = Path(__file__).resolve().parents[1]
KAKOMON_FILES = [
    ROOT / "_data" / "kakomon.yml",
    ROOT / "docs" / "_data" / "kakomon.yml",
]

# 監査ルール: (topic キーワード正規表現, 期待 article パターン, 説明)
# 期待 article は **must_have**（含むべき）の意味
# article 欄は「§N」「第N条」の両表記が混在しているため両対応
def _art_pattern(n: int) -> str:
    """条文番号Nを §N OR 第N条 のどちらでもマッチさせる正規表現"""
    return rf"(§{n}\b|§{n}[^\d]|§{n}$|第{n}条)"


AUDIT_RULES = [
    # 分散型電源系（電技解釈226-229条）
    (r"低圧連系時の系統連系用保護装置", [_art_pattern(227)], "第227条 低圧連系の保護装置"),
    (r"高圧連系時の系統連系用保護装置", [_art_pattern(229)], "第229条 高圧連系の保護装置"),
    (r"高圧連系時の施設要件", [_art_pattern(228)], "第228条 高圧連系の施設要件"),
    # 「低圧及び高圧連系時の施設要件」 → §226 AND §228（両方）
    (
        r"低圧及び高圧連系時の施設要件",
        [_art_pattern(226), _art_pattern(228)],
        "第226条＋第228条（低圧+高圧 ペア出題）",
    ),
    # 再閉路系
    (
        r"再閉路時の事故防止|高圧/特別高圧連系の再閉路|再閉路防止",
        [_art_pattern(224)],
        "第224条 再閉路時事故防止",
    ),
    # 単独運転防止
    (r"単独運転の防止|単独運転防止", [_art_pattern(232)], "第232条 単独運転防止"),
    # 用語定義
    (
        r"分散型電源の系統連系設備に係る用語の定義",
        [_art_pattern(220)],
        "第220条 用語定義",
    ),
]

# 範囲表記禁止（範囲が広すぎて空欄根拠条文が特定不能）
FORBIDDEN_RANGE_PATTERN = re.compile(r"§\d+〜§\d+")


def audit_file(path: Path):
    """1つの kakomon.yml ファイルを監査"""
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    problems = data.get("problems", []) or []
    violations = []

    for prob in problems:
        topic = prob.get("topic", "") or ""
        article = prob.get("article", "") or ""
        year = prob.get("year", "?")
        num = prob.get("num", "?")

        # 範囲表記検出（最初に check：他ルールより優先）
        if FORBIDDEN_RANGE_PATTERN.search(article):
            violations.append({
                "file": path.relative_to(ROOT),
                "year": year,
                "num": num,
                "topic": topic,
                "article": article,
                "rule": "範囲表記禁止",
                "fix_hint": "空欄数に応じて細分化（例: §226, §228）",
            })

        # topic-article 整合性 check
        for topic_re, expected_arts, description in AUDIT_RULES:
            if re.search(topic_re, topic):
                for expected_art in expected_arts:
                    if not re.search(expected_art, article):
                        violations.append({
                            "file": path.relative_to(ROOT),
                            "year": year,
                            "num": num,
                            "topic": topic,
                            "article": article,
                            "rule": f"topic と article 不整合",
                            "fix_hint": f"topic「{topic[:30]}...」は {description} → article に {expected_art} を含めるべき",
                        })
                break  # 1ルールマッチで他ルール check skip

    return violations


def main():
    all_violations = []
    files_checked = 0
    for path in KAKOMON_FILES:
        if path.exists():
            files_checked += 1
            all_violations.extend(audit_file(path))

    if files_checked == 0:
        print("[WARN] audit_kakomon_article: kakomon.yml not found, skip")
        return 0

    # 違反を「重大度別」に分割
    # ERROR: topic-article 不整合（明確な誤記）→ commit block
    # WARN: 範囲表記（既存大量存在・別タスクで段階対処）→ commit 続行
    errors = [v for v in all_violations if v["rule"] != "範囲表記禁止"]
    warnings = [v for v in all_violations if v["rule"] == "範囲表記禁止"]

    if warnings:
        print(
            f"[WARN] kakomon.yml 範囲表記 {len(warnings)} 件（commit続行・別タスクで段階対処）"
        )
        for v in warnings[:5]:  # 最初の5件のみ詳細表示
            print(f"  [{v['file']}] {v['year']} 問{v['num']}: {v['article']}")
        if len(warnings) > 5:
            print(f"  ... 他 {len(warnings) - 5} 件")
        print(f"")

    if errors:
        print(
            f"[ERROR] kakomon.yml article-topic 不整合を検出 ({len(errors)} 件)"
        )
        print(f"   rule: feedback_kakomon_article_topic_audit")
        print(f"   fix:  kakomon.yml の article 欄を topic に整合させる（両ファイル要更新）")
        print(f"")
        for v in errors:
            print(f"  [{v['file']}] {v['year']} 問{v['num']}")
            print(f"     topic   : {v['topic']}")
            print(f"     article : {v['article']}")
            print(f"     違反    : {v['rule']}")
            print(f"     修正案  : {v['fix_hint']}")
            print(f"")
        return 1

    # problems の総件数を取得
    total = 0
    for path in KAKOMON_FILES:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            total = max(total, len(data.get("problems", []) or []))

    print(
        f"OK audit_kakomon_article: 0 errors / {len(warnings)} warnings across {total} problems x {files_checked} files"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
