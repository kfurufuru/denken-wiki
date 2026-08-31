# honest-hold punch list — ローカル機（e-Gov 到達可）で消す残件

> 生成: 2026-08-31（**Fable 反証監査の指摘を反映して再生成**）／対象 `docs/**/*.md`
> 抽出条件: `honest-hold|未照合` を含む行から、**解消済みの記録**（`解消|照合済|是正した|確定した|読み取り`）と
> **監修ログ節以降**（過去の記録）を除いたもの。**再現コマンドは末尾**。

## なぜこのファイルが要るか

PR #184 の本文は「各記事の honest-hold ボックスがそのまま punch list になっている」と書いていたが、
**測ったらそうなっていなかった**。素の grep には ①解消済みの記録が混ざる ②大半は
**同じ行に法令名が無く、何を取ってくればよいか分からない**。本ファイルはその2点を潰した実物。

**未解消 60件**。以下、**取ってくる一次資料ごと**に束ねた。1資料を引けばその束がまとめて片付く。

初版（55件）からの増分は、Fable 反証監査を受けて**未照合の明示を足した結果**（`jiko-5.md` の AND 判定・
`48.md` と `trap-patterns.md` の 1,000kW の帰属）。**債務が増えたのではなく、隠れていた債務が台帳に載った**。

## A. 電気事業法施行規則 — 17件

- `docs/articles/jigyoho/43.md:705`
    - !!! danger "honest-hold: 施行規則側の数値（2時間・7,000V・出力上限）は一次照合していない"
- `docs/articles/jigyoho/43.md:711`
    - | **7,000V以下**（外部委託の電圧上限） | R04上問1 が「受電電圧7,000V以下の保安体系」を出題（`kakomon.yml`）。ただし**条文原文とは未照合** |
- `docs/articles/jigyoho/43.md:713`
    - | **5,000kW未満 ／ 2,000kW未満 ／ 600V以下**（外部委託の規模上限） | **未照合** |
- `docs/articles/jigyoho/43.md:721`
    - | 距離 | 主たる勤務場所から **2時間以内**で到達できる範囲（**未照合**） |
- `docs/articles/jigyoho/43.md:744`
    - 設備の種別ごとに上限が異なる。**「7,000V以下」かつ規模上限**の組合せで判定する（**出力上限の数値は未照合** — 上記 honest-hold）。
- `docs/articles/jigyoho/47.md:60`
    - !!! danger "honest-hold: 別表第2 の閾値は一次照合していない"
- `docs/articles/jigyoho/47.md:67`
    - ### 発電所の認可・届出 閾値一覧（別表第2より・**未照合**）
- `docs/articles/jigyoho/48.md:56`
    - !!! danger "honest-hold: 別表第二 の閾値は一次照合していない／旧版の自己矛盾を是正"
- `docs/articles/jigyoho/48.md:57`
    - - **旧版は同じページ内で矛盾していた**。この表に「需要設備（電力規模）＝最大電力 ≥1,000kW」という届出要件の行があった一方、下の H25 問2 判定演習では「**最大電力は届出閾値ではない**」と明記していた。演習側が正しいため、**当該行を削除した**。1,000kW は**施行規則側**で出る数値で、**法第43条の本文に数値は無い**（e-Gov 実測）。施行規則側の条項は未照合。
- `docs/articles/jigyoho/48.md:64`
    - | **予備発電設備** | 出力 **≥1,000kW**（**未照合**） | 1MW 以上のディーゼル発電機 |
- `docs/articles/jigyoho/48.md:123`
    - 旧来「1,000kW」が届出閾値として教材に登場するケースがあるが、**現行施行規則 別表第二の需要設備閾値は「受電電圧10,000V以上」**。最大電力1,000kW以上 は**第48条 工事計画届出の閾値ではない**。なお 1,000kW を**法第43条（主任技術者）の数値**として覚えるのも誤りで、**第43条の本文に数値は一切ない**（e-Gov `339AC0000000170` で全5項を実測）。1,000kW が出るのは**施行規則側**だが、その条項は本 repo に一次資料が無く**未照合**。
- `docs/articles/other/koji-shi-5.md:10`
    - !!! danger "honest-hold: 第5条の項構成と罰則額は一次照合していない"
- `docs/articles/other/koji-shi-5.md:14`
    - - **「3万円以下の罰金」「免状返納命令」も未照合**。罰則の条番号・金額は本ページでは断定できない。
- `docs/reference/numbers.md:169`
    - | 自家用電気工作物の定期安全管理検査 | ==4年（〜8年）に1回==（**法第55条本文に頻度の記載は無く「主務省令で定めるところにより」の委任。頻度の典拠は施行規則側で未照合＝honest-hold**） | 電気事業法第55条（検査義務の根拠） | 保安規程に定める自主検査サイクルとの整合 |
- `docs/strategy/trap-patterns.md:154`
    - **需要設備は出力ではなく受電電圧で判定する**: 上記は**発電設備**の閾値。需要設備（工場・ビルの受変電）の届出判定軸は **受電電圧 1万V 以上** で、**最大電力 1,000kW は第48条の閾値ではない**（1,000kW が出るのは**施行規則側**。**法第43条の本文に数値は無い**ことは e-Gov で実測済みだが、施行規則側の条項は未照合）。→ [第48条](../articles/jigyoho/48.md)
- `docs/themes/kosakubutsu-bunrui.md:122`
    - ※上記以外の種別・付帯条件（ダムを伴う水力の扱い等）は施行規則の定めによる（本ページでは未照合のため記載を保留）。
- `docs/themes/kosakubutsu-bunrui.md:369`
    - - **2026-08-28 現行区分体系へ全面改稿**（Fable 一任）: 2022年改正（令和5年3月20日施行）後の4区分体系（一般用／事業用／小規模事業用／自家用）へページ全体を改稿。「小出力発電設備」→「小規模発電設備」、太陽光の一般用上限 50kW未満→10kW未満（10kW以上50kW未満は小規模事業用）、風力の全量移行を反映。第2条第18号（「蓄電」追加）・第38条・第57条・電技第2条を e-Gov 取得スナップショットで逐語照合。施行規則第48条の出力値は 38.md を正として踏襲。旧・冒頭警告ボックスは改正解説＋差分マトリクスに転用。R06下 A-1 の旧法文引用（逐

## B. 電気事業法施行令 — 6件

- `docs/articles/jigyoho/56.md:72`
    - **honest-hold**: 産業保安監督部長への**権限委任の範囲**（どちらの条文の権限がどこまで委任されているか）は**電気事業法施行令の原文と未照合**。旧版は「第56条は監督部長を含まない」と断定していたが、その根拠は確認できないため撤回した。
- `docs/articles/other/koji-shi-2.md:34`
    - !!! danger "honest-hold: 「軽微な工事」の数値（30VA・36V 等）は一次照合していない"
- `docs/articles/other/koji-shi-2.md:39`
    - - 以降の「30VA」「36V」表記には、この honest-hold が全て掛かる（各所で繰り返さない）。
- `docs/articles/other/koji-shi-2.md:137`
    - DB 対象外年度（H18〜H22）の実績は未照合のため、ここには載せません（honest-hold）。
- `docs/articles/other/koji-shi-2.md:470`
    - - イ = ==**30**==（**未照合** — 冒頭 honest-hold 参照）
- `docs/articles/other/koji-shi-2.md:474`
    - 「イ＝30」は**施行令第1条の原文と未照合**（冒頭 honest-hold）。ただし押さえるべき対比軸は数値そのものではなく **VA と A の単位の違い**——「30A（100Vなら3kVA）」と読み替えさせるのが定番のひっかけ。

## C. 電気工事士法（法・施行令・施行規則） — 3件

- `docs/articles/other/koji-shi-3.md:201`
    - DB 対象外年度（H18〜H22）の実績は未照合のため、ここには載せません（honest-hold）。
- `docs/articles/other/koji-shi-5.md:66`
    - | **根拠** | 電気工事士法第5条第3項（**項番号は未照合** — 冒頭 honest-hold） |
- `docs/articles/other/koji-shi-5.md:200`
    - DB 対象外年度（H18〜H22）の実績は未照合のため、ここには載せません（honest-hold）。

## D. 電気用品安全法（法・施行令・省令・別表） — 13件

- `docs/articles/other/pse-27.md:15`
    - - **例外**: 研究・試験目的（所定の手続を経た場合。**手続語は未照合** — 下記 honest-hold）
- `docs/articles/other/pse-27.md:32`
    - | **例外** | 研究・試験目的で、所定の手続を経た場合（**手続語は未照合**） | 第27条第2項 |
- `docs/articles/other/pse-27.md:106`
    - !!! danger "honest-hold: 例外の手続語（許可／届出／承認）は一次照合していない"
- `docs/articles/other/pse-27.md:126`
    - | **手続語** | **未照合**（許可／届出／承認のいずれかを断定しない） |
- `docs/articles/other/pse-27.md:128`
    - | **期間・記録** | **未照合**（旧版の「通常1〜2年」「使用先・用途・期間を記録」は条文根拠を確認できないため撤回） |
- `docs/articles/other/pse-27.md:139`
    - あくまで **研究・試験目的で経済産業大臣の所定の手続を経た場合のみ**（手続語は上記 honest-hold）。
- `docs/articles/other/pse-27.md:164`
    - 4. 🟡 **「表示なし品を「試験販売」と称して売ることは許可」** → 認められない。研究・試験目的で所定の手続を経た場合のみが例外（**手続語は未照合**）
- `docs/articles/other/pse-28.md:15`
    - - **例外**: 研究・試験目的（所定の手続を経た場合。**手続語は未照合** — 下記 honest-hold）
- `docs/articles/other/pse-28.md:117`
    - !!! danger "honest-hold: 例外の手続語（許可／届出／承認）は一次照合していない"
- `docs/articles/other/pse-28.md:122`
    - - **確実なのは、例外があること自体と、その目的が研究・試験・開発であること**まで。姉妹条の [第27条（販売制限）](pse-27.md) にも同じ honest-hold が掛かる。
- `docs/articles/other/pse-28.md:133`
    - | 使用場面 | 例外に当たりうる場面（**手続語は未照合**） |
- `docs/articles/other/pse-28.md:144`
    - あくまで **経済産業大臣の所定の手続が完了した場合のみ**（手続語は上記 honest-hold）。
- `docs/articles/other/pse-28.md:170`
    - 5. 🟢 **「テスト用途なら無表示品を使用できる」** → 経済産業大臣の所定の手続なしではできない（**手続語は未照合**）

## E. 電気関係報告規則 — 3件

- `docs/articles/other/jiko-4.md:65`
    - | **火力発電所** | 復水器冷却水の温度上昇（温排水） | 水温に関する基準の超過（**具体的な基準値は本環境で未照合**） |
- `docs/articles/other/jiko-5.md:146`
    - !!! warning "この4条件の AND 構造は**ページ内の論理**から導いたもので、条文原文とは未照合（honest-hold）"
- `docs/articles/other/jiko-5.md:151`
    - （蓄電所を含むか等）まではこの記述で保証しない。→ `inbox/honest-hold-punchlist-2026-08-31.md` セクションE

## G. JIS / JESC / 経産省告示 — 10件

- `docs/articles/jigyoho/43.md:712`
    - | **2時間以内**（兼任の距離要件） | **未照合**。条文ではなく告示・審査基準側にある可能性がある |
- `docs/articles/kaishaku/149.md:510`
    - 旧 v1.0（〜2026-05-09）は「**施設場所×工事種類**」（がいし引き／金属管／フロアダクト等の○×表）として執筆されていました。これは経産省告示PDF未照合のまま denken-ou.com 等の二次ソース解説を流用した結果の **完全な誤同定** で、2026-05-10 Phase D-B 監査で発見・全面書き直しに至りました。
- `docs/articles/kaishaku/159.md:209`
    - - **2026-08-29 監査是正**: 過去問実績の「H29頃／H24頃」を撤回。SoT（H23〜R07下・全247問）に解釈第159条の出題は登録が無く、実績の主張に裏付けが無かった（honest-hold）。新設ゲート `scripts/check_kakomon_citations.py` が検出。
- `docs/articles/kaishaku/192.md:23`
    - | **典拠（一次ソース）** | 電気設備の技術基準の解釈 第192条（経産省 産業保安・安全グループ電力安全課が示す省令の解釈） — 経産省ページ <https://www.meti.go.jp/policy/safety_security/industrial_safety/sangyo/electric/detail/setsubi_kijun.html> ／ ⚠ 経産省告示PDF本文は未照合（接続失敗） |
- `docs/articles/kaishaku/192.md:25`
    - | **要再確認** | 経産省PDF未照合（kakomon.yml H28問9・R05下問8 の空欄正解と denken-ou-cache.yml topic「電気さくの施設方法」からの再構築） |
- `docs/articles/kaishaku/192.md:143`
    - !!! note "[要再確認] 経産省告示PDFと未照合"
- `docs/articles/kaishaku/38.md:64`
    - !!! note "[要再確認] 経産省告示PDFと未照合"
- `docs/articles/kaishaku/38.md:218`
    - **数値検証 PASS** — 本ページに登場する数値は以下の出典で確認済み（38-1表は経産省告示PDF未照合・[要再確認]）：
- `docs/articles/kijun/67.md:252`
    - !!! note "解釈第155条 本文の取り扱い（逐語未照合）"
- `docs/themes/haisen-koji.md:219`
    - !!! warning "⚠️ R04上問4 は SoT の条番号が原典と矛盾（honest-hold）"

## H. 過去問の原本（試験センター公表問題） — 4件

- `docs/articles/kaishaku/159.md:177`
    - > 旧版は「H29頃／H24頃」という**年度も問番号も特定できない行**を実績として載せていたが、SoT に裏付けが無い。実績の主張を撤回する（honest-hold）。第156条（施設場所×工事の種類）との複合で問われる可能性は残るため、学習優先度は工事種類表と併せて判断すること。
- `docs/articles/kaishaku/164.md:88`
    - > 旧版は「R04上（問番号なし）」「H28頃」という**問番号を特定できない行**を実績として載せていたが、SoT に裏付けが無い。実績の主張を撤回する（honest-hold）。第156条の工事種類表と組み合わせて問われる可能性は残る。
- `docs/articles/kaishaku/38.md:18`
    - - **要再確認**: 経産省PDF未照合（kakomon.yml H30問6・R04下問3 と themes/hatsuhendenjo.md からの推定）
- `docs/themes/kosakubutsu-bunrui.md:254`
    - - [第38条ページ](../articles/jigyoho/38.md)の照合記録によれば、**600V・10kW・20kW・50kW** が問われた（問題文の逐語は本環境で未照合）。

## I. 電気技術者試験センターの配点公表資料 — 4件

- `docs/kakomon/ranking.md:40`
    - > **配点の内訳は未照合**: 1問あたりの配点は本 repo 収録の実問題（R04上問10=A問題6点／R05上問12=B問題14点）に基づく。
- `docs/kakomon/ranking.md:41`
    - > B問題3題の内訳が 14/14/12 か 14/13/13 かは電気技術者試験センターの公表資料と未照合のため断定しない。
- `docs/strategy/b-mondai-strategy.md:33`
    - !!! warning "配点の内訳は年度により変動する（未照合）"
- `docs/strategy/b-mondai-strategy.md:35`
    - B問題3題の内訳（14点が何題で12点が何題か）は**電気技術者試験センターの公表資料と未照合**のため断定しない。

---

## 法令ではない残件がある（PR 本文の要約の訂正）

PR 本文の「残るもの」は残件を**法令の条文原文だけ**のように書いていたが、実測すると
**H（過去問の原本）・I（試験センターの配点公表資料）**が含まれる。これらは e-Gov では解けない。

- **H** … 出題実績の主張を撤回して honest-hold にした箇所。解消には**試験センター公表の問題冊子**が要る
  （`kakomon.yml` は SoT だが、問題文の逐語までは持たない）。
- **I** … B問題の配点内訳（14/14/12 か 14/13/13 か）。repo 収録の実問題から確定しているのは
  「A問題6点・B問題14点」の2点のみ。

## 根本解（Fable 反証監査の提案・採用）

セクション A・E の債務は、**電気事業法施行規則（LawId `407M50000400077`）と
電気関係報告規則（同 `340M50000400054`）の e-Gov キャッシュを `scripts/cache/` に追加**し、
`scripts/check_law_verbatim.py` の `SOURCES` に登録すれば**まとめて逐語照合ゲートに載る**。
本環境は e-Gov が egress proxy で遮断されているため取得できない（実測 2026-08-31T14:38Z・
`curl: (56) CONNECT tunnel failed, response 403`／陽性対照 `api.github.com` は http=200）。
**ローカル機での最優先タスクはこの2ファイルの取得**。

## 再現コマンド

```bash
python3 - <<'EOF'
import re,pathlib
MARK=re.compile(r"honest-hold|未照合")
RESOLVED=re.compile(r"解消|照合済|是正した|確定した|読み取り")
for p in sorted(pathlib.Path("docs").rglob("*.md")):
    txt=p.read_text(encoding="utf-8")
    m=re.search(r"^##\s*.*監修ログ",txt,re.M)
    for i,l in enumerate((txt[:m.start()] if m else txt).splitlines(),1):
        if MARK.search(l) and not RESOLVED.search(l):
            print(f"{p}:{i}: {l.strip()[:160]}")
EOF
```

陽性対照: 上のコマンドが 0件を返したら**抽出器の故障を疑う**（本ファイル生成時点で 60件）。
