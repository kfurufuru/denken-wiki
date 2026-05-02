#!/usr/bin/env python3
"""
出題頻度の整合性監査
- 各 kijun/*.md の過去問実績エントリ数を実カウント
- 表記された出題頻度（X回/Y年）と比較
- 星の数が回数に整合するか確認

星の判定基準（提案）:
  ★☆☆☆☆: 0-1回
  ★★☆☆☆: 2回
  ★★★☆☆: 3回
  ★★★★☆: 4-5回
  ★★★★★: 6回以上
"""
import re
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

KIJUN = Path(__file__).parent.parent / "docs" / "articles" / "kijun"

def expected_stars(n):
    if n <= 1: return "★☆☆☆☆"
    if n == 2: return "★★☆☆☆"
    if n == 3: return "★★★☆☆"
    if n <= 5: return "★★★★☆"
    return "★★★★★"

def parse_page(path):
    text = path.read_text(encoding="utf-8")
    # 出題頻度（行頭・非インデントの standalone 行を優先。
    # linter追加の `!!! abstract` 内の絵文字行は4スペース字下げのため除外）
    m = re.search(r"^\*\*出題頻度\*\*[:：]\s*(.+)", text, re.MULTILINE)
    auto_meta_only = False
    if not m:
        # フォールバック: インデントを許容して最初の出題頻度行を読む（=自動注入メタのみ）
        m = re.search(r"\*\*出題頻度\*\*[:：]\s*(.+)", text)
        auto_meta_only = True
    freq_line = m.group(1) if m else ""
    # 星の数
    stars_m = re.search(r"(★+☆*)", freq_line)
    stars = stars_m.group(1) if stars_m else ""
    # X回/Y年
    n_m = re.search(r"(\d+)(?:〜(\d+))?\s*回", freq_line)
    if n_m:
        low = int(n_m.group(1))
        high = int(n_m.group(2)) if n_m.group(2) else low
    else:
        low, high = 0, 0
    # 過去問実績テーブル: ヘッダ後の |...| 行を数える
    sec = re.search(r"##\s+(?:[\d\.\s]*)?(?:📝\s*)?過去問実績(.+?)(?=\n##\s|\Z)", text, re.S)
    actual = 0
    if sec:
        for line in sec.group(1).splitlines():
            line = line.strip()
            if line.startswith("|") and not line.startswith("|---") and "年度" not in line and "----" not in line:
                # 実エントリ行
                cols = [c for c in line.split("|") if c.strip()]
                if cols and re.match(r"^[HR]\d", cols[0].strip()):
                    actual += 1
    return {"freq_line": freq_line, "stars": stars, "low": low, "high": high, "actual": actual, "auto_meta_only": auto_meta_only}

def main():
    pages = sorted(KIJUN.glob("*.md"))
    pages = [p for p in pages if p.name != "index.md"]
    print(f"{'page':>8} | {'実カウント':>8} | {'表記':>10} | {'星':6} | {'期待星':6} | 判定")
    print("-" * 80)
    issues = []
    for p in pages:
        d = parse_page(p)
        exp = expected_stars(d["actual"])
        within = d["low"] <= d["actual"] <= d["high"]
        stars_ok = d["stars"] == exp
        # 「省令§N直接の出題なし」と明示されたページは、過去問実績テーブルに
        # 関連条文（解釈§17等）の問題が並ぶため、件数照合を免除する
        if "出題なし" in d["freq_line"]:
            within = True
            stars_ok = True
            exp = d["stars"] if d["stars"] else exp
        # 自動注入メタのみのページは ★ ではなく 🔥 表記なので星照合を免除（件数のみ照合）
        if d["auto_meta_only"]:
            stars_ok = True
            exp = d["stars"] if d["stars"] else "(自動メタ)"
        verdict = "OK" if (within and stars_ok) else "NG"
        if not within or not stars_ok:
            issues.append((p.name, d, exp))
        freq_disp = f"{d['low']}〜{d['high']}回" if d["low"] != d["high"] else f"{d['low']}回"
        print(f"{p.name:>8} | {d['actual']:>8}件 | {freq_disp:>10} | {d['stars']:6} | {exp:6} | {verdict}")
    print()
    print(f"[SUMMARY] 全{len(pages)}ページ中、頻度不整合: {len(issues)}件")
    if issues:
        print("\n=== 修正候補 ===")
        for name, d, exp in issues:
            print(f"  {name}: 実{d['actual']}件 / 表記={d['low']}-{d['high']}回 {d['stars']} → 期待 {exp}")

if __name__ == "__main__":
    main()
