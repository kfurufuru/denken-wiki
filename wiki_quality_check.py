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
    ("5秒で思い出す", r"##.*(5秒で思い出す|全体像と要点)"),
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


# =============================================================================
# v3.1 品質スコアラ（3軸 / 18項目 / 重大欠陥cap）
# =============================================================================

V3_AXES = {
    "正確性": {
        "max": 32,
        "items": ["I01", "I02", "I03", "I04", "I05"],
    },
    "試験得点直結度": {
        "max": 35,
        "items": ["I06", "I07", "I08", "I09", "I10", "I11"],
    },
    "学習継続性": {
        "max": 33,
        "items": ["I12", "I13", "I14", "I15", "I16", "I17", "I18"],
    },
}

V3_ITEM_MAX = {
    "I01": 6, "I02": 6, "I03": 6, "I04": 7, "I05": 7,
    "I06": 6, "I07": 7, "I08": 5, "I09": 5, "I10": 5, "I11": 7,
    "I12": 5, "I13": 5, "I14": 6, "I15": 4, "I16": 4, "I17": 4, "I18": 5,
}

# 合計が100点になることを保証
assert sum(V3_ITEM_MAX.values()) == 100, \
    f"V3項目合計が100でない: {sum(V3_ITEM_MAX.values())}"
assert sum(a["max"] for a in V3_AXES.values()) == 100, \
    f"V3軸合計が100でない: {sum(a['max'] for a in V3_AXES.values())}"


def _score_i01(content: str, path: Path) -> tuple:
    """I01 条文番号3階層正確 (6点)"""
    meta = get_kakomon_meta(path)
    target = meta.get("target", "")
    has_clause = bool(re.search(r"第\s*\d+\s*項", content))
    has_item = bool(re.search(r"第\s*\d+\s*号", content))

    if not target:
        # 条番号推定不可の場合は階層加点のみ
        score = 0
        if has_clause:
            score += 2
        if has_item:
            score += 2
        return (min(score, 6), f"target未推定 / 項={has_clause} 号={has_item}")

    # 条が記事内に明示されているかチェック
    stem_num = re.sub(r"[^\d]", "", path.stem)
    has_article = bool(re.search(rf"第\s*{stem_num}\s*条", content)) or stem_num in content
    score = 2 if has_article else 0
    if has_clause:
        score += 2
    if has_item:
        score += 2
    return (min(score, 6), f"target={target} 条={has_article} 項={has_clause} 号={has_item}")


def _score_i02(content: str) -> tuple:
    """I02 数値基準正確 (6点)"""
    if re.search(r"数値検証.*PASS", content):
        return (6, "PASS")
    if re.search(r"数値検証.*CONDITIONAL", content):
        return (4, "CONDITIONAL")
    if re.search(r"数値検証.*INCONCLUSIVE", content):
        return (2, "INCONCLUSIVE")
    if re.search(r"数値検証.*MISSING", content):
        return (0, "MISSING")
    return (0, "数値検証ラベルなし")


def _score_i03(content: str, path: Path) -> tuple:
    """I03 法改正対応 (6点) — Sprint 2 修正: kakomon.yml 最新年度ベース判定

    判定（優先順）:
    - 改正注意ブロック明記 → 6点
    - 「改正対象外」「改正記録なし」明記 → 6点
    - 最新出題が R04 以降（改正リスク低） → 6点（対象外扱い）
    - 最新出題が H 始まり（古い）かつ改正注記なし → 0点（C03 capと整合）
    - meta 推定不可 → 6点（対象外扱い）
    """
    # 明示的な改正注記は最優先
    if re.search(r"📌\s*改正注意", content):
        return (6, "改正注意ブロックあり")
    if re.search(r"改正対象外|改正記録なし", content):
        return (6, "改正対象外明記")

    meta = get_kakomon_meta(path)
    latest = meta.get("latest_year") or ""

    # 最新出題が R04 以降なら改正リスク低（対象外扱い）
    if latest.startswith("R"):
        try:
            ynum = int(re.sub(r"[^\d]", "", latest) or "0")
            if ynum >= 4:
                return (6, f"最新出題{latest}（R04+） 対象外扱い")
            else:
                # R01-R03 は中間 → 改正注記なしなら 0点
                return (0, f"最新出題{latest}（R03以前）+改正注記なし")
        except ValueError:
            pass

    # H 始まり = 古い → 0点（C03 cap と整合）
    if latest.startswith("H"):
        return (0, f"最新出題{latest}（H・古い）+改正注記なし")

    # meta 推定不可（条文未登録など）→ 対象外
    return (6, "出題実績推定不可 対象外扱い")


def _score_i04(content: str) -> tuple:
    """I04 例外条件省略しない (7点)"""
    has_kagiri = bool(re.search(r"この限りでない", content))
    has_warning = bool(re.search(r"!!!\s*warning", content))
    has_unconditional_note = bool(re.search(r"無条件ではない", content))

    if not has_kagiri:
        # 「この限りでない」が無い記事は満点扱い（該当外）
        return (7, "例外文言なし（対象外）")
    if has_kagiri and has_warning and has_unconditional_note:
        return (7, "例外+warning+無条件否定すべて明示")
    if has_kagiri and has_warning:
        return (7, "例外+warning 明示")
    if has_kagiri and has_unconditional_note:
        return (4, "例外+無条件否定のみ（warning欠如）")
    return (2, "「この限りでない」のみ説明不足")


def _score_i05(content: str) -> tuple:
    """I05 出典版数記載 (7点)"""
    if re.search(r"令和\s*\d+\s*年.*版", content):
        return (7, "令和X年版 明記")
    if re.search(r"e-Gov.*\d{4}", content):
        return (7, "e-Gov版数明記")
    if re.search(r"lawid=", content):
        return (7, "lawid記載")
    if re.search(r"version.*\d+", content, re.IGNORECASE):
        return (7, "version明記")
    if re.search(r"最終確認:?\s*\d{4}-\d{2}-\d{2}", content):
        return (3, "最終確認日のみ")
    return (0, "出典版数なし")


def _score_i06(content: str) -> tuple:
    """I06 出題形式再現 (6点) — Sprint 1.1 拡張: セクション名類義語

    検出対象セクション名: 試験で問われること / 頻出ひっかけ / 落とし穴 / 出題パターン
    """
    has_section = bool(re.search(r"##.*(試験で問われること|頻出ひっかけ|落とし穴|出題パターン)", content))
    has_question = bool(re.search(r"\?\?\?\s*question", content))
    if has_section and has_question:
        return (6, "セクション+question両方")
    if has_section or has_question:
        return (3, f"section={has_section} question={has_question}")
    return (0, "両方なし")


def _score_i07(content: str) -> tuple:
    """I07 ひっかけ説明 (7点)"""
    has_table = bool(re.search(r"まぎらわしい選択肢", content))
    has_x_o = bool(re.search(r"❌", content) and re.search(r"✅", content))
    has_red = "🔴" in content
    has_yellow = "🟡" in content
    has_green = "🟢" in content
    all_severity = has_red and has_yellow and has_green
    cnt = sum([has_table, has_x_o, all_severity])
    if cnt == 3:
        return (7, "table+❌✅+🔴🟡🟢")
    if cnt == 2:
        return (5, f"table={has_table} x/o={has_x_o} severity={all_severity}")
    if cnt == 1:
        return (2, f"table={has_table} x/o={has_x_o} severity={all_severity}")
    return (0, "全要素なし")


def _score_i08(content: str) -> tuple:
    r"""I08 年度横断照合 (5点) — Sprint 1.1 拡張: 過去問テーブルのH/R混在も範囲扱い

    範囲記載の検出:
    - 同一行 H\d+...R\d+
    - 過去問テーブルや本文に「過去N年」「H\d+」「R\d+」両方の言及
    """
    has_r08 = bool(re.search(r"R0?8.*予測|R8.*予測", content))
    has_year_range = bool(re.search(r"H\d+.*R\d+|過去\s*\d+\s*年", content))
    # 過去問テーブルでH年度とR年度が両方ある場合も範囲とみなす
    has_h = bool(re.search(r"H\d+", content))
    has_r = bool(re.search(r"R\d+", content))
    if not has_year_range and has_h and has_r:
        has_year_range = True
    if has_r08 and has_year_range:
        return (5, "R8予測+年度範囲")
    if has_r08 or has_year_range:
        return (2, f"r8={has_r08} range={has_year_range}")
    return (0, "なし")


def _score_i09(content: str, path: Path) -> tuple:
    """I09 過去問実績連携 (5点) — Sprint 2 修正: kakomon.yml 登録ベース

    旧称「過去問リンク」→ 新称「過去問実績連携」
    判定（優先順）:
    - kakomon.yml registered ≥ 5件 → 5点
    - kakomon.yml registered ≥ 1件 → 3点
    - kakomon.yml registered = 0件（出題実績なし） → 5点（対象外扱い）
    - meta 推定不可（条番号取得失敗など） → 5点（対象外扱い）
    - 補助加点: denken-ou.com URL があれば +1（上限5）
    """
    meta = get_kakomon_meta(path)
    url_cnt = len(re.findall(r"denken-ou\.com", content))

    # meta 推定不可（"target" キーすらない）→ 対象外
    if not meta.get("target"):
        score = 5
        return (score, f"meta推定不可 対象外扱い (URL{url_cnt}件)")

    registered = meta.get("registered", 0)

    if registered == 0:
        return (5, f"出題実績なし条文 対象外扱い (URL{url_cnt}件)")
    if registered >= 5:
        base = 5
        return (base, f"kakomon登録{registered}件 (URL{url_cnt}件)")
    if registered >= 1:
        # 補助加点: URL があれば +1（上限5）
        base = 3
        if url_cnt >= 1:
            base = min(base + 1, 5)
        return (base, f"kakomon登録{registered}件 (URL{url_cnt}件)")
    return (0, f"kakomon登録なし URL{url_cnt}件")


def _score_i10(content: str) -> tuple:
    """I10 改変過去問明記 (5点)"""
    cnt = len(re.findall(r"denken-ou\.com", content))
    if cnt == 0:
        # 過去問URL自体ない記事は項目除外（満点扱い）
        return (5, "URL0件のため対象外")
    has_note = bool(re.search(r"改変なし|改変あり", content))
    if has_note:
        return (5, "改変明記あり")
    return (0, f"URL{cnt}件あるが改変明記なし")


def _score_i11(content: str) -> tuple:
    """I11 サイト学習ルート (7点)"""
    nav_links = len(re.findall(r"\[[^\]]+\]\(\.\.\/\.\.\/[^)]+\)", content))
    has_keyword = bool(re.search(r"risky\.md|index\.md|攻略戦略", content))
    if nav_links >= 2 or (has_keyword and nav_links >= 1):
        return (7, f"nav={nav_links} keyword={has_keyword}")
    if nav_links >= 1 or has_keyword:
        return (4, f"nav={nav_links} keyword={has_keyword}")
    return (0, "なし")


def _score_i12(content: str) -> tuple:
    """I12 初学者要約 (5点)"""
    has_5sec = bool(re.search(r"5秒で思い出す", content))
    has_overview = bool(re.search(r"全体像", content))
    has_tab = bool(re.search(r'===\s*"🌳"', content))
    if has_5sec or has_overview or has_tab:
        return (5, f"5秒={has_5sec} 全体像={has_overview} 🌳tab={has_tab}")
    return (0, "なし")


def _score_i13(content: str) -> tuple:
    """I13 3列翻訳テーブル (5点) — Sprint 2 修正: 類義語拡張

    列名候補（OR判定）:
    - 列1（日常語系）: 日常語 / 日常表現 / 言い換え / 俗称 / 読み
    - 列2（法規系）: 法規表現 / 条文表現 / 正式名称 / 条文上の語
    - 列3（試験系）: 試験での意味 / 試験対策 / 混同注意 / ひっかけ / 正答

    判定:
    - 列1+列2+列3 全て検出 → 5点
    - 列1+列2 または 列2+列3 → 3点
    - 1列のみ → 0点
    """
    col1_keywords = ["日常語", "日常表現", "言い換え", "俗称", "読み"]
    col2_keywords = ["法規表現", "条文表現", "正式名称", "条文上の語"]
    col3_keywords = ["試験での意味", "試験対策", "混同注意", "ひっかけ", "正答"]

    has_col1 = any(kw in content for kw in col1_keywords)
    has_col2 = any(kw in content for kw in col2_keywords)
    has_col3 = any(kw in content for kw in col3_keywords)

    cnt = sum([has_col1, has_col2, has_col3])
    detail = f"日常={has_col1} 法規={has_col2} 試験={has_col3}"

    if has_col1 and has_col2 and has_col3:
        return (5, f"3列翻訳テーブル {detail}")
    # 隣接2列パターン: 列1+列2 または 列2+列3
    if (has_col1 and has_col2) or (has_col2 and has_col3):
        return (3, f"2列翻訳 {detail}")
    if cnt == 1:
        return (0, f"1列のみ {detail}")
    return (0, f"翻訳テーブルなし {detail}")


def _score_i14(content: str) -> tuple:
    """I14 視覚要素適切 (6点)"""
    svg_cnt = len(re.findall(r"<svg[\s>]", content))
    mermaid_cnt = len(re.findall(r"```mermaid", content))
    # 全SVGが<div>でラップされているか（簡易: svg数 == <div>...<svg のパターン数）
    div_wrapped = len(re.findall(r"<div[^>]*>\s*<svg", content))
    score = 0
    detail = []
    if svg_cnt >= 3:
        score += 2
        detail.append(f"svg={svg_cnt}")
    else:
        detail.append(f"svg={svg_cnt}(不足)")
    if mermaid_cnt >= 1:
        score += 2
        detail.append(f"mermaid={mermaid_cnt}")
    else:
        detail.append("mermaid=0")
    if svg_cnt > 0 and div_wrapped >= svg_cnt:
        score += 2
        detail.append("全svg<div>ラップ")
    elif svg_cnt == 0:
        # SVGがない場合はラップ加点を諦める（条件成立せず）
        detail.append("svg無のためラップ評価不可")
    else:
        detail.append(f"div={div_wrapped}/{svg_cnt}")
    return (score, " ".join(detail))


def _score_i15(content: str) -> tuple:
    """I15 実務イメージ (4点)"""
    keywords = ["実務", "現場", "施工", "設計"]
    cnt = sum(len(re.findall(kw, content)) for kw in keywords)
    if cnt >= 5:
        return (4, f"{cnt}箇所")
    if cnt >= 2:
        return (2, f"{cnt}箇所")
    return (0, f"{cnt}箇所")


def _score_i16(content: str) -> tuple:
    """I16 暗記tip (4点) — Sprint 1.1 拡張: 類義語キーワードを追加

    検出対象: !!! tip "💡|暗記|核心|ポイント|コツ" のいずれか / **暗記の核心**
    """
    if re.search(r'!!!\s*tip\s*"(💡|暗記|核心|ポイント|コツ)', content):
        return (4, "tip 暗記/核心/ポイント/コツ")
    if re.search(r'!!!\s*abstract\s*"(💡|暗記|核心)', content):
        return (4, "abstract 暗記系")
    if re.search(r"\*\*暗記の核心\*\*", content):
        return (4, "暗記の核心")
    return (0, "なし")


def _score_i17(content: str) -> tuple:
    """I17 重要度・頻出度表示 (4点) — Sprint 2 修正: bold形式・テーブル形式・必須文言も検出

    検出パターン:
    - 明示形式: `重要度: A` / `重要度：S`
    - bold形式: `**重要度**: A` / `**重要度** A`
    - テーブル形式: `| 重要度 | A |`
    - 必須文言: 「重要必須」「頻出必須」
    """
    has_fire = "🔥" in content
    has_rank_plain = bool(re.search(r"重要度[:：]\s*[SABC]", content))
    has_rank_bold = bool(re.search(r"\*\*重要度\*\*\s*[:：]?\s*[SABC]", content))
    has_rank_table = bool(re.search(r"\|\s*重要度\s*\|\s*[SABC]\s*\|", content))
    has_must = bool(re.search(r"重要必須|頻出必須", content))

    has_rank = has_rank_plain or has_rank_bold or has_rank_table or has_must
    detail = (
        f"🔥={has_fire} plain={has_rank_plain} bold={has_rank_bold} "
        f"table={has_rank_table} must={has_must}"
    )

    if has_fire and has_rank:
        return (4, f"🔥+重要度ランク ({detail})")
    if has_fire or has_rank:
        return (2, detail)
    return (0, "なし")


def _score_i18(content: str) -> tuple:
    """I18 確認問題 (5点)"""
    has_abstract = bool(re.search(r"!!!\s*abstract", content))
    has_success = bool(re.search(r"\?\?\?\s*success", content))
    if has_abstract and has_success:
        return (5, "abstract+success")
    if has_abstract or has_success:
        return (2, f"abstract={has_abstract} success={has_success}")
    return (0, "なし")


def _check_caps_v3(content: str, path: Path, items: dict) -> list:
    """重大欠陥cap発火検査

    Sprint 1 修正（2026-05-05・AI社員諮問結果反映）:
    - C01: 「条/項/号3階層」→「条番号自体が一致」のみで判定（条文構造的に項/号がない記事を救済）
    - C06: 完全削除（「R5/クロスレビュー/並列エージェント」は法規記事に書く慣例なしと江間証言で確定）
    """
    caps = []

    # C01: 条番号自体が一致しない（path stem の条番号が記事内に現れない）
    stem_num = re.sub(r"[^\d]", "", path.stem)
    if stem_num:
        # path 由来の条番号が記事内 (h1 や条文原文セクション) に明示的に現れるか
        article_present = bool(re.search(rf"第\s*{stem_num}\s*条", content))
        # kakomon.yml ターゲットも併用（記事番号が登録されているか）
        meta = get_kakomon_meta(path)
        kakomon_ok = meta.get("registered", 0) > 0 or meta.get("target") == ""  # 登録あり or 推定不可
        if not article_present and not kakomon_ok:
            caps.append(("C01", 69, f"条番号{stem_num}が記事内に未明示+kakomon登録なし"))

    # C02: 数値検証MISSING
    if re.search(r"数値検証.*MISSING", content):
        caps.append(("C02", 69, "数値検証MISSING"))

    # C03: kakomon.yml最新がH始まりかつ改正注記なし
    meta = get_kakomon_meta(path)
    latest = meta.get("latest_year") or ""
    if latest.startswith("H") and not re.search(r"📌\s*改正注意|改正対象外|改正記録なし", content):
        caps.append(("C03", 69, f"最新出題{latest}（古い）+改正注記なし"))

    # C04: 「この限りでない」あるが warning なし
    if re.search(r"この限りでない", content) and not re.search(r"!!!\s*warning", content):
        caps.append(("C04", 79, "この限りでない+warning欠如"))

    # C05: 出典版数なし（I05が0点）
    if items["I05"][0] == 0:
        caps.append(("C05", 89, "出典版数記載なし"))

    # C06: 削除（Sprint 1で廃止 — 法規記事に書く慣例なし）

    return caps


def _classify_verdict(score: int) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    return "D"


def score_v3(path: Path) -> dict:
    """v3.1 3軸18項目スコアリング"""
    if not path.exists():
        return {"path": str(path), "error": "File not found", "score": 0}

    content = path.read_text(encoding="utf-8")

    items = {}
    items["I01"] = _score_i01(content, path) + (V3_ITEM_MAX["I01"],)
    items["I02"] = _score_i02(content) + (V3_ITEM_MAX["I02"],)
    items["I03"] = _score_i03(content, path) + (V3_ITEM_MAX["I03"],)
    items["I04"] = _score_i04(content) + (V3_ITEM_MAX["I04"],)
    items["I05"] = _score_i05(content) + (V3_ITEM_MAX["I05"],)
    items["I06"] = _score_i06(content) + (V3_ITEM_MAX["I06"],)
    items["I07"] = _score_i07(content) + (V3_ITEM_MAX["I07"],)
    items["I08"] = _score_i08(content) + (V3_ITEM_MAX["I08"],)
    items["I09"] = _score_i09(content, path) + (V3_ITEM_MAX["I09"],)
    items["I10"] = _score_i10(content) + (V3_ITEM_MAX["I10"],)
    items["I11"] = _score_i11(content) + (V3_ITEM_MAX["I11"],)
    items["I12"] = _score_i12(content) + (V3_ITEM_MAX["I12"],)
    items["I13"] = _score_i13(content) + (V3_ITEM_MAX["I13"],)
    items["I14"] = _score_i14(content) + (V3_ITEM_MAX["I14"],)
    items["I15"] = _score_i15(content) + (V3_ITEM_MAX["I15"],)
    items["I16"] = _score_i16(content) + (V3_ITEM_MAX["I16"],)
    items["I17"] = _score_i17(content) + (V3_ITEM_MAX["I17"],)
    items["I18"] = _score_i18(content) + (V3_ITEM_MAX["I18"],)

    # 統一フォーマット: (got, max, detail)
    items_norm = {k: (v[0], v[2], v[1]) for k, v in items.items()}

    # 軸別集計
    axis_scores = {}
    for axis_name, conf in V3_AXES.items():
        got = sum(items_norm[i][0] for i in conf["items"])
        axis_scores[axis_name] = (got, conf["max"])

    raw_total = sum(s[0] for s in axis_scores.values())

    # cap適用
    caps = _check_caps_v3(content, path, items_norm)
    if caps:
        max_after_caps = min(c[1] for c in caps)
        final_score = min(raw_total, max_after_caps)
    else:
        max_after_caps = 100
        final_score = raw_total

    # タイブレーカー情報
    s_score = axis_scores["正確性"][0]
    version_match = re.search(r"令和\s*(\d+)\s*年", content)
    version_date = version_match.group(0) if version_match else ""
    update_match = re.search(r"最終確認:?\s*(\d{4}-\d{2}-\d{2})", content)
    update_date = update_match.group(1) if update_match else ""

    return {
        "path": str(path.relative_to(REPO_ROOT)) if path.is_relative_to(REPO_ROOT) else str(path),
        "score": final_score,
        "raw_score": raw_total,
        "axis_scores": axis_scores,
        "items": items_norm,
        "caps_triggered": [c[0] for c in caps],
        "caps_detail": caps,
        "max_after_caps": max_after_caps,
        "verdict": _classify_verdict(final_score),
        "tiebreakers": {
            "s_score": s_score,
            "version_date": version_date,
            "update_date": update_date,
        },
        "lines": len(content.splitlines()),
        "kakomon_meta": get_kakomon_meta(path),
    }


def print_score_v3(result: dict):
    if "error" in result:
        print(f"❌ {result['path']}: {result['error']}")
        return

    print(f"\n📄 {result['path']} ({result['lines']}行)")
    print(f"🎯 v3.1総合スコア: {result['score']}/100  →  Verdict: {result['verdict']}")
    if result["raw_score"] != result["score"]:
        print(f"   （cap適用前: {result['raw_score']}/100, cap上限: {result['max_after_caps']}）")

    # 3軸バー
    print(f"\n[3軸内訳]")
    for axis_name, (got, max_pts) in result["axis_scores"].items():
        bar = "█" * int(got / max_pts * 20) + "░" * (20 - int(got / max_pts * 20))
        print(f"  {axis_name:12s} {bar} {got:3d}/{max_pts:3d}")

    # 18項目バー
    print(f"\n[18項目詳細]")
    item_labels = {
        "I01": "条文番号3階層", "I02": "数値基準正確", "I03": "法改正対応",
        "I04": "例外条件省略しない", "I05": "出典版数記載",
        "I06": "出題形式再現", "I07": "ひっかけ説明", "I08": "年度横断照合",
        "I09": "過去問実績連携", "I10": "改変過去問明記", "I11": "サイト学習ルート",
        "I12": "初学者要約", "I13": "3列翻訳テーブル", "I14": "視覚要素適切",
        "I15": "実務イメージ", "I16": "暗記tip", "I17": "重要度頻出度", "I18": "確認問題",
    }
    for item_id in sorted(result["items"].keys()):
        got, max_pts, detail = result["items"][item_id]
        bar_len = int(got / max_pts * 10) if max_pts > 0 else 0
        bar = "█" * bar_len + "░" * (10 - bar_len)
        label = item_labels.get(item_id, "")
        print(f"  {item_id} {label:18s} {bar} {got}/{max_pts}  {detail}")

    # cap発火
    if result["caps_triggered"]:
        print(f"\n[⚠️ 重大欠陥cap発火]")
        for cap_id, cap_max, cap_detail in result["caps_detail"]:
            print(f"  {cap_id}: max={cap_max}  {cap_detail}")
        print(f"  → 最終cap上限: {result['max_after_caps']}")
    else:
        print(f"\n[✅ cap発火なし]")

    # タイブレーカー
    tb = result["tiebreakers"]
    print(f"\n[タイブレーカー情報] S軸={tb['s_score']}/32, 版数={tb['version_date'] or '-'}, 更新日={tb['update_date'] or '-'}")

    # 改善ナビ: 不足項目TOP3（早川条件・Sprint 1 追加）
    deficits = []
    for item_id, (got, max_pts, detail) in result["items"].items():
        deficit = max_pts - got
        if deficit > 0:
            label = item_labels.get(item_id, "")
            deficits.append((deficit, item_id, label, got, max_pts, detail))
    deficits.sort(key=lambda x: -x[0])  # 不足が大きい順
    if deficits:
        print(f"\n[💡 改善ナビ: 不足項目TOP3（次にここを直すと点が伸びる）]")
        for deficit, item_id, label, got, max_pts, detail in deficits[:3]:
            print(f"  {item_id} {label:18s} +{deficit}点見込み  現在{got}/{max_pts}  ({detail})")


def rank_all_v3(top_n: int = None):
    """v3.1 全ページランキング（verdict別グルーピング）"""
    results = []
    for md_file in ARTICLES_DIR.rglob("*.md"):
        if md_file.name == "index.md":
            continue
        results.append(score_v3(md_file))

    # ソート: スコア降順 → S軸降順 → 版数 → 更新日
    def _sort_key(r):
        if "error" in r:
            return (-1, 0, "", "")
        tb = r.get("tiebreakers", {})
        return (
            -r.get("score", 0),
            -tb.get("s_score", 0),
            tb.get("version_date", ""),
            tb.get("update_date", ""),
        )
    results.sort(key=_sort_key)

    if top_n:
        results = results[:top_n]

    # verdict別グルーピング
    groups = {"S": [], "A": [], "B": [], "C": [], "D": []}
    for r in results:
        if "error" in r:
            continue
        groups[r["verdict"]].append(r)

    print(f"\n🏆 v3.1 品質ランキング（{len(results)}件）\n")
    for verdict in ["S", "A", "B", "C", "D"]:
        bucket = groups[verdict]
        if not bucket:
            continue
        emoji = {"S": "🌟", "A": "🥇", "B": "🥈", "C": "🥉", "D": "📉"}[verdict]
        print(f"\n{emoji} {verdict}ランク ({len(bucket)}件)")
        print(f"{'順位':<4}{'スコア':<8}{'S軸':<6}{'cap':<14}{'パス'}")
        print("-" * 80)
        for i, r in enumerate(bucket, 1):
            cap_str = ",".join(r["caps_triggered"]) if r["caps_triggered"] else "-"
            s_axis = r["tiebreakers"]["s_score"]
            print(f"{i:<4}{r['score']:<8}{s_axis:<6}{cap_str:<14}{r['path']}")
    return results


def main():
    parser = argparse.ArgumentParser(description="denken-wiki 品質チェッカー")
    parser.add_argument("path", nargs="?", help="記事のパス（相対 or 絶対）")
    parser.add_argument("--rank", action="store_true", help="全ページをランキング表示")
    parser.add_argument("--top", type=int, help="ランキング上位N件のみ")
    parser.add_argument("--check-reference", action="store_true", help="リファレンス更新候補を検出")
    parser.add_argument("--v3", action="store_true", help="v3.1スコアラを使用（3軸18項目+cap）")
    args = parser.parse_args()

    if args.check_reference:
        check_reference()
    elif args.rank and args.v3:
        rank_all_v3(args.top)
    elif args.rank:
        rank_all(args.top)
    elif args.path:
        path = Path(args.path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        if args.v3:
            print_score_v3(score_v3(path))
        else:
            print_score(score_article(path))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
