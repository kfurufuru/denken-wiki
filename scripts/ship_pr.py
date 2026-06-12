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

注意:
  - 出荷直前に origin/<base> を fetch して最新 SHA をベースにする。
    実行中に base が動いた場合は commit 作成前に再チェックして中断する。
  - 既存ブランチ名は既定でエラー。--force-update で PATCH（force）する。
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


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--repo", default="kfurufuru/denken-wiki")
    ap.add_argument("--base", default="master")
    ap.add_argument("--branch", required=True, help="作成する feature ブランチ名")
    ap.add_argument(
        "--file",
        action="append",
        required=True,
        dest="files",
        help="repo相対path[=内容ファイル]。複数指定可",
    )
    ap.add_argument("--commit-msg-file", required=True)
    ap.add_argument("--pr-title-file", required=True)
    ap.add_argument("--pr-body-file", required=True)
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
    args = ap.parse_args()

    os.chdir(ROOT)

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
            base_blob = run(["git", "rev-parse", f"origin/{args.base}:{repo_path}"])
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


if __name__ == "__main__":
    main()
