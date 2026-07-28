#!/usr/bin/env python3
"""
kakomon.yml の article フィールドから条文ごとの出題回数を集計する。

マッピング:
  省令§N         -> kijun/N.md
  解釈§N         -> kaishaku/N.md
  事業法§N       -> jigyoho/N.md
  工事士法§N     -> other/koji-shi-N.md
  電気用品安全法§N -> other/pse-N.md
  報告規則§N     -> other/jiko-N.md
  施行規則§N     -> (該当ページなし。集計のみ表示)

article フィールドの曖昧表記（"事業法§40, 施行規則" 等）は
カンマ・読点・スラッシュ・スペース・「及び」「、」「・」で区切られた
個別エントリとして扱い、各々を別カウントする（過大評価寄りの安全側）。
"""
from __future__ import annotations
import io
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

# stdout を UTF-8 に固定（Windows 対策）。直接実行時のみ。
if __name__ == "__main__":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
KAKOMON = ROOT / "_data" / "kakomon.yml"
ARTICLES = ROOT / "docs" / "articles"

# 法令名 → ページディレクトリ・ファイル名プレフィクス
LAW_TO_PATH = {
    "省令": ("kijun", ""),
    "解釈": ("kaishaku", ""),
    "事業法": ("jigyoho", ""),
    "工事士法": ("other", "koji-shi-"),
    "電気用品安全法": ("other", "pse-"),
    "報告規則": ("other", "jiko-"),
}

# §記号と全角同等記号のバリエーション
ARTICLE_SEP = r"[§§]"

# "省令§5", "事業法§40", "解釈§17" などにマッチ。
# 番号は連続する第一の整数のみを取る。
# 施行規則も法令名として認識する（ページなし→unmapped 集計のみ）。
# 認識しないと "事業法§43, 施行規則§52" の §52 が直前法令を引き継いで
# 事業法§52（溶接自主検査・無関係）へ幻カウントされる。
LAW_PATTERN = re.compile(
    r"(省令|事業法|解釈|工事士法|電気用品安全法|報告規則|施行規則)\s*" + ARTICLE_SEP + r"\s*(\d+)"
)

# "§17", "§220" 単独（前方の法令名を引き継ぐケース、例: 解釈§47, §48）
SHORT_PATTERN = re.compile(ARTICLE_SEP + r"\s*(\d+)")


def parse_article_field(field: str):
    """article フィールドを解析して (law, num) のリストを返す。"""
    if not field:
        return []
    results = []
    # 空白を1個に正規化（全角空白も）
    text = field.replace("　", " ")
    # 句読点・スラッシュ等で分割
    chunks = re.split(r"[、,，/／・]+|及び|並びに", text)
    last_law = None
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        m = LAW_PATTERN.search(chunk)
        if m:
            last_law = m.group(1)
            results.append((last_law, int(m.group(2))))
            # 同チャンク内に "解釈§47, §48" のような場合に対応するため
            # 残り部分を再検索
            for m2 in SHORT_PATTERN.finditer(chunk[m.end():]):
                results.append((last_law, int(m2.group(1))))
        else:
            # 法令名なし、§N だけの場合 → 直前の法令を引き継ぐ
            for m2 in SHORT_PATTERN.finditer(chunk):
                if last_law is not None:
                    results.append((last_law, int(m2.group(1))))
    return results


def to_filepath(law: str, num: int) -> Path | None:
    if law not in LAW_TO_PATH:
        return None
    sub, prefix = LAW_TO_PATH[law]
    return ARTICLES / sub / f"{prefix}{num}.md"


def main():
    data = yaml.safe_load(KAKOMON.read_text(encoding="utf-8"))
    problems = data.get("problems", [])
    print(f"[INFO] kakomon.yml: 全 {len(problems)} 問")

    counter = Counter()
    unmapped = Counter()

    for p in problems:
        field = p.get("article", "") or ""
        for law, num in parse_article_field(field):
            path = to_filepath(law, num)
            if path is None:
                unmapped[(law, num)] += 1
                continue
            counter[path] += 1

    # 上位10
    print("\n=== 上位10条（出題回数） ===")
    for path, n in counter.most_common(10):
        rel = path.relative_to(ROOT).as_posix()
        exists = "OK" if path.exists() else "MISSING"
        print(f"  {n:>3} 回 | {rel} [{exists}]")

    # 全条文ファイル列挙（index.md 除外）
    all_files = []
    for sub in ("kijun", "kaishaku", "jigyoho", "other"):
        for f in sorted((ARTICLES / sub).glob("*.md")):
            if f.name == "index.md":
                continue
            all_files.append(f)
    print(f"\n[INFO] 条文 Markdown ファイル数: {len(all_files)}")

    # 0回の条文
    zero_files = [f for f in all_files if counter.get(f, 0) == 0]
    print(f"\n=== 出題0回の条文（{len(zero_files)}件・先頭10件） ===")
    for f in zero_files[:10]:
        print(f"  {f.relative_to(ROOT).as_posix()}")

    # 集計結果を file -> count の辞書として出力（呼び出し側で再利用）
    result = {f.as_posix(): counter.get(f, 0) for f in all_files}

    # マッピング不明のサンプル
    if unmapped:
        print(f"\n[WARN] 未マッピング法令: {len(unmapped)}件")
        for (law, num), n in sorted(unmapped.items())[:5]:
            print(f"  {law}§{num}  x{n}")

    return result, all_files


# 「📊 試験対策メタ」の自動注入値（例: "**出題頻度**: 🔥🔥（過去14年で 2 回出題）"）
META_FREQ = re.compile(r"過去14年で\s*(\d+)\s*回出題")


def audit_meta_drift():
    """注入済みメタの出題回数が kakomon.yml の現集計と食い違う条文を列挙する。

    なぜ必要か（2026-07-28 制定）:
      `inject_frequency_meta.py` は「既に『試験対策メタ』admonition があれば skip」する
      **一度きりの注入**なので、`_data/kakomon.yml` に問題が追加されてもメタの数字は
      更新されない。結果、記事が学習者に示す「過去14年で N 回出題」（＝優先度の判断材料）が
      静かに古くなる。CI もこれを検査していなかった。

    注意:
      この差分は**そのまま自動修正してはいけない**。再帰属（H30問3 を省令第30条＋第47条へ
      戻した PR 等）で手作業により訂正されたメタもあり、どちらが正かは個別に一次照合が要る。
      本関数は**検出のみ**（非ゲート WARN）。
    """
    data = yaml.safe_load(KAKOMON.read_text(encoding="utf-8"))
    counter = Counter()
    for p in data.get("problems", []):
        for law, num in parse_article_field(p.get("article", "") or ""):
            path = to_filepath(law, num)
            if path is not None:
                counter[path] += 1

    rows = []
    for sub in ("kijun", "kaishaku", "jigyoho", "other"):
        d = ARTICLES / sub
        if not d.is_dir():
            continue
        for f in sorted(d.glob("*.md")):
            if f.name == "index.md":
                continue
            m = META_FREQ.search(f.read_text(encoding="utf-8"))
            if not m:
                continue
            claimed, actual = int(m.group(1)), counter.get(f, 0)
            if claimed != actual:
                rows.append((f.relative_to(ROOT).as_posix(), claimed, actual))
    return rows


def main_audit_meta() -> int:
    rows = audit_meta_drift()
    for rel, claimed, actual in rows:
        print(f"  WARN {rel}: メタ「{claimed} 回出題」 vs kakomon.yml 集計 {actual} 回")
    print(f"[SUMMARY] 頻度メタのドリフト: {len(rows)}件")
    return 0  # 非ゲート（exit には影響させない）


if __name__ == "__main__":
    if "--audit-meta" in sys.argv:
        sys.exit(main_audit_meta())
    main()
