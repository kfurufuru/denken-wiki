#!/usr/bin/env python3
"""条文原文の「引用漏れ」と本文の「号数主張」を、原典の**構造**と突合する.

`check_law_verbatim.py` は「引用した文が原典と一致するか」しか見ない。
引用した文が全部正しくても、**引用しなかった項・号**は誰も見ていなかった。

制定事案（2026-09-01〜02・PR #184 13〜15章）: 逐語ゲート 0件のまま

  kaishaku/117  第五号が丸ごと欠落
  kaishaku/150  第2項（非包装ヒューズ）が丸ごと欠落 → 本文 7 箇所が「4つの号」と
                条全体を第1項だけで語っていた
  kaishaku/227  第三号ロ・第四号イ〜ホ・第2項が欠落
  kaishaku/229  第三号ロ・第四号（母線連絡用遮断器を含む）が欠落
  kaishaku/149  本文が「3つの号」と書いていたが第1項は四号構成
  kaishaku/22   （反証監査で発覚）三号で切れて七号＋第2項が欠落。本文 11 箇所が
                「3号」「箱規定なし」と断定し、正しい選択肢を誤りと判定させていた

2つの検査を持つ。

  OMIT   原典にある 項（第2項以降）・号 のうち、ページの条文原文が持たないもの
  CLAIM  本文の「Nつの号」「N号構成」等の件数主張が、第1項の号数と一致しないもの

射程の限界（広げない。誤爆するゲートは入れない）:
  - OMIT の項判定はページ全文の「第N項」の出現で満たす（原文引用でなく本文の言及でも可）。
    「項があることを知っているページ」を通し、「項の存在ごと落としたページ」だけを止める。
  - OMIT の号は 項をまたいだ集合で比較する（第2項一号を第1項一号で満たしてしまう）。
    項の脱落は上の項判定が別に拾う。
  - CLAIM は**第1項の号数**とだけ比べる。「4つの号」が条全体を指すのか第1項を指すのかは
    文からは決まらない（150.md 型）ので、第2項以降に言及する行と「にまとめ」は検査しない。
    対象は articles/ のみ（themes 等は法令の帰属が行単位で決まらない）。
  - 原典の解釈PDF抽出テキストは約50字で折り返されるため、項・号の**先頭行**だけを
    番号で認識する。項は 2,3,4… と連続するものだけを採る（表の数値行を項と誤認しない）。

使い方:
  python scripts/check_genbun_omission.py               # docs/articles 全体
  python scripts/check_genbun_omission.py docs/articles/kaishaku/22.md
  python scripts/check_genbun_omission.py --self-test   # 検出器の生存証明
"""
from __future__ import annotations

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_law_verbatim import SOURCES, genbun_quotes, load_kaishaku  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 正当な理由がある欠落だけを「ファイル:第N条:種別:値」を鍵にして通す。
# ratchet（増やすときは理由を書く）。
ALLOWLIST: dict[str, str] = {
    # 用語の定義（19号）は柱書だけを逐語引用し、各号の定義は本文の「定義（要点）」表で
    # 扱う設計。表は要約であって逐語ゲートの射程外＝**沈黙させず債務として明示**する
    # （表の19語を原典と逐語で結ぶ検査は本ゲートの外。解消するときはこの行を消す）。
    "docs/articles/kijun/1.md:第1条:OMIT:号一,二,三,四,五,六,七,八,九,十,十一,十二,十三,十四,十五,十六,十七,十八,十九":
        "柱書のみ逐語引用・19号の定義は要点表（要約）で扱う設計。逐語未照合の債務として可視化",
}

KAN = "一二三四五六七八九十"

# 原典（解釈PDF抽出テキスト）の項・号の先頭行。折り返しの続き行は番号で始まらない。
# 最小長は表のセル行（「5m」「一般」等）を弾くため。
KOU_LINE = re.compile(r"^(\d+)[ 　](.{15,})$")
GOU_LINE = re.compile(rf"^([{KAN}]+)[ 　](.{{8,}})$")

# ページ側の号の書き出し（**一　** / 一 / 第一号 / - 一 …）
PAGE_GOU = re.compile(rf"^(?:第)?([{KAN}]+)(?:号)?[ 　]")
PAGE_KOU = re.compile(r"^(\d+)[ 　]")
KOU_MENTION = re.compile(r"第(\d+)項")

# 本文の件数主張。「3つの号」「4号構成」等。漢数字の主張は取らない（「一号」等と衝突する）。
# 数字と語の間に空白を許さない（「2026-08-31 号構成の…」の日付末尾を主張と誤認した実測）。
CLAIM = re.compile(r"(?<![-/.\d])(\d+)(?:つの号|号構成|号で構成|号立て|つの施設方法)")
# 主張のスコープが第1項と決まらない行は検査しない（150.md 型は原理的に取れない）
CLAIM_SKIP = re.compile(r"にまとめ|第[2-9]項|第[1-9][0-9]項")
# 行内に真の号数が「全7号」「7号のうち」の形で書かれていれば、部分の言及は主張ではない
# （22.md「3つの施設方法（全7号のうち一〜三号）」）。
LINE_GOU_NUMS = re.compile(r"(\d+)(?:つの)?号")
ART_MENTION = re.compile(r"第(\d+)条")


def kan2int(k: str) -> int | None:
    """漢数字（一〜十九）→ int。範囲外は None."""
    if k == "十":
        return 10
    if len(k) == 1:
        return KAN.index(k) + 1 if k in KAN else None
    if len(k) == 2 and k[0] == "十" and k[1] in KAN[:9]:
        return 10 + KAN.index(k[1]) + 1
    return None


def int2kan(n: int) -> str:
    if 1 <= n <= 10:
        return KAN[n - 1]
    if 11 <= n <= 19:
        return "十" + KAN[n - 11]
    return str(n)


# 条の構造: {項番号: [号番号...]}。第1項は常に存在する。
Structure = dict[int, list[int]]


def structure_kaishaku(body: str) -> Structure:
    paras: Structure = {1: []}
    cur = 1
    for raw in body.splitlines():
        s = raw.strip()
        m = KOU_LINE.match(s)
        if m and int(m.group(1)) == cur + 1:
            cur += 1
            paras[cur] = []
            continue
        m = GOU_LINE.match(s)
        if m:
            n = kan2int(m.group(1))
            if n and n not in paras[cur]:
                paras[cur].append(n)
    return paras


def load_structures_kaishaku(path: Path) -> dict[str, Structure]:
    arts, _full, _sha = load_kaishaku(path)
    return {num: structure_kaishaku(body) for num, body in arts.items()}


def load_structures_egov(path: Path) -> dict[str, Structure]:
    """e-Gov XML は Paragraph/Item が構造として入っている（附則は除外）."""
    root = ET.parse(path).getroot()
    supp = {id(a) for sp in root.iter("SupplProvision") for a in sp.iter("Article")}
    out: dict[str, Structure] = {}
    for art in root.iter("Article"):
        if id(art) in supp:
            continue
        num = art.get("Num")
        if not num or num in out:
            continue
        paras: Structure = {}
        for pa in art.findall("Paragraph"):
            pn = pa.get("Num") or ""
            if not pn.isdigit():
                continue
            items = sorted(
                {int(it.get("Num")) for it in pa.findall("Item") if (it.get("Num") or "").isdigit()}
            )
            paras[int(pn)] = items
        paras.setdefault(1, [])
        out[num] = paras
    return out


def load_all() -> tuple[dict[str, dict[str, Structure]], list[str]]:
    loaded: dict[str, dict[str, Structure]] = {}
    errors: list[str] = []
    for group, (label, path, kind) in SOURCES.items():
        if not path.exists():
            errors.append(f"原典キャッシュがありません: {path}（{label}）")
            continue
        loaded[group] = (
            load_structures_egov(path) if kind == "egov" else load_structures_kaishaku(path)
        )
        if not loaded[group]:
            errors.append(f"原典から条文を1件も抽出できませんでした: {path.name}")
    return loaded, errors


def page_side(path: Path) -> tuple[set[int], set[int], set[int]]:
    """ページが持つ 項番号（全文の言及＋原文の書き出し）・号番号（原文の書き出し）・
    原文として実際に引用している項番号（第1項は引用があれば常に含む）."""
    text = path.read_text(encoding="utf-8")
    kou = {int(x) for x in KOU_MENTION.findall(text)}
    quoted_kou: set[int] = set()
    gou: set[int] = set()
    for _line, q in genbun_quotes(path):
        t = re.sub(r"<[^>]+>|[*=＝`]", "", q).strip()
        t = re.sub(r"^[-・]\s*", "", t)
        quoted_kou.add(1)
        m = PAGE_GOU.match(t)
        if m:
            n = kan2int(m.group(1))
            if n:
                gou.add(n)
        m = PAGE_KOU.match(t) or re.match(r"^第(\d+)項", t)
        if m:
            kou.add(int(m.group(1)))
            quoted_kou.add(int(m.group(1)))
    return kou, gou, quoted_kou


@dataclass
class Finding:
    kind: str  # OMIT / CLAIM
    file: str
    line: int  # OMIT は 0
    article: str
    detail: str

    @property
    def key(self) -> str:
        return f"{self.file}:第{self.article}条:{self.kind}:{self.detail}"


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def check_omission(path: Path, num: str, st: Structure) -> list[Finding]:
    pk, pg, quoted = page_side(path)
    want_k = {n for n in st if n >= 2}
    # 号は、ページが**原文として引用している項**の分だけ求める。第1項だけを引用し
    # 他の項は本文で言及するページ（kaishaku/75）に、引用していない項の号まで要求しない。
    want_g: set[int] = set()
    for n, items in st.items():
        if n in quoted:
            want_g |= set(items)
    out: list[Finding] = []
    mk = sorted(want_k - pk)
    mg = sorted(want_g - pg)
    if mk:
        out.append(Finding("OMIT", rel(path), 0, num, "項" + ",".join(map(str, mk))))
    if mg:
        out.append(Finding("OMIT", rel(path), 0, num, "号" + ",".join(int2kan(n) for n in mg)))
    return out


def check_claims(path: Path, num: str, arts: dict[str, Structure]) -> list[Finding]:
    out: list[Finding] = []
    for i, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if CLAIM_SKIP.search(raw):
            continue
        claims = [int(m.group(1)) for m in CLAIM.finditer(raw)]
        if not claims:
            continue
        cands = [num] + [a for a in ART_MENTION.findall(raw) if a != num]
        # 第1項に号が無い条（kaishaku/120「3つの施設方法」＝柱書の列挙）は比べる対象が無い
        counts = {a: len(arts[a].get(1, [])) for a in cands if a in arts and arts[a].get(1)}
        if not counts:
            continue
        line_nums = {int(x) for x in LINE_GOU_NUMS.findall(raw)}
        if line_nums & set(counts.values()):
            continue
        for n in claims:
            if n in counts.values():
                continue
            shown = "・".join(f"第{a}条={c}" for a, c in counts.items())
            out.append(Finding("CLAIM", rel(path), i, num, f"{n}({shown})"))
    return out


def scan(targets: list[Path]) -> tuple[list[Finding], list[str], int]:
    loaded, errors = load_all()
    findings: list[Finding] = []
    checked = 0
    for path in targets:
        group = path.parent.name
        if group not in loaded:
            continue
        arts = loaded[group]
        num = path.stem
        if num not in arts:
            continue
        if not genbun_quotes(path):
            continue
        checked += 1
        findings.extend(check_omission(path, num, arts[num]))
        findings.extend(check_claims(path, num, arts))
    return findings, errors, checked


def collect(paths: list[str]) -> list[Path]:
    if not paths:
        return sorted(p for g in SOURCES for p in (ROOT / "docs" / "articles" / g).glob("*.md"))
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


def self_test() -> int:
    """検出器の生存証明（vacuous pass 防止）.

    合成した原典・ページで OMIT / CLAIM が実際に立つことと、
    完全な引用では立たないこと（陰性対照）を見る。
    """
    import tempfile

    ok = True

    def report(hit: bool, label: str) -> None:
        nonlocal ok
        print(f"  [{'PASS' if hit else 'FAIL'}] {label}")
        ok &= hit

    # 原典の構造抽出（解釈テキスト形式）。折り返し行・表のセル行・(イ)(ロ) を混ぜる
    body = (
        "第999条 低圧用の配線器具は、次の各号により施設すること。 \n"
        "一 充電部分が露出しないように施設すること。ただし、取扱者以外の者が出入りできないよう\n"
        "に施設する場合は、この限りでない。 \n"
        "二 湿気の多い場所又は水気のある場所に施設する場合は、防湿装置を施すこと。 \n"
        "イ 接地極は、地下75cm以上の深さに埋設すること。 \n"
        "(イ) 接地極を鉄柱その他の金属体の底面から30cm以上の深さに埋設すること。 \n"
        "999-1表 \n"
        "5 m \n"
        "150／Ig \n"
        "三 配線器具に電線を接続する場合は、堅ろうに、かつ、電気的に完全に接続すること。 \n"
        "2 低圧用の非包装ヒューズは、不燃性のもので製作した箱の内部に施設すること。 \n"
        "一 極相互の間に、絶縁性の隔壁を設けること。 \n"
        "二 カバーは、耐アーク性の合成樹脂で製作したものであること。 \n"
        "7 これは項ではない（連続しない番号＝表由来の数値行の想定）。 \n"
    )
    st = structure_kaishaku(body)
    report(st == {1: [1, 2, 3], 2: [1, 2]}, f"原典構造の抽出: {st}")

    def page(md: str) -> Path:
        d = Path(tempfile.mkdtemp())
        p = d / "999.md"
        p.write_text(md, encoding="utf-8")
        return p

    full = (
        "# 第999条\n\n## 2. 条文原文\n\n"
        "> **第1項** 低圧用の配線器具は、次の各号により施設すること。\n"
        "> **一　**充電部分が露出しないように施設すること。\n"
        "> 二 湿気の多い場所又は水気のある場所に施設する場合は、防湿装置を施すこと。\n"
        "> **第三号** 配線器具に電線を接続する場合は、堅ろうに接続すること。\n"
        "> **第2項** 低圧用の非包装ヒューズは、箱の内部に施設すること。\n"
        "> - 一 極相互の間に、絶縁性の隔壁を設けること。\n"
        "> 二 カバーは、耐アーク性の合成樹脂で製作したものであること。\n\n"
        "## 3. 解説\n\n本条第1項は3つの号で構成される。\n"
    )
    f = check_omission(page(full), "999", st)
    report(not f, f"陰性対照: 完全な引用で OMIT が立たない {[x.detail for x in f]}")
    f = check_claims(page(full), "999", {"999": st})
    report(not f, f"陰性対照: 正しい号数主張で CLAIM が立たない {[x.detail for x in f]}")

    # 第2項と第三号を落とす（150.md / 117.md 型）
    dropped = full.replace(
        "> **第三号** 配線器具に電線を接続する場合は、堅ろうに接続すること。\n", ""
    )
    dropped = dropped.split("> **第2項**")[0] + "\n## 3. 解説\n\n本条第1項は3つの号で構成される。\n"
    f = check_omission(page(dropped), "999", st)
    kinds = sorted(x.detail for x in f)
    report(kinds == ["号三", "項2"], f"OMIT 検出: 第2項と第三号の欠落 {kinds}")

    # 本文に「第2項」の言及だけがあれば項の欠落は通す（設計どおりの緩さを固定）
    mentioned = dropped + "\n第2項は非包装ヒューズの規定。\n"
    f = check_omission(page(mentioned), "999", st)
    report([x.detail for x in f] == ["号三"], "OMIT: 本文が第2項に言及していれば項は通す")

    # 件数主張（149.md 型）
    wrong = full.replace("3つの号で構成", "4つの号で構成")
    f = check_claims(page(wrong), "999", {"999": st})
    report(len(f) == 1 and f[0].detail.startswith("4("), f"CLAIM 検出: 4つの号 vs 第1項=3 {[x.detail for x in f]}")

    # 第2項以降に言及する行は検査しない（150.md 型は取れないと明示）
    scoped = full.replace("本条第1項は3つの号で構成される。", "本条は第1項・第2項合わせて5つの号で構成される。")
    f = check_claims(page(scoped), "999", {"999": st})
    report(not f, "CLAIM: 第2項に言及する行は検査しない")

    # 行内に真の号数が書かれていれば部分の言及は通す／日付末尾を主張と誤認しない／
    # 第1項に号が無い条は比べない
    for md, label in (
        (full.replace("本条第1項は3つの号で構成される。", "中核となる2つの施設方法（全3号のうち一〜二号）"), "行内に全3号の明記"),
        (full.replace("本条第1項は3つの号で構成される。", "- 2026-08-31 号構成の波及漏れを是正"), "日付 2026-08-31 の末尾"),
    ):
        f = check_claims(page(md), "999", {"999": st})
        report(not f, f"CLAIM 陰性: {label} {[x.detail for x in f]}")
    f = check_claims(page(full.replace("3つの号", "5つの施設方法")), "999", {"999": {1: [], 2: [1, 2]}})
    report(not f, "CLAIM 陰性: 第1項に号が無い条は比べない")

    # 引用していない項の号は求めない（第1項だけを引用するページ）
    only1 = full.split("> **一　**")[0] + "\n## 3. 解説\n\n第2項は非包装ヒューズ。\n"
    f = check_omission(page(only1), "999", st)
    report([x.detail for x in f] == ["号一,二,三"], f"OMIT: 引用した第1項の号だけ求める {[x.detail for x in f]}")

    # 行内で他条を挙げていれば、その条の第1項号数でも通す
    other = full.replace("本条第1項は3つの号で構成される。", "第998条は5つの号で構成される。")
    f = check_claims(page(other), "999", {"999": st, "998": {1: [1, 2, 3, 4, 5]}})
    report(not f, "CLAIM: 行内の他条の号数と一致すれば通す")

    # 実データ側の生存証明: 原典キャッシュから既知の構造が取れること
    loaded, errors = load_all()
    report(not errors, f"原典キャッシュの読込 {errors}")
    k = loaded.get("kaishaku", {})
    report(k.get("22", {}).get(1) == [1, 2, 3, 4, 5, 6, 7] and 2 in k.get("22", {}),
           f"解釈第22条: 第1項七号＋第2項 {k.get('22')}")
    report(k.get("150", {}) == {1: [1, 2, 3, 4], 2: [1, 2, 3]}, f"解釈第150条: {k.get('150')}")
    j = loaded.get("jigyoho", {})
    report(j.get("38", {}).get(1) == [1, 2, 3] and 4 in j.get("38", {}), f"事業法第38条: {j.get('38')}")

    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="対象ファイル／ディレクトリ（省略時 docs/articles 全体）")
    ap.add_argument("--self-test", action="store_true", help="検出器の生存証明")
    ap.add_argument("--no-allowlist", action="store_true", help="allowlist を無視して全件表示")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    findings, errors, checked = scan(collect(args.paths))
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2

    allowed = 0
    shown: list[Finding] = []
    for f in findings:
        if not args.no_allowlist and f.key in ALLOWLIST:
            allowed += 1
            continue
        shown.append(f)

    for f in shown:
        where = f"{f.file}:{f.line}" if f.line else f.file
        if f.kind == "OMIT":
            print(f"[OMIT]  {where}  第{f.article}条  原典にあるがページの条文原文に無い: {f.detail}")
        else:
            n, _, rest = f.detail.partition("(")
            print(f"[CLAIM] {where}  第{f.article}条  本文の号数主張 {n} が第1項の号数と不一致 ({rest[:-1]})")

    print(
        f"\ncheck_genbun_omission: {len(shown)}件"
        f"（{checked}ページを照合・allowlist {allowed}件）"
    )
    return 1 if shown else 0


if __name__ == "__main__":
    sys.exit(main())
