"""
kakomon.yml の article フィールドを denken-ou.com で外部照合する監査スクリプト.

電技解釈は改正で条番号が変わることがある。kakomon.yml の article が
denken-ou.com（信頼できる過去問解説サイト）と一致するかチェックする。

使い方:
    python scripts/audit_kakomon.py --article 解釈§224         # 特定条文の全出題を照合
    python scripts/audit_kakomon.py --recent 10                # 最新10件をスポット監査
    python scripts/audit_kakomon.py --year R06下               # 特定年度の全問を照合
    python scripts/audit_kakomon.py --all                      # 全件（247件・約8分）
    python scripts/audit_kakomon.py --recent 10 --json out.json  # JSON出力

出力:
    [N/M] ✓ R06下問7 | recorded=解釈§224 | denken-ou=第224条
    [N/M] ✗ R06下問7 | recorded=解釈§227 | denken-ou=第224条  ← 不一致

注意:
    - denken-ou.com への礼儀として --delay (default 2秒) 間隔でリクエスト
    - 平成年度はURL構造が異なる場合があり対応外（令和のみ確実）
    - HTMLパースは簡易版。誤検出時は手動で URL を開いて確認すること
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

import yaml

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
KAKOMON_YML = ROOT / "_data" / "kakomon.yml"


def parse_year(y: str):
    """'R06下' → ('R', 6, '下')、'H29' → ('H', 29, None) を返す."""
    m = re.match(r"^(R)0?(\d+)(上|下)?$", y)
    if m:
        return ("R", int(m.group(2)), m.group(3))
    m = re.match(r"^(H)(\d+)$", y)
    if m:
        return ("H", int(m.group(2)), None)
    return None


def build_url(year: str, num: int) -> str | None:
    """denken-ou.com の URL を構築。令和のみ確実対応."""
    parsed = parse_year(year)
    if not parsed:
        return None
    era, ynum, period = parsed
    if era == "R" and period:
        period_num = 1 if period == "上" else 2
        return f"https://denken-ou.com/houkir{ynum}-{period_num}-{num}/"
    if era == "R" and not period:
        # R01〜R03（上下期制以前）
        return f"https://denken-ou.com/houkir{ynum}-{num}/"
    # 平成は URL 構造が複数パターンあり未対応
    return None


def fetch_page(url: str) -> str | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "audit_kakomon/1.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception:
        return None


# 「第224条」「解釈第224条」等を抽出
ART_PATTERNS = [
    re.compile(r"電気設備の?技術基準の解釈\s*第\s*(\d+)\s*条"),
    re.compile(r"電技解釈\s*第\s*(\d+)\s*条"),
    re.compile(r"解釈\s*第\s*(\d+)\s*条"),
    re.compile(r"電気設備技術基準\s*第\s*(\d+)\s*条"),
    re.compile(r"電気事業法\s*(?:施行規則\s*)?第\s*(\d+)\s*条"),
    re.compile(r"電気事業法施行令\s*第\s*(\d+)\s*条"),
]


def extract_article_num(html: str | None) -> str | None:
    """ページHTMLから条文番号を抽出。

    優先度:
    1. フルネーム表記（「電気設備の技術基準の解釈 第N条」等）の最初のマッチ → 主要本文と判定
    2. それがなければ短縮形（「解釈第N条」「§N」等）の最頻出
    関連記事リンクの短縮形による誤検出を回避するため."""
    if not html:
        return None
    # 上位2パターンはフルネーム表記。最初の出現を主要参照と判定
    for pat in ART_PATTERNS[:2]:
        m = pat.search(html)
        if m:
            return m.group(1)
    # フォールバック: 全パターンで最頻出
    from collections import Counter

    nums: list[str] = []
    for pat in ART_PATTERNS:
        for m in pat.finditer(html):
            nums.append(m.group(1))
    if not nums:
        return None
    return Counter(nums).most_common(1)[0][0]


def extract_article_num_from_recorded(article: str) -> str | None:
    """'解釈§224' / '省令§17' から数字部分を抽出."""
    if not article:
        return None
    m = re.search(r"§\s*(\d+)", article)
    if m:
        return m.group(1)
    m = re.search(r"第\s*(\d+)\s*条", article)
    if m:
        return m.group(1)
    return None


def year_sort_key(p: dict):
    parsed = parse_year(p["year"])
    if not parsed:
        return (0, 0, 0, p.get("num", 0))
    era_v = 1 if parsed[0] == "R" else 0
    period_v = 1 if parsed[2] is None else (2 if parsed[2] == "上" else 3)
    return (era_v, parsed[1], period_v, p.get("num", 0))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--article", help="特定条文の出題のみ照合 (例: 解釈§224)")
    parser.add_argument("--recent", type=int, help="最新N件を照合")
    parser.add_argument("--year", help="特定年度のみ照合 (例: R06下)")
    parser.add_argument("--all", action="store_true", help="全件照合 (約8分)")
    parser.add_argument("--json", help="不一致をJSON出力")
    parser.add_argument(
        "--cache",
        help="検証済み（一致した）エントリをYAMLキャッシュに保存。pre-commitフック用",
    )
    parser.add_argument(
        "--delay", type=float, default=2.0, help="リクエスト間隔秒 (default: 2)"
    )
    args = parser.parse_args()

    data = yaml.safe_load(KAKOMON_YML.read_text(encoding="utf-8"))
    problems = data["problems"]

    if args.article:
        target = [p for p in problems if args.article in p.get("article", "")]
    elif args.year:
        target = [p for p in problems if p["year"] == args.year]
    elif args.recent:
        target = sorted(problems, key=year_sort_key, reverse=True)[: args.recent]
    elif args.all:
        target = problems
    else:
        parser.print_help()
        return 1

    if not target:
        print("対象なし")
        return 0

    print(f"監査対象: {len(target)}件 | delay={args.delay}秒")
    print("-" * 80)

    mismatches = []
    skipped = 0
    matched = 0
    matched_entries: list[dict] = []

    for i, p in enumerate(target, 1):
        url = build_url(p["year"], p["num"])
        if not url:
            skipped += 1
            print(f"[{i}/{len(target)}] - {p['year']}問{p['num']} | URL構築不可（平成等）")
            continue

        time.sleep(args.delay)
        html = fetch_page(url)
        if html is None:
            skipped += 1
            print(f"[{i}/{len(target)}] ? {p['year']}問{p['num']} | 取得失敗 {url}")
            continue

        actual = extract_article_num(html)
        recorded = extract_article_num_from_recorded(p.get("article", ""))

        if actual and recorded and actual == recorded:
            matched += 1
            matched_entries.append(p)
            mark = "✓"
        elif actual and recorded and actual != recorded:
            mismatches.append(
                {
                    "year": p["year"],
                    "num": p["num"],
                    "topic": p.get("topic", ""),
                    "recorded": p.get("article", ""),
                    "denken_ou_article_num": actual,
                    "url": url,
                }
            )
            mark = "✗"
        else:
            skipped += 1
            mark = "?"

        rec_str = p.get("article", "N/A")
        act_str = f"第{actual}条" if actual else "N/A"
        print(
            f"[{i}/{len(target)}] {mark} {p['year']}問{p['num']:<2} "
            f"| recorded={rec_str:<15} | denken-ou={act_str}"
        )

    print("-" * 80)
    print(f"一致: {matched} | 不一致: {len(mismatches)} | スキップ/失敗: {skipped}")

    if mismatches:
        print("\n=== 不一致詳細（要手動確認） ===")
        print(
            "⚠️  本スクリプトの HTML 解析は簡易版で、関連記事リンク等に含まれる条番号を\n"
            "    誤検出することがある。✗ 表示は必ず URL を開いて手動確認すること。\n"
        )
        for m in mismatches:
            print(
                f"  {m['year']}問{m['num']}: {m['topic']}\n"
                f"    記録: {m['recorded']} → denken-ou: 第{m['denken_ou_article_num']}条\n"
                f"    URL: {m['url']}"
            )

    if args.json:
        out = Path(args.json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(mismatches, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nJSON保存: {args.json}")

    if args.cache:
        from datetime import datetime, timezone

        cache_path = Path(args.cache)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        existing: dict = {}
        if cache_path.exists():
            existing = yaml.safe_load(cache_path.read_text(encoding="utf-8")) or {}
        verified = existing.get("verified", {}) if isinstance(existing, dict) else {}
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for p in matched_entries:
            key = f"{p['year']}-{p['num']}"
            verified[key] = {
                "topic": p.get("topic", ""),
                "article": p.get("article", ""),
                "verified_at": now,
            }
        out_data = {
            "_comment": "denken-ou.com 外部照合で kakomon.yml と一致確認済みエントリ。pre-commit hookが参照する",
            "verified": verified,
        }
        cache_path.write_text(
            yaml.safe_dump(out_data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        print(f"\nキャッシュ保存: {args.cache} | 検証済み {len(verified)}件")

    return 0 if not mismatches else 2


if __name__ == "__main__":
    sys.exit(main())
