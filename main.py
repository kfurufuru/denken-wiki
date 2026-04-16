"""
MkDocs Macros Plugin - 電験3種 法規 過去問マクロ
denken-wiki の kakomon/*.md で使用するマクロ関数を定義

マクロ一覧:
  theme_year_table()              - 出題頻度サマリ表（全テーマ × 年度）
  theme_ranking_table()           - テーマ別頻度ランキング表
  kakomon_freq_badge(theme)       - テーマ頻度バッジ（◎ N問/M年）
  kakomon_recent_problems(theme)  - 直近5問のミニ出題実績テーブル
  render_freq_summary(theme)      - 出題傾向サマリブロック（テーマページ用）
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

# 星評価の閾値（H18〜R07下：312問ベース）
def get_stars(count):
    if count >= 40: return "★★★★★"
    if count >= 20: return "★★★★☆"
    if count >= 12: return "★★★☆☆"
    if count >= 6:  return "★★☆☆☆"
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

    # ------------------------------------------------------------------ #
    #  ヘルパー: 年コード → 表示ラベル変換                                  #
    # ------------------------------------------------------------------ #
    def _year_label(year_code: str) -> str:
        """'R06上' → 'R6上' など短縮形に変換"""
        import re
        m = re.match(r"(R|H)0?(\d+)(上|下)?$", year_code)
        if m:
            era, num, half = m.groups()
            return f"{era}{num}{half or ''}"
        return year_code

    # ------------------------------------------------------------------ #
    #  kakomon_freq_badge(theme) — ◎/○/△ バッジを返す                    #
    # ------------------------------------------------------------------ #
    @env.macro
    def kakomon_freq_badge(theme: str) -> str:
        """
        使い方: {{ kakomon_freq_badge('setsuchi') }}
        → '◎ 17問 / 14年出題' のような文字列を返す。
        テーマが見つからない場合は '未集計' を返す。
        """
        problems = env.variables.get("problems", [])
        # テーマに一致する問題を抽出
        matched = [p for p in problems if p.get("theme") == theme]
        if not matched:
            return "未集計"

        total_problems = len(matched)
        # 出題された年（重複なし）
        years_with_problem = len({p.get("year") for p in matched})
        # 全年度数（DISPLAY_COLSから逆算: H25〜R07 = 14カラム）
        total_years = len(DISPLAY_COLS)

        if years_with_problem >= total_years * 0.8:
            badge = "◎"
        elif years_with_problem >= total_years * 0.5:
            badge = "○"
        elif years_with_problem >= total_years * 0.2:
            badge = "△"
        else:
            badge = "─"

        return f"**{badge} {total_problems}問 / {years_with_problem}年出題**（H25〜R07）"

    # ------------------------------------------------------------------ #
    #  kakomon_recent_problems(theme, n) — 直近N問ミニテーブル             #
    # ------------------------------------------------------------------ #
    @env.macro
    def kakomon_recent_problems(theme: str, n: int = 5) -> str:
        """
        使い方: {{ kakomon_recent_problems('setsuchi') }}
        直近n問（年度降順）の出題実績をMarkdownテーブルで返す。
        """
        problems = env.variables.get("problems", [])
        matched = [p for p in problems if p.get("theme") == theme]
        if not matched:
            return "_出題実績データなし_"

        # 年度コードを降順ソート（文字列ソートでR>H、数値部分は0埋め正規化）
        def sort_key(p):
            y = p.get("year", "")
            import re
            m = re.match(r"(R|H)(\d+)(上|下)?", y)
            if m:
                era_val = 200 if m.group(1) == "R" else 100
                num = int(m.group(2))
                half = 1 if m.group(3) == "下" else 0
                return era_val + num + half * 0.1
            return 0

        matched_sorted = sorted(matched, key=sort_key, reverse=True)
        recent = matched_sorted[:n]

        header = "| 年度 | 問 | 形式 | 出題内容 |"
        sep    = "|------|:--:|:----:|---------|"
        rows = [header, sep]
        for p in recent:
            year  = _year_label(p.get("year", ""))
            num   = p.get("num", "─")
            form  = p.get("form", "─")
            topic = p.get("topic", "─")
            rows.append(f"| {year} | 問{num} | {form} | {topic} |")

        return "\n".join(rows)

    # ------------------------------------------------------------------ #
    #  render_freq_summary(theme) — 出題傾向サマリブロック                  #
    # ------------------------------------------------------------------ #
    @env.macro
    def render_freq_summary(theme: str) -> str:
        """
        使い方: {{ render_freq_summary('setsuchi') }}
        テーマページ用の出題傾向サマリブロック（admonition形式）を生成する。
        「直近5問テーブル」＋「出題頻度バッジ」をセットで出力。
        """
        badge  = kakomon_freq_badge(theme)
        table  = kakomon_recent_problems(theme, n=5)

        lines = [
            '!!! info "出題傾向（自動集計 · kakomon.yml）"',
            f"    出題頻度: {badge}  ",
            "    ",
            "    直近の出題実績:",
            "    ",
        ]
        # テーブル各行をadmonitionのインデント（4スペース）に揃える
        for line in table.splitlines():
            lines.append(f"    {line}")

        return "\n".join(lines)

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
