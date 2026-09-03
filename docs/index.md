# 電験3種 法規Wiki

> 電験3種 法規 — 条文×過去問クロスリファレンス

!!! abstract "🧭 棲み分けルール"
    **数値・暗記は [法規Wiki Hub](https://kfurufuru.github.io/secretary-portal-public/denken-hoki-wiki.html)、条文・解説・"なぜ" は本サイト**

    迷ったら：直前期は Hub から、深掘りしたい時は本サイトから。

!!! tip "🎯 動的な学習機能（進捗管理・65分タイマー・暗記カード・直前チェック・ランダム10問演習）"
    本サイトは**条文・過去問の解説（書庫）**に特化しています。
    進捗管理・**65分タイマー**・**暗記カード**・**直前チェック（数値・公式・ひっかけ）**・**間違いノート**等の**動的な学習機能**は
    [**法規Wiki Hub**](https://kfurufuru.github.io/secretary-portal-public/denken-hoki-wiki.html) でご利用ください。
    （Hub-Body責務分離：Hub=入口と進捗、Body=条文と解説）

## このWikiの目的

条文を**暗記する**のではなく、**なぜその法令が必要か**を物理・現場・法規の3層で理解する。

```
🟥 法律（電気事業法）     ← なぜ規制するのか
🟧 政令（施行令）         ← 規制の範囲
🟨 省令（技術基準）       ← 何を守るか
🟩 告示・解釈（電技解釈）  ← どうやって守るか
🟦 規格/ガイドライン（JIS等）← 具体的な数値・方法
```

---

## 🚀 合格最短ルート

### 60点を超える攻略順序（推奨学習順）

| 優先度 | テーマ | 対象ページ | 得点期待 |
|--------|--------|-----------|---------|
| 🔴 最優先 | 電気事業法の骨格（目的・保安規程・主任技術者・外部委託） | [事業法体系](themes/jigyoho-taikei.md) / [施設管理](themes/shisetsu-kanri.md) | A問題 3〜4問 |
| 🔴 最優先 | 電技・解釈の頻出条文（接地・絶縁・対地電圧） | [接地](themes/setsuchi.md) / [絶縁](themes/zetsuen.md) | A問題 2〜3問 |
| 🔴 最優先 | 分散型電源・系統連系（解釈第220条〜第232条） | [分散型電源](themes/bunsan-dengen.md) / [単独運転の防止](themes/tandoku-unten-boushi.md) | A問題 1問（ほぼ毎回） |
| 🟠 重要 | 保護装置・施設ルール | [保護装置](themes/hogo-sochi.md) / [配線工事](themes/haisen-koji.md) | A問題 2問 |
| 🟠 重要 | B問題計算（需要率・電圧降下・短絡・接地抵抗） | [計算テンプレ](reference/b-mondai-template.md) / [需要率](themes/juyoritsu-fukaritsu.md) | B問題 2〜3問 |
| 🟡 次点 | 頻出数値の総ざらい＋過去問3年分 | [数値一覧](reference/numbers.md) / [過去問](kakomon/index.md) | 仕上げ |

### 捨ててよい / 捨てにくい論点

| 判定 | 論点 | 理由 |
|------|------|------|
| 🔴 捨てにくい | 事業法（目的・保安規程・主任技術者） | 毎年2〜3問出る |
| 🔴 捨てにくい | 接地・絶縁・保護装置 | A問題の定番＋B問題にも絡む |
| 🔴 捨てにくい | B問題計算（需要率・電圧降下） | 配点が大きい |
| 🔴 捨てにくい | 分散型電源・系統連系 | 過去問SoT集計で直近19回試験中 **14** 回出題（単一テーマの再出題ランキング1位・R04下期以降は **7** 回連続で毎回出題） |
| 🟡 余裕があれば | 特殊場所 | 19回試験中 **7** 回・2〜3年に1回ペース |
| 🟢 後回しOK | PCB・サイバーセキュリティ・最新制度 | 出ても1問 |

---

## 📊 ダッシュボード

### 出題頻度 TOP5 テーマ

| 順位 | テーマ | 20年間の出題数 | 頻出度 |
|------|--------|---------------|--------|
| 1 | [電気事業法体系](themes/jigyoho-taikei.md) | 60回 | ★★★★★ |
| 2 | [電気施設管理](themes/shisetsu-kanri.md) | 53回 | ★★★★★ |
| 3 | [配線工事](themes/haisen-koji.md) | 22回 | ★★★★★ |
| 4 | [保護装置（過電流・地絡）](themes/hogo-sochi.md) | 19回 | ★★★★★ |
| 5 | [架空電線路](themes/kachiku-densen.md) | 16回 | ★★★★★ |

### クイックアクセス

| カテゴリ | リンク |
|---------|-------|
| 📍 学習の進め方を確認 | [学習システム全体マップ](reference/system-map.md) |
| 🔍 テーマ別で探す | [テーマ一覧](themes/index.md) |
| 📖 条文番号で探す | [条文一覧](articles/index.md) |
| 📝 過去問から探す | [過去問マッピング](kakomon/index.md) |
| 🔢 条文ベースで数値を確認 | [頻出数値一覧](reference/numbers.md)（暗記用は[法規Wiki Hub](https://kfurufuru.github.io/secretary-portal-public/denken-hoki-wiki.html)） |
| 🎯 攻略戦略で学ぶ | [攻略戦略](strategy/index.md) |
| 🏛️ 法体系を確認する | [法体系の全体構造](reference/hourei-taikei.md) |

---

## 📋 確認ステータス

- ✅ **確認済み**: e-Gov法令検索 + 他ネット情報 + 本Wiki の3点が一致
- ⚠️ **未確認**: 数値・条文番号の突合が未完了。e-Gov法令を正とする
- 各ページのヘッダーにステータスを表示

---


---

## 🎯 攻略戦略

合格に向けた体系的な戦略ガイドです。

| 戦略 | 概要 | ページ |
|------|------|--------|
| 攻略戦略トップ | 3つの攻略戦略、合格ライン設計、学習ロードマップ | [攻略戦略](strategy/index.md) |
| 法令マスタ | 法令階層構造、頻出条文ヒートマップ、数値プロパティ集約表 | [法令マスタ](strategy/hourei-master.md) |
| B問題メソッド化 | 8つの計算パターンをPython風メソッドで定義 | [B問題メソッド](strategy/b-mondai-method.md) |
| 弱点ログ | スプリント運用で弱点を可視化・克服 | [弱点ログ](strategy/jakuten-log.md) |

## 📚 参考文献

主要な法令原文へのリンクは [参考文献・外部リンク](reference/links.md) を参照。

| 法令 | リンク |
|------|--------|
| 電気設備技術基準（省令） | [e-Gov検索](https://laws.e-gov.go.jp/) で「電気設備に関する技術基準」を検索 |
| 電気事業法 | [e-Gov](https://laws.e-gov.go.jp/document?lawid=339AC0000000170) |
| 第三種 過去問題・解答 | [試験センター](https://www.shiken.or.jp/chief/third/qa/) |

---

## 関連システム

本Wikiは学習システムの「知識ベース」層です。全体の関係は [システムマップ](reference/system-map.md) を参照。

| システム | 役割 | リンク |
|---------|------|--------|
| **denken-wiki**（本サイト） | 条文×過去問 知識リファレンス | ここ |
| **denken3-study** | 過去問の進捗管理・達成率 | [ダッシュボード](https://kfurufuru.github.io/denken3-study/) |
| **テスト記録** | バグマップ・習熟度トラッキング | [テスト記録](https://kfurufuru.github.io/denken3-study/quiz.html) |

---

*管理者: kfurufuru | 最終更新: 2026-04-06 | v0.2*
