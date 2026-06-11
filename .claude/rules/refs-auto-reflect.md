# 参考文献の自動反映運用

## 目的
編集セッションで新規参照した一次ソース・解説サイトを忘れずに `docs/reference/links.md` に反映する。

## 運用フロー

### 編集中（Claude エージェント）
- 新規 URL を参照したとき（eGov API・経産省PDF・JEAC・過去問サイト 等）
- 「これ links.md に未収載だな」と判断したら **必ず** `_data/refs-pending.yml` に append
- 形式:
  ```yaml
  - url: "..."
    title: "..."
    category: "(links.md のセクション名・部分一致でOK)"
    used_in: "(編集セッション・記事名)"
    used_at: "YYYY-MM-DD"
    rationale: "(なぜ役に立ったか・何が links.md に無くて困ったか)"
  ```

### 月次 or 任意のタイミング（オーケストレータ）
- `python scripts/merge_refs.py --dry-run` でプレビュー
- 問題なければ `python scripts/merge_refs.py` で実反映
- pending → merged に移動・links.md に追記される

## 編集ルール
- pending は **append-only**（直接削除しない・merge スクリプトのみが移動可）
- カテゴリが既存セクションに無い場合は警告される。`docs/reference/links.md` のセクション拡張を別タスクで実施してから merge を再実行
- 重複チェックはスクリプト任せ（人間は重複を気にせず append OK・既出URLは自動で merged に移動される）

## カテゴリのマッチング仕様
`category` フィールドは links.md の H2 見出し（`## …`）と次の優先順位で照合される:

1. 完全一致（`category == 見出し`）
2. 見出しが category を含む（例: category=`"法令原文"` → H2=`"法令原文（e-Gov法令検索）"` にマッチ）
3. category が見出しを含む（例: category=`"1.3 電気工事士・工事業系"` → H2=`"電気工事士"` がマッチ）

実運用では `"法令原文"` `"技術規格"` `"試験情報"` `"学習リソース"` のような短いキーワードを推奨。

## CLI
```bash
python scripts/merge_refs.py                  # 実行（実反映）
python scripts/merge_refs.py --dry-run        # 何が追加されるか確認のみ（書き込みなし）
python scripts/merge_refs.py --verbose        # 詳細ログ（H2見出し一覧も表示。--dry-run なしだと実反映される）
python scripts/merge_refs.py --skip-url-check # URL死活確認を省略（オフライン環境・bot拒否の誤検出回避）
```

- ADD 候補の URL は死活確認（HEAD→GET フォールバック・timeout 10s）され、4xx/5xx・接続不可は `[WARN-URL]` 警告とともに pending に残る（リンク切れを links.md に公開しない・JEAC9701 404 事案の再発防止）
- 実マージ時、refs-pending.yml 先頭のヘッダコメントはスクリプトが自動付与する（文言の正本は merge_refs.py 内 `PENDING_HEADER` 定数）

## 関連ファイル
- `_data/refs-pending.yml` — append-only ログ
- `scripts/merge_refs.py` — マージスクリプト
- `docs/reference/links.md` — 反映先（直接編集も可能だが、自動運用ではこのスクリプト経由）
