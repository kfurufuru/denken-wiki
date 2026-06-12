#!/usr/bin/env python3
"""gh api (Git Data API) で feature ブランチ + PR を作る定型出荷スクリプト.

git push が hook で全ブロックされる環境での標準出荷手段。毎回 bash で
blobs→tree→commit→ref→pulls を手書きするとトークンを浪費し、かつ過去事故の
罠を踏み直すため、定型を 1 コマンドに固定する。

構造的に封じる既知の罠（番号は .claude メモリの ship-workflow 罠台帳に対応）:
  罠7  : 各段 40hex SHA ガード（失敗時のエラー JSON が後段へ連鎖破壊するのを防止）
  罠9  : コミットメッセージ / PR 本文はファイル渡し + UTF-8 明示読み
         （stdin/cp932 経由の mojibake が squash merge で恒久残存する事故の防止）
  罠11 : blob はファイル生バイトから base64。既定で CRLF→LF 正規化
         （autocrlf=true の worktree 読みで全行 diff 化する事故の防止）
  罠12 : index（`git show :path`）非依存。`git add` 漏れで HEAD 旧内容が
         無言 blob 化する事故（PR #92→#101）を構造的に排除。
         出荷後に PR の files を実測し、意図ファイル全数一致を検証

使い方:
  python scripts/ship_pr.py \
      --branch claude/my-fix \
      --file docs/themes/foo.md \
      --file docs/bar.md=.tmp/fixed-bar.md \
      --commit-msg-file .tmp/msg.txt \
      --pr-title-file .tmp/title.txt \
      --pr-body-file .tmp/body.md

  --file は「repo相対path」または「repo相対path=内容ファイル」。
  = 省略時は repo 相対 path のファイルをそのまま内容として使う。
  PR 本文・コミットメッセージは事前にファイルへ UTF-8 で書き出しておく。

  フル出荷（作成→CI 待機→squash マージ→ブランチ削除）:
  python scripts/ship_pr.py \
      --branch claude/my-fix \
      --file docs/foo.md \
      --commit-msg-file .tmp/msg.txt \
      --pr-title-file .tmp/title.txt \
      --pr-body-file .tmp/body.md \
      --watch-ci --merge --close-issue 123

  既存 PR の後半工程だけ実行（作成済み PR #45 の CI 待機→マージ→issue close）:
  python scripts/ship_pr.py --finish --pr 45 --close-issue 123

注意:
  - 出荷直前に origin/<base> を fetch して最新 SHA をベースにする。
    実行中に base が動いた場合は commit 作成前に再チェックして中断する。
  - 既存ブランチ名は既定でエラー。--force-update で PATCH（force）する。
  - --merge はマージ直前に PR の mergeable を確認し CONFLICTING なら中断する
    （base 乖離→再出荷を促す。並行セッションとの二重実装検出の防衛線）。
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HEX40 = re.compile(r"^[0-9a-f]{40}$")
ROOT = Path(__file__).resolve().parent.parent

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def clean_env() -> dict:
    """GITHUB_TOKEN/GH_TOKEN を除いた環境（gh は keyring の auth を使う）."""
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    return env


def run(cmd: list[str], **kw) -> str:
    return subprocess.check_output(cmd, env=clean_env(), **kw).decode("utf-8").strip()


def gh_api(repo: str, endpoint: str, payload: dict, method: str = "POST") -> dict:
    """gh api を --input(JSON ファイル) 経由で叩く。応答 JSON を dict で返す."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(payload, f, ensure_ascii=True)
        tmp = f.name
    try:
        out = run(
            ["gh", "api", "-X", method, f"repos/{repo}/{endpoint}", "--input", tmp]
        )
    finally:
        os.unlink(tmp)
    return json.loads(out)


def guard_sha(sha: str, label: str) -> str:
    if not HEX40.match(sha or ""):
        sys.exit(f"FATAL: {label} の SHA が不正: {sha!r}")
    return sha


def read_content(path_spec: str, normalize_lf: bool) -> tuple[str, bytes]:
    """'repo相対path' or 'repo相対path=内容ファイル' → (repo相対path, バイト列)."""
    if "=" in path_spec:
        repo_path, src = path_spec.split("=", 1)
    else:
        repo_path, src = path_spec, path_spec
    raw = Path(src).read_bytes()
    if normalize_lf and b"\x00" not in raw:
        raw = raw.replace(b"\r\n", b"\n")
    return repo_path, raw


def gh_json(repo: str, number: int, fields: str) -> dict:
    """gh pr view <N> --json <fields> を dict で返す."""
    out = run(
        ["gh", "pr", "view", str(number), "--repo", repo, "--json", fields]
    )
    return json.loads(out)


def watch_ci(
    repo: str, number: int, timeout: int, interval: int = 15, allow_no_ci: bool = False
) -> None:
    """PR の CI checks をポーリング。全 pass で return・fail/timeout で exit 1.

    - pending/queued/in_progress は再ポーリング。
    - checks が 1 つも無い状態が 90 秒続いたら「CI 未トリガー」warning を
      出して exit 1（後段マージへ進めない安全弁）。
    - quality-check.yml は paths フィルタ（docs/**・_data/** 等）のため scripts
      のみ等の PR は CI 対象外で正当に未トリガーになる。その場合は --allow-no-ci
      で WARN 表示のうえ watch をスキップして続行できる。
    """
    print(f"watch  = CI checks をポーリング (PR #{number} / timeout {timeout}s)")
    deadline = time.time() + timeout
    no_checks_since: float | None = None
    while True:
        # commits[].statusCheckRollup に全 check-run の state が載る
        data = gh_json(repo, number, "statusCheckRollup")
        rollup = data.get("statusCheckRollup") or []
        if not rollup:
            now = time.time()
            if no_checks_since is None:
                no_checks_since = now
            elif now - no_checks_since >= 90:
                if allow_no_ci:
                    print(
                        "  WARN: 90 秒間 checks 未トリガー。--allow-no-ci 指定のため"
                        " CI 対象外 PR（paths フィルタ）と判定し watch をスキップ"
                    )
                    return
                sys.exit(
                    "FATAL: CI が 90 秒間 1 つもトリガーされていない（未トリガー疑い）。"
                    "ワークフロー設定 / branch protection を確認すること。scripts のみ等の"
                    " CI 対象外 PR（quality-check.yml の paths フィルタ）なら"
                    " --allow-no-ci を付けて再実行。"
                )
            print("  checks: 未トリガー（待機中）...")
        else:
            no_checks_since = None
            pending, failed = [], []
            for c in rollup:
                # CheckRun: status/conclusion / StatusContext: state
                status = (c.get("status") or "").upper()
                concl = (c.get("conclusion") or "").upper()
                state = (c.get("state") or "").upper()
                name = c.get("name") or c.get("context") or "?"
                if status in ("QUEUED", "IN_PROGRESS", "PENDING") or state == "PENDING":
                    pending.append(name)
                elif concl in ("FAILURE", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED") \
                        or state in ("FAILURE", "ERROR"):
                    failed.append((name, c.get("detailsUrl") or c.get("targetUrl") or ""))
            if failed:
                print("  checks: FAIL")
                for name, url in failed:
                    print(f"    ✗ {name}  {url}")
                sys.exit(f"FATAL: CI が失敗 (PR #{number})。上記 URL で詳細を確認すること。")
            if pending:
                print(f"  checks: {len(pending)} 件 pending（{', '.join(pending[:3])}...）")
            else:
                print(f"  checks: 全 pass ({len(rollup)} 件)")
                return
        if time.time() >= deadline:
            sys.exit(
                f"FATAL: CI 待機が timeout ({timeout}s)。"
                "--watch-timeout を伸ばすか手動で確認すること。"
            )
        time.sleep(interval)


def merge_pr(repo: str, number: int) -> None:
    """mergeable=CONFLICTING を弾いてから squash マージ＋リモートブランチ削除."""
    data = gh_json(repo, number, "mergeable,state")
    mergeable = (data.get("mergeable") or "").upper()
    if mergeable == "CONFLICTING":
        sys.exit(
            f"FATAL: PR #{number} が CONFLICTING（base 乖離 or 二重実装）。"
            "ブランチを最新 base で作り直して再出荷すること。"
        )
    subprocess.check_call(
        ["gh", "pr", "merge", str(number), "--repo", repo, "--squash", "--delete-branch"],
        env=clean_env(),
    )
    print(f"merge  = PR #{number} squash マージ＋ブランチ削除 完了")


def close_issue(repo: str, number: int, pr_number: int) -> None:
    comment = f"PR #{pr_number} マージ完了・WIP解除"
    subprocess.check_call(
        ["gh", "issue", "close", str(number), "--repo", repo, "--comment", comment],
        env=clean_env(),
    )
    print(f"issue  = #{number} close（{comment}）")


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", default="kfurufuru/denken-wiki")
    ap.add_argument("--base", default="master")
    # --finish モードでは作成系引数が不要になるため required は外し、手動検証する
    ap.add_argument("--branch", help="作成する feature ブランチ名")
    ap.add_argument(
        "--file",
        action="append",
        dest="files",
        help="repo相対path[=内容ファイル]。複数指定可",
    )
    ap.add_argument("--commit-msg-file")
    ap.add_argument("--pr-title-file")
    ap.add_argument("--pr-body-file")
    ap.add_argument(
        "--keep-eol",
        action="store_true",
        help="CRLF→LF 正規化を無効化（既定は LF 正規化＝罠11対策）",
    )
    ap.add_argument(
        "--force-update",
        action="store_true",
        help="ブランチ既存時に PATCH refs --force で上書き",
    )
    # --- 後半工程（CI 待機→マージ→issue close） ---
    ap.add_argument(
        "--watch-ci",
        action="store_true",
        help="PR 作成後に CI checks を 15 秒間隔でポーリング（全 pass で続行）",
    )
    ap.add_argument(
        "--watch-timeout",
        type=int,
        default=600,
        help="--watch-ci のタイムアウト秒（既定 600）",
    )
    ap.add_argument(
        "--merge",
        action="store_true",
        help="checks 全 pass 後に squash マージ＋リモートブランチ削除（CONFLICTING は中断）",
    )
    ap.add_argument(
        "--close-issue",
        type=int,
        metavar="N",
        help="マージ成功後に issue N を close（コメント付き）",
    )
    ap.add_argument(
        "--finish",
        action="store_true",
        help="既存 PR の後半のみ実行（--pr 必須・watch-ci→merge→close-issue）",
    )
    ap.add_argument("--pr", type=int, help="--finish 時に対象とする既存 PR 番号")
    ap.add_argument(
        "--allow-no-ci",
        action="store_true",
        help="checks 未トリガー90秒でも FATAL にせず watch をスキップ"
        "（scripts のみ等 paths フィルタで CI 対象外の PR 用）",
    )
    args = ap.parse_args()

    # 引数検証（ネットワークに出る前に止める）
    if args.finish:
        if args.pr is None:
            ap.error("--finish には --pr N が必須です")
    else:
        missing = [
            name
            for name, val in (
                ("--branch", args.branch),
                ("--file", args.files),
                ("--commit-msg-file", args.commit_msg_file),
                ("--pr-title-file", args.pr_title_file),
                ("--pr-body-file", args.pr_body_file),
            )
            if not val
        ]
        if missing:
            ap.error(f"PR 作成には次の引数が必須です: {', '.join(missing)}")

    os.chdir(ROOT)

    # --finish: 既存 PR の後半工程のみ実行して終了（watch-ci → merge → close-issue）
    if args.finish:
        watch_ci(args.repo, args.pr, args.watch_timeout, allow_no_ci=args.allow_no_ci)
        merge_pr(args.repo, args.pr)
        if args.close_issue is not None:
            close_issue(args.repo, args.close_issue, args.pr)
        return

    # 1. base を最新化して SHA/tree を確定
    subprocess.check_call(
        ["git", "fetch", "origin", args.base],
        env=clean_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_sha = guard_sha(run(["git", "rev-parse", f"origin/{args.base}"]), "base")
    base_tree = guard_sha(
        run(["git", "rev-parse", f"origin/{args.base}^{{tree}}"]), "base_tree"
    )
    print(f"base   = {base_sha} (origin/{args.base})")

    # 2. blob 作成（ファイル直 base64・index 非依存 = 罠12 対策）
    entries = []
    intended_paths: set[str] = set()
    for spec in args.files:
        repo_path, raw = read_content(spec, normalize_lf=not args.keep_eol)
        b64 = base64.b64encode(raw).decode("ascii")
        blob = gh_api(args.repo, "git/blobs", {"encoding": "base64", "content": b64})
        sha = guard_sha(blob.get("sha", ""), f"blob {repo_path}")
        # ベースと同一内容（=変更なし）の登録は事故の兆候なので止める
        try:
            # 新規ファイルでは rev-parse が fatal を stderr に吐くが想定内のため抑止
            base_blob = run(
                ["git", "rev-parse", f"origin/{args.base}:{repo_path}"],
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            base_blob = ""  # 新規ファイル
        if base_blob == sha:
            sys.exit(
                f"FATAL: {repo_path} の blob がベースと同一（変更が入っていない）。"
                "Edit の反映漏れ（罠12）を疑うこと。"
            )
        entries.append({"path": repo_path, "mode": "100644", "type": "blob", "sha": sha})
        intended_paths.add(repo_path)
        print(f"blob   = {sha} {repo_path} ({len(raw)} bytes)")

    # 3. tree
    tree = gh_api(args.repo, "git/trees", {"base_tree": base_tree, "tree": entries})
    tree_sha = guard_sha(tree.get("sha", ""), "tree")
    print(f"tree   = {tree_sha}")

    # 4. base が動いていないか最終確認（動いていたら作り直しが安全）
    subprocess.check_call(
        ["git", "fetch", "origin", args.base],
        env=clean_env(),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    now_sha = run(["git", "rev-parse", f"origin/{args.base}"])
    if now_sha != base_sha:
        sys.exit(
            f"FATAL: origin/{args.base} が実行中に前進 ({base_sha[:7]}→{now_sha[:7]})。"
            "再実行して最新ベースで出荷し直すこと。"
        )

    # 5. commit（メッセージはファイル渡し = 罠9 対策）
    msg = Path(args.commit_msg_file).read_text(encoding="utf-8-sig").rstrip("\n") + "\n"
    commit = gh_api(
        args.repo, "git/commits", {"message": msg, "tree": tree_sha, "parents": [base_sha]}
    )
    commit_sha = guard_sha(commit.get("sha", ""), "commit")
    print(f"commit = {commit_sha}")

    # 6. ref
    ref_payload = {"ref": f"refs/heads/{args.branch}", "sha": commit_sha}
    try:
        gh_api(args.repo, "git/refs", ref_payload)
    except subprocess.CalledProcessError:
        if not args.force_update:
            sys.exit(
                f"FATAL: refs/heads/{args.branch} の作成に失敗（既存ブランチ?）。"
                "--force-update で上書きするか別名にすること。"
            )
        gh_api(
            args.repo,
            f"git/refs/heads/{args.branch}",
            {"sha": commit_sha, "force": True},
            method="PATCH",
        )
    print(f"ref    = refs/heads/{args.branch}")

    # 7. PR
    title = Path(args.pr_title_file).read_text(encoding="utf-8-sig").strip()
    body = Path(args.pr_body_file).read_text(encoding="utf-8-sig")
    pr = gh_api(
        args.repo,
        "pulls",
        {"title": title, "body": body, "head": args.branch, "base": args.base},
    )
    number = pr.get("number")
    print(f"PR     = #{number} {pr.get('html_url')}")

    # 8. 出荷後検証: PR の files が意図と全数一致するか（罠12 の事後検知）
    files_json = run(
        ["gh", "pr", "view", str(number), "--repo", args.repo, "--json", "files"]
    )
    actual = {f["path"] for f in json.loads(files_json)["files"]}
    if actual != intended_paths:
        sys.exit(
            "FATAL: PR の変更ファイルが意図と不一致。\n"
            f"  意図: {sorted(intended_paths)}\n  実際: {sorted(actual)}"
        )
    print(f"verify = OK ({len(actual)} files 全数一致)")

    # 9. 後半工程（指定時）: CI 待機 → squash マージ → issue close
    if args.watch_ci or args.merge:
        watch_ci(args.repo, number, args.watch_timeout, allow_no_ci=args.allow_no_ci)
    if args.merge:
        merge_pr(args.repo, number)
        if args.close_issue is not None:
            close_issue(args.repo, args.close_issue, number)
    elif args.close_issue is not None:
        print("WARN: --close-issue は --merge と併用時のみ有効（マージしていないため skip）")


if __name__ == "__main__":
    main()
