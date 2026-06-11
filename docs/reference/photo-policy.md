# 写真導入ポリシー — 受験生混同論点の視覚化

!!! note "📊 目的"
    電技解釈・省令の用語混同（電線種別・保護装置・支持物・特殊機器等）を視覚的に解消する。受験生が「**文字だけでは区別できない論点**」に写真を配置し、誤答リスクを減らす。本ポリシーは [解釈第66条 v2.3.3](../articles/kaishaku/66.md) の硬銅線写真導入（2026-05-23）を契機に策定された wiki 全体の運用ガイドライン。

| 項目 | 内容 |
|------|------|
| 文書種別 | denken-wiki 運用ポリシー（写真導入時に参照） |
| 適用範囲 | docs/articles/ 配下の全条文記事 + docs/themes/ 配下のテーマページ |
| 策定日 | 2026-05-23（古舘氏指示「受験生が間違えやすい語句、用語、考え方は写真も取り入れよう」を契機） |
| 初回適用 | [解釈第66条 セクション4 硬銅線写真（CC BY-SA 3.0）](../articles/kaishaku/66.md) |
| 関連 | [安全率マスタリファレンス](safety-factors.md)（混同論点のマスタ化アプローチの姉妹版） |

---

## 1. 写真導入の選定基準

### ✅ 写真を入れるべき論点

1. **物理形状で区別される対象**
    - 例: 木柱 vs 鉄筋コンクリート柱 vs 鉄塔／配線用遮断器 vs 漏電遮断器
2. **見た目が似ているが性質が違う対象**
    - 例: 硬銅線 vs 軟銅線（共に銅色だが加工硬化の有無で別物）／絶縁電線 vs ケーブル
3. **出題実績がある混同論点**
    - 過去問で「形状から識別」「材質から識別」を問われた論点

### ❌ 写真を入れない方がよい論点

1. **数値計算問題** — 写真より計算式・SVG模式図が効く
2. **概念的・抽象的説明** — 写真は補助にならない（例：絶縁性能・力率・有効電力）
3. **法的手続き** — 報告・届出・許可の文書手続きは表形式の方が効く
4. **回路結線説明** — SVG（回路図）が圧倒的に明瞭

### 写真 vs SVG の判定フロー

```
論点は物理形状の対比か？
├── Yes → 写真候補（実物の質感が伝わるか）
│         ├── Yes → 写真採用
│         └── No → SVG模式図
└── No → SVG（構造図・回路図・フロー図）
```

→ **理想は「SVG模式図（必須）＋ 写真（補助）」の組合せ**。kaishaku/66.md の「構造対比SVG＋実物写真」が標準パターン。

---

## 2. ライセンスポリシー（厳守）

### 必須要件

| ソース優先順位 | ライセンス | 備考 |
|---|---|---|
| **1位: Wikimedia Commons** | CC BY-SA 3.0 / 4.0 ／ Public Domain | 標準ソース。クレジット必須 |
| 2位: Unsplash | Unsplash License（CC0相当） | Wikimedia に該当画像がない場合の代替 |
| 3位: Pexels | Pexels License（CC0相当） | 同上 |
| 4位: 古舘氏オリジナル | 自著作物 | 三菱ケミカル鶴見の実設備写真は社内承認後 |

### 🚫 禁止事項

- **著作権不明・標準著作権適用のWebサイト画像** の使用禁止
- **企業ロゴ・製品写真**（メーカーカタログ等）の無断引用禁止
- **TwitterやXの画像** の引用禁止（ライセンス管理不可）
- 画像加工が必要な場合は SA（Share Alike）条項に注意

### ⚠️ 出典確認の3点チェック（pre-flight）

1. **ライセンス** — CC BY-SA / CC0 / Public Domain のいずれか
2. **著者名** — 帰属表示に必須
3. **画像内容** — タイトル/キャプションが本文と一致するか確認（用語混同サイトに注意・kaishaku/66.md の `industry.haleoahu001.com` 事例参照）

---

## 3. クレジット表記フォーマット（標準テンプレート）

### CC BY-SA 3.0/4.0 画像

```markdown
<figure markdown>
  ![代替テキスト](../../assets/images/ファイル名.jpg){ width="500" loading="lazy" }
  <figcaption>キャプション本文（受験生への解説）。画像: <a href="ソースURL" target="_blank" rel="noopener">著者名, Wikimedia Commons</a> / <a href="https://creativecommons.org/licenses/by-sa/3.0/" target="_blank" rel="noopener">CC BY-SA 3.0</a>（無改変・引用）</figcaption>
</figure>
```

### Public Domain 画像

```markdown
<figure markdown>
  ![代替テキスト](../../assets/images/ファイル名.jpg){ width="500" loading="lazy" }
  <figcaption>キャプション本文。画像: <a href="ソースURL" target="_blank" rel="noopener">タイトル</a>（Public Domain, Wikimedia Commons）</figcaption>
</figure>
```

### Unsplash / Pexels (CC0)

```markdown
<figure markdown>
  ![代替テキスト](../../assets/images/ファイル名.jpg){ width="500" loading="lazy" }
  <figcaption>キャプション本文。画像: <a href="ソースURL" target="_blank" rel="noopener">著者名 on Unsplash</a>（CC0・商用利用可・出典表示推奨）</figcaption>
</figure>
```

### 古舘氏オリジナル写真

```markdown
<figure markdown>
  ![代替テキスト](../../assets/images/ファイル名.jpg){ width="500" loading="lazy" }
  <figcaption>キャプション本文。撮影: 古舘氏（三菱ケミカル鶴見・YYYY-MM-DD・社内承認済）</figcaption>
</figure>
```

---

## 4. ファイル配置規約

### パス命名規則

```
docs/assets/images/[条文番号]-[論点キーワード].jpg
```

例:

- `docs/assets/images/66-kodousen.jpg`（解釈第66条・硬銅線）
- `docs/assets/images/14-mccb-vs-elb.jpg`（省令第14条・MCCB と ELB の対比）
- `docs/assets/images/21-cubicle.jpg`（解釈第21条・キュービクル）

### ファイル形式・サイズ

| 形式 | 用途 | サイズ目安 |
|---|---|---|
| **JPEG** | 写真（実物撮影・自然画像） | 200KB〜2MB |
| **PNG** | 図表・スクリーンショット（透過必要時） | 100KB〜1MB |
| **WebP** | 大量画像で容量削減したい場合 | 〜500KB |

mkdocs Material の `loading="lazy"` 属性で遅延読み込みされるため、1記事に複数枚あっても初期表示は速い。

### Git 管理

- 画像ファイルは **Git LFS 不使用**（denken-wiki は LFS 未設定・通常の Git で管理）
- 大容量画像（5MB超）は `mogrify -resize 1920x1920` 等で事前圧縮
- 重複画像は避け、シンボリックリンクではなくMD参照で対応

---

## 5. 1記事あたりの写真上限

| 記事種別 | 写真上限 | 理由 |
|---|---|---|
| 通常条文記事（v1.x） | **2〜3枚** | 記事肥大化防止 |
| 重要度A級の混同論点記事（v2.x〜v2.3） | **3〜5枚** | 視覚情報の充実 |
| ゴールドスタンダード級（v2.3+） | **5〜8枚** | 完全な視覚化（例: 解釈第21条候補） |
| reference 横断マスタ | **0〜10枚** | 目的次第・マトリクス中心の場合は少なめ |

→ **「写真より SVG が適切な場合は SVG 優先」**。SVG の方が情報密度高く、ライセンス問題なし。

---

## 6. retrofit 優先度判定マトリクス

既存記事に写真を追加する際の優先度。**出題頻度 × 混同リスク** でスコアリング。

### 優先度A（即時対応推奨・記事品質を底上げ）

| 記事 | 混同論点 | 出題頻度 | 候補画像 |
|---|---|---|---|
| [省令第14条](../articles/kijun/14.md) | 過電流遮断器 vs 漏電遮断器 vs 開閉器 vs MCCB | ✅4回 | MCCB写真・ELB写真（テストボタン有無） |
| [省令第57条](../articles/kijun/57.md) | 絶縁電線 vs ケーブル vs 裸電線 | ✅3回 | IV/VVF/CVT の対比写真 |
| [解釈第21条](../articles/kaishaku/21.md) | キュービクル vs さく・へい vs 柱上変圧器 | ✅4回 | キュービクル写真・柱上変圧器写真 |
| [省令第63条](../articles/kijun/63.md) | 配線用遮断器 vs 漏電遮断器 | ✅3回 | 分電盤内ブレーカー写真 |

### 優先度B（v2.0 化時に対応）

- 省令第32条 支持物の倒壊防止（木柱・鉄筋コンクリート柱・鉄塔の対比写真）
- 解釈第61条 支線の安全率（支線・控線・架空地線の対比）
- 解釈第36条 地絡遮断装置の施設（ELB 内部構造）

### 優先度C（記事新規作成時に同時整備）

- 省令第59条 機械器具の感電・火災防止
- 解釈第59条/第60条 木柱・基礎の構造
- 解釈第91条 がいし装置（懸垂がいし vs ピンがいし）

---

## 7. 監修ログへの記録（写真追加時の必須事項）

写真を追加した記事の監修ログには、以下を必ず記録する：

```markdown
- **YYYY-MM-DD vX.Y.Z 改訂**:
    - 採用画像: [`assets/images/[ファイル名].jpg`] (出典: [タイトル](ソースURL), 著者名, ライセンス)
    - 採用理由: [どの混同論点を解消するか・どの選択肢の誤答防止に効くか]
    - 代替検討: [なぜ SVG ではなく写真を選んだか・なぜこの画像か]
    - ライセンス検証: ✅ CC BY-SA 3.0 確認済 / クレジット表記 figcaption に明記
```

---

## 8. 関連ポリシー・ガイドライン

- [安全率マスタリファレンス](safety-factors.md) — 混同論点をマスタ集約する姉妹アプローチ
- [解釈第66条 v2.3.3](../articles/kaishaku/66.md) — 本ポリシーの初回適用例（硬銅線・CC BY-SA 3.0）
- denken-wiki の `.claude/docs/denken-page-creation.md` — ページ作成全体ルール
- denken-wiki の `.claude/rules/work-rules.md` — Claude Code 作業ルール

---

## 監修ログ

- **2026-05-23 v1.0 初版**:
    - **策定契機**: 古舘氏「受験生が間違えやすい語句、用語、考え方は写真も取り入れよう」（[解釈第66条 セクション4 硬銅線写真](../articles/kaishaku/66.md) 完成承認の場で指示）
    - **既存事例の参照**: kaishaku/66.md v2.3.3 で確立した「**SVG構造対比＋CC BY-SA 3.0実物写真**」の組合せパターンを wiki 全体の標準として明文化
    - **ライセンスソース確定**: Wikimedia Commons（CC BY-SA / Public Domain）を1位ソースとし、Unsplash/Pexels（CC0）を補完ソースに位置付け
    - **混同罠教材化**: 用語混同サイト（`industry.haleoahu001.com` 等のタイトル/本文矛盾事例）を pre-flight 確認の対象として明示
    - **未確認領域**: 古舘氏オリジナル写真（三菱ケミカル鶴見の実設備）の社内承認手続きフローは別途確認待ち
- **L6 システム学び**: 数値暗記の罠（feedback_law_article_number_verification・safety-factors.md）と同じ構造で、**用語混同の罠** も「視覚化（写真・SVG）＋ 一次ソース確認」で防ぐ。両者を統合した「**混同罠対策マスタ**」が今後の wiki 整備の中核

---

*最終確認: 2026-05-23 ｜ ステータス: v1.0（初版） ｜ ライセンスポリシー: ✅ Wikimedia Commons CC BY-SA / CC0 必須 ｜ クレジット表記: ✅ figcaption フォーマット標準化済 ｜ retrofit punch list: ✅ 優先度A 4本特定済 ｜ [バージョニング基準](versioning.md)*
