#!/usr/bin/env python
"""Stop hook: 完了宣言レビュー強制 — denken-wiki 版 (v1.2).

完了マーカー検出時のみ作動し、`完了レビュー:` ブロックに
改善点 / 再発防止 / 水平展開 / 残件 / トークン の5ラベルが揃っているか検証。
不足なら exit 2 で完了報告をブロック（stderr に違反通知）。

v1.2 (2026-06-13): 「トークン」ラベル追加 — トークン消費を抑える改善を
  実施したか（実施内容 or 検討の上「対象なし」+理由）を完了時に必ず棚卸す。
  典拠: memory feedback-token-economy-always（節約検討は事後でなく常時・
  完了レビューを最終チェックポイントに昇格）。

完了マーカー（いずれか）:
  1. 「今回の学び:」見出し（task-retrospective skill スキーマ）
  2. 「完了レビュー:」見出し（同上）
  3. 完了宣言フレーズ（v1.1 追加）: 「残作業はありません」「残件なし」
     「すべて完了」「全件完了」「完全クリーン」等 — 見出しなしの
     完了断定そのものをトリガにする

v1.1 の背景（2026-06-11 denken-wiki 事案）:
  .secretary 版 v1 はトリガが見出し（自己申告マーカー）のみのため、
  見出しを書かずに「残作業はありません」と断定した完了報告は素通りした。
  実際には U+FFFD 残置・スクリプトのフットガン・未検証ガード等の残件が
  あり、翌ターンの「残件はないか？」で露呈。残件ゼロの宣言フレーズ自体を
  トリガに加え、宣言には必ず4ラベルの実測レビューを伴わせる。

設計（.secretary/.claude/hooks/task_retrospective_check.py v1 から移植）:
  - 完了マーカー不在の応答（mid-task・軽微質問返答）は exit 0 でパス＝毎ターン nag しない
  - code fence (```...```) は strip（fence 内ダミーで騙せない）
  - 完了レビュー内の「残件: なし」は宣言トリガにもなるがブロック自体が
    要件を満たすため pass（自己整合）
  - stop_hook_active 時は exit 0（無限ループ防止）
  - fail-open: transcript 不読・JSON 不正は exit 0

配置: <repo>/.claude/hooks/task_retrospective_check.py（git tracked・全 worktree に伝播）
登録: <repo>/.claude/settings.json Stop hooks（$CLAUDE_PROJECT_DIR 経由で worktree 安全）
SoT: task-retrospective skill ＋ memory: feedback-premature-completion-declaration
"""
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

SECTION_LINE_LIMIT = 20

# 完了マーカー1・2（heading 形・prose 誤検出回避）
LEARNING_HEADING_RE = re.compile(
    r"(?:^|\n)\s*(?:#+\s*)?(?:今回の)?学び\s*[:：]", re.IGNORECASE
)
REVIEW_HEADING_RE = re.compile(
    r"(?:^|\n)\s*(?:#+\s*)?完了レビュー\s*[:：]"
)
# 完了マーカー3（v1.1）: 残件ゼロの宣言フレーズ。
# 「マージ完了」のような per-item 完了報告では発火させない（nag 回避）—
# 「何も残っていない」という全体宣言のみ対象。
COMPLETION_DECLARATION_RE = re.compile(
    r"残(?:作業|件|タスク)\s*(?:[はも]|[:：])?\s*(?:ありません|なし|ゼロ)"
    r"|すべて完了|全件完了|全タスク完了|完全クリーン"
)
CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

# 完了レビュー ブロックに必須の5ラベル
REQUIRED_LABELS = {
    "改善点": re.compile(r"改善点\s*[:：]"),
    "再発防止": re.compile(r"再発防止\s*[:：]"),
    "水平展開": re.compile(r"水平展開\s*[:：]"),
    "残件": re.compile(r"残件\s*[:：]"),
    "トークン": re.compile(r"トークン\s*[:：]"),
}


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
                if d.get("type") != "assistant":
                    continue
                content = d.get("message", {}).get("content", [])
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


def strip_code_fences(text: str) -> str:
    return CODE_FENCE_RE.sub("", text)


def extract_review_section(text: str) -> str:
    m = REVIEW_HEADING_RE.search(text)
    if not m:
        return ""
    tail = text[m.end():]
    return "\n".join(tail.split("\n")[:SECTION_LINE_LIMIT])


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

    cleaned = strip_code_fences(last_text)

    decl = COMPLETION_DECLARATION_RE.search(cleaned)
    # 完了マーカー不在 → mid-task / 軽微応答 → パス（nag しない）
    if not (
        LEARNING_HEADING_RE.search(cleaned)
        or REVIEW_HEADING_RE.search(cleaned)
        or decl
    ):
        sys.exit(0)

    section = extract_review_section(cleaned)
    if not section:
        trigger = f"完了宣言「{decl.group(0)}」" if decl else "「今回の学び:」見出し"
        sys.stderr.write(
            f"ERROR: 完了レビュー規律違反（典拠=task-retrospective skill）— {trigger} を検出しましたが\n"
            "  `完了レビュー:` ブロックがありません。残件ゼロの宣言には実測レビューが必須です。\n"
            "対応: 完了報告末尾に以下を出す（残件は grep/status 等の実測結果を添える）:\n"
            "  完了レビュー:\n"
            "    改善点: <... or なし>\n"
            "    再発防止: <... or 該当なし>\n"
            "    水平展開: <... or 該当なし>\n"
            "    残件: <実測 or なし>\n"
            "    トークン: <消費を抑える改善の実施内容 or 検討の上「対象なし」+理由>\n"
        )
        sys.exit(2)

    missing = [name for name, rx in REQUIRED_LABELS.items() if not rx.search(section)]
    if missing:
        sys.stderr.write(
            "ERROR: 完了レビュー規律違反（典拠=task-retrospective skill）— `完了レビュー:` ブロックに不足ラベル: "
            + " / ".join(missing) + "\n"
            "5ラベル（改善点・再発防止・水平展開・残件・トークン）すべて必須。\n"
            "該当なしは「なし」「該当なし」と明示（空欄＝Check未実施は禁止）。\n"
            "トークン: 消費を抑える改善を実施したか（実施内容 or 検討の上「対象なし」+理由）。\n"
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
