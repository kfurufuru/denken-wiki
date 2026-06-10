# 参考文献・外部リンク

> 法令原文・試験情報・技術規格・eGov API 罠ガイドへの公式リンク集。数値や条文の確認はここから。2026-05-10 リファクタで7セクション構造へ再編。

---

## 1. 法令原文（一次ソース）

> このセクションでは、電験3種試験範囲をカバーする法律・政令・省令の eGov 直リンクを5系統に分けて掲載する。

### 1.1 電気事業法系

| 法令名 | LawId | eGov リンク | API 直リンク | 備考 |
|--------|-------|------------|------------|------|
| 電気事業法 | 339AC0000000170 | [eGov](https://laws.e-gov.go.jp/law/339AC0000000170/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/339AC0000000170) | 第38条〜第57条が試験範囲の中心 |
| 電気事業法施行令 | 340CO0000000206 | [eGov](https://laws.e-gov.go.jp/law/340CO0000000206/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/340CO0000000206) | 昭和40年政令第206号。事業区分・自家用工作物等の細則 |
| 電気事業法施行規則 | 407M50000400077 | [eGov](https://laws.e-gov.go.jp/law/407M50000400077/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/407M50000400077) | 電圧維持義務・届出様式・主任技術者免状区分等 |

**個別条文の重要アンカー（電気事業法施行規則 LawId 407M50000400077）**:

| 条文 | 内容 | 試験での頻出度 |
|------|------|--------------|
| 第50条 | 保安規程の記載事項（自家用電気工作物） | ★★★★★ |
| 第56条 | 主任技術者免状の電圧範囲・出力範囲 | ★★★★★ |
| 第96条 | 4年に1回の絶縁耐力検査・自主検査 | ★★★★☆ |

!!! tip "施行令と施行規則の見分け方"
    LawId 末尾が `CO` = 政令（Cabinet Order）／`M50000400` = 経済産業省令。試験で「政令で定める」と書かれていれば施行令、「経済産業省令で定める」と書かれていれば施行規則を見ること。

### 1.2 電気設備技術基準系

| 法令名 | LawId | eGov リンク | API 直リンク | 備考 |
|--------|-------|------------|------------|------|
| 電気設備に関する技術基準を定める省令 | **409M50000400052** | [eGov](https://laws.e-gov.go.jp/law/409M50000400052/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/409M50000400052) | 平成9年通商産業省令第52号（旧 337M50000400052 は廃止） |
| 電気設備の技術基準の解釈（最新PDF） | — | [経産省PDF](https://www.meti.go.jp/policy/safety_security/industrial_safety/law/files/dengikaishaku.pdf) | — | 第1条〜第218条＋220条系。**eGov 未登録のためローカルPDFキャッシュ必須**（後述） |
| 電気設備の技術基準の解釈（最新改正情報） | — | [経産省お知らせ](https://www.meti.go.jp/policy/safety_security/industrial_safety/oshirase/2025/11/20251120-2.html) | — | 令和6年11月改正案内 |

!!! warning "旧 LawId 337M50000400052 を引用しない"
    監査エージェントが旧 LawId（337M50000400052・昭和40年）を現行（409M50000400052・平成9年全部改正）と取り違えるケースが多発（2026-05-10 監査時）。**LawId は必ず409始まり**。eGov で旧 ID を叩くと404を返す（または旧テキストで誤情報）。

**発電用5技術基準を定める省令**（系統別の独立省令）:

| 法令名 | LawId | eGov リンク | API 直リンク |
|--------|-------|------------|------------|
| 発電用火力設備に関する技術基準を定める省令 | 409M50000400051 | [eGov](https://laws.e-gov.go.jp/law/409M50000400051/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/409M50000400051) |
| 発電用水力設備に関する技術基準を定める省令 | 409M50000400050 | [eGov](https://laws.e-gov.go.jp/law/409M50000400050/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/409M50000400050) |
| 発電用太陽電池設備に関する技術基準を定める省令 | 503M60000400029 | [eGov](https://laws.e-gov.go.jp/law/503M60000400029/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/503M60000400029) |
| 発電用風力設備に関する技術基準を定める省令（風技省令） | 409M50000400053 | [eGov](https://laws.e-gov.go.jp/law/409M50000400053/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/409M50000400053) |
| 発電用原子力設備に関する技術基準を定める命令 | 340M50000400062 | [eGov](https://laws.e-gov.go.jp/law/340M50000400062/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/340M50000400062) |

!!! note "発電用5技術基準の構造"
    省令第52条（一般電気工作物・自家用電気工作物）と並列で5系統の発電設備独自の技術基準が存在する。電験3種では火力・水力・風力・太陽電池の4本が出題対象（原子力は出題対象外だが念のためリンク掲載）。

### 1.3 電気工事士・工事業系

| 法令名 | LawId | eGov リンク | API 直リンク | 備考 |
|--------|-------|------------|------------|------|
| 電気工事士法 | 335AC0000000139 | [eGov](https://laws.e-gov.go.jp/law/335AC0000000139/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/335AC0000000139) | 第一種・第二種電気工事士の作業範囲 |
| 電気工事士法施行令 | 335CO0000000260 | [eGov](https://laws.e-gov.go.jp/law/335CO0000000260/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/335CO0000000260) | 昭和35年政令第260号 |
| 電気工事士法施行規則 | 335M50000400097 | [eGov](https://laws.e-gov.go.jp/law/335M50000400097/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/335M50000400097) | 軽微な工事・特殊電気工事 |
| **電気工事業の業務の適正化に関する法律** | **345AC1000000096** | [eGov](https://laws.e-gov.go.jp/law/345AC1000000096/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/345AC1000000096) | 通称「電気工事業法」。登録電気工事業者・主任電気工事士 |
| 電気工事業の業務の適正化に関する法律施行令 | 345CO0000000327 | [eGov](https://laws.e-gov.go.jp/law/345CO0000000327/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/345CO0000000327) | — |
| 電気工事業の業務の適正化に関する法律施行規則 | 345M50000400103 | [eGov](https://laws.e-gov.go.jp/law/345M50000400103/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/345M50000400103) | 帳簿記載事項・標識掲示 |

!!! warning "電気工事業法の LawId は AC1（AC0 ではない）"
    `345AC1000000096` の `AC1` は法律で正式な記号体系。`AC0` で叩くと404。本リポジトリ内の旧記述で `345AC0000000096` と書かれている箇所は誤記（2026-05-10 監査で発覚・要訂正対象）。

### 1.4 報告・公害系

| 法令名 | LawId | eGov リンク | API 直リンク | 備考 |
|--------|-------|------------|------------|------|
| 電気関係報告規則 | 340M50000400054 | [eGov](https://laws.e-gov.go.jp/law/340M50000400054/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/340M50000400054) | 事故報告（速報24時間／詳報30日） |
| **特定工場における公害防止組織の整備に関する法律**（公害防止組織法） | **346AC0000000107** | [eGov](https://laws.e-gov.go.jp/law/346AC0000000107/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/346AC0000000107) | 特定工場での公害防止管理者・統括者の選任義務 |

### 1.5 電気用品安全法系

| 法令名 | LawId | eGov リンク | API 直リンク | 備考 |
|--------|-------|------------|------------|------|
| 電気用品安全法 | 336AC0000000234 | [eGov](https://laws.e-gov.go.jp/law/336AC0000000234/) | [API v1](https://laws.e-gov.go.jp/api/1/lawdata/336AC0000000234) | PSEマーク・特定電気用品 |

- [電気設備の技術基準の解釈の解説（令和6年10月22日改正・最新版）](https://www.meti.go.jp/policy/safety_security/industrial_safety/sangyo/electric/files/20241022-3.pdf) — 上記H30版の最新差し替え。解釈条番号・条見出しの現行確認はこの令和6年版を優先する
- [電気設備の技術基準の解釈の解説（平成30年10月1日改正）第1章 総則](https://www.meti.go.jp/policy/safety_security/industrial_safety/oshirase/2018/09/300928-5.pdf) — 解釈の各条 条見出し【】と解説本文が一次ソース。第2節「電線」3〜12条（裸電線等/絶縁電線/多心型電線/コード/キャブタイヤケーブル/各ケーブル）の現行タイトル照合に必須。経産省告示PDF本体は重く取得困難だが、本『解説』は条見出しを明示しており条番号監査に有用
---

## 2. 経産省告示・通達

> このセクションでは、eGov に登録されない告示・通達のうち電験3種で参照頻度が高いものを掲載する。

| 文書名 | リンク | 備考 |
|--------|--------|------|
| 電気設備の技術基準の解釈（最新PDF） | [経産省PDF](https://www.meti.go.jp/policy/safety_security/industrial_safety/law/files/dengikaishaku.pdf) | 第1条〜第218条＋220条系。告示扱いのため eGov 未収載 |
| 電気設備技術基準・解釈の最新改正情報 | [経産省お知らせ](https://www.meti.go.jp/policy/safety_security/industrial_safety/oshirase/2025/11/20251120-2.html) | 令和6年11月改正 |
| 産業保安・電力安全 トップ | [経産省](https://www.meti.go.jp/policy/safety_security/industrial_safety/) | 全告示・通達のハブ |

!!! warning "告示は eGov に登録されない → ローカルPDFキャッシュ必須"
    電技解釈は経済産業省告示扱いで eGov 法令データベースには登録されていない。**経産省PDFを scripts/cache/ にダウンロードして照合に使う運用が必須**。PDFのURL（`dengikaishaku.pdf`）は同一URLで上書き更新されるため、改正の都度 `wget` し直す。

---

## 3. 民間規程・技術規格（解釈で参照される）

> このセクションでは、解釈条文中で「○○規程による」と参照される民間規格・規程・技術規格をまとめる。

| 規程名 | 発行団体 | 内容 | 試験での参照箇所 |
|--------|---------|------|----------------|
| **JEAC 9701 系統連系規程** | 日本電気協会（JEAC） | 分散型電源の系統連系の技術要件 | 解釈第220条系の根拠（[JEAC情報](https://www.denki.or.jp/)） |
| **JESC（日本電気技術規格委員会）** | JESC | 電気技術規格の認定機関 | 解釈第220条系（分散型電源・スポットネットワーク等）で頻出参照（[JESC](https://www.jesc.gr.jp/)） |
| JEM | 日本電機工業会 | 電気機器規格 | キュービクル・受電設備関連 |
| IEC 60479 | IEC（国際電気標準会議） | 人体への電流の影響 | 感電の物理的背景（Level 2） |
| JIS C 60364 | 日本産業規格 | 低圧電気設備の設計・施工 | 接地方式（TT/TN/IT）の出題あり |
| JIS A 4201 | 日本産業規格 | 建築物等の雷保護 | 避雷器関連で参照 |
| JIS C 4620 | 日本産業規格 | キュービクル式高圧受電設備 | 施設管理の出題で登場 |

- [JEAC 9701 系統連系規程](https://www.denki.or.jp/JEAC9701) — 解釈第220条系の『直流流出防止』の実規定はJEACに集約されている可能性
---

## 4. 試験情報・過去問・学習リソース

> このセクションでは、公式試験情報・過去問解説サイト・学習リソース（解説記事・教材）を掲載する。

### 4.1 公式（試験センター）

| サイト | URL | 内容 |
|--------|-----|------|
| 電気技術者試験センター（ECEE） | [shiken.or.jp](https://www.shiken.or.jp/) | 試験日程・申込・合格発表 |
| 第三種 過去問題と解答 | [ECEE 過去問](https://www.shiken.or.jp/chief/third/qa/) | **公式の問題用紙・模範解答 PDF直リンク**（H23〜R07上下 19年分・年度別アンカー） |
| 試験情報 | [ECEE 受験案内](https://www.shiken.or.jp/shiken/) | 受験案内・日程 |

### 4.2 解説サイト

| サイト | URL | 特徴 |
|--------|-----|------|
| 電験王 | [denken-ou.com](https://denken-ou.com/) | 過去問解説。本Wikiでは解説文を引用しない（著作権配慮）。URL パターン: `houkir{年}-{期}-{問}` |
| **過去問.com 第三種電気主任技術者** | [kakomonn.com/denken3/](https://kakomonn.com/denken3/) | 過去問複数年度横断検索。denken-ou.com の404補完用 |
| 電気の神髄 | [shimatake-web.com](https://shimatake-web.com/) | 実務寄りの解説が豊富 |
| 電験 法規解説（joho.info） | [denken.joho.info](https://denken.joho.info/) | 法規分野の体系・条文解説。電気事業法の法令ピラミッドや電技解釈の位置づけが整理されている |

!!! warning "過去問解説は複数ソース併用"
    denken-ou.com 単独依存は404多発のため避ける（2026-05 監査時）。`過去問.com` および `公式PDF` を併用して照合する運用が必須。

!!! warning "著作権に関する注意"
    本Wikiでは過去問の問題文は試験センター公式のものを参照し、解説はすべて独自に作成しています。他サイトの解説文をコピー・転載することはありません。

- [電験王3 H23 法規 問3（電気設備の保安原則・穴埋）](https://denken-ou.com/houkih23-3/) — 空欄（電位上昇/接地/大地に通ずる）の根拠が省令第10条・第11条と確定した一次解説。R07下問3の再出題元。audit_kakomon.py が未対応の平成年度URLパターン houkih{N}-{問} が実在する実証例（将来のbuild_url拡張候補）
- [電験王3 H23 法規 問4（電線の接続・論説）](https://denken-ou.com/houkih23-4/) — 解釈第12条が論説の誤選択肢（20%→25%・例外『含め』）として出題された実例。改変なしの過去問引用元として使用

- [電気設備技術基準・解釈 目次（令和2年度版・電気の真髄）](https://denki-no-shinzui.com/wp-content/uploads/2019/02/%E9%9B%BB%E6%B0%97%E8%A8%AD%E5%82%99%E6%8A%80%E8%A1%93%E5%9F%BA%E6%BA%96%E3%83%BB%E8%A7%A3%E9%87%88_%E4%BB%A4%E5%92%8C2%E5%B9%B4%E5%BA%A6%E7%89%88.pdf) — 省令と解釈の目次を一覧化。解釈の第3節=電路の絶縁及び接地(13〜19条)・第4節=電気機械器具の保安原則(20〜31条)の節構成確認に有用（ただし解釈1〜12条は省略されている点に注意）

- [日本電気技術者協会 解説〔その3〕電線と高圧・特別高圧機器の施設](https://jeea.or.jp/course/contents/11103/index_small.html) — 解釈第5条=絶縁電線・第12条=電線の接続・第21/22条=高圧/特別高圧機器施設を条番号付きで明記。条見出し監査の二次照合に有用
---

## 5. 法改正トラッキング

> このセクションでは、電験3種試験範囲の法令改正を継続的に追跡する一次ソースをまとめる。

| ソース | URL | 用途 |
|--------|-----|------|
| 経産省「電気事業法等の改正について」 | [METI 改正情報](https://www.meti.go.jp/policy/safety_security/industrial_safety/) | 法律・省令・告示の最新改正のハブ |
| denken-wiki 法令改正トラッキング（内部） | [hourei-kaisei.md](hourei-kaisei.md) | 試験範囲に絞った改正履歴 |
| JESC 改正情報 | [jesc.gr.jp/revision/](https://www.jesc.gr.jp/) | 民間規程改正（解釈第220条系の根拠） |

---

## 6. ツール・API

> このセクションでは、本リポジトリで一次ソース照合に使う eGov API・ローカルキャッシュ・監査スクリプトをまとめる。

### 6.1 eGov 法令API（罠注意）

**API ベースURL**:

```
https://laws.e-gov.go.jp/api/1/lawdata/<LawId>
```

例: `https://laws.e-gov.go.jp/api/1/lawdata/409M50000400052`（電気設備技術基準）

!!! warning "eGov API の4大罠"
    1. **罠1: API バージョン**  
       v1 (`/api/1/`) が現行で確実に動く。v2 (`/api/2/`) はエンドポイントが異なり (`law_data` 等) 単純に叩くと 404 を返すケースあり。**スクリプトは v1 を既定に**。
    2. **罠2: MainProvision vs SupplProvision**  
       XML パース時、`MainProvision`（本則）と `SupplProvision`（附則）の両方に同一番号の条文が出現するケースあり。**MainProvision のみに絞ってパースする**こと（混在で「同じ条文が2つある」誤検出になる）。
    3. **罠3: 旧 LawId と現行 LawId**  
       電気設備技術基準は旧 `337M50000400052`（昭和40年）→ 現行 `409M50000400052`（平成9年全部改正）。旧 ID で叩くと404または旧テキスト（既廃止内容）が返る。同様に他の電力系省令も平成9年全部改正で 4XX 系番号に切り替わっている。
    4. **罠4: ArticleCaption の有無**  
       第38条等は `ArticleCaption` が空欄で、第50条等は `（保安規程）` のように括弧書き付き。`audit_kakomon.py` 等で ArticleCaption を必須前提でパースすると空欄条文を見逃すので、フォールバックとして ArticleTitle を使うこと。

**LawId 体系**:

| 接尾記号 | 種別 | 例 |
|---------|------|-----|
| `AC0` / `AC1` | 法律（Act） | 339AC0000000170（電気事業法）、345AC1000000096（電気工事業法） |
| `CO` | 政令（Cabinet Order） | 340CO0000000206（電気事業法施行令） |
| `M50000400` | 経済産業省令 | 407M50000400077（電気事業法施行規則） |
| `M50000400000` 等 | 各省令（先頭4桁が省コード） | 厚労省・国交省等 |
| `M60000400` | 令和の経産省令 | 503M60000400029（太陽電池設備技術基準） |

### 6.2 ローカルキャッシュ一覧

法令本文のローカルキャッシュを `scripts/cache/` 配下に配置する。eGov API レート制限・オフライン照合・改正前テキスト保全のため。

| LawId | 法令名 | キャッシュパス | 取得日 |
|-------|--------|--------------|--------|
| 409M50000400052 | 電気設備に関する技術基準を定める省令 | `scripts/cache/egov-409M50000400052.xml` | 2026-05-03 |
| 339AC0000000170 | 電気事業法 | （未配置） | — |
| 407M50000400077 | 電気事業法施行規則 | （未配置） | — |
| 340CO0000000206 | 電気事業法施行令 | （未配置） | — |
| 340M50000400054 | 電気関係報告規則 | （未配置） | — |
| 335AC0000000139 | 電気工事士法 | （未配置） | — |
| 345AC1000000096 | 電気工事業法 | （未配置） | — |
| 336AC0000000234 | 電気用品安全法 | （未配置） | — |
| — | 電気設備の技術基準の解釈（経産省PDF） | （未配置・PDF配置必須） | — |

!!! tip "キャッシュ取得コマンド"
    ```bash
    # eGov API から XML をダウンロード（例: 電気事業法）
    curl -o scripts/cache/egov-339AC0000000170.xml \
      https://laws.e-gov.go.jp/api/1/lawdata/339AC0000000170
    ```

### 6.3 監査スクリプト

本リポジトリの一次ソース照合・整合性チェックに使うスクリプト群。

| スクリプト | 用途 |
|-----------|------|
| `wiki_check.py` | 第N条記法・placeholder（要確認等）検出 |
| `wiki_quality_check.py` | v3.1 スコアリング（18項目3軸＋重大欠陥cap6種・S/A/B/C/D判定） |
| `scripts/audit_frequency.py` | kijun 出題頻度（★数）と kakomon.yml 件数の整合 |
| `scripts/check_frequency_consistency.py` | メタ記載と手書きテーブルの矛盾検出 |
| `scripts/audit_kaishaku_titles.py` | kaishaku H1 と index の整合 |
| `scripts/audit_kakomon.py` | 過去問外部照合（denken-ou.com キャッシュ） |
| `scripts/check_law_citations.py` | 法令引用整合（条番号・タイトル） |
| `scripts/check_kakomon_consistency.py` | md 内テーブル ↔ by-field.md 整合 |
| `scripts/precommit_kakomon.py` | pre-commit hook（kakomon.yml キャッシュ照合・0トークン） |
| `scripts/precommit_evidence_check.py` | pre-commit hook（数値検証 PASS の根拠列必須化） |

---

## 7. ローカル成果物

> このセクションでは、denken-wiki と連携する学習システム・GitHub リポジトリへのリンクをまとめる。

| 成果物 | URL | 役割 |
|--------|-----|------|
| 学習進捗ダッシュボード | [denken3-study](https://kfurufuru.github.io/denken3-study/) | 過去問の進捗管理・達成率・弱点マップ |
| テスト記録ダッシュボード | [テスト記録](https://kfurufuru.github.io/denken3-study/quiz.html) | バグマップ・レビュー予定 |
| 全体マップ | [システムマップ](system-map.md) | 3つの学習システムの関係図 |
| GitHub リポジトリ | [kfurufuru/denken-wiki](https://github.com/kfurufuru/denken-wiki) | 本Wiki のソース |

---

## このWikiについて

| 項目 | 内容 |
|------|------|
| 管理者 | Furutachi |
| リポジトリ | [GitHub](https://github.com/kfurufuru/denken-wiki) |
| ライセンス | 個人学習用 |
| ビルド | MkDocs Material + GitHub Pages |
| 数値の正確性 | eGov 法令を正とする。✅ = 3点確認済み / ⚠️ = 未確認 |

---

!!! note "役に立った参考文献の追加ルール"
    今後の編集で新規参照したURLは `_data/refs-pending.yml` に追記し、`scripts/merge_refs.py` で本ページに反映する運用とする（半自動マージ）。直接編集は最小限にし、追記漏れを防ぐ。

*最終更新: 2026-06-11（セクション3を「民間規程・技術規格」/セクション4を「試験情報・過去問・学習リソース」へ見出し拡張＝refs カテゴリ照合先の整備・issue #58／AC0 誤記 LawId の重複 bullet を削除。前回: 2026-05-10 リファクタで7セクション構造へ再編）*
