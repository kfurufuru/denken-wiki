#!/usr/bin/env python
"""destructive_block_check.py の self-test（9ケース・回帰ガード）.

Stop hook の偽陽性は全セッションの送信をブロックする事故になるため、
hook 変更時は必ず本テストを実行する:
    python .claude/hooks/tests/test_destructive_block_check.py
"""
import json
import os
import subprocess
import sys
import tempfile

HOOK = os.path.join(os.path.dirname(__file__), "..", "destructive_block_check.py")

FENCE = "```"


def run_case(name, assistant_text, expect_rc, stop_hook_active=False, raw_lines=None):
    with tempfile.NamedTemporaryFile(
        "w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as f:
        for line in (raw_lines or []):
            f.write(line + "\n")
        f.write(
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [{"type": "text", "text": assistant_text}]
                    },
                }
            )
            + "\n"
        )
        path = f.name
    try:
        payload = json.dumps(
            {"transcript_path": path, "stop_hook_active": stop_hook_active}
        )
        r = subprocess.run(
            [sys.executable, HOOK],
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        ok = r.returncode == expect_rc
        print(f"{'PASS' if ok else 'FAIL'}: {name} (rc={r.returncode}, expect={expect_rc})")
        if not ok and r.stderr:
            print("  stderr:", r.stderr[:200])
        return ok
    finally:
        os.unlink(path)


def main() -> int:
    results = []

    # 1. bare 破壊 block（今回の実事故の形・git -C 挟み）→ ブロック
    results.append(run_case(
        "bare destructive block (incident form)",
        f"不要なら以下で破棄:\n{FENCE}\ngit -C C:\\repo stash drop; git -C C:\\repo branch -D fix/old\n{FENCE}\n",
        2,
    ))

    # 2. 読み取り block 先行（2分割プロトコル準拠）→ 通過
    results.append(run_case(
        "inspection block precedes destructive block",
        f"①消える対象を確認:\n{FENCE}\ngit stash show -u --stat\n{FENCE}\n①の出力を見てから②:\n{FENCE}\ngit stash drop\n{FENCE}\n",
        0,
    ))

    # 3. text fence の例示 → 通過
    results.append(run_case(
        "educational example in text fence",
        f"危険な例:\n{FENCE}text\nrm -rf / と git reset --hard は破壊的\n{FENCE}\n",
        0,
    ))

    # 4. fence 外散文・インライン code → 通過
    results.append(run_case(
        "prose / inline code only",
        "過去に `git stash drop` を実行した報告。git branch -D の説明文。",
        0,
    ))

    # 5. 破壊コマンドなしの通常応答 → 通過
    results.append(run_case(
        "normal response with safe block",
        f"確認コマンド:\n{FENCE}bash\ngit status && python scripts/check_mojibake.py\n{FENCE}\n",
        0,
    ))

    # 6. stop_hook_active（無限ループ防止）→ 通過
    results.append(run_case(
        "stop_hook_active passthrough",
        f"{FENCE}\ngit stash drop\n{FENCE}\n",
        0,
        stop_hook_active=True,
    ))

    # 7. 読み取り block が破壊 block の後（順序違反）→ ブロック
    results.append(run_case(
        "inspection AFTER destructive (wrong order)",
        f"{FENCE}\ngit branch -D fix/old\n{FENCE}\n後から確認:\n{FENCE}\ngit log master..fix/old\n{FENCE}\n",
        2,
    ))

    # 8. PowerShell の再帰削除 bare → ブロック
    results.append(run_case(
        "powershell Remove-Item -Recurse bare",
        f"{FENCE}powershell\nRemove-Item -Recurse -Force C:\\repo\\dir\n{FENCE}\n",
        2,
    ))

    # 9. adversarial: valid JSON だが非dict行 ["x"] / message 非dict が混在しても
    #    クラッシュせず（fail-open）破壊 block を検出→ブロック（PR #506/#509 同ガード）
    results.append(run_case(
        "non-dict transcript lines do not crash (fail-open)",
        f"{FENCE}\ngit stash drop\n{FENCE}\n",
        2,
        raw_lines=['["unexpected","shape"]', '{"type":"assistant","message":"not-a-dict"}'],
    ))

    total, passed = len(results), sum(results)
    print(f"\n{passed}/{total} PASS")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
