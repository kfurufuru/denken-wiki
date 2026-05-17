"""
H18-H22, R01-R02 の過去問を docs/kakomon/*.md からパースして _data/kakomon.yml に append する。
一度きりの実行を想定。実行後はスクリプトを残すが再実行は不要。

theme はトピック語のキーワードマッチで既存schemeにマップ。マッチしないものは "other"。
"""
import re
import yaml
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
YML_PATH = REPO / "_data" / "kakomon.yml"
KAKOMON_DIR = REPO / "docs" / "kakomon"

YEAR_LABEL_MAP = {
    "H18": "平成18年（2006年）",
    "H19": "平成19年（2007年）",
    "H20": "平成20年（2008年）",
    "H21": "平成21年（2009年）",
    "H22": "平成22年（2010年）",
    "R01": "令和元年（2019年）",
    "R02": "令和2年（2020年）",
}

TARGET_FILES = {
    "H18": "H18.md",
    "H19": "H19.md",
    "H20": "H20.md",
    "H21": "H21.md",
    "H22": "H22.md",
    "R01": "R01.md",
    "R02": "R02.md",
}

# テーマ推定キーワード（既存schema優先順位）
THEME_RULES = [
    ("setsuchi",         ["接地工事", "B種接地", "D種接地", "接地抵抗"]),
    ("zetsuen",          ["絶縁性能", "絶縁抵抗", "絶縁耐力試験", "絶縁油"]),
    ("kachiku-densen",   ["架空電線", "架空引込", "支線", "支持物", "風圧荷重", "弛度"]),
    ("chichuu-densen",   ["地中電線"]),
    ("densen-cable",     ["ケーブル", "電線の接続"]),
    ("hatsuhendenjo",    ["発電所", "変電所", "風車", "風力", "発電機", "蓄電池", "太陽電池"]),
    ("bunsan-dengen",    ["分散型電源", "系統連系"]),
    ("hogo-sochi",       ["保護装置", "保護協調", "地絡", "過電流継電器", "遮断器"]),
    ("haisen-koji",      ["金属管工事", "ライティングダクト", "金属ダクト", "配線", "屋内配線"]),
    ("shiyo-basho",      ["屋内電路", "電気使用場所", "住宅"]),
    ("shijimono",        ["足場金具", "昇塔防止"]),
    ("tokushu-basho",    ["特殊", "電気さく", "電気浴器", "水中照明", "遊戯用電車"]),
    ("yogo-teigi",       ["用語の定義", "用語定義"]),
    ("shunin-gijutsusha", ["主任技術者"]),
    ("jigyoho-taikei",   ["電気事業法", "事業用電気工作物", "一般用電気工作物", "保安規程",
                          "事故報告", "電気工事士", "電気工事業", "PCB", "公害",
                          "電気の使用制限", "工事計画", "技術基準適合", "電気用品安全",
                          "電圧", "周波数", "立入検査", "電圧及び周波数",
                          "電磁誘導", "電磁障害"]),
    ("shisetsu-kanri",   ["需要率", "不等率", "負荷率", "力率改善", "高調波", "コンデンサ",
                          "全日効率", "日負荷曲線", "変圧器", "水力発電",
                          "百分率インピーダンス", "高圧受電", "キュービクル",
                          "単線結線図", "電力", "供給支障"]),
]

FORM_NORMALIZE = {
    "穴埋/計算": "計算",
    "計算/論説": "計算",
}

def estimate_theme(topic: str) -> str:
    for theme, keywords in THEME_RULES:
        for kw in keywords:
            if kw in topic:
                return theme
    return "other"

def parse_md_table(md_text: str) -> list[dict]:
    """過去問テーブル行をパース。問N行のみ抽出。"""
    rows = []
    for line in md_text.splitlines():
        m = re.match(
            r"\|\s*問(\d+)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|",
            line
        )
        if not m:
            continue
        num = int(m.group(1))
        topic = m.group(2).strip()
        bunrui = m.group(3).strip()  # 未使用（themeはtopic推定）
        form = FORM_NORMALIZE.get(m.group(4).strip(), m.group(4).strip())
        article = m.group(6).strip()
        # 「事業法第43条」→「事業法§43」変換（既存schemaに合わせる）
        article = re.sub(r"第(\d+)条(の\d+)?", lambda x: f"§{x.group(1)}{x.group(2) or ''}", article)
        article = article.replace(", ", ", ")
        rows.append({
            "num": num,
            "topic": topic,
            "form": form,
            "article": article,
        })
    return rows

def main():
    data = yaml.safe_load(YML_PATH.read_text(encoding="utf-8"))
    existing_keys = {(p["year"], p["num"]) for p in data["problems"]}

    additions = []
    for year_key, filename in TARGET_FILES.items():
        md_path = KAKOMON_DIR / filename
        if not md_path.exists():
            print(f"[SKIP] {filename} not found")
            continue
        md_text = md_path.read_text(encoding="utf-8")
        rows = parse_md_table(md_text)
        if len(rows) != 13:
            print(f"[WARN] {filename}: {len(rows)} rows parsed (expected 13)")
        for row in rows:
            key = (year_key, row["num"])
            if key in existing_keys:
                print(f"[SKIP] {year_key} 問{row['num']} already exists")
                continue
            theme = estimate_theme(row["topic"])
            additions.append({
                "year": year_key,
                "year_label": YEAR_LABEL_MAP[year_key],
                "num": row["num"],
                "topic": row["topic"],
                "theme": theme,
                "form": row["form"],
                "article": row["article"],
            })

    if not additions:
        print("[DONE] no additions needed")
        return

    print(f"[INFO] {len(additions)} entries to append")
    additions.sort(key=lambda p: (p["year"], p["num"]))

    # 既存スタイル維持のためテキスト追記方式（既存エントリは触らない）
    text = YML_PATH.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        text += "\n"

    def q(s) -> str:
        return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'

    new_lines = []
    for p in additions:
        new_lines.append(f'  - year: {q(p["year"])}')
        new_lines.append(f'    year_label: {q(p["year_label"])}')
        new_lines.append(f'    num: {p["num"]}')
        new_lines.append(f'    topic: {q(p["topic"])}')
        new_lines.append(f'    theme: {q(p["theme"])}')
        new_lines.append(f'    form: {q(p["form"])}')
        new_lines.append(f'    article: {q(p["article"])}')
    text += "\n".join(new_lines) + "\n"

    YML_PATH.write_text(text, encoding="utf-8")
    print(f"[OK] appended {len(additions)} entries to {YML_PATH} (text-append mode)")

if __name__ == "__main__":
    main()
