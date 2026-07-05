import json, subprocess, sys, os, tempfile
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "task_retrospective_check.py")

def run(assistant_text, tools=0, raw_lines=None):
    """temp transcript: `tools` 個の assistant tool_use ブロック + 最終 assistant text。
    tools: int なら Bash（読み書きしない作業 proxy）を N 個。
           list なら指定ツール名（"Edit" 等）で1個ずつ書く（v1.4 編集ゲート検証用）。
    raw_lines: transcript に生で挟む行（壊れた JSON 等の adversarial 用）。"""
    fd, path = tempfile.mkstemp(suffix=".jsonl"); os.close(fd)
    names = ["Bash"] * tools if isinstance(tools, int) else list(tools)
    with open(path, "w", encoding="utf-8") as f:
        for line in (raw_lines or []):
            f.write(line + "\n")
        for i, name in enumerate(names):
            f.write(json.dumps({"type":"assistant","message":{"content":[
                {"type":"tool_use","id":f"t{i}","name":name,"input":{}}]}}, ensure_ascii=False)+"\n")
        rec = {"type":"assistant","message":{"content":[{"type":"text","text":assistant_text}]}}
        f.write(json.dumps(rec, ensure_ascii=False)+"\n")
    payload = json.dumps({"transcript_path": path, "stop_hook_active": False})
    p = subprocess.run([sys.executable, HOOK], input=payload, capture_output=True, text=True, encoding="utf-8")
    os.unlink(path)
    return p.returncode, (p.stderr or "")

R="完了レビュー:\n  改善点: {a}\n  再発防止: {b}\n  水平展開: {c}\n  残件: {z}\n  トークン: {t}\n"
def blk(a,b,c,z="なし",t="対象なし（軽微）"):return R.format(a=a,b=b,c=c,z=z,t=t)
SKIP = "今回の学び:\n  memory_skipped: 軽微\n"

# name, text, tools, expect_exit[, raw_lines]
cases=[
 # --- v1.3 回帰（既存挙動を維持・tools=0）---
 ("1 反省3全bareなし→BLOCK",blk("なし","該当なし","なし"),0,2),
 ("2 証跡ありescape→PASS",blk("なし","なし","なし（adversarial 3問確認済）"),0,0),
 ("3 改善点実質→PASS",blk("段階発見が遅い","memory化","他repo展開"),0,0),
 ("4 トークン欠落→BLOCK(既存5ラベル)","完了レビュー:\n  改善点: 実質\n  再発防止: 実質\n  水平展開: 実質\n  残件: なし\n",0,2),
 ("5 残件/トークンなしでも反省3実質→PASS",blk("実質a","実質b","実質c","なし","対象なし"),0,0),
 ("6 全角コロン3なし→BLOCK","完了レビュー：\n  改善点：なし\n  再発防止：該当なし\n  水平展開：なし\n  残件：なし\n  トークン：対象なし\n",0,2),
 ("7 マーカー無→PASS","作業継続中。",0,0),
 ("8 『問題なし、ただし』非bare→PASS",blk("問題なし、ただし履歴残存","対応予定","展開予定"),0,0),
 # --- v1.4: マーカー3（宣言語彙）の編集事実ゲート（.secretary 版 PR #504 同原則）---
 # 9 偽陽性再現: 状況報告（前セッション成果の報告・このセッションは編集ゼロ）
 ("9 宣言のみ・編集なし(状況報告)→PASS(v1.4)","PR #479 はマージ済で、残件なしです。",["Bash","Read"],0),
 # 10 偽陽性再現: hook監査で宣言フレーズを散文言及（read-only多数＝本ファイル点検セッションの形）
 ("10 宣言語彙の散文言及・read-only大量→PASS(v1.4)",
  "この hook は「すべて完了」という語彙で発火します。偽陽性リスクがあります。",["Read","Grep"]*10,0),
 # 11 真陽性回帰: 実編集セッションで宣言のみ・レビュー無（v1.1 denken-wiki事案の形）
 ("11 編集あり+宣言のみ→BLOCK(真陽性回帰)","修正しました。残作業はありません。",["Edit","Bash"],2),
 # 12 編集あり+宣言+完備レビュー→PASS（正規の完了報告）
 ("12 編集あり+宣言+完備レビュー→PASS","すべて完了。\n"+blk("段階発見が遅い","ゲートをテスト固定","他hookへ展開"),["Write"],0),
 # 13 fence内の宣言だけ+編集あり→PASS（fence strip回帰）
 ("13 fence内宣言のみ+編集あり→PASS","例:\n```\nすべて完了。残件なし\n```\n作業中です。",["Edit"],0),
 # 14 見出しマーカーはゲート外: 編集なしでも「学び:」見出しはschema検証→BLOCK
 ("14 編集なし+学び見出し+レビュー無→BLOCK(ゲート外)",SKIP,["Read"],2),
 # 15 adversarial: NotebookEdit も編集系として拾う
 ("15 NotebookEdit+宣言のみ→BLOCK","対応済み。残件: なし",["NotebookEdit"],2),
 # 16 adversarial: valid JSON だが非dict行 ["x"] + 編集 + 宣言 → クラッシュせず BLOCK（fail-open）
 ("16 非dict-json行+Edit+宣言のみ→BLOCK","全件完了です。",["Edit"],2,
  ['["unexpected","shape"]']),
 # 17 adversarial: message 非dict + 編集 + 宣言 → クラッシュせず BLOCK
 ("17 message非dict+Edit+宣言のみ→BLOCK","全件完了です。",["Edit"],2,
  ['{"type":"assistant","message":"not-a-dict"}']),
 # 18 adversarial: 壊れ行のみ+編集なし+宣言 → PASS（判定不能は発火しない側に倒す・クラッシュなし）
 ("18 壊れ行のみ+編集なし+宣言→PASS","全件完了です。",0,0,
  ['{broken json', '["unexpected","shape"]']),
]
ok=0
for case in cases:
    name,text,tools,exp = case[:4]
    rc,err = run(text, tools, case[4] if len(case) > 4 else None)
    s = "PASS" if rc==exp else "FAIL"; ok += rc==exp
    print(f"[{s}] {name} (exit={rc} exp={exp})")
    if rc!=exp and err:
        print("   stderr:", err.replace("\n"," ")[:160])
print(f"{ok}/{len(cases)} PASS")
sys.exit(0 if ok==len(cases) else 1)
