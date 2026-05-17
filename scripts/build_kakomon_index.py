"""
_data/kakomon.yml から全問一覧 docs/kakomon/index-full.md を生成する。
ソート: 年度降順（R07下→...→H18）× 問番号昇順（問1→問13）
"""
import yaml
from pathlib import Path
from collections import defaultdict

REPO = Path(__file__).resolve().parent.parent
YML_PATH = REPO / "_data" / "kakomon.yml"
OUT_PATH = REPO / "docs" / "kakomon" / "index-full.md"

# 年度ソート順（新しい順）。下期→上期、Rxx→Hxx
YEAR_ORDER = [
    "R07下", "R07上",
    "R06下", "R06上",
    "R05下", "R05上",
    "R04下", "R04上",
    "R03",
    "R02", "R01",
    "H30", "H29", "H28", "H27", "H26", "H25", "H24", "H23", "H22", "H21", "H20", "H19", "H18",
]

THEME_LABEL = {
    "setsuchi": "接地工事",
    "zetsuen": "絶縁",
    "kachiku-densen": "架空電線",
    "jigyoho-taikei": "事業法体系",
    "shisetsu-kanri": "施設管理",
    "bunsan-dengen": "分散型電源",
    "hogo-sochi": "保護装置",
    "haisen-koji": "配線工事",
    "shiyo-basho": "使用場所",
    "shijimono": "支持物",
    "hatsuhendenjo": "発変電所",
    "chichuu-densen": "地中電線",
    "tokushu-basho": "特殊場所",
    "densen-cable": "電線・ケーブル",
    "yogo-teigi": "用語定義",
    "shunin-gijutsusha": "主任技術者",
    "other": "その他",
}

def main():
    data = yaml.safe_load(YML_PATH.read_text(encoding="utf-8"))
    problems = data["problems"]

    # 年度別にまとめる
    by_year = defaultdict(list)
    for p in problems:
        by_year[p["year"]].append(p)
    for year in by_year:
        by_year[year].sort(key=lambda p: p["num"])

    # 年度カバレッジ（実在年度のみソート順から拾う）
    years_present = [y for y in YEAR_ORDER if y in by_year]
    unknown_years = sorted(set(by_year.keys()) - set(YEAR_ORDER))
    if unknown_years:
        years_present.extend(unknown_years)

    lines = []
    lines.append("# 法規 過去問 全問一覧（年度×問番号）")
    lines.append("")
    lines.append(f"> 検索動線の起点。年度・問番号・論点・分野で全{len(problems)}問を一覧できます。")
    lines.append("> 「R04 問13」「令和4 問13」「非接地 テブナン」等のキーワード検索の最終着地点として設計。")
    lines.append("")
    lines.append("---")
    lines.append("")

    # 年度別表（年度降順）
    for year in years_present:
        plist = by_year[year]
        if not plist:
            continue
        year_label = plist[0].get("year_label", year)
        lines.append(f"## {year_label}（{year}）")
        lines.append("")
        lines.append("| 問 | 論点 | 分野 | 形式 | 関連条文 |")
        lines.append("|----|------|------|------|----------|")
        for p in plist:
            theme = THEME_LABEL.get(p.get("theme", "other"), p.get("theme", ""))
            form = p.get("form", "")
            article = p.get("article", "−")
            topic = p.get("topic", "")
            lines.append(f"| 問{p['num']} | {topic} | {theme} | {form} | {article} |")
        lines.append("")
        lines.append(f"→ [{year_label} 詳細ページ]({year.rstrip('上下')}.md)")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("")
    lines.append("## 関連ページ")
    lines.append("")
    lines.append("- [年度別一覧（by-year）](by-year.md)")
    lines.append("- [分野別一覧（by-field）](by-field.md)")
    lines.append("- [再出題ランキング](ranking.md)")
    lines.append("- [テーマ別解説（themes）](../themes/index.md)")
    lines.append("- [戦略パターン（strategy）](../strategy/index.md)")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*自動生成: `scripts/build_kakomon_index.py`*  ")
    lines.append("*ソースオブトゥルース: `_data/kakomon.yml`*  ")
    lines.append("*編集は yml 側で行い、本スクリプト再実行で更新。*")
    lines.append("")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] generated: {OUT_PATH}")
    print(f"     years: {len(years_present)}, problems: {len(problems)}")

if __name__ == "__main__":
    main()
