"""v3.1 採点軸 vs 擬似主観品質 Spearman相関検証.

ひろゆき指摘への回答: 採点軸が本当に品質と相関しているかの検証。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# wiki_quality_check.py を import 可能にする
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from wiki_quality_check import (  # noqa: E402
    score_v3,
    get_kakomon_meta,
    V3_AXES,
)

DOCS_ARTICLES = ROOT / "docs" / "articles"


# ---------------------------------------------------------------------------
# 擬似主観品質 (proxy quality) 計算
# ---------------------------------------------------------------------------

def compute_proxy_features(path: Path) -> dict:
    """記事から代理指標 6種 を抽出"""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # 行数
    n_lines = len(lines)

    # SVG数
    n_svg = len(re.findall(r"<svg[\s>]", content))

    # テーブル数（パイプ行の連続を1テーブルとカウント）
    table_lines = [bool(re.match(r"^\s*\|.*\|.*\|", l)) for l in lines]
    n_tables = 0
    in_table = False
    for is_t in table_lines:
        if is_t and not in_table:
            n_tables += 1
            in_table = True
        elif not is_t:
            in_table = False

    # 監修ログ更新数: 「監修ログ」 セクション内の `- **YYYY-MM-DD**` を数える
    n_audit = 0
    sec_match = re.search(
        r"(?:^|\n)##+\s*(?:監修ログ|更新履歴)[^\n]*\n(.*?)(?=\n##+\s|\Z)",
        content,
        re.DOTALL,
    )
    if sec_match:
        body = sec_match.group(1)
        n_audit = len(re.findall(r"^\s*-\s*\*\*\d{4}-\d{2}-\d{2}\*\*", body, re.MULTILINE))

    # kakomon.yml 登録件数
    meta = get_kakomon_meta(path)
    n_kakomon = meta.get("registered", 0)

    # 内部リンク数 (.md 拡張子付き)
    n_links = len(re.findall(r"\[[^\]]+\]\([^)]+\.md[^)]*\)", content))

    return {
        "lines": n_lines,
        "svg": n_svg,
        "tables": n_tables,
        "audit": n_audit,
        "kakomon": n_kakomon,
        "links": n_links,
    }


PROXY_WEIGHTS = {
    "lines": 0.20,
    "svg": 0.20,
    "tables": 0.10,
    "audit": 0.20,
    "kakomon": 0.15,
    "links": 0.15,
}


def normalize_to_100(values: list[float]) -> list[float]:
    """min-max正規化 → 0-100"""
    lo, hi = min(values), max(values)
    if hi == lo:
        return [50.0] * len(values)
    return [(v - lo) / (hi - lo) * 100 for v in values]


def compute_proxy_scores(features_list: list[dict]) -> list[float]:
    """各記事の features dict のリストから合成スコアを算出"""
    keys = list(PROXY_WEIGHTS.keys())
    normalized = {}
    for k in keys:
        raw = [f[k] for f in features_list]
        normalized[k] = normalize_to_100(raw)

    proxy = []
    for i in range(len(features_list)):
        s = sum(PROXY_WEIGHTS[k] * normalized[k][i] for k in keys)
        proxy.append(s)
    return proxy


# ---------------------------------------------------------------------------
# Spearman 相関（標準ライブラリ手計算）
# ---------------------------------------------------------------------------

def rank(values: list[float]) -> list[float]:
    """同順位を平均ランクで処理"""
    sorted_idx = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and values[sorted_idx[j + 1]] == values[sorted_idx[i]]:
            j += 1
        avg_rank = (i + j) / 2 + 1  # 1-indexed
        for k in range(i, j + 1):
            ranks[sorted_idx[k]] = avg_rank
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    """同順位対応 Spearman 相関係数"""
    n = len(xs)
    rx, ry = rank(xs), rank(ys)
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    num = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    den_x = sum((rx[i] - mean_rx) ** 2 for i in range(n)) ** 0.5
    den_y = sum((ry[i] - mean_ry) ** 2 for i in range(n)) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    md_files = sorted(DOCS_ARTICLES.rglob("*.md"))
    # index など非記事ファイル除外: kijun/kaishaku/jigyoho/furyoku/other 配下のみ
    valid = [
        p for p in md_files
        if p.parent.name in ("kijun", "kaishaku", "jigyoho", "furyoku", "other")
        and p.stem != "index"
    ]

    rows = []
    for p in valid:
        v3 = score_v3(p)
        if "error" in v3:
            continue
        features = compute_proxy_features(p)
        rows.append({
            "path": str(p.relative_to(ROOT)),
            "v3_score": v3["score"],
            "axis_scores": v3.get("axis_scores", {}),
            "features": features,
        })

    n = len(rows)
    print(f"# v3.1 採点軸 vs 擬似主観品質 Spearman相関検証")
    print(f"\n対象記事: {n}件\n")

    proxy_scores = compute_proxy_scores([r["features"] for r in rows])
    for i, r in enumerate(rows):
        r["proxy_score"] = proxy_scores[i]

    v3_arr = [r["v3_score"] for r in rows]
    rho_total = spearman(v3_arr, proxy_scores)

    def verdict(rho):
        if rho >= 0.5:
            return "✅ ≥0.5 採点軸は妥当"
        if rho >= 0.3:
            return "⚠️ 0.3-0.5 弱相関 配点見直し必要"
        return "❌ <0.3 採点軸破綻"

    print("## 全体相関")
    print(f"- Spearman ρ = {rho_total:.3f}  (n={n})")
    print(f"- 判定: {verdict(rho_total)}\n")

    # 軸別
    print("## 軸別相関")
    axis_rhos = {}
    for axis_name in V3_AXES.keys():
        axis_arr = [r["axis_scores"].get(axis_name, (0, 0))[0] for r in rows]
        rho = spearman(axis_arr, proxy_scores)
        axis_rhos[axis_name] = rho
        print(f"- {axis_name}軸 ρ = {rho:.3f}")
    most_div = min(axis_rhos.items(), key=lambda x: x[1])
    print(f"- 最も品質と乖離している軸: {most_div[0]} (ρ={most_div[1]:.3f})\n")

    # 外れ値分析: ランク差
    rx = rank(v3_arr)
    ry = rank(proxy_scores)
    diffs = []
    for i, r in enumerate(rows):
        d = rx[i] - ry[i]  # 正: v3が擬似より高評価
        diffs.append((d, r["path"], r["v3_score"], proxy_scores[i]))

    over = sorted(diffs, key=lambda x: -x[0])[:5]  # v3高・擬似低
    under = sorted(diffs, key=lambda x: x[0])[:5]  # v3低・擬似高

    print("## 過大評価TOP5（v3高・擬似低）")
    for d, p, v, q in over:
        print(f"- {p}  v3={v}  擬似={q:.1f}  ランク差=+{d:.0f}")

    print("\n## 過小評価TOP5（v3低・擬似高）")
    for d, p, v, q in under:
        print(f"- {p}  v3={v}  擬似={q:.1f}  ランク差={d:.0f}")

    # GO/NO-GO
    print("\n## 結論")
    go = "GO" if rho_total >= 0.5 else "NO-GO"
    print(f"Sprint 3 着手判定: **{go}**")
    if rho_total >= 0.5:
        print(f"理由: 全体ρ={rho_total:.3f}で必要条件 ≥0.5 を満たす。採点軸は擬似主観品質と相関。")
    elif rho_total >= 0.3:
        print(f"理由: 全体ρ={rho_total:.3f}で弱相関のみ。Sprint 3 前に最低相関軸 ({most_div[0]}) の配点見直し必須。")
    else:
        print(f"理由: 全体ρ={rho_total:.3f}で採点軸が品質と無相関。Sprint 3 前に項目選定からやり直し。")


if __name__ == "__main__":
    main()
