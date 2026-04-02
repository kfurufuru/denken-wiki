"""
MkDocs Macros Plugin - 電験3種 法規 過去問マクロ
denken-wiki の kakomon/*.md で使用するマクロ関数を定義
"""


THEMES = [
    ("setsuchi", "接地工事"),
    ("zetsuen", "絶縁性能・耐圧試験"),
    ("kachiku-densen", "架空電線路"),
    ("jigyoho-taikei", "電気事業法の体系"),
    ("shisetsu-kanri", "電気施設管理"),
    ("bunsan-dengen", "分散型電源・系統連系"),
    ("hogo-sochi", "保護装置（過電流・地絡）"),
    ("haisen-koji", "配線工事・屋内配線"),
    ("shiyo-basho", "電気使用場所の施設"),
    ("shijimono", "支持物・架空電線路の強度"),
    ("hatsuhendenjo", "発変電所の施設"),
    ("chichuu-densen", "地中電線路"),
    ("tokushu-basho", "特殊場所の施設"),
    ("densen-cable", "電線・ケーブルの選定"),
    ("yogo-teigi", "用語の定義"),
    ("shunin-gijutsusha", "電気主任技術者の職務"),
]

# サマリ表の列定義: (表示ラベル, 対応する year コードのリスト) ※新しい年が左
DISPLAY_COLS = [
    ("R8",  ["R08上", "R08下"]),
    ("R7",  ["R07上", "R07下"]),
    ("R6",  ["R06上", "R06下"]),
    ("R5",  ["R05上", "R05下"]),
    ("R4",  ["R04上", "R04下"]),
    ("R3",  ["R03"]),
    ("R2",  ["R02"]),
    ("R1",  ["R01"]),
    ("H30", ["H30"]),
    ("H29", ["H29"]),
    ("H28", ["H28"]),
    ("H27", ["H27"]),
    ("H26", ["H26"]),
    ("H25", ["H25"]),
]

# 星評価の閾値（H23〜R05下：195問ベース）
def get_stars(count):
    if count >= 20: return "★★★★★"
    if count >= 12: return "★★★★☆"
    if count >= 7:  return "★★★☆☆"
    if count >= 3:  return "★★☆☆☆"
    return "★☆☆☆☆"


def define_env(env):

    @env.macro
    def theme_year_table():
        """出題頻度サマリ表（H25〜R5）を生成"""
        problems = env.variables.get("problems", [])

        col_labels = [c[0] for c in DISPLAY_COLS]
        header = "| テーマ | 計 | " + " | ".join(col_labels) + " |"
        sep    = "|--------|:--:|" + "-----|" * len(DISPLAY_COLS)

        rows = [header, sep]
        for slug, name in THEMES:
            cells = []
            count = 0
            for col_label, col_years in DISPLAY_COLS:
                found = any(
                    p.get("year") in col_years and p.get("theme") == slug
                    for p in problems
                )
                if found:
                    count += 1
                    cells.append("○")
                else:
                    cells.append("")
            row = f"| [{name}](../themes/{slug}.md) | **{count}** | " + " | ".join(cells) + " |"
            rows.append(row)

        return "\n".join(rows)

    @env.macro
    def theme_ranking_table():
        """テーマ別出題頻度ランキング表を生成"""
        problems = env.variables.get("problems", [])

        counts = []
        for slug, name in THEMES:
            count = sum(1 for p in problems if p.get("theme") == slug)
            counts.append((slug, name, count))

        counts.sort(key=lambda x: -x[2])

        header = "| 順位 | テーマ | 出題数 | 頻度 | 備考 |"
        sep    = "|------|--------|--------|------|------|"
        rows = [header, sep]

        for rank, (slug, name, count) in enumerate(counts, 1):
            stars = get_stars(count)
            note = ""
            if slug == "jigyoho-taikei":
                note = "毎年問1〜2で出題。穴埋め・論説"
            elif slug == "shisetsu-kanri":
                note = "毎年問10〜13で出題。計算問題が中心"
            elif slug == "bunsan-dengen":
                note = "H27以降ほぼ毎年出題。近年増加傾向"
            row = f"| {rank} | [{name}](../themes/{slug}.md) | {count}問 | {stars} | {note} |"
            rows.append(row)

        return "\n".join(rows)
