"""kaishaku/*.md の条番号↔条見出しを、内部整合 + 原典由来マスタとの外部照合で検査する。

## 検査の2層

1. **内部整合**（従来から）
   - ファイル名 (NN.md) と H1「電技解釈 第NN条 — タイトル」の条番号が一致するか
   - kaishaku/index.md の表記と H1 タイトルが一致するか（INDEX_DIFF = warning）

2. **外部照合**（2026-07-26 追加・`--external`）
   - H1 タイトル（末尾の補足「（…）」を除去したもの）が、原典由来の条見出しマスタ
     `_data/kaishaku_article_titles.json` と**逐語一致**するか
   - kaishaku/index.md の各行タイトルも同じマスタと照合する

## なぜ外部照合を足したか（前提が変わった）

本スクリプトは長らく「電技解釈は告示で e-Gov 法令API に載らないため**外部正本と照合
できない**。内部整合のみ検査する」という前提で書かれていた。その結果、**条番号と内容の
対応の誤りが CI 全緑のまま残存**し、2026-07-26 に連続して発覚した:

- PR #156: 「漏電遮断器＝解釈第37条」→ 正しくは**第36条**（第37条は避雷器等の施設）
- PR #157: 「第71条＝高圧架空電線の施設（電線規格）」→ 正しくは**建造物との接近**
- PR #158: 第133条として公開されていた内容が実は**第135条**だった（133.md → 135.md 改名）

前提が変わったのは、**経産省公表PDF（令和7年11月版）から機械抽出した条見出しマスタ**
（解釈233条）が入手できたため。e-Gov API は依然使えないが、原典PDF由来の正本があれば
逐語照合できる。マスタは CI から再生成できない（原典PDFはローカルのみ）ので
`_data/` にコピーで同梱する。更新手順はマスタの `_meta.regeneration` に記載。

省令側（articles/kijun/*.md）には本スクリプトを適用しない。省令は e-Gov 法令API
（lawid=409M50000400052）に登録済みで、`scripts/audit_titles.py` が一次情報を直接
照合しているため役割が重複する。PDF抽出版の省令76条を e-Gov 78条と突合したところ
5件の欠陥（第1条・第41条の欠落／第3条・第38条・第39条の誤抽出）も確認したので、
省令はマスタに同梱していない。

## ERROR / WARN の分離

一度に全件を赤にしないため、逐語不一致を2段階に分ける。

- **ERROR** … 主張タイトルが**他の条の見出しに強く一致**し、かつ当該条より明確に近い
  （= 条番号の誤帰属。上記3事案と同型の高確信エラー）
- **WARN**  … 単に乖離（短縮表記・改正前の旧見出し・補足付き等）。CI では落とさない

さらに、既知の未是正箇所は `KNOWN_DIVERGENCES` に登録して ERROR から除外する
（ratchet: 登録した文字列が1文字でも変わると allowlist を外れて再検出される。
また、もう発火しない登録は STALE_ALLOWLIST として報告し、リストが縮む方向にのみ動く）。

## 使い方

    python scripts/audit_kaishaku_titles.py              # 内部整合のみ（従来互換）
    python scripts/audit_kaishaku_titles.py --external   # 内部整合 + 外部照合
    python scripts/audit_kaishaku_titles.py --external --strict   # ERROR で exit 2（CI用）
    python scripts/audit_kaishaku_titles.py --external --all      # WARN も全部表示
    python scripts/audit_kaishaku_titles.py --self-test
"""
from __future__ import annotations

import io
import json
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
KAISHAKU = ROOT / "docs" / "articles" / "kaishaku"
INDEX_MD = KAISHAKU / "index.md"
MASTER_PATH = ROOT / "_data" / "kaishaku_article_titles.json"

# --- 類似度しきい値（check_theme_article_numbers.py / check_hoki_law_titles.py と同思想）
SIM_OK = 0.60      # これ以上なら「その条の見出しの言い換え」とみなす
SIM_MARGIN = 0.45  # ERROR に必要な「他条の方が近い」差

# ---------------------------------------------------------------------------
# 既知の未是正箇所（段階導入の allowlist / ratchet）
#
#   キー: ("h1" | "index", 条番号)
#   claimed: 現在書かれているタイトル。**1文字でも変わったら allowlist を外れて再検出**
#   reason : なぜ今 ERROR で落とさないか（是正予定なら punch list 側に残す）
#
# ここに載っているのは「正しい」という保証ではなく「既知・是正待ち」の意味。
# 是正したら登録を削除すること（削除し忘れは STALE_ALLOWLIST で検出される）。
# ---------------------------------------------------------------------------
# 2026-07-26 導入時点で ERROR 判定になった既存箇所は**すべて kaishaku/index.md の
# 「📝 作成予定」行**（記事本体は未作成で、表に置かれた仮タイトルが誤っている）。
# 記事本体（articles/kaishaku/*.md の H1）の ERROR は 0 件だった。
# → index.md の是正は本ゲート導入とは別 PR で行う（punch list は
#   .claude/docs/kaishaku-title-punchlist.md）。
KNOWN_DIVERGENCES: dict[tuple[str, int], dict[str, str]] = {
    ("index", 2): {
        "claimed": "その他の用語の定義",
        "reason": "作成予定行の仮タイトル。原典 第2条＝適用除外（用語の定義は第1条）",
    },
    ("index", 23): {
        "claimed": "発電所等への取扱者以外の者の立入の防止",
        "reason": "作成予定行の仮タイトル。原典 第23条＝アークを生じる器具の施設（立入の防止は第38条）",
    },
    ("index", 24): {
        "claimed": "さく・へいの施設",
        "reason": "作成予定行の仮タイトル。原典 第24条＝高圧又は特別高圧と低圧との混触による危険防止施設",
    },
    ("index", 25): {
        "claimed": "発電所等の電線及び移動電線の施設",
        "reason": "作成予定行の仮タイトル。原典 第25条＝特別高圧と高圧との混触等による危険防止施設",
    },
    ("index", 35): {
        "claimed": "高圧電路に施設する過電流遮断器の性能",
        "reason": "作成予定行の仮タイトル。原典 第35条＝過電流遮断器の施設の例外（高圧・特別高圧の性能は第34条）",
    },
    ("index", 42): {
        "claimed": "特別高圧用変圧器の施設",
        "reason": "作成予定行の仮タイトル。原典 第42条＝発電機の保護装置（特別高圧配電用変圧器の施設は第26条）",
    },
    ("index", 65): {
        "claimed": "架空電線の高さ",
        "reason": "作成予定行の仮タイトル。原典 第65条＝低高圧架空電線路に使用する電線（高さは第68条）。65.md は PR #157 で作成済みなのでステータス表記も要更新",
    },
    ("index", 67): {
        "claimed": "高圧架空電線の高さ",
        "reason": "作成予定行の仮タイトル。原典 第67条＝低高圧架空電線路の架空ケーブルによる施設（高さは第68条）",
    },
    ("index", 125): {
        "claimed": "地中箱の施設",
        "reason": "作成予定行の仮タイトル。原典 第125条＝地中電線と他の地中電線等との接近又は交差（地中箱の施設は第121条）",
    },
    # ("index", 149) は PR #160 で是正済み（STALE_ALLOWLIST が発火したので登録削除）
    ("index", 156): {
        "claimed": "合成樹脂管工事",
        "reason": "作成予定行の仮タイトル。原典 第156条＝低圧屋内配線の施設場所による工事の種類（合成樹脂管工事は第158条）",
    },
    ("index", 157): {
        "claimed": "金属可とう電線管工事",
        "reason": "作成予定行の仮タイトル。原典 第157条＝がいし引き工事（金属可とう電線管工事は第160条）",
    },
    ("index", 96): {
        "claimed": "架空電線と架空弱電流電線等との共架",
        "reason": "作成予定行の仮タイトル。原典 第96条＝特別高圧架空電線が建造物等と接近又は交差する場合の支線の施設（共架は第81条）",
    },
    ("index", 172): {
        "claimed": "バスダクト工事",
        "reason": "作成予定行の仮タイトル。原典 第172条＝特殊な配線等の施設（バスダクト工事は第163条）",
    },
    ("index", 182): {
        "claimed": "臨時配線の施設",
        "reason": "作成予定行の仮タイトル。原典 第182条＝出退表示灯回路の施設（臨時配線は第180条）",
    },
}


# ---------------------------------------------------------------------------
# パース
# ---------------------------------------------------------------------------
# H1 は YAML フロントマター（--- ... ---）の後に来ることがあるため、先頭行だけを
# 見ると frontmatter 付きファイルが一律 NO_H1 になり検査対象から落ちる（PR #160 修正）。
# frontmatter を除去したうえで**最初の `# ` 見出し行**だけを見る。
# 本文全体を正規表現で走査する実装にはしない — コードブロック内や解説中に現れる
# 「# 電技解釈 第N条 — …」を H1 と誤認しうるため。H1 はページに1つが規約。
def strip_front_matter(text: str) -> str:
    """先頭の YAML front matter を除去する（無ければそのまま返す）"""
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---\n", 3)
    return text if end == -1 else text[end + len("\n---\n"):]


def parse_h1_text(text: str) -> tuple[int | None, str | None]:
    body = strip_front_matter(text)
    first_line = next((ln for ln in body.split("\n") if ln.startswith("# ")), "")
    m = re.match(r"^#\s*電技解釈\s*第(\d+)条\s*[—\-‐–]\s*(.+?)\s*$", first_line)
    if not m:
        return None, None
    return int(m.group(1)), m.group(2).strip()


def parse_h1(path: Path) -> tuple[int | None, str | None]:
    return parse_h1_text(path.read_text(encoding="utf-8"))


def parse_index_titles(text: str | None = None) -> dict[int, str]:
    """kaishaku/index.md の表から 条番号→タイトル のマップを抽出"""
    if text is None:
        if not INDEX_MD.exists():
            return {}
        text = INDEX_MD.read_text(encoding="utf-8")
    titles: dict[int, str] = {}
    # | 第NN条 | [タイトル](NN.md) | ... |  または  | 第NN条 | タイトル | ...
    for m in re.finditer(r"\|\s*第(\d+)条\s*\|\s*(?:\[([^\]]+)\]\([^)]+\)|([^|]+?))\s*\|", text):
        n = int(m.group(1))
        t = (m.group(2) or m.group(3) or "").strip()
        titles[n] = t
    return titles


# ---------------------------------------------------------------------------
# 外部照合
# ---------------------------------------------------------------------------
# 末尾の補足括弧を落とす。
#   「電路の対地電圧の制限（住宅の屋内電路 150V）」→「電路の対地電圧の制限」
# 見出しの**途中**にある括弧は原典見出しの一部でありうるので触らない。
TRAILING_PAREN = re.compile(r"(?:[（(][^（()）]*[）)])+\s*$")


def strip_supplement(title: str) -> str:
    """末尾の補足「（…）」を除去（連続していれば全部）。"""
    prev = None
    s = title.strip()
    while prev != s:
        prev = s
        s = TRAILING_PAREN.sub("", s).strip()
        if not s:  # 括弧だけのタイトルは元に戻す（除去しすぎない）
            return title.strip()
    return s


def norm_exact(s: str) -> str:
    """逐語一致の判定用。空白のみ吸収し、字句は変えない。"""
    return re.sub(r"[\s　]", "", s)


def norm_fuzzy(s: str) -> str:
    """類似度計算用の正規化（記号・定型語尾を落とす）。"""
    s = re.sub(r"[\s　、，,・（）()「」【】]", "", s)
    return s.replace("等", "").replace("の防止", "").replace("防止", "")


def sim(a: str, b: str) -> float:
    """0..1 の類似度。包含は 1.0 にせず長さ比で減点する。

    「電路の絶縁」は「電路の絶縁性能」の部分文字列だが別概念（絶縁の原則 vs 絶縁性能）で、
    1.0 にすると第13条↔第14条のような隣接条を誤って同一視する。
    """
    na, nb = norm_fuzzy(a), norm_fuzzy(b)
    if not na or not nb:
        return 0.0
    if na in nb or nb in na:
        return 0.6 + 0.4 * (min(len(na), len(nb)) / max(len(na), len(nb)))
    return SequenceMatcher(None, na, nb).ratio()


def load_master(path: Path | None = None) -> dict[int, str]:
    p = path or MASTER_PATH
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    table = data.get("解釈", {})
    return {int(k): v for k, v in table.items()}


def classify(kind: str, num: int, claimed: str, master: dict[int, str]) -> tuple[str, str] | None:
    """(status, detail) を返す。一致していれば None。

    status: "ERROR"（他条の見出しに強く一致＝誤帰属） / "WARN"（単なる乖離）
            / "MASTER_MISSING"（マスタに当該条が無い＝判定不能）
    """
    truth = master.get(num)
    if truth is None:
        return ("MASTER_MISSING", f"第{num}条 はマスタに無い（判定不能・fail-open）: 「{claimed}」")

    base = strip_supplement(claimed)
    if norm_exact(base) == norm_exact(truth):
        return None

    truth_s = sim(base, truth)
    best_n, best_s = None, 0.0
    for n2, t2 in master.items():
        if n2 == num:
            continue
        s2 = sim(base, t2)
        if s2 > best_s:
            best_n, best_s = n2, s2

    if best_n is not None and best_s >= SIM_OK and (best_s - truth_s) >= SIM_MARGIN:
        return (
            "ERROR",
            f"第{num}条「{base}」… 原典は「{truth}」"
            f" → **第{best_n}条**（{master[best_n]}）では？",
        )
    return ("WARN", f"第{num}条「{base}」… 原典は「{truth}」（短縮表記・改正前見出し等なら問題なし）")


def external_scan(master: dict[int, str]) -> tuple[list[tuple[str, str, str]], set[tuple[str, int]]]:
    """外部照合。(results, fired_allowlist_keys) を返す。"""
    results: list[tuple[str, str, str]] = []
    fired: set[tuple[str, int]] = set()

    def handle(kind: str, num: int, claimed: str, where: str) -> None:
        verdict = classify(kind, num, claimed, master)
        if verdict is None:
            return
        status, detail = verdict
        allow = KNOWN_DIVERGENCES.get((kind, num))
        if allow is not None and allow["claimed"].strip() == claimed.strip():
            fired.add((kind, num))
            if status == "ERROR":
                results.append(("ALLOWLISTED", where, f"{detail}  ※既知: {allow['reason']}"))
                return
        results.append((status, where, detail))

    for md in sorted(KAISHAKU.glob("*.md"), key=lambda p: p.name):
        if md.name == "index.md" or not md.stem.isdigit():
            continue
        h1_n, h1_title = parse_h1(md)
        if h1_n is None or h1_n != int(md.stem):
            continue  # 内部整合検査（NO_H1 / MISMATCH_FILE）の担当
        handle("h1", h1_n, h1_title, md.name)

    for num, title in sorted(parse_index_titles().items()):
        if not title:
            continue
        handle("index", num, title, "index.md")

    return results, fired


# ---------------------------------------------------------------------------
# 内部整合（従来）
# ---------------------------------------------------------------------------
def internal_scan() -> list[tuple[str, str, str]]:
    results: list[tuple[str, str, str]] = []
    index_titles = parse_index_titles()

    for md in sorted(KAISHAKU.glob("*.md"), key=lambda p: p.name):
        if md.name == "index.md":
            continue
        try:
            file_n = int(md.stem)
        except ValueError:
            continue
        h1_n, h1_title = parse_h1(md)
        if h1_n is None:
            results.append(("NO_H1", md.name, "H1 が解釈タイトル形式でない"))
            continue
        if file_n != h1_n:
            results.append((
                "MISMATCH_FILE",
                md.name,
                f"ファイル名=第{file_n}条 / H1=第{h1_n}条 ({h1_title})",
            ))
            continue
        idx_title = index_titles.get(file_n)
        if idx_title and idx_title != h1_title:
            # 軽微: index は短縮表記の場合がある → warning のみ
            results.append((
                "INDEX_DIFF",
                md.name,
                f"H1='{h1_title}' / index='{idx_title}'",
            ))
        else:
            results.append(("OK", md.name, f"第{file_n}条 {h1_title}"))

    return results


# ---------------------------------------------------------------------------
# self-test
# ---------------------------------------------------------------------------
def self_test() -> int:
    cases: list[tuple[str, bool]] = []

    master = {
        13: "電路の絶縁",
        14: "低圧電路の絶縁性能",
        36: "地絡遮断装置の施設",
        37: "避雷器等の施設",
        53: "架空電線路の支持物の昇塔防止",
        65: "低高圧架空電線路に使用する電線",
        71: "低高圧架空電線と建造物との接近",
        133: "臨時電線路の施設",
        135: "電力保安通信用電話設備の施設",
        143: "電路の対地電圧の制限",
        226: "低圧連系時の施設要件",
    }

    def c(kind: str, num: int, claimed: str):
        return classify(kind, num, claimed, master)

    # --- 逐語一致 ---
    cases.append(("逐語一致はPASS", c("h1", 226, "低圧連系時の施設要件") is None))
    cases.append((
        "末尾の補足（…）を strip して一致（第143条の実例）",
        c("h1", 143, "電路の対地電圧の制限（住宅の屋内電路 150V）") is None,
    ))
    cases.append((
        "連続する末尾補足も strip",
        c("h1", 226, "低圧連系時の施設要件（第1項）（要点）") is None,
    ))
    cases.append(("全角空白差は吸収", c("h1", 226, "低圧　連系時の施設要件") is None))

    # --- 実事案の再現（退行テスト）---
    r = c("h1", 37, "地絡遮断装置の施設")
    cases.append(("PR#156 型（ELB を第37条と誤帰属）を ERROR 検出",
                  r is not None and r[0] == "ERROR" and "第36条" in r[1]))
    r = c("h1", 71, "低高圧架空電線路に使用する電線")
    cases.append(("PR#157 型（第71条に第65条の内容）を ERROR 検出",
                  r is not None and r[0] == "ERROR" and "第65条" in r[1]))
    r = c("h1", 133, "電力保安通信用電話設備の施設")
    cases.append(("PR#158 型（第133条に第135条の内容）を ERROR 検出",
                  r is not None and r[0] == "ERROR" and "第135条" in r[1]))

    # --- 偽陽性の退行テスト（実データで踏んだもの）---
    r = c("h1", 53, "架空電線路の支持物に取扱者が昇降に使用する足場金具等の施設")
    cases.append(("改正前の旧見出し（第53条）は WARN 止まり（他条ではないため）",
                  r is not None and r[0] == "WARN"))
    r = c("h1", 14, "低圧電路の絶縁抵抗")
    cases.append(("包含による誤ERRORを出さない（第14条 vs 第13条）",
                  r is not None and r[0] == "WARN"))
    r = c("h1", 143, "住宅の屋内電路の対地電圧の制限")
    cases.append(("短縮/言い換えは WARN 止まり", r is not None and r[0] == "WARN"))

    # --- fail-open ---
    r = c("h1", 100, "何らかの見出し")
    cases.append(("マスタに無い条は MASTER_MISSING（fail-open）",
                  r is not None and r[0] == "MASTER_MISSING"))

    # --- H1 パーサ（frontmatter 対応の退行テスト）---
    fm = "---\ntitle: x\ntags:\n  - y\n---\n\n# 電技解釈 第17条 — 接地工事の種類及び施設方法\n\n本文\n"
    cases.append(("frontmatter 付きでも H1 を拾う", parse_h1_text(fm) == (17, "接地工事の種類及び施設方法")))
    cases.append(("H1 無しは None", parse_h1_text("---\ntitle: x\n---\n\n## 見出し\n")[0] is None))
    cases.append((
        "H2 は H1 として拾わない",
        parse_h1_text("## 電技解釈 第17条 — 接地工事の種類及び施設方法\n")[0] is None,
    ))
    cases.append((
        "全角ダッシュ以外（半角ハイフン）も許容",
        parse_h1_text("# 電技解釈 第65条 - 低高圧架空電線路に使用する電線\n")
        == (65, "低高圧架空電線路に使用する電線"),
    ))

    # --- index パーサ ---
    idx = (
        "| 条文 | タイトル | 頻出テーマ | ステータス |\n"
        "|------|---------|-----------|-----------|\n"
        "| 第226条 | [低圧連系時の施設要件](226.md) | — | 📄 作成済み |\n"
        "| 第135条 | 電力保安通信用電話設備の施設 | — | 📝 作成予定 |\n"
    )
    cases.append(("index のリンク付き/なし両方を抽出",
                  parse_index_titles(idx) == {226: "低圧連系時の施設要件",
                                              135: "電力保安通信用電話設備の施設"}))

    # --- strip_supplement の境界 ---
    cases.append(("括弧だけのタイトルは strip しすぎない",
                  strip_supplement("（注記）") == "（注記）"))
    cases.append(("見出し途中の括弧は残す",
                  strip_supplement("35,000V（特高）を超える電線と建造物") ==
                  "35,000V（特高）を超える電線と建造物"))

    # --- allowlist の ratchet ---
    for (kind, num), entry in KNOWN_DIVERGENCES.items():
        cases.append((f"allowlist 登録 ({kind},{num}) に claimed/reason がある",
                      bool(entry.get("claimed")) and bool(entry.get("reason"))))

    ok = True
    for name, passed in cases:
        print(("  PASS " if passed else "  FAIL ") + name)
        ok = ok and passed
    print("self-test:", "ALL PASS" if ok else "FAILED")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    if "--self-test" in argv:
        return self_test()

    external = "--external" in argv
    strict = "--strict" in argv
    show_all = "--all" in argv

    results = internal_scan()
    ok = [r for r in results if r[0] == "OK"]
    issues = [r for r in results if r[0] != "OK"]

    for r in ok:
        print(f"  [OK] {r[1]} - {r[2]}")
    if issues:
        print()
        print("=== 内部整合の異常 ===")
        for r in issues:
            print(f"  [{r[0]}] {r[1]} - {r[2]}")
    print()
    print(f"内部整合 Total: {len(results)} / OK: {len(ok)} / 異常: {len(issues)}")

    serious = [r for r in issues if r[0] in ("MISMATCH_FILE", "NO_H1")]
    rc = 0 if not serious else 2

    if not external:
        return rc

    master = load_master()
    print()
    if not master:
        # マスタ欠損は **fail-closed**。fail-open にすると「マスタを消せば CI が緑」
        # という抜け道になり、本ゲートを入れた意味が消える
        # （個々の条がマスタに無い場合だけ MASTER_MISSING で fail-open する）。
        print(f"[ERROR] 外部照合: マスタが読めない（{MASTER_PATH}）")
        print("        _data/kaishaku_article_titles.json を復元すること。"
              "更新手順は同ファイルの _meta.regeneration を参照。")
        return 2 if strict else (rc or 0)

    ext, fired = external_scan(master)
    errors = [r for r in ext if r[0] == "ERROR"]
    warns = [r for r in ext if r[0] == "WARN"]
    allowed = [r for r in ext if r[0] == "ALLOWLISTED"]
    missing = [r for r in ext if r[0] == "MASTER_MISSING"]
    stale = sorted(k for k in KNOWN_DIVERGENCES if k not in fired)

    print(f"=== 外部照合（原典マスタ 解釈{len(master)}条 / {MASTER_PATH.name}）===")
    if errors:
        print(f"NG ERROR {len(errors)} 件（条番号↔条見出しの誤帰属の疑い）")
        for r in errors:
            print(f"  [ERROR] {r[1]} - {r[2]}")
    else:
        print("OK ERROR 0 件")
    if allowed:
        print(f"  （ALLOWLISTED {len(allowed)} 件 — 既知・是正待ち。--all で表示）")
        if show_all:
            for r in allowed:
                print(f"  [ALLOWLISTED] {r[1]} - {r[2]}")
    if warns:
        print(f"  （WARN {len(warns)} 件 — 短縮表記・改正前見出しなら問題なし。--all で表示）")
        if show_all:
            for r in warns:
                print(f"  [WARN] {r[1]} - {r[2]}")
    if missing:
        print(f"  （MASTER_MISSING {len(missing)} 件 — マスタ側の欠落で判定不能。--all で表示）")
        if show_all:
            for r in missing:
                print(f"  [MASTER_MISSING] {r[1]} - {r[2]}")
    if stale:
        print(f"NG STALE_ALLOWLIST {len(stale)} 件（是正済み or 記述変更 → KNOWN_DIVERGENCES から削除すること）")
        for k in stale:
            print(f"  [STALE_ALLOWLIST] {k[0]}:第{k[1]}条 - 登録内容「{KNOWN_DIVERGENCES[k]['claimed']}」が現れない")

    if strict and (errors or stale):
        rc = rc or 2
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
