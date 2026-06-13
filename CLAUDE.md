# denken-wiki

電験3種（第三種電気主任技術者）CBT試験の攻略戦略Wikiサイト。

## ⚠️ 最新テンプレート参照ルール（必読）

「最新テンプレート参照して」と指示された場合、**必ず最初に**以下を実行:

```bash
python wiki_quality_check.py --rank --v3 | head -10
```

スコア最上位の `kijun/*.md` を **唯一のゴールドスタンダード** として Read する。
CLAUDE.md・他ドキュメントの記述は補助情報であり、`--rank --v3` 出力が真のゴールド指定。

**スコアラv3.1 の判定基準**: 18項目3軸（正確性32/試験直結度35/学習継続性33）+ 重大欠陥cap 6種 + S/A/B/C/D判定。100点取得は意図的に困難（誤判定防止）。詳細は `wiki_quality_check.py` 冒頭docstring。

**v1スコア（既存7項目100点）は deprecated**: 100点が多発しゴールド一意決定不能のため。互換性のため `--rank` (フラグなし) で残置するが新規参照禁止。

---

## 最高品質リファレンス（補助情報）

新規ページ追加・既存ページ改修時は、上記 `--rank --v3` で特定したゴールドスタンダードを必ず Read して、セクション構成・図解の使い方・admonition の使い分け・チェックボックス形式を**並列比較しながら**実装する。

**比較駆動編集の原則**: 「ゴールドスタンダードレベルか？」を各セクション完成時に自問する。不足があれば補完してから完了宣言する。

品質検証は `python wiki_quality_check.py <article_path> --v3` で自動チェックする（kakomon.yml の登録メタも併せて表示される）。

## 条文ページ作成ワークフロー（必須）

新規条文ページ作成・全面改修の前に必ず `.claude/docs/denken-page-creation.md` を Read し、5ステップのチェックリスト（kakomon.yml確認 → denken-ou.com照合 → e-Gov照合 → 信頼度自己評価）を実行する。

**⚠️ 同ファイルは自動読込されない**（2026-06-11 トークン節約のため `.claude/rules/` → `.claude/docs/` へ移動・毎セッション21k chars削減）。**条文ページ（articles/配下）に触る作業を始める瞬間に、必ず最初の手順として Read すること**。読まずに書き始めるのは過去事故（2026-05-02 §224 改正前論点で全面書き直し）の再発要因。戦略ページ用 `.claude/docs/strategy-page-3-layer.md` も同様にオンデマンド参照。

**禁止**: kakomon.yml の `topic` 文字列だけ信じて書き始めること（過去事例: 2026-05-02 §224 改正前の論点で書いてしまい全面書き直し）。

**外部監査**: `python scripts/audit_kakomon.py --article 解釈§<番号>` で kakomon.yml と denken-ou.com の条番号一致を照合できる。新規ページ作成時・月次定期で実行する。

**pre-commit フック（推奨セットアップ）**: `_data/denken-ou-cache.yml` を `--cache` で生成済み。`.git/hooks/pre-commit` に `python scripts/precommit_kakomon.py` を登録すると、kakomon.yml の article 誤編集を **commit時に0トークンで自動検出** できる。詳細は `.claude/docs/denken-page-creation.md` 参照。

### リファレンス自動更新ルール（重要）

ページ改修・追加完了時は必ず `python wiki_quality_check.py --rank --v3` を実行し、以下を確認する:

1. 既存トップ（v3 ランキングの首位）のスコアを上回るページが出現したか
2. 上回った場合 → **作業完了宣言の前に**ユーザーに以下フォーマットで通知する:

```
🏆 リファレンス更新候補（v3.1）
- 現トップ: [path] (verdict: X / score: XX点)
- 新候補: [path] (verdict: Y / score: YY点)
- 上回った要素: [軸別の差分・特に正確性軸/試験直結度軸]
リファレンスを切り替えますか？ (Y/n)
```

3. ユーザー承認後、本 CLAUDE.md および `.claude/docs/denken-page-creation.md` の参照記述（あれば）を更新する。なお、運用上の真のゴールド指定は常に `--rank --v3` の出力であり、ファイル中のパス記述は補助情報。

> **月次の自動検知**: `.github/workflows/reference-drift.yml`（月初）が `--rank --v3` 首位と `_data/reference-gold.yml` の記録の乖離を検知して Issue 化する。**新ゴールドを承認したら同ファイルの `gold.path/score/verdict/updated` も更新する**（reference-gold.yml が首位の機械可読な真実・真のゴールドは常に `--rank --v3`）。

## プロジェクト概要

- **サイト**: https://kfurufuru.github.io/denken-wiki/
- **リポジトリ**: kfurufuru/denken-wiki
- **目的**: 電験3種CBT試験の攻略戦略・学習メソッドの集約
- **対象**: 電験3種受験者（特にCBT方式）
- **関連**: `.secretary/denken3-study-dashboard`（学習ダッシュボード）、`.secretary/denken-study/`（学習記録・e-log）

## 現状

条文解説ページが3法令体系で稼働中:
- `docs/articles/kijun/` — 電気設備技術基準（省令）
- `docs/articles/kaishaku/` — 電技解釈
- `docs/articles/jigyoho/` — 電気事業法

## 技術スタック

- MkDocs + Material for MkDocs（静的サイトジェネレータ）
- GitHub Pages（ホスティング）
- GitHub Actions（自動デプロイ）
- MathJax（数式）
- Python（MkDocs依存）

## 初期構築手順

```bash
# 1. MkDocs環境構築
pip install mkdocs-material

# 2. mkdocs.yml作成（ei-wikiのmkdocs.ymlを参考にする）
# 3. docs/index.md 作成
# 4. GitHub Actionsワークフロー作成（.github/workflows/deploy.yml）
# 5. ローカルプレビュー確認
mkdocs serve

# 6. mainブランチにpush → GitHub Pages自動デプロイ
```

## ファイル構造

```
denken-wiki/
├── mkdocs.yml
├── docs/
│   ├── index.md
│   ├── articles/           # 条文解説ページ（主力コンテンツ）
│   │   ├── kijun/          # 電気設備技術基準（省令）
│   │   ├── kaishaku/       # 電技解釈
│   │   └── jigyoho/        # 電気事業法
│   ├── themes/             # テーマ横断ページ
│   ├── strategy/           # 攻略戦略
│   ├── reference/          # 用語索引・リファレンス
│   └── kakomon/            # 過去問データ
├── .github/workflows/deploy.yml
└── .claude/
    ├── commands/
    ├── rules/
    └── skills/
```

## よく使うコマンド

```bash
mkdocs serve              # ローカルプレビュー
mkdocs build              # 静的サイトビルド
# デプロイはmainブランチへのpushでGitHub Actions自動実行
```

## コンテンツ規約

### 条文解説ページ（標準セクション構成）

ゴールドスタンダード: `kaishaku/226.md`（2026-06-09 時点で `--rank --v3` 単独首位 = verdict S / 100点・施設規定系）。記事タイプ別に kijun/58.md（数値規定）・jiko-3.md（手続規定）・jiko-1.md（定義条文）も参照。常に `python wiki_quality_check.py --rank --v3 | head -10` で最新の首位を確認すること（ここのパス記述は補助情報）。

| # | セクション | 必須 | 内容 |
|---|----------|:----:|------|
| 冒頭 | タイトル + 出題頻度 + 概要blockquote + 概要テーブル | ✅ | `🔥🔥🔥🔥🔥` 形式 + 直近出題は各出題を**／**で区切る + 概要テーブル（後述） |
| 冒頭+ | 改正・番号ズレ注記 | 条件付 | 改正/番号誤りがある場合のみ。詳細は `.claude/docs/denken-page-creation.md` 参照 |
| 1 | 全体像と要点 | ✅ | 「5秒で思い出す」箇条書き3-5項目 + `??? question` セルフチェック |
| 2 | 条文原文 | 推奨 | 省令条文を引用（eGov未確認は `[要確認]` 付記） |
| 3 | 原文解析 | 推奨 | ブロック分解テーブル: 原文 \| 意味 \| 試験のポイント |
| 4 | かみ砕き解説 / 因果理解 | ✅ | 「なぜ」の因果チェーンを重視 |
| 5 | 図で理解 | ✅ | SVG（物理概念）or Mermaid（判定ロジック）|
| 6 | 深掘りテーマ | 任意 | 条文固有の論点（例: 絶縁と接地の矛盾解消）。類似機器の比較表あれば配置 |
| 7 | 試験で問われること | 推奨 | 出題パターン分類 |
| 8 | 頻出ひっかけ / 落とし穴 | ✅ | 🔴🟡🟢 重要度別 + **❌→✅形式**（後述） |
| 9 | 穴埋め過去問チャレンジ | ✅ | 実過去問優先（denken-ou.com出典URL必須）+ `!!! abstract` + `??? success` 折りたたみ解答 |
| 10 | まぎらわしい選択肢と正解の違い | ✅ | テーブル: 誤答 \| 正答 \| なぜ違うか |
| 11 | 関連条文 / 関連ページ | ✅ | 内部リンク。上位・並列・委任先を整理 |
| 12 | 過去問実績 | ✅ | テーブル + `!!! note` R08出題予測 |
| 13 | 用語集 | 推奨 | 条文内の類似語・紛らわしい用語を定義テーブルで整理 |
| 14 | 最終チェック | ✅ | `- [ ]` チェックボックス（分類別） |
| フッター | バージョン | ✅ | `*最終確認: YYYY-MM-DD \| ステータス: vX.Y \| ...*` |

**セルフチェック分散ルール**: `??? question` ブロックは冒頭だけでなく、条文の複雑さに応じて必要な数を配置する

### 冒頭の概要テーブル（必須）

タイトル・出題頻度・blockquoteの直後に、ページの位置づけを示すテーブルを配置する。

```markdown
| 項目 | 内容 |
|------|------|
| 条文 | 電気設備に関する技術基準を定める省令 第○条 |
| 規定内容 | （1行で要約） |
| 性格 | 数値規定 / 原則規定 / 手続規定 など |
| 委任先 | 解釈第○条（具体的な実施方法） |
| 上位 | 省令第○条（上位原則） |
```

### 出題回ごとの warning（該当箇所に配置）

特定の過去問で出題されたひっかけは、該当する解説箇所に `!!! warning` で紐付ける。

```markdown
!!! warning "R06上 問8 で出題されたひっかけ"
    「過電流遮断器」の穴埋めに「配線用遮断器」「漏電遮断器」が選択肢として登場する。
    ...
```

### ひっかけセクション書式（❌→✅形式・必須）

受験者が「正しい内容」と誤読しないよう、**必ず❌→✅の対比形式**で書く。

```markdown
### 🔴 致命的（これを間違えたら即失点）

1. ❌「低圧は一律 0.1MΩ でOK」
    - → ✅ **3段階**（0.1／0.2／0.4MΩ）に分かれる。0.1MΩ は対地電圧150V以下のみ
2. ❌「電路全体で一度測定すればOK」
    - → ✅ **開閉器又は過電流遮断器で区切れる電路ごと**に個別測定
```

**禁止**: `**「〇〇でOK」**` のように誤った内容を太字で目立たせる書き方（受験者が正解と誤読する）

### 類似機器比較表（条文に複数機器が登場する場合）

列構成: `機器 | 別名・略称 | 主な役割 | 検出対象 | 条文との関係`

```markdown
| 機器 | 別名・略称 | 主な役割 | 検出対象 | 第○条との関係 |
|------|----------|---------|---------|-------------|
| **開閉器** | スイッチ、ナイフスイッチ、負荷開閉器など | 電路を開閉する | 原則なし | 測定区切りとして条文に明記 |
```

### MΩ表記ルール（Ω太字バグ回避・必須・plain Ω も対象）

MkDocs環境で太字内のΩ（U+03A9/U+2126）がフォント依存でキリル文字に化ける。

- ✅ `**0.1**MΩ` / `**10**Ω以下` — 単位（MΩ・Ω）を太字の外に出す
- ❌ `**0.1MΩ**` / `**10Ω以下**` — 太字内にΩを含めない（接地抵抗系の plain Ω も同様）
- SVGの場合: `<tspan>` で数値部（font-weight:bold）と単位部（font-weight:normal）を分離
- 機械ゲート: `scripts/check_value_consistency.py` V01 が MΩ・plain Ω とも **ERROR** でブロック（2026-06-10 昇格）。一掃は `python scripts/check_value_consistency.py docs --fix`
- ビルド時フック `hooks/bold_unit_separator.py` が残存太字Ωを実行時に自動分離する安全網（2026-06-10 誤ペアリングバグ修正済み）。ただしソース正書法が一次防衛線であり、フックに頼って太字内Ωを書かない

### 攻略戦略ページ（必須セクション）
1. **目標得点設計** — 配点戦略
2. **頻出テーマ** — ヒートマップまたは頻度テーブル
3. **攻略手順** — ステップバイステップ
4. **弱点対策** — jakuten-log.mdへのリンク

### Markdown規約
- H1はページに1つ。`##` 以下で構成
- リストは `-`（`*` 不可）
- 数式: MathJax記法 `$E=IR$` / `$$P=VI\cos\theta$$`
- Admonition: `!!!`（常時表示）= 解説コンテンツ、`???`（折りたたみ）= quiz解答のみ
- Mermaid: 判定フロー・分類ツリーに使用（````mermaid` フェンシング）
- SVG: 物理的概念の図解に使用（必ず `<div>` で囲む）
- 重要度コード: `🔴` 致命的 / `🟡` 注意 / `🟢` 軽微（ひっかけセクションで使用）
- `==highlight==`: 試験頻出の数値・キーワードに適用
- `§` 記号は使用禁止（`第5条` `1.` `2.` 形式で記載）

### 日本語表記
- 「です・ます」調（戦略ページは体言止め可）
- 電験公式用語を使用（例: 電気主任技術者 ※「電気管理者」不可）
- 専門用語は初出時に英語併記（例: 力率（Power Factor））
- SI単位は半角スペース区切り
- eGov未確認の法令数値・条文は `[要確認]` フラグ必須

## Skill配置ルール

| 配置 | パス | 対象Skill |
|------|------|----------|
| グローバル | `~/.claude/skills/` | ai-architect, ai-reviewer, inbox-manager, morning-reporter |
| ローカル | `.claude/skills/` | study-coach, mkdocs-writer, wiki-deployer |

## 命名規則

- ファイル名: ケバブケース（例: `hourei-master.md`）
- ブランチ: `feature/ページ名` または `fix/修正内容`
- コミット: 日本語可。`add:`, `fix:`, `update:` プレフィックス推奨

## .secretary連携

| データ | 場所 | 方向 |
|--------|------|------|
| 学習記録・e-log | `.secretary/denken-study/` | 参照元 |
| 学習ダッシュボード | `.secretary/denken3-study-dashboard/` | 参照元 |
| 誤答パターン | `.secretary/denken-study/e-log/` | → 弱点ログへ昇格 |
| 知識整理 | `.secretary/knowledge/` | → wikiページへ昇格 |

- 編集セッションで新規参照したURL・参考文献は `_data/refs-pending.yml` に append（自動反映運用・詳細は `.claude/docs/refs-auto-reflect.md` ※トークン節約のためオンデマンド化 2026-06-13）
