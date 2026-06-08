#!/usr/bin/env python3
"""
Pre-commit hook: redirect_maps key vs docs/ 実在ファイル衝突検出

mkdocs-redirects プラグインの redirect_maps エントリのキーが docs/ 配下に実在する場合、
mkdocs-redirects は実在ファイルより redirect_maps を優先するため、新規ファイルが
配信不能になる（HTTP 200 で "Redirecting..." が返る silent failure）。

本hookは commit前にこの衝突を検出して block する。

## 背景

2026-05-24 Phase E（電技解釈第227条⇄第229条 主題スワップ解消）で、
旧 `kaishaku/227.md`（高圧保護） → `229.md` にリネームと同時に、
新 `kaishaku/227.md`（低圧保護）を別内容で新規作成した。redirect_maps に
`'articles/kaishaku/227.md': 'articles/kaishaku/229.md'` を残置していたため、
新227.md が配信されず常にリダイレクトページが返る silent failure が発生。
古舘さんの「Wikiで確認できないの？」指摘で発覚。mkdocs build PASS /
hoki_check PASS で検出できなかった盲点を埋める目的の機構。

## AI社員諮問記録

落合陽一・ひろゆき・ホリエモン 全員一致で「A. pre-commit hook 即実装」採用
（2026-05-24・pool: decision）。

## 関連 rule

feedback_redirect_vs_new_file_collision
"""
import sys
from pathlib import Path

# Windows cp932 環境での stdout encoding 対策 (feedback_win_python_stdout_encoding)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, TypeError):
        pass

try:
    import yaml
except ImportError:
    print("[WARN] precommit_redirect_collision: PyYAML not installed, skip")
    sys.exit(0)

ROOT = Path(__file__).resolve().parents[1]
MKDOCS_YAML = ROOT / "mkdocs.yml"
DOCS_DIR = ROOT / "docs"


class MkDocsYamlLoader(yaml.SafeLoader):
    """
    mkdocs.yml の `!!python/name:material.extensions.emoji.twemoji` など
    カスタムタグを無視する Loader。
    redirect_maps の検出のみ目的・タグの値は不要なため None を返す。
    """


def _ignore_python_tag(loader, tag_suffix, node):
    return None


MkDocsYamlLoader.add_multi_constructor("tag:yaml.org,2002:python/name:", _ignore_python_tag)
MkDocsYamlLoader.add_multi_constructor("tag:yaml.org,2002:python/object/apply:", _ignore_python_tag)
MkDocsYamlLoader.add_multi_constructor("tag:yaml.org,2002:python/object:", _ignore_python_tag)


def extract_redirect_maps(config):
    """mkdocs.yml の plugins セクションから redirect_maps を抽出"""
    plugins = config.get("plugins", []) or []
    for p in plugins:
        if isinstance(p, dict) and "redirects" in p:
            redirects_config = p["redirects"] or {}
            return redirects_config.get("redirect_maps", {}) or {}
    return {}


def main():
    if not MKDOCS_YAML.exists():
        # mkdocs project でない（別repo等）→ 対象外
        return 0

    with MKDOCS_YAML.open("r", encoding="utf-8") as f:
        try:
            config = yaml.load(f, Loader=MkDocsYamlLoader)
        except yaml.YAMLError as e:
            # YAML parse error: 別の validator に任せる
            print(f"[WARN] precommit_redirect_collision: mkdocs.yml YAML parse error ({e}), skip")
            return 0

    redirect_maps = extract_redirect_maps(config)
    if not redirect_maps:
        print("OK precommit_redirect_collision: redirect_maps 未定義（衝突なし）")
        return 0

    collisions = []
    for src_path in redirect_maps:
        full_path = DOCS_DIR / src_path
        if full_path.exists():
            collisions.append((src_path, redirect_maps[src_path]))

    if collisions:
        print("[ERROR] redirect_maps key vs docs/ 実在ファイル衝突を検出")
        print(f"   rule: feedback_redirect_vs_new_file_collision")
        print(f"   fix:  redirect_maps から該当キーを削除（新規ファイル実体を優先）")
        print(f"")
        print(f"## 衝突 -{len(collisions)} 件")
        for src, dst in collisions:
            print(f"   {src} → {dst}")
            print(f"     ⚠ docs/{src} が実在 → mkdocs-redirects が新規ファイルを block・配信不能")
        print(f"")
        print(f"## Phase E 教訓 (2026-05-24)")
        print(f"リネーム＋同パス新規作成 同時発生時、redirect_maps を残すと")
        print(f"mkdocs-redirects が実在ファイルを上書きする silent failure を起こす。")
        print(f"新規ファイル作成時は必ず該当 redirect entry を削除すること。")
        return 1

    print(f"OK precommit_redirect_collision: 0 collisions across {len(redirect_maps)} redirect entries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
