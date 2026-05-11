"""
太字内の単位記号を自動分離（フォント崩れ対策）

問題：
  Material for MkDocs 標準フォント Roboto Bold で、特定の単位記号（Ω, Ω, ㎡ など）の
  太字グリフが日本語フォントへフォールバックされる際、グリフ欠落や太さ不揃いで
  「文字化けに見える」現象が起きる。

対策：
  Markdown ソース中で `**100Ω以下**` のように太字内に Ω を書いても、
  ビルド時に `**100** Ω **以下**` のように単位記号を太字対象から外して出力する。

  これにより執筆者は気にせず `**100Ω以下**` と書ける（根本解決）。

対象記号：
  Ω (U+03A9 Greek Capital Omega) / Ω (U+2126 Ohm Sign)

スコープ：
  Markdown のテキストレベル（コードブロック、インラインコード、HTML属性は除外）

実装上の注意：
  - 同一太字スパン内に複数のΩがあるケースに備えて複数回パスする
  - 既に分離済みのΩを再パスで誤検出しないよう、処理済みΩは一時的に
    \x00OMEGA_MARKER\x00 に退避し、最後に復元する
"""
import re

# 太字内に対象記号を含むパターン
# キャプチャ: (前半テキスト)(対象記号)(後半テキスト)
_PATTERN = re.compile(
    r'\*\*'                # 開始 **
    r'([^*\n`]*?)'         # 前半（バックティック・改行・*以外、非貪欲）
    r'([ΩΩ])'         # 対象単位記号 (U+03A9 / U+2126)
    r'([^*\n`]*?)'         # 後半
    r'\*\*'                # 終了 **
)

# 処理済みΩを一時退避するマーカー（再パスで誤検出されないよう非対象記号として保持）
_OMEGA_MARKER = '\x00OMEGA_PROCESSED\x00'

# コードブロック・インラインコード保護用パターン
_CODE_BLOCK = re.compile(r'```.*?```', re.DOTALL)
_INLINE_CODE = re.compile(r'`[^`\n]+`')


def _replace(match: re.Match) -> str:
    before, _sym, after = match.group(1), match.group(2), match.group(3)
    parts = []
    # 注意: CommonMark仕様では `**X **` (末尾空白) の `**` が closing として
    # 認識されないため、必ず strip() してから太字スパンで囲む
    before_stripped = before.strip()
    after_stripped = after.strip()
    if before_stripped:
        parts.append(f'**{before_stripped}**')
    parts.append(_OMEGA_MARKER)
    if after_stripped:
        parts.append(f'**{after_stripped}**')
    return ' '.join(parts)


def _protect_and_transform(text: str) -> str:
    """コード領域を退避してから変換、最後に復元"""
    placeholders = {}

    def stash(m: re.Match) -> str:
        key = f'\x01PLACEHOLDER_{len(placeholders)}\x01'
        placeholders[key] = m.group(0)
        return key

    # コード領域を退避
    text = _CODE_BLOCK.sub(stash, text)
    text = _INLINE_CODE.sub(stash, text)

    # 変換（複数回適用：太字内に対象記号が複数あるケースに対応。
    # 処理済みΩは _OMEGA_MARKER に置き換わるので再検出されない）
    for _ in range(5):
        new_text = _PATTERN.sub(_replace, text)
        if new_text == text:
            break
        text = new_text

    # マーカーをΩに復元
    text = text.replace(_OMEGA_MARKER, 'Ω')

    # コード領域を復元
    for key, val in placeholders.items():
        text = text.replace(key, val)
    return text


def on_page_markdown(markdown: str, *, page=None, config=None, files=None, **kwargs) -> str:
    """MkDocs hook entry point"""
    return _protect_and_transform(markdown)
