# kakomon.yml 監査の効率化アーキ提案

**目的**: 「次回は洗い出しに時間・トークン消費しないやり方」を実現する4層アーキ設計。AI関与を「異常検出時のみ」に最小化する。

## 現状コスト（今回の監査）

| 項目 | 値 |
|------|-----|
| 全件監査時間 | ~8分（247件 × 2秒） |
| 部分監査時間 | ~1分（30件） |
| AI トークン | スクリプト実行はurllib直結なので **0** |
| AI コンテキスト | 結果サマリ読込 ~500トークン |
| 人間の手間 | バックグラウンド実行＋結果確認 |

**ボトルネック**: AIトークンではなく **wallclock時間**（同期待ち）と**実行頻度の判断コスト**（いつ走らせるか）。

## 改善後アーキ（4層・AI関与最小化）

```
┌────────────────────────────────────────────────────┐
│ Layer 1: 永続キャッシュ                              │
│ _data/denken-ou-cache.yml                          │
│ → 全247件の denken-ou.com 条文番号を1度だけ取得保存  │
│ → 改正がない限り再取得不要（電技解釈は数年に1回改正）  │
└────────────────────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ Layer 2: pre-commit hook（ローカル・即時）           │
│ .git/hooks/pre-commit                              │
│ → kakomon.yml の変更行を抽出                        │
│ → キャッシュと突合し不一致あれば commit を拒否       │
│ コスト: 1秒未満 / コミット、AIトークン 0             │
└────────────────────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ Layer 3: 月次 GitHub Actions（サーバ側・自動）       │
│ .github/workflows/audit-kakomon.yml                │
│ → 月初に audit_kakomon.py --all を実行              │
│ → キャッシュ更新                                     │
│ → 不一致があれば GitHub Issue を自動作成             │
│ コスト: GitHub Actions無料枠内、AIトークン 0         │
└────────────────────────────────────────────────────┘
                       ↓
┌────────────────────────────────────────────────────┐
│ Layer 4: morning-reporter 統合                      │
│ 朝のブリーフィング時に open issue を1行通知         │
│ AI関与: issueがある時のみ（例: 月1回・数百トークン）  │
└────────────────────────────────────────────────────┘
```

## 期待効果

| 指標 | 現状 | 改善後 |
|------|------|--------|
| 監査トリガ | 手動（忘れがち） | 自動（月次cron） |
| 私（AI）の関与 | 毎回 | 異常検出時のみ |
| Wallclock | 都度8分 | 0秒（Actions側で完結） |
| AIトークン消費 | 結果読込500/回 | 0（issueがある時のみ数百） |
| 漏れリスク | 高（忘却） | 低（強制実行） |
| 法令改正検出 | 手動 | キャッシュ vs 最新 で自動検出 |

## 実装計画（合計~40分）

### Step 1: キャッシュ生成（10分・初回のみ）

```bash
python scripts/audit_kakomon.py --all --json _data/denken-ou-cache.yml
```

審査完了後、フォーマットを yaml に変換して `_data/denken-ou-cache.yml` に保存。

### Step 2: pre-commit hook（15分）

`scripts/precommit-kakomon.py` を新規作成：
- git diff で kakomon.yml の変更行を抽出
- 各変更エントリのarticle番号 vs キャッシュを照合
- 不一致なら `sys.exit(1)` でコミット拒否

`.git/hooks/pre-commit` に登録（または `.pre-commit-config.yaml` 経由）。

### Step 3: GitHub Actions（10分）

`.github/workflows/audit-kakomon.yml`:
- `schedule: cron: '0 0 1 * *'`（月初0:00 UTC）
- `audit_kakomon.py --all` 実行
- 不一致があれば `gh issue create --title "kakomon監査不一致 N件"` で自動作成
- キャッシュ更新分は PR で人間レビュー

### Step 4: morning-reporter統合（5分）

`.secretary/skills/morning-reporter` に「denken-wikiの open audit issue を1行通知」を追加。GitHub CLI経由で `gh issue list` を読み取り、件数のみ報告。

## 追加メリット（副次効果）

1. **電技解釈改正の自動検知**: 月次でキャッシュと最新を比較するため、改正による条番号変更を即座に発見できる
2. **新規ページ作成の高速化**: 条文ページ作成時、キャッシュをローカル参照すれば denken-ou.com への都度アクセス不要（denken-page-creation.md の Step2 が瞬時化）
3. **kakomon.yml 編集ミスの即時検知**: pre-commit で防がれるので「マージ後気づく」を防止

## トレードオフ（注意点）

| トレードオフ | 対策 |
|-------------|------|
| キャッシュが古くなる | 月次更新で対処、TTL 管理不要 |
| denken-ou.com の構造変更 | テストで保護、scriptでretry/エラーログ |
| GitHub Actionsの月次実行コスト | 約5分実行 = 無料枠内（月2000分） |
| pre-commit が遅いとUX低下 | キャッシュ参照のみなので 0.1 秒以下 |

## 推奨実装順

優先度A: **Step 1（キャッシュ生成）+ Step 2（pre-commit）**
→ ローカル完結で即効性高い。GitHub Actions無しでも70%の価値を確保

優先度B: **Step 3（GitHub Actions）**
→ 完全自動化。法令改正検出までカバー

優先度C: **Step 4（morning-reporter）**
→ UI改善。issueがあれば気づく仕組み

## 結論

**「監査を実行するタスク」自体を AI から分離**し、cron+hookで自走化する。AIの仕事は「異常があった時の意思決定（修正方針）」だけにする。これが時間・トークン消費を最小化する根本解。

次回 GO がもらえたら Step 1+2 から実装します。
