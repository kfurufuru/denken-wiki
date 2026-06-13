import json, subprocess, sys, os, tempfile
HOOK = os.path.join(os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else ".", "task_retrospective_check.py")
HOOK = "task_retrospective_check.py"
def run(t):
    fd,p=tempfile.mkstemp(suffix=".jsonl");os.close(fd)
    open(p,"w",encoding="utf-8").write(json.dumps({"type":"assistant","message":{"content":[{"type":"text","text":t}]}},ensure_ascii=False)+"\n")
    r=subprocess.run([sys.executable,HOOK],input=json.dumps({"transcript_path":p}),capture_output=True,text=True,encoding="utf-8")
    os.unlink(p);return r.returncode
R="完了レビュー:\n  改善点: {a}\n  再発防止: {b}\n  水平展開: {c}\n  残件: {z}\n  トークン: {t}\n"
def blk(a,b,c,z="なし",t="対象なし（軽微）"):return R.format(a=a,b=b,c=c,z=z,t=t)
cases=[
 ("1 反省3全bareなし→BLOCK",blk("なし","該当なし","なし"),2),
 ("2 証跡ありescape→PASS",blk("なし","なし","なし（adversarial 3問確認済）"),0),
 ("3 改善点実質→PASS",blk("段階発見が遅い","memory化","他repo展開"),0),
 ("4 トークン欠落→BLOCK(既存5ラベル)","完了レビュー:\n  改善点: 実質\n  再発防止: 実質\n  水平展開: 実質\n  残件: なし\n",2),
 ("5 残件/トークンなしでも反省3実質→PASS",blk("実質a","実質b","実質c","なし","対象なし"),0),
 ("6 全角コロン3なし→BLOCK","完了レビュー：\n  改善点：なし\n  再発防止：該当なし\n  水平展開：なし\n  残件：なし\n  トークン：対象なし\n",2),
 ("7 マーカー無→PASS","作業継続中。",0),
 ("8 『問題なし、ただし』非bare→PASS",blk("問題なし、ただし履歴残存","対応予定","展開予定"),0),
]
ok=0
for n,t,e in cases:
    rc=run(t); s="PASS" if rc==e else "FAIL"; ok+= rc==e
    print(f"[{s}] {n} (exit={rc} exp={e})")
print(f"{ok}/{len(cases)} PASS")
sys.exit(0 if ok==len(cases) else 1)
