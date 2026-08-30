#!/usr/bin/env python3
"""一次照合済みの事実を repo 全体で固定するゲート (check_verified_facts.py)

レジストリ: `_data/verified-facts.yml`

既存ゲートとの棲み分け:
  - audit_*_titles.py       … 条番号 ↔ 条見出し
  - check_law_verbatim.py   … 「条文原文」ブロックの逐語
  - check_law_facts.py      … 特定の数値ハルシネーション3類型（固定実装）
  - 本スクリプト            … **解説・要約・暗記表・SVG・mermaid に書かれた数値と判定軸**

条文原文が正しくても、その下の解説表が別の値を書いていれば学習者はそちらを覚える。
2026-08-28 の全数監査で是正した誤りの多くはこの層にあり、既存ゲートは1件も
検出していなかった（B種接地の 50/Ig・支持物の安全率1.5・第131条の罰則・
径間60/120m・低圧耐圧1分間・「発生から24時間」など）。

2種類のルール:
  forbid      正規表現が現れたら ERROR。**一次照合の結果「存在しない」と確定した表記**を
              二度と書けなくする ratchet。
  consistent  名前付きグループ `value` を持つ正規表現で値を抜き出し、
              `expect` と異なるものを ERROR。同じ事実がページ間でズレるのを止める。

除外:
  - `allow_files` … その表記を**誤りとして説明する**ページ（ひっかけ集など）を明示的に通す
  - 各ページの「監修ログ／変更履歴」節は対象外（過去の誤りを記録する場所のため）

Usage:
    python scripts/check_verified_facts.py                 # docs/ 全体
    python scripts/check_verified_facts.py docs/articles/kijun/11.md
    python scripts/check_verified_facts.py --self-test
    python scripts/check_verified_facts.py --list

Exit codes:
    0  findings 0件
    1  findings 1件以上
    2  レジストリが無い／壊れている
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("ERROR: PyYAML が必要です (pip install pyyaml)", file=sys.stderr)
    sys.exit(2)

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "_data" / "verified-facts.yml"
DEFAULT_TARGET = ROOT / "docs"

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 監修ログ・変更履歴は「かつてこう書いていた」を残す場所なので検査しない。
# ここを検査すると、是正した事実を記録することが不可能になる。
HISTORY_HEAD = re.compile(r"^#{1,6}\s*(?:📜\s*)?(?:監修ログ|変更履歴|改訂履歴)")
# 打ち消し線（~~誤り~~）も「誤りとして提示している」ので対象外
STRIKE = re.compile(r"~~[^~]*~~")

# 5択・4択の**選択肢行**は「誤りを含むのが仕様」なので対象外。
# ここを検査すると「次のうち正しいものはどれか」の誤答選択肢が全部 ERROR になる。
# 解答・解説（??? success 配下の本文）は選択肢行の形をしていないので検査は続く。
CHOICE_LINE = re.compile(r"^\s*(?:[A-Da-dア-オ][.．)）]|[(（][1-5１-５][)）]|[①-⑤])\s")


# Markdown の強調記法。**この Wiki は重要な数値ほど `==` や `**` で囲む**ため、
# 装飾を残したまま照合すると「事故発生から==24時間以内==」のような書き方を
# 一切検出できない（実測: 監査前コミットの jigyoho/106.md を素通りした）。
EMPHASIS = re.compile(r"==|\*\*|`")


def normalize(line: str) -> str:
    """全角英数・全角記号を畳み、Markdown の強調記法を落として比較用に揃える."""
    return EMPHASIS.sub("", unicodedata.normalize("NFKC", line))


def scannable_lines(path: Path) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    in_history = False
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if re.match(r"^#{1,6}\s", raw):
            in_history = bool(HISTORY_HEAD.match(raw))
        if in_history:
            continue
        if CHOICE_LINE.match(raw.strip()):
            continue
        out.append((i, STRIKE.sub("", normalize(raw))))
    return out


class Finding:
    def __init__(self, fact_id: str, rel: str, line: int, kind: str, hit: str, why: str):
        self.fact_id, self.rel, self.line = fact_id, rel, line
        self.kind, self.hit, self.why = kind, hit, why

    def render(self) -> str:
        return (
            f"[{self.kind}] {self.rel}:{self.line} ({self.fact_id})\n"
            f"        検出: {self.hit}\n"
            f"        理由: {self.why}"
        )


def load_registry() -> list[dict]:
    if not REGISTRY.exists():
        raise SystemExit(f"ERROR: レジストリがありません: {REGISTRY}")
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8")) or {}
    facts = data.get("facts") or []
    if not facts:
        raise SystemExit("ERROR: レジストリに facts が1件もありません（vacuous pass 防止）")
    for f in facts:
        for key in ("id", "label", "source", "verified"):
            if not f.get(key):
                raise SystemExit(f"ERROR: fact に {key} がありません: {f.get('id', f)}")
        if not f.get("forbid") and not f.get("consistent"):
            raise SystemExit(f"ERROR: fact {f['id']} に forbid も consistent もありません")
    return facts


# unless で抑制した箇所（件数をサマリに出して「見えない除外」にしない）
SUPPRESSED: list[tuple[str, str, int]] = []


def check(paths: list[Path], facts: list[dict]) -> list[Finding]:
    findings: list[Finding] = []
    compiled = []
    for f in facts:
        allow = set(f.get("allow_files") or [])
        forbids = [(re.compile(r["pattern"]), r["why"]) for r in (f.get("forbid") or [])]
        cons = f.get("consistent")
        cons_re = re.compile(cons["pattern"]) if cons else None
        # 同じ行に現れたら抑制する正規表現（「その値は誤り」と説明している行・
        # 別条の同じ数値 等）。ルールごとにレジストリで明示する（隠れた大域規則にしない）。
        unless = [re.compile(u) for u in (f.get("unless") or [])]
        # 行がこれら全てに一致するときだけルールを適用する（対象の絞り込み）。
        # 例: 「立入検査の拒否 → 100万円」は電気事業法の話なので、
        # 同名の見出しを持つ電気用品安全法の表に誤爆しないよう `第107条` を要求する。
        require = [re.compile(r) for r in (f.get("require") or [])]
        compiled.append((f, allow, forbids, cons_re, cons, unless, require))

    for path in paths:
        rel = path.relative_to(ROOT).as_posix()
        lines = scannable_lines(path)
        for f, allow, forbids, cons_re, cons, unless, require in compiled:
            if rel in allow:
                continue
            for line, text in lines:
                if require and not all(r.search(text) for r in require):
                    continue
                # unless は「ルールが当たった行」にだけ適用する。
                # 先に評価すると、`ではない` 等を含むだけの行が丸ごと検査対象外になり、
                # 抑制件数も実態を表さない（実測で 10,235 行が"抑制"扱いになった）。
                def _suppressed() -> bool:
                    if any(u.search(text) for u in unless):
                        SUPPRESSED.append((f["id"], rel, line))
                        return True
                    return False

                for rx, why in forbids:
                    m = rx.search(text)
                    if m:
                        if _suppressed():
                            break
                        findings.append(
                            Finding(f["id"], rel, line, "FORBID", m.group(0), why)
                        )
                if cons_re:
                    for m in cons_re.finditer(text):
                        got = normalize(m.group("value")).replace(",", "")
                        want = normalize(cons["expect"]).replace(",", "")
                        if got != want:
                            if _suppressed():
                                break
                            findings.append(
                                Finding(
                                    f["id"],
                                    rel,
                                    line,
                                    "DIFFER",
                                    f"{m.group(0)}（値 {m.group('value')}）",
                                    f"一次照合済みの値は {cons['expect']}（{f['source']}）",
                                )
                            )
    return findings


def collect(paths: list[str]) -> list[Path]:
    if not paths:
        return sorted(DEFAULT_TARGET.rglob("*.md"))
    out: list[Path] = []
    for p in paths:
        q = Path(p)
        if not q.is_absolute():
            q = ROOT / p
        if q.is_dir():
            out.extend(sorted(q.rglob("*.md")))
        elif q.exists():
            out.append(q)
    return out


def self_test(facts: list[dict]) -> int:
    """全ルールが「壊れた入力」で実際に fire することを毎回証明する.

    レジストリのルールは正規表現なので、リファクタで silently マッチしなくなっても
    「0件」で緑になる。ルールごとに陽性サンプルを持たせ、fire しないルールを落とす。
    ここで落ちたルールは、その事故を検出できないただの飾り。
    """
    samples: dict[str, list[str]] = {
        "b-shu-coefficient": [
            "遮断時間 0.5秒以内なら **50/Ig** まで厳格化される。",
            "B種接地は 0.5秒以内で区分が変わる。",
        ],
        "penalty-118": ["主任技術者を選任しなかった場合は第118条により100万円以下の罰金。"],
        "penalty-120": ["保安規程の届出を怠ると第120条の300万円以下の罰金。"],
        "nonexistent-article-131": ["命令違反は電気事業法第131条の罰則が適用される。"],
        "article-43-paragraphs": ["第43条第6項で大臣が解任を命じることができる。"],
        "article-47-no-days": ["工事計画の認可は第47条により着工の90日前までに申請する。"],
        "wooden-pole-safety-factor": ["支持物の安全率は1.5以上が試験の核心数値。"],
        "span-63": ["第63条の径間は木柱60m、B種120mが上限である。"],
        "lv-withstand-10min": [
            "低圧器具（300V以下）：対地間試験 ==500V（交流、1分間）==、絶縁抵抗 ≥ ==0.1MΩ==",
            "対地間試験電圧は500V固定である。",
        ],
        "sokuho-start-point": ["速報は事故の発生から24時間以内に行う。"],
        "article-40-minister": ["第40条は経済産業大臣が修理・改造を命令できる規定。"],
        "exam-full-score": ["法規は13問・60点満点で採点される。"],
        "penalty-shunin-unassigned": ["| 主任技術者の未選任 | **100万円以下の罰金** | 第43条・第117条 |"],
        "penalty-inspection-refusal": ["| 立入検査の拒否・妨害 | **30万円以下の罰金** | 第107条・第119条 |"],
        "table-156-1-floorduct": ["フロアダクト工事は点検できる隠ぺい場所で使用できる。"],
        "table-149-3-plug": ["20A未満の差込みプラグが接続できないものを除く。"],
        "table-68-1-footbridge": ["横断歩道橋の上に施設する低圧架空電線の高さは4mである。"],
        "table-29-1-voltage-axis": ["接地種別は対地電圧300V以下ならD種、超過ならC種で判定する。"],
        "kaishaku-37-is-hiraiki": ["解釈第33条（過電流遮断器）／第36条（地絡遮断装置）／第37条（漏電遮断器・30mA・0.1秒）"],
        "cd-shu-500ohm-is-17": ["解釈第36条（地絡遮断装置の施設＝漏電遮断器・C/D種500Ω緩和の根拠）"],
        "kaishaku-14-no-100v": ["公式基準：対地電圧100Vにおいて漏れ電流1mA以下（解釈第14条第1項第二号）"],
        "koji-keikaku-30days-is-48": ["| 認可申請→工事開始まで 30 日以上 | 電気事業法 第47条（工事計画の認可） |"],
        "jigyoho-43-no-shonin": ["| 第43条 | 主任技術者の兼任 | 承認 | 兼任前に申請 |"],
        "shiken-denatsu-uses-saidai-shiyo": ["（例：6.6kV → 交流9,900V → 直流19,800V）"],
        "elb-30ma-not-in-genten": ["| 漏電遮断器（ELB） | 零相変流器で地絡電流検出・30mA以下で動作 | 省令第59条 |"],
        "chichuu-125-1-tsushinsen": [
            "| 特別高圧地中電線 ↔ 地中弱電流電線等（電力保安通信線を除く） | ==0.6m== |",
        ],
    }
    ok = True
    for f in facts:
        fid = f["id"]
        cases = samples.get(fid)
        if not cases:
            print(f"  [FAIL] {fid}: self-test の陽性サンプルがありません")
            ok = False
            continue
        forbids = [(re.compile(r["pattern"]), r["why"]) for r in (f.get("forbid") or [])]
        cons = f.get("consistent")
        cons_re = re.compile(cons["pattern"]) if cons else None
        unless = [re.compile(u) for u in (f.get("unless") or [])]
        require = [re.compile(r) for r in (f.get("require") or [])]
        for text in cases:
            t = normalize(text)
            if require and not all(r.search(t) for r in require):
                print(f"  [FAIL] {fid}: 陽性サンプルが require を満たさない: {text[:40]}")
                ok = False
                continue
            if any(u.search(t) for u in unless):
                print(f"  [FAIL] {fid}: 陽性サンプルが unless で抑制された: {text[:40]}")
                ok = False
                continue
            fired = any(rx.search(t) for rx, _ in forbids)
            if not fired and cons_re:
                for m in cons_re.finditer(t):
                    if normalize(m.group("value")).replace(",", "") != normalize(
                        cons["expect"]
                    ).replace(",", ""):
                        fired = True
            print(f"  [{'PASS' if fired else 'FAIL'}] {fid}: {text[:44]}")
            ok &= fired

    # 陰性対照: 正しい記述で fire しないこと（誤爆で規約が使えなくなるのを防ぐ）
    negatives = [
        "17-1表は 150/Ig（下記以外）・300/Ig（1秒超2秒以下）・600/Ig（1秒以下）。",
        "主任技術者の未選任は第118条第7号により300万円以下の罰金。",
        "保安規程の届出違反は第120条により30万円以下の罰金。",
        "木柱の安全率は2.0以上（解釈第59条）。",
        "低圧電路は最大使用電圧の1.5倍（500V未満なら500V）を連続して10分間加える。",
        "| 主任技術者の未選任 | **300万円以下の罰金** | 第43条第1項 → **第118条第7号** |",
        "| 立入検査（第107条第1項）の拒否・妨害・忌避 | **1年以下の拘禁刑 又は 100万円以下の罰金**（併科あり） | **第117条の2 第12号** |",
        "速報は事故の発生を知った時から24時間以内。",
        "第40条の命令権者は主務大臣である。",
        "法規は100点満点・合格ライン60点。",
        "フロアダクト工事が○なのは点検できない隠ぺい場所・乾燥・300V以下のみ。",
        "コンセントは20A未満の差込みプラグが接続できるものを除く。",
        "横断歩道橋の上に施設する低圧架空電線の高さは3m以上（68-1表）。",
        "接地種別は機械器具の使用電圧300V以下ならD種、300V超ならC種。",
        "| 特別高圧地中電線 ↔ 地中弱電流電線等 | ==0.6m== |",
        # 第81条（架空電線の共架）には原典どおりのただし書があり、この記述は正しい。
        # require: ['地中'] で除外されることの回帰ガード（初版はここで7件誤爆した）。
        "| 電力保安通信線も本条対象 | 電力保安通信線は適用除外 | 本文ただし書 |",
        # 是正後の正しい記述（回帰ガード）
        "解釈第36条（地絡遮断装置の施設＝漏電遮断器）・第17条（接地工事の種類及び施設方法＝C種/D種の500Ω緩和はこちら。第3項・第4項）",
        "公称6.6kV の最大使用電圧は6,900V（6,600×1.15/1.1）→ 交流10,350V → 直流20,700V",
        # ひっかけ表が「届出なのに認可/許可/承認と混同しやすい」と正しく警告している行。
        # jigyoho-43 のパターンから「承認」単独を外し「兼任」必須にしたので、unless に頼らず
        # パターン段階で外れる（陰性対照ループは require は見るが unless は見ない）。
        "| ① 自社選任 | 経済産業大臣 | 届出（事後・遅滞なく）| 電気事業法 第43条第3項 | 「認可」「許可」「承認」と混同 |",
        # C種/D種の判別軸を正しく示している行（|跨ぎを全ルールに適用して誤爆させた事案の回帰ガード）
        "| 🔴 致命的 | C種・D種の判別を「対地電圧」で行う | 使用電圧 で判別（300V以下→D種／300V超→C種）。三相400V機器は C種 |",
    ]
    for text in negatives:
        t = normalize(text)
        hits = []
        for f in facts:
            for r in f.get("forbid") or []:
                if re.search(r["pattern"], t):
                    hits.append(f["id"])
            cons = f.get("consistent")
            if cons:
                for m in re.finditer(cons["pattern"], t):
                    if normalize(m.group("value")).replace(",", "") != normalize(
                        cons["expect"]
                    ).replace(",", ""):
                        hits.append(f["id"])
        hits = [
            h for h in hits
            if all(re.search(r, t) for r in (
                next(f for f in facts if f["id"] == h).get("require") or []
            ))
        ]
        print(f"  [{'PASS' if not hits else 'FAIL'}] 陰性対照: {text[:44]}"
              + (f" → 誤爆 {hits}" if hits else ""))
        ok &= not hits

    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--self-test", action="store_true", help="全ルールの発火＋陰性対照")
    ap.add_argument("--list", action="store_true", help="レジストリの一覧を表示")
    ap.add_argument(
        "--show-suppressed", action="store_true",
        help="unless で抑制した行を列挙（除外が効きすぎていないかの点検用）",
    )
    args = ap.parse_args()

    facts = load_registry()

    if args.list:
        for f in facts:
            kinds = []
            if f.get("forbid"):
                kinds.append(f"forbid×{len(f['forbid'])}")
            if f.get("consistent"):
                kinds.append("consistent")
            print(f"{f['id']:<28} {'/'.join(kinds):<14} {f['label']}")
            print(f"{'':28} 典拠: {f['source']}（照合 {f['verified']}）")
        return 0

    if args.self_test:
        return self_test(facts)

    targets = collect(args.paths)
    findings = check(targets, facts)
    for f in findings:
        print(f.render())
    print(
        f"\ncheck_verified_facts: {len(findings)}件"
        f" — {len(targets)}ファイル・{len(facts)}事実を照合"
        + (f"・unless で抑制 {len(SUPPRESSED)}行" if SUPPRESSED else "")
    )
    if args.show_suppressed:
        for fid, rel, line in SUPPRESSED:
            print(f"  suppressed {rel}:{line} ({fid})")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
