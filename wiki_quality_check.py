"""denken-wiki 条文解説ページの品質スコアリング

使い方:
  python wiki_quality_check.py <article_path>          # 1ファイルのスコア表示
  python wiki_quality_check.py --rank                  # 全条文解説ページをランキング
  python wiki_quality_check.py --rank --top 5          # 上位5件のみ
  python wiki_quality_check.py --check-reference       # 現リファレンス(kijun/5)を上回るページ検出

スコア基準（100点満点）:
  必須セクション (40点): 10セクション x 4点
  図解 (15点): SVG or Mermaid 各5点 + 第2図解で+5点
  セルフチェック分散 (10点): 3箇所以上で満点
  重要度コード (10点): 🔴🟡🟢 全種類使用で満点
  穴埋め過去問 (10点): !!! abstract + ??? success
  最終チェック (10点): - [ ] チェックボックス3項目以上
  バージョン管理 (5点): フッターに最終確認日 + vX.Y
"""

import sys
import re
import argparse
import io
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

REPO_ROOT = Path(__file__).parent
ARTICLES_DIR = REPO_ROOT / "docs" / "articles"
REFERENCE_PATH = ARTICLES_DIR / "kijun" / "5.md"
KAKOMON_YML = REPO_ROOT / "_data" / "kakomon.yml"

_KAKOMON_CACHE = None


def _load_kakomon():
    global _KAKOMON_CACHE
    if _KAKOMON_CACHE is not None:
        return _KAKOMON_CACHE
    try:
        import yaml
        if KAKOMON_YML.exists():
            data = yaml.safe_load(KAKOMON_YML.read_text(encoding="utf-8"))
            _KAKOMON_CACHE = data.get("problems", []) if isinstance(data, dict) else []
        else:
            _KAKOMON_CACHE = []
    except Exception:
        _KAKOMON_CACHE = []
    return _KAKOMON_CACHE


def get_kakomon_meta(path: Path) -> dict:
    """ページの条文番号を path から推定し、kakomon.yml の登録状況を返す.

    例: kaishaku/224.md → 解釈§224 → 登録件数・最新年度・出題年度一覧
    """
    parts = path.parts
    if "articles" not in parts:
        return {}
    try:
        idx = parts.index("articles")
        category = parts[idx + 1]  # kijun / kaishaku / jigyoho
        stem = path.stem  # 224, 11, etc.
        if not stem.isdigit():
            return {}
    except (IndexError, ValueError):
        return {}

    prefix_map = {"kijun": "省令", "kaishaku": "解釈", "jigyoho": "事業法"}
    prefix = prefix_map.get(category, "")
    if not prefix:
        return {}

    target_pattern = f"{prefix}§{stem}"
    problems = _load_kakomon()
    matches = [p for p in problems if target_pattern in p.get("article", "")]
    if not matches:
        return {"registered": 0, "target": target_pattern}

    years = sorted(
        set(p["year"] for p in matches),
        key=lambda y: (
            1 if y.startswith("R") else 0,
            int(re.sub(r"[^\d]", "", y) or "0"),
            2 if "下" in y else (1 if "上" in y else 0),
        ),
    )
    return {
        "registered": len(matches),
        "target": target_pattern,
        "latest_year": years[-1] if years else None,
        "all_years": years,
    }

REQUIRED_SECTIONS = [
    ("5秒で思い出す", r"##.*5秒で思い出す"),
    ("条文原文 or 概要", r"##.*(条文原文|条文の概要)"),
    ("かみ砕き解説 or 因果理解", r"##.*(かみ砕き解説|因果理解|定義|事業用|位置づけ)"),
    ("図で理解", r"##.*(図で理解|分類体系|系統図|判定フローチャート)"),
    ("試験で問われること or 落とし穴", r"##.*(試験で問われること|頻出落とし穴|頻出ひっかけ)"),
    ("穴埋め過去問チャレンジ", r"##.*穴埋め過去問チャレンジ"),
    ("まぎらわしい選択肢", r"##.*まぎらわしい選択肢"),
    ("関連条文 or 関連ページ", r"##.*(関連条文|関連ページ)"),
    ("過去問実績", r"##.*過去問実績"),
    ("最終チェック", r"##.*最終チェック"),
]


def score_article(path: Path) -> dict:
    """記事の品質スコアを計算"""
    if not path.exists():
        return {"path": str(path), "error": "File not found", "score": 0}

    content = path.read_text(encoding="utf-8")
    breakdown = {}

    # 1. 必須セクション (40点)
    section_score = 0
    missing = []
    for name, pattern in REQUIRED_SECTIONS:
        if re.search(pattern, content):
            section_score += 4
        else:
            missing.append(name)
    breakdown["必須セクション"] = (section_score, 40, missing)

    # 2. 図解 (15点)
    has_svg = bool(re.search(r"<svg[\s>]", content))
    has_mermaid = bool(re.search(r"```mermaid", content))
    figure_count = len(re.findall(r"<svg[\s>]", content)) + len(re.findall(r"```mermaid", content))
    fig_score = 0
    if has_svg:
        fig_score += 5
    if has_mermaid:
        fig_score += 5
    if figure_count >= 2:
        fig_score += 5
    breakdown["図解"] = (fig_score, 15, f"SVG={has_svg}, Mermaid={has_mermaid}, 図数={figure_count}")

    # 3. セルフチェック分散 (10点)
    question_blocks = len(re.findall(r"\?\?\? question", content))
    sc_score = min(question_blocks * 3, 10) if question_blocks >= 1 else 0
    if question_blocks >= 3:
        sc_score = 10
    breakdown["セルフチェック分散"] = (sc_score, 10, f"{question_blocks}箇所")

    # 4. 重要度コード (10点)
    has_red = "🔴" in content
    has_yellow = "🟡" in content
    has_green = "🟢" in content
    severity_score = sum([has_red, has_yellow, has_green]) * 3
    if has_red and has_yellow and has_green:
        severity_score = 10
    breakdown["重要度コード"] = (severity_score, 10, f"🔴={has_red}, 🟡={has_yellow}, 🟢={has_green}")

    # 5. 穴埋め過去問 (10点)
    has_abstract = bool(re.search(r"!!! abstract", content))
    has_success = bool(re.search(r"\?\?\? success", content))
    quiz_score = 0
    if has_abstract:
        quiz_score += 5
    if has_success:
        quiz_score += 5
    breakdown["穴埋め過去問"] = (quiz_score, 10, f"abstract={has_abstract}, success={has_success}")

    # 6. 最終チェック (10点)
    checkbox_count = len(re.findall(r"- \[ \]", content))
    check_score = min(checkbox_count * 2, 10) if checkbox_count >= 3 else 0
    breakdown["最終チェックbox"] = (check_score, 10, f"{checkbox_count}項目")

    # 7. バージョン管理 (5点)
    has_version = bool(re.search(r"v\d+\.\d+", content))
    has_date = bool(re.search(r"最終確認", content))
    version_score = (5 if has_version and has_date else 2 if has_version or has_date else 0)
    breakdown["バージョン管理"] = (version_score, 5, f"version={has_version}, date={has_date}")

    total = sum(s[0] for s in breakdown.values())

    return {
        "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
        "score": total,
        "lines": len(content.splitlines()),
        "breakdown": breakdown,
        "kakomon_meta": get_kakomon_meta(path),
    }


def print_score(result: dict):
    if "error" in result:
        print(f"❌ {result['path']}: {result['error']}")
        return
    print(f"\n📄 {result['path']} ({result['lines']}行)")
    print(f"🎯 総合スコア: {result['score']}/100")
    print(f"\n内訳:")
    for category, (got, max_pts, detail) in result["breakdown"].items():
        bar = "█" * int(got / max_pts * 10) + "░" * (10 - int(got / max_pts * 10))
        print(f"  {category:20s} {bar} {got:3d}/{max_pts:3d}  {detail}")

    # kakomon.yml 登録メタを表示（採点外の参考情報）
    meta = result.get("kakomon_meta") or {}
    if meta:
        if meta.get("registered", 0) == 0:
            print(f"\n📊 kakomon.yml: {meta.get('target','?')} の登録なし")
        else:
            years = "/".join(meta.get("all_years", []))
            print(
                f"\n📊 kakomon.yml: {meta['target']} | 登録 {meta['registered']}件 "
                f"| 最新 {meta.get('latest_year','?')} | 全年度 [{years}]"
            )
            # 鮮度警告: 最新登録が R04 より前なら法令改正リスク注意
            latest = meta.get("latest_year") or ""
            if latest.startswith("H") or latest in ("R01", "R02", "R03"):
                print(
                    "  ⚠️  最新出題が古い。法令改正で条番号が変わっている可能性あり。"
                    "scripts/audit_kakomon.py で外部照合推奨"
                )


def rank_all(top_n: int = None):
    results = []
    for md_file in ARTICLES_DIR.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        results.append(score_article(md_file))
    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    if top_n:
        results = results[:top_n]
    print(f"\n🏆 条文解説ページ品質ランキング（{len(results)}件）\n")
    print(f"{'順位':<4}{'スコア':<8}{'行数':<6}{'パス'}")
    print("-" * 70)
    for i, r in enumerate(results, 1):
        if "error" in r:
            continue
        marker = " 🌟" if str(r["path"]).endswith("kijun\\5.md") or str(r["path"]).endswith("kijun/5.md") else ""
        print(f"{i:<4}{r['score']:<8}{r['lines']:<6}{r['path']}{marker}")
    return results


def check_reference():
    """現リファレンス(kijun/5)を上回るページがあるか検出"""
    if not REFERENCE_PATH.exists():
        print(f"❌ リファレンスファイルが見つかりません: {REFERENCE_PATH}")
        return
    ref_result = score_article(REFERENCE_PATH)
    ref_score = ref_result["score"]
    print(f"\n📌 現リファレンス: {ref_result['path']} (スコア: {ref_score}/100)\n")

    candidates = []
    for md_file in ARTICLES_DIR.rglob("*.md"):
        if md_file.name == "index.md" or md_file == REFERENCE_PATH:
            continue
        result = score_article(md_file)
        if result.get("score", 0) > ref_score:
            candidates.append(result)

    if not candidates:
        print("✅ リファレンスを上回るページはありません。kijun/5 が最高Verを維持しています。")
        return

    candidates.sort(key=lambda r: r["score"], reverse=True)
    print(f"🏆 リファレンス更新候補: {len(candidates)}件\n")
    for c in candidates:
        diff = c["score"] - ref_score
        print(f"  ⭐ {c['path']} (スコア: {c['score']}/100, +{diff}点)")
    print(f"\n→ CLAUDE.md の「条文解説ページの品質基準」行を最上位ページに書き換えてください。")


def main():
    parser = argparse.ArgumentParser(description="denken-wiki 品質チェッカー")
    parser.add_argument("path", nargs="?", help="記事のパス（相対 or 絶対）")
    parser.add_argument("--rank", action="store_true", help="全ページをランキング表示")
    parser.add_argument("--top", type=int, help="ランキング上位N件のみ")
    parser.add_argument("--check-reference", action="store_true", help="リファレンス更新候補を検出")
    args = parser.parse_args()

    if args.check_reference:
        check_reference()
    elif args.rank:
        rank_all(args.top)
    elif args.path:
        path = Path(args.path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        print_score(score_article(path))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
