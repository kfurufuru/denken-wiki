#!/usr/bin/env python
"""Stop hook: 破壊コマンドの bare runnable block 禁止ゲート (v1.0).

Claude の応答内 code fence に破壊コマンド（stash drop / branch -D /
reset --hard / clean -f / --force 系 / rm -r 系 / Remove-Item -Recurse）を
検出したとき、同一応答内でそれより**前**に読み取り block（消える対象の
実測表示）が存在しなければ exit 2 で送信をブロックする。

背景（2026-06-11 消失未遂・AI社員諮問 全員一致で導入）:
  Claude が「git stash drop; git branch -D …」の runnable block を
  「中身は照合確認済み」という虚偽の安全主張付きでユーザーに渡した。
  実際は未照合の untracked 34件を内包（stash drop の untracked 分は
  reflog にも残らない不可逆）。ユーザーの ▷ 実行は PreToolUse hook
  （block-dangerous-git）を通らないため、「Claude が渡す runnable block」
  が唯一の hook 非通過経路だった。
  - A3 原則（主軸）: 破壊opは block で渡さず Claude 自身が in-session 実行
    （実測 → ユーザー明示承認 → CLAUDE_ALLOW_DANGEROUS_GIT=1）。
  - 本 hook（A1・補強）: A3 逸脱時の backstop。2分割プロトコル
    （①読み取り block → ②破壊 block）を機械強制する。

誤検知回避（諮問の設計指示）:
  - 検査対象は実行系 fence（bash/sh/powershell 等 + タグなし）のみ。
    ```text / ```yaml / ```python 等の非実行タグ fence・fence 外の散文・
    インライン code は対象外 → 教育目的のコマンド例示は ```text に書く。
  - 読み取り block（stash show / git log / ls 等を含み破壊コマンドを
    含まない実行系 fence）が破壊 block より前にあれば通過（soft gate）。
  - stop_hook_active 時は exit 0（無限ループ防止）・fail-open
    （transcript 不読・JSON 不正は exit 0）。

配置: <repo>/.claude/hooks/destructive_block_check.py（git tracked・全 worktree に伝播）
登録: <repo>/.claude/settings.json Stop hooks
SoT: memory feedback-runnable-command-blocks（A3 原則・2分割プロトコル）
self-test: python .claude/hooks/tests/test_destructive_block_check.py
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ```lang\n ... ``` フェンス（lang 行は info string 全体）
CODE_FENCE_RE = re.compile(r"```([^\n`]*)\n(.*?)```", re.DOTALL)

# 実行系 fence: タグなし（▷ が付き得る）+ 明示的なシェル系タグのみ検査。
# それ以外のタグ（text/yaml/python/diff/…）はすべて対象外（ホワイトリスト方式）。
EXEC_LANGS = {
    "", "bash", "sh", "shell", "zsh", "powershell", "pwsh",
    "cmd", "bat", "console", "terminal",
}

# 破壊コマンド（block-dangerous-git の対象と整合・行内に -C <path> 等が
# 挟まる形 `git -C path stash drop` も拾う）
DESTRUCTIVE_RES = [
    re.compile(r"\bgit\b[^\n]*?\bstash\s+(?:drop|clear)\b"),
    re.compile(r"\bgit\b[^\n]*?\bbranch\s+-D\b"),
    re.compile(r"\bgit\b[^\n]*?\breset\s+--hard\b"),
    re.compile(r"\bgit\b[^\n]*?\bclean\s+-[a-zA-Z]*f"),
    re.compile(r"\bgit\b[^\n]*?--force\b"),
    re.compile(r"\brm\s+-[a-zA-Z]*r"),          # rm -r / -rf / -fr
    re.compile(r"\bRemove-Item\b[^\n]*-Recurse", re.IGNORECASE),
]

# 読み取り block 判定（破壊コマンド非含有が前提・対象実測に使う代表形）
READONLY_RE = re.compile(
    r"\bgit\b[^\n]*?\b(?:stash\s+(?:show|list)|log|status|show|diff|ls-files|rev-list)\b"
    r"|\b(?:ls|dir|Get-ChildItem|cat|head|tail|find|grep|wc)\b",
    re.IGNORECASE,
)


def normalize_path(p: str) -> str:
    if sys.platform == "win32" and re.match(r"^/[a-zA-Z]/", p):
        return p[1].upper() + ":" + p[2:]
    return p


def get_last_assistant_text(transcript_path: str) -> str:
    transcript_path = normalize_path(transcript_path)
    if not transcript_path or not os.path.isfile(transcript_path):
        return ""
    last_text = ""
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for line in f:
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # 行が valid JSON でも dict とは限らない（["x"] 等）。d.get() の
                # AttributeError で hook 全体が exit 1 する fail-open 違反を防ぐ
                # （.secretary 版 PR #506/#509・task_retrospective_check v1.4 と同ガード）。
                if not isinstance(d, dict) or d.get("type") != "assistant":
                    continue
                msg = d.get("message", {})
                content = msg.get("content", []) if isinstance(msg, dict) else []
                if isinstance(content, str):
                    last_text = content
                elif isinstance(content, list):
                    parts = [
                        c.get("text", "")
                        for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    ]
                    if parts:
                        last_text = "\n".join(parts)
    except (OSError, UnicodeDecodeError):
        return ""
    return last_text


def first_destructive_hit(body: str):
    for rx in DESTRUCTIVE_RES:
        m = rx.search(body)
        if m:
            return m.group(0)
    return None


def analyze(text: str):
    """返り値: (違反 list[(pos, コマンド断片)], 読み取り block 開始 pos の list)."""
    violations = []
    inspections = []
    for m in CODE_FENCE_RE.finditer(text):
        lang = m.group(1).strip().lower().split()[0] if m.group(1).strip() else ""
        if lang not in EXEC_LANGS:
            continue
        body = m.group(2)
        hit = first_destructive_hit(body)
        if hit:
            violations.append((m.start(), hit))
        elif READONLY_RE.search(body):
            inspections.append(m.start())
    return violations, inspections


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    if payload.get("stop_hook_active"):
        sys.exit(0)

    last_text = get_last_assistant_text(payload.get("transcript_path", ""))
    if not last_text:
        sys.exit(0)

    violations, inspections = analyze(last_text)
    if not violations:
        sys.exit(0)

    # 各破壊 block について「より前に読み取り block がある」なら解除（2分割準拠）
    unresolved = [
        (pos, hit)
        for pos, hit in violations
        if not any(ins_pos < pos for ins_pos in inspections)
    ]
    if not unresolved:
        sys.exit(0)

    frags = " / ".join(hit for _, hit in unresolved[:3])
    sys.stderr.write(
        f"ERROR: 破壊コマンドの bare runnable block を検出（A3原則違反・2026-06-11 AI社員諮問全員一致のゲート）: {frags}\n"
        "ユーザーの ▷ 実行は block-dangerous-git hook を通らない＝この block が唯一の無防備経路。対応（いずれか）:\n"
        "  1. 【原則 A3】block で渡さず Claude 自身が in-session 実行する（対象実測 → ユーザー明示承認 →\n"
        "     先頭 CLAUDE_ALLOW_DANGEROUS_GIT=1 で監査バイパス実行）\n"
        "  2. 【fallback 2分割】破壊 block の前に読み取り block（消える対象の全数表示:\n"
        "     git stash show -u --stat / git log master..branch 等）を配置し「①の出力を見てから②を」と案内\n"
        "  3. 【例示目的】実行させる意図がないコマンド例は ```text フェンスに変更\n"
        "SoT: memory feedback-runnable-command-blocks / .claude/hooks/destructive_block_check.py\n"
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
