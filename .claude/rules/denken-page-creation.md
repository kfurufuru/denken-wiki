# 条文ページ作成ワークフロー（必須チェックリスト）

`docs/articles/{kijun,kaishaku,jigyoho}/*.md` を新規作成・全面改修する際は、以下の手順を必ず踏む。

## 背景（なぜ必要か）

- 電技解釈は数年置きに改正され、**条番号が変わる** ことがある（特に分散型電源系 §220台）
- ローカル `_data/kakomon.yml` の `topic` 文字列を盲信すると、改正前の論点で書いてしまうリスクがある
- 過去事例（2026-05-02）：第224条を「低圧連系の保護装置」（旧版）で書いたが、現行は「高圧/特別高圧連系の再閉路防止」だった

## 必須チェックリスト（ページ作成前）

```
□ Step1: kakomon.yml で該当条文の出題実績を確認
   python -c "import yaml; data=yaml.safe_load(open('_data/kakomon.yml',encoding='utf-8'));
              [print(p) for p in data['problems'] if '§{条番号}' in p['article']]"

□ Step2: denken-ou.com で最新出題例の論点を確認
   - URL パターン: https://denken-ou.com/houkir{年}-{期}-{問}/
     例: R6下問7 → houkir6-2-7、R7上問4 → houkir7-1-4
   - 最低1件、出題実績がある場合は最新年度を確認

□ Step3: kakomon.yml の topic 文字列と denken-ou.com の論点を照合
   - 一致 → そのまま執筆
   - 不一致 → 法令改正で内容が変わった可能性。e-Gov公式で現行条文を確認
   - kakomon.yml 側を修正してから執筆

□ Step4: e-Gov公式（または経産省PDF）で条文タイトル・本文を照合
   https://laws.e-gov.go.jp/ で「電気設備の技術基準の解釈」を検索
   タイトルが正本と一致しているか確認

□ Step5: 確信度自己評価
   - 条文タイトル: 90%以上か？ → No なら e-Gov 再確認
   - 出題内容: 90%以上か？ → No なら denken-ou.com 再確認
   - <70% の項目は [要確認] フラグ付きで記載
```

## 自動化ツール

| 用途 | コマンド |
|------|---------|
| kakomon.yml の denken-ou.com 照合 | `python scripts/audit_kakomon.py --article 解釈§224` |
| ランダム監査（最新N件） | `python scripts/audit_kakomon.py --recent 10` |
| 全件監査＋キャッシュ生成 | `python scripts/audit_kakomon.py --all --cache _data/denken-ou-cache.yml` |
| pre-commit フック（自動・0トークン） | `python scripts/precommit_kakomon.py` |
| 内部整合性（md ↔ by-field.md） | `python scripts/check_kakomon_consistency.py` |
| 品質スコア | `python wiki_quality_check.py docs/articles/{path}.md` |
| 品質ランキング | `python wiki_quality_check.py --rank` |

### 効率化アーキ（4層）

```
Layer 1: _data/denken-ou-cache.yml ← --all --cache で生成（実装済）
Layer 2: pre-commit hook ← scripts/precommit_kakomon.py（実装済）
Layer 3: .github/workflows/audit-kakomon.yml（実装済・月初0:00 UTC自動実行）
Layer 4: morning-reporter統合（任意・gh issue list で件数表示）
```

### Layer 3 動作仕様

| 項目 | 内容 |
|------|------|
| トリガ | 月初9:00 JST（`cron: 0 0 1 * *`）＋ `workflow_dispatch` 手動実行 |
| 処理 | `audit_kakomon.py --all` 実行 → mismatch を `inbox/audit-mismatches.json` へ |
| 賢いフィルタ | キャッシュ登録済みエントリで mismatch のみを「real issue」と判定（HTML簡易パース誤検出を除外） |
| アラート | real issue がある時のみ GitHub Issue を `audit` ラベル付きで自動作成 |
| 成果物保管 | inbox/audit-*.json を 90日 artifact として保管 |
| 必要権限 | `contents: read` + `issues: write` |

### Layer 4（任意）morning-reporter 統合

朝のブリーフィング時に `gh issue list -R kfurufuru/denken-wiki --label audit --state open --json number,title` を実行し、件数があれば1行通知。issueが無い時はAIトークン消費0。

**pre-commit hook の有効化（初回のみ）**:
```bash
# キャッシュ生成（約8分・1回のみ）
python scripts/audit_kakomon.py --all --cache _data/denken-ou-cache.yml

# .git/hooks/pre-commit に登録
echo '#!/bin/sh
python scripts/precommit_kakomon.py' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

これ以降、`kakomon.yml` の article を誤って編集しても commit時に検出される（AI関与・トークン消費 = 0）。

## 禁止事項

- ❌ kakomon.yml の topic 文字列だけで内容を決めて書く
- ❌ 条文原文を未確認のまま [要確認] なしで本文に書く
- ❌ 「○○条と思われる」レベルの推定で関連条文リンクを張る

## 推奨事項

- ✅ denken-ou.com の解説で出題実績がある条文は、その論点を必ず本文に反映
- ✅ 条文原文セクションは [要確認: e-Gov公式の本文をここに転記] プレースホルダから始める
- ✅ 改正リスクのある条文（§220台 分散型電源系・§225 スポットネットワーク等）は脚注で「条番号は X 年改正後の番号」と明記

## 改正履歴（要監視条文）

| 改正年 | 影響範囲 | 状況 |
|--------|---------|------|
| 2024年? | §220〜§232（分散型電源系） | 第224条が「低圧の保護装置」→「高圧/特別高圧 再閉路防止」に変更（要確認: 正確な改正年） |
| 2024年? | §227・§229（分散型電源 保護装置） | 旧§227 ≒「高圧連系の保護装置」→ 現行§229／現行§227 ＝「低圧連系の保護装置」（denken-ou.com の解説は現行番号、kakomon.yml の article は旧番号で残置のケースあり） |

新たに改正情報を確認したらここに追記する。

---

## 改正情報・番号ズレの記載ルール（記事側の必須要件）

法令改正で条番号や内容が変わった、または **既存記事の条番号が現行と異なる** ことが判明した条文は、**記事冒頭に必ず注記ブロックを配置する**。学習者が混乱しないようにすることが最優先。

### 2つのケースを区別する

| ケース | 判定方法 | 注記の見出し |
|--------|---------|------|
| **A. 法令改正で番号が変わった** | 経産省告示・JESC・電気書院追補版に改正記録あり | `📌 法令改正による条番号変更` |
| **B. 記事側の番号誤り（改正記録なし）** | 改正記録は無いが現行と既存記事の番号がズレている | `⚠️ 条番号誤記の訂正` |

**判定不能なら `[要確認]` を必ず付ける。** 「改正されたらしい」のような根拠なしで A を選択しない。

### 必須フォーマット（冒頭メタ直下に配置）

```markdown
!!! warning "📌 改正注意（条番号・内容の変動）"
    - **本ページの条番号**: 第NNN条（kakomon.yml・既存リンク互換のため維持）
    - **現行条番号**: 第MMM条（YYYY年MM月改正以降）
    - **改正前の対応**: 旧第NNN条 = 「○○○」
    - **改正根拠**: [経産省告示 第○○号](URL) / [JESC 改正情報](URL)（${改正年月日}公布・${施行年月日}施行）
    - **試験対策の注意**: R06以降の出題は **現行第MMM条** として解説される。穴埋めの空欄語句は変わらないが、関連条文の番号は現行体系で覚えること。
```

### 改正根拠の必須要件（出典なき注記は禁止）

| 項目 | 必須/任意 | ソース候補 |
|------|:---:|------|
| 改正年月日（公布日） | 必須 | 経産省告示・JESC改正履歴・官報 |
| 施行年月日 | 必須 | 同上 |
| 出典URL | **必須**（最低1本） | 経産省 `meti.go.jp/policy/safety_security/...` / JESC `jesc.gr.jp/revision/` / 電気書院 追補版PDF |
| 改正前後の条番号対応 | 必須 | denken-ou.com 解説 vs e-Gov 現行条文 |

**出典が取れない場合は `[要確認]` フラグを付ける。**「改正されたらしい」「番号が変わったようだ」のような根拠なし記述は禁止。

### 適用判定フロー

```
□ kakomon.yml の article 番号と denken-ou.com 解説の条番号が異なる
  → 改正の可能性あり。e-Gov/経産省で現行条番号を確認
□ 現行と旧で番号が異なる確証が取れた
  → 改正注記ブロックを記事冒頭に配置（必須）
□ kakomon.yml の article を現行番号に揃えるかは別判断（一括修正は影響大）
  → 暫定は記事内の注記で吸収、根本対応は別タスクで一括修正
```

### ファイル名・URLの扱い

- 既存ページの URL は **学習コンテンツの被リンク互換** を優先して原則維持
- リネーム（例：`227.md` → `229.md`）は kakomon.yml・関連ページ全体を一括棚卸しできる別タスクで実施
- リネームしない場合は記事冒頭の改正注記で吸収する

### 禁止事項

- ❌ 条番号がズレている事実を確認しながら、注記なしで本文だけ書き換える
- ❌ 「（改正で番号変わった）」のような曖昧な1行で済ませる（学習者が見落とす）
