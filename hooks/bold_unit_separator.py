"""太字内の単位記号を自動分離（フォント崩れ対策・実行時セーフティネット）

問題：
  Material for MkDocs 標準フォント Roboto Bold で、特定の単位記号（Ω, Ω, ㎡ など）の
  太字グリフが日本語フォントへフォールバックされる際、グリフ欠落や太さ不揃いで
  「文字化けに見える」現象が起きる。

対策：
  Markdown ソース中で `**100Ω以下**` のように太字内に Ω が紛れても、
  ビルド時に `**100** Ω **以下**` のように単位記号を太字対象から外して出力する。

  ※ ソース側の正書法は CLAUDE.md「MΩ表記ルール」=「数値だけ太字（**100**Ω以下）」であり、
    scripts/check_value_consistency.py V01（ERROR）が pre-commit/CI で強制する。
    本フックは「それでも残った太字内Ω」を読者に見せないための実行時の安全網。

対象記号：
  Ω (U+03A9 Greek Capital Omega) / Ω (U+2126 Ohm Sign)
  SI接頭辞付き（kΩ・KΩ・MΩ・mΩ・µΩ・μΩ）は接頭辞ごと一体で太字の外へ出す。
  （旧実装は **0.1MΩ** → `**0.1M** Ω` と M を数値側に残し単位を分断する欠陥があった）

スコープ：
  Markdown のテキストレベル・行単位（コードブロック、インラインコードは除外）。

2026-06-10 誤ペアリングバグ修正（実装方式の変更理由）：
  旧実装は `\\*\\*([^*]*?)([ΩΩ])([^*]*?)\\*\\*` の単一正規表現で太字スパンを推定して
  いたため、`**0.1**MΩ／**0.2**MΩ`（正書法の連続）や `| **A種** | 10Ω | **B種** |`
  （テーブル行のセル跨ぎ）のように Ω が2つの太字スパンの「間」にある行で、
  閉じ ** と次の開き ** を誤ペアリングし、Ω を逆に太字内へ押し込み・余計な
  太字断片（`**以下 ／**` 等）を生成していた。ビルド済みHTMLに `<strong> Ω </strong>`
  が kijun/58 で25箇所出るなどの実害（散発は 2026-05-12 フック導入時から、
  正書法化 PR #59 で拡大）。
  現実装は行を `**` で左→右に機械的にペアリングし、真の太字スパンの内側だけを
  変換する（scripts/check_value_consistency.py の bold_inside_segments と同方式）。
"""
import re

# 太字の外へ出す単位トークン（SI接頭辞も一体で扱う）
_UNIT_SPLIT = re.compile(r'([kKMmµμ]?[ΩΩ])')
_OMEGA = re.compile(r'[ΩΩ]')

# コードブロック・インラインコード保護用パターン
_CODE_BLOCK = re.compile(r'```.*?```', re.DOTALL)
_INLINE_CODE = re.compile(r'`[^`\n]+`')


def _split_bold_segment(seg: str) -> str:
    """太字スパンの内側テキストを「単位だけ太字の外」に再構成して返す。

    '100Ω以下'           -> '**100** Ω **以下**'
    '0.1MΩ'              -> '**0.1** MΩ'
    'C種=10Ω、D種=100Ω'  -> '**C種=10** Ω **、D種=100** Ω'

    注意: CommonMark では `**X **`（終端空白）の `**` が closing と認識されない
    ため、各断片は strip() してから太字で囲み、空白1つで連結する。
    """
    parts = []
    for i, token in enumerate(_UNIT_SPLIT.split(seg)):
        if i % 2 == 1:  # 単位トークン → 太字の外（元の字体 U+03A9/U+2126 を保持）
            parts.append(token)
        else:
            t = token.strip()
            if t:
                parts.append(f'**{t}**')
    return ' '.join(parts)


def _transform_line(line: str) -> str:
    """1行を `**` 左→右ペアリングで分解し、Ωを含む真の太字スパンだけ変換する。"""
    if '**' not in line or not _OMEGA.search(line):
        return line
    # ***（bold+italic 等）は ** ペアリングが多義になるため触らない（保守的スキップ）
    if '***' in line:
        return line
    parts = line.split('**')
    n_markers = len(parts) - 1
    n_spans = n_markers // 2
    out = [parts[0]]
    for k in range(n_spans):
        inner = parts[2 * k + 1]
        if _OMEGA.search(inner):
            out.append(_split_bold_segment(inner))
        else:
            out.append(f'**{inner}**')
        out.append(parts[2 * k + 2])
    if n_markers % 2 == 1:  # 閉じられていない末尾の ** はそのまま温存
        out.append('**')
        out.append(parts[-1])
    return ''.join(out)


def _protect_and_transform(text: str) -> str:
    """コード領域を退避してから行単位で変換、最後に復元"""
    placeholders = {}

    def stash(m: re.Match) -> str:
        key = f'\x01PLACEHOLDER_{len(placeholders)}\x01'
        placeholders[key] = m.group(0)
        return key

    text = _CODE_BLOCK.sub(stash, text)
    text = _INLINE_CODE.sub(stash, text)

    text = '\n'.join(_transform_line(ln) for ln in text.split('\n'))

    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text


def on_page_markdown(markdown: str, *, page=None, config=None, files=None, **kwargs) -> str:
    """MkDocs hook entry point"""
    return _protect_and_transform(markdown)


if __name__ == '__main__':
    # セルフテスト: python hooks/bold_unit_separator.py で実行
    _CASES = [
        # (入力, 期待出力)
        ('**100Ω以下**', '**100** Ω **以下**'),
        ('**0.1MΩ**', '**0.1** MΩ'),
        ('**0.4MΩ以上**', '**0.4** MΩ **以上**'),
        ('**883 Ω**', '**883** Ω'),
        ('**C種=10Ω、D種=100Ω**', '**C種=10** Ω **、D種=100** Ω'),
        # 正書法（数値のみ太字）は不変 — 旧実装はこれを誤ペアリングで破壊していた
        ('**0.1**MΩ／**0.2**MΩ／**0.4**MΩ', '**0.1**MΩ／**0.2**MΩ／**0.4**MΩ'),
        ('**10**Ω以下 ／ **100**Ω ／ **2**Ω以下', '**10**Ω以下 ／ **100**Ω ／ **2**Ω以下'),
        # テーブル行のセル跨ぎ（Ωが太字スパンの間）も不変
        ('| **A種** | 10Ω 以下 | **B種** |', '| **A種** | 10Ω 以下 | **B種** |'),
        ('| **D 種接地工事** | 100Ω 以下 | ELB → **500Ω 以下まで緩和** |',
         '| **D 種接地工事** | 100Ω 以下 | ELB → **500** Ω **以下まで緩和** |'),
        # 同一行に複数の太字Ωスパン
        ('**10Ω以下**（条件次第で **500Ω以下** に緩和）',
         '**10** Ω **以下**（条件次第で **500** Ω **以下** に緩和）'),
        # U+2126 OHM SIGN は字体を保持して外へ
        ('**10Ω**', '**10** Ω'),
        # SI接頭辞
        ('**数kΩ**', '**数** kΩ'),
        # 太字なし・コード内は不変
        ('人体抵抗 数百Ω〜数kΩ', '人体抵抗 数百Ω〜数kΩ'),
        ('`**10Ω**` はNG例', '`**10Ω**` はNG例'),
        # 閉じ忘れ ** は温存
        ('a ** b 10Ω c', 'a ** b 10Ω c'),
        # 単位のみの太字スパンは太字を外して plain に（旧実装は **M** Ω と分断していた）
        ('0.4**MΩ**', '0.4MΩ'),
    ]
    failed = 0
    for src, want in _CASES:
        got = _protect_and_transform(src)
        ok = got == want
        failed += 0 if ok else 1
        print(f'{"OK " if ok else "NG "} {src!r}')
        if not ok:
            print(f'     want: {want!r}')
            print(f'     got : {got!r}')
    # 冪等性: 全ケースの出力をもう一度通しても変化しないこと
    for src, want in _CASES:
        once = _protect_and_transform(src)
        twice = _protect_and_transform(once)
        if once != twice:
            failed += 1
            print(f'NG  idempotency: {src!r} -> {once!r} -> {twice!r}')
    print(f'\n{len(_CASES)} cases, {failed} failed')
    raise SystemExit(1 if failed else 0)
