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
    - 平成は houkih{N}-{問} 形式で対応（links.md 収載の houkih23-3/houkih23-4 で実証）。
      年度によっては未掲載・URL体系違いがあり得るが、404 等は「取得失敗 skipped」で安全に流れる
    - HTMLパースは簡易版。誤検出時は手動で URL を開いて確認すること
    - 「根拠条文（法）＋記載事項（施行規則）」の 2 層構造ページ（保安規程等）は
      denken-ou が施行規則条番号や定義条番号を主表示するため、KNOWN_OK_MISMATCH に
      登録して誤検出（real な改正でない）を mismatch から除外する
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
    """denken-ou.com の URL を構築。令和（上下期/年1回）・平成に対応."""
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
    if era == "H":
        # 平成は年1回制・期なし。未掲載年度の 404 は取得失敗として skipped
        return f"https://denken-ou.com/houkih{ynum}-{num}/"
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


# ---------------------------------------------------------------------------
# 既知の正当な不一致（denken-ou 主表示 ≠ kakomon.yml 代表条文）— 誤検出抑止
# ---------------------------------------------------------------------------
# 以下のパターンでは yml が正しくても denken-ou の主表示条番号と食い違う:
#   - 2 層構造: 「根拠条文（法）」と「記載事項の出典（施行規則）」の出題で、
#     denken-ou は施行規則条番号や定義条番号を主表示する（保安規程等）
#   - 多条文出題: 複数条文にまたがる出題を yml が「省令§7, 解釈§12」のように
#     列挙 or 「解釈§181〜§199」のように範囲で記録し、denken-ou 主表示が
#     yml 先頭の条番号と異なる
#   - 解説順ノイズ: denken-ou が計算の前提条文（定義等）を先に解説するため
#     簡易パースが出題本体でない条番号を主表示として拾う
# いずれも real な改正・誤登録ではなく誤検出。
# yml が正しいと人手で確認したケースを登録し mismatch から除外する。
#   キー: (year, num)
#   recorded_num: yml 側の代表条番号（これが変わったら allowlist を外し再検出）
KNOWN_OK_MISMATCH: dict = {
    ("R04下", 1): {
        "recorded_num": "42",
        "reason": (
            "保安規程の根拠は電気事業法第42条（作成・届出義務）。denken-ou は"
            "大規模事業者の定義＝法第38条第4項第5号／施行規則第48条の2、記載事項＝"
            "施行規則第50条第2項第14号 を主表示するため §38/§50 を拾う。代表条文は §42。"
        ),
    },
    ("R05下", 1): {
        "recorded_num": "42",
        "reason": (
            "保安規程の根拠は電気事業法第42条。問題文が『電気事業法施行規則に基づく』"
            "と明記し denken-ou も『施行規則第50条からの出題』と解説するため §50 を拾う。"
            "記載事項の列挙は施行規則第50条第3項（自家用）だが代表条文は法 §42。"
        ),
    },
    # --- 平成分（2026-06-11 build_url 平成対応に伴うスポット監査で確認） ---
    ("H23", 4): {
        "recorded_num": "7",
        "reason": (
            "電線接続の多条文出題。denken-ou 自身が『省令第7条，解釈第12条，第143条，"
            "第150条，第158条及び第159条からの出題』と明記しており yml の"
            "『省令§7, 解釈§12』は正。簡易パースは解釈フルネーム初出（第12条）を主表示として拾う。"
        ),
    },
    ("H23", 8): {
        "recorded_num": "181",
        "reason": (
            "特殊機器の横断出題（denken-ou 明記: 解釈第187条・第189条・第190条）を yml は"
            "範囲表記 解釈§181〜§199 で記録。主表示の第187条は範囲内で、改正・誤登録ではない。"
        ),
    },
    ("H26", 5): {
        "recorded_num": "26",
        "reason": (
            "電圧維持の 2 層構造（義務の根拠＝電気事業法第26条、101±6V/202±20V の具体値＝"
            "施行規則の表）。denken-ou は施行規則第38条（現行番号。yml 記載の§44 は旧番号）を"
            "主表示するため §38 を拾う。代表条文は法 §26 で正。"
        ),
    },
    ("H28", 1): {
        "recorded_num": "43",
        "reason": (
            "主任技術者選任の 2 層構造（選任義務の根拠＝電気事業法第43条、選任を要しない"
            "事業場の要件＝施行規則第52条第2項）。denken-ou は『電気事業法施行規則第52条"
            "（抜粋）』を主表示するため §52 を拾う。2026-06-11 一次照合で旧登録 §38 を"
            "『事業法§43, 施行規則§52』へ訂正した上での正当な残差。代表条文は法 §43。"
        ),
    },
    ("H28", 10): {
        "recorded_num": "42",
        "reason": (
            "保安規程の根拠は電気事業法第42条。R05下問1 と同一問題の 2 層構造で、denken-ou は"
            "記載事項＝施行規則第50条第3項 を主表示するため §50 を拾う。代表条文は法 §42。"
        ),
    },
    ("H28", 12): {
        "recorded_num": "15",
        "reason": (
            "交流絶縁耐力試験（解釈第15条＝最大使用電圧の1.5倍を10分）の計算問題。denken-ou は"
            "計算の前提となる最大使用電圧（解釈第1条の定義・1.15/1.1係数）を先に解説するため"
            "第1条を主表示として拾う。出題本体は §15 で yml は正。"
        ),
    },
    ("H30", 2): {
        "recorded_num": "38",
        "reason": (
            "太陽電池発電所の設置手続の多条文出題（denken-ou 明記: 法第38条＋施行規則第48条・"
            "第52条・第65条。解説中はさらに法第43条・第48条・第51条の2・規則第74条に言及）。"
            "denken-ou の先頭引用は法第38条で yml と一致するが、簡易パースの最頻出計数が"
            "第48条（規則48＋法48）になる。代表条文は法 §38 で正。"
        ),
    },
    # --- 監査トリアージ最終バッチ（2026-06-12 denken-ou raw HTML 一次照合） ---
    ("H24", 3): {
        "recorded_num": "19",
        "reason": (
            "正誤組合せ問題。問題文中に電気事業法第1条（目的）・第2条の条文が引用されており、"
            "簡易パースがそのフルネーム初出（法第1条・第2条）を主表示として誤拾いする。出題の主題は"
            "公害等の防止・PCB禁止＝省令第19条で yml の §19 が正。denken-ou も省令第19条を解説の中心に置く。"
        ),
    },
    ("H24", 11): {
        "recorded_num": "15",
        "reason": (
            "高圧引込ケーブルの交流絶縁耐力試験。前提として最大使用電圧の定義（解釈第1条の1.15/1.1係数）"
            "が先に解説されるため簡易パースが解釈第1条を定義ノイズとして拾う。出題本体は"
            "最大使用電圧の1.5倍を10分＝解釈第15条で yml は正。"
        ),
    },
    ("H25", 3): {
        "recorded_num": "57",
        "reason": (
            "電気使用場所の配線の使用電線の 2 層構造（原則＝省令第57条、具体的な電線種別＝解釈第142条）。"
            "denken-ou は計算・列挙で解釈第142条を主表示するため簡易パースが第142条を拾うが、"
            "出題の根拠は省令第57条で yml の §57 が正。"
        ),
    },
    ("H29", 4): {
        "recorded_num": "33",
        "reason": (
            "ガス絶縁機器等の危険の防止の 2 層構造（原則＝省令第33条、具体的な圧力試験等＝解釈第40条）。"
            "denken-ou は省令第33条からの問題と明示しつつ具体は解釈第40条で解説するため簡易パースが"
            "第40条を拾う。代表条文は省令 §33 で正。"
        ),
    },
    ("H27", 1): {
        "recorded_num": "38",
        "reason": (
            "自家用電気工作物の 2 層構造（PR #86 で『事業法§38, 施行規則§48』へ訂正済み。事業の根拠＝"
            "法第38条、600V境界の定義＝施行規則第48条）。denken-ou も施行規則第48条を主表示し簡易パースの"
            "最頻出計数も第48条（規則48＋法48）になるが、代表条文は法 §38 で正。"
        ),
    },
    ("H29", 8): {
        "recorded_num": "42",
        "reason": (
            "架空弱電流電線路への誘導作用による通信障害の防止の 2 層構造（PR #86 で『省令§42, 解釈§52』へ"
            "訂正済み。原則＝省令第42条、具体的な離隔等＝解釈第52条）。denken-ou は解釈第52条からの出題と明示・"
            "主表示するため簡易パースが第52条を拾う。代表条文は省令 §42。"
        ),
    },
}


def is_known_ok(year: str, num: int, recorded: str | None) -> bool:
    """既知の正当な不一致（2 層構造）なら True。mismatch から除外する."""
    k = KNOWN_OK_MISMATCH.get((year, num))
    return bool(k and recorded and k["recorded_num"] == recorded)


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
    allowlisted = 0
    matched_entries: list[dict] = []

    for i, p in enumerate(target, 1):
        url = build_url(p["year"], p["num"])
        if not url:
            skipped += 1
            print(f"[{i}/{len(target)}] - {p['year']}問{p['num']} | URL構築不可（年度書式不明）")
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
        elif actual and recorded and is_known_ok(p["year"], p["num"], recorded):
            # 既知の正当な不一致（2 層構造）。yml が正しいので検証済み扱い
            matched += 1
            allowlisted += 1
            matched_entries.append(p)
            mark = "✓*"
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
    print(
        f"一致: {matched} | 不一致: {len(mismatches)} | スキップ/失敗: {skipped}"
        + (f" | 既知の正当な不一致(allowlist): {allowlisted}" if allowlisted else "")
    )
    if allowlisted:
        print(
            "  ✓* = denken-ou 主表示と代表条文が 2 層構造で正当に異なる既知ケース"
            "（KNOWN_OK_MISMATCH 登録済み・誤検出抑止）"
        )

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
