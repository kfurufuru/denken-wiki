"""MkDocs post-build hook: inject hoki-wiki entries into search_index.json.

Fetches the hoki-wiki search index (58 entries) from the secretary-portal
GitHub Pages deployment and merges them into MkDocs Material's lunr.js
search index, so denken-wiki users can search hoki-wiki content from this
site (Phase 2 of bidirectional cross-search).

Source: https://kfurufuru.github.io/secretary-portal/data/hoki-search-index.json
Target: site/search/search_index.json (lunr.js index built by mkdocs-material)

Failure policy:
- Network failure / non-200 response: warn and skip (do not fail build).
- Zero entries fetched: hard fail (sys.exit(1)) — indicates upstream regression.
- JSON parse / write failure: hard fail.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

HOKI_INDEX_URL = (
    "https://kfurufuru.github.io/secretary-portal/data/hoki-search-index.json"
)
HOKI_PAGE_URL = (
    "https://kfurufuru.github.io/secretary-portal/denken-hoki-wiki.html"
)
EXPECTED_MIN_ENTRIES = 1  # 0件はビルド失敗
TIMEOUT_SEC = 15


def _log(msg: str) -> None:
    print(f"[inject_hoki] {msg}", file=sys.stderr)


def _fetch_hoki_entries() -> list[dict]:
    req = urlrequest.Request(
        HOKI_INDEX_URL,
        headers={"User-Agent": "denken-wiki-mkdocs-hook/1.0"},
    )
    with urlrequest.urlopen(req, timeout=TIMEOUT_SEC) as resp:
        if resp.status != 200:
            raise RuntimeError(f"non-200 status: {resp.status}")
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise RuntimeError("expected JSON array at root")
    return data


def _build_doc(entry: dict) -> dict:
    eid = entry.get("id", "").strip()
    title = entry.get("title", "").strip()
    chapter = entry.get("chapterTitle", "").strip()
    num = entry.get("num", "").strip()
    freq = entry.get("freq", "").strip()
    priority = entry.get("priority", "").strip()

    location = f"{HOKI_PAGE_URL}#{eid}" if eid else HOKI_PAGE_URL
    label_chapter = chapter or "暗記Hub"
    full_title = f"{title}（暗記Hub: {label_chapter}）" if title else f"暗記Hub: {label_chapter}"

    text_parts = [chapter, num]
    if freq:
        text_parts.append(f"出題頻度:{freq}")
    if priority:
        text_parts.append(f"優先度:{priority}")
    text_parts.append("暗記Hub")
    text = " ".join(p for p in text_parts if p)

    return {"location": location, "title": full_title, "text": text}


def on_post_build(config, **kwargs):
    site_dir = Path(config["site_dir"])
    index_path = site_dir / "search" / "search_index.json"
    if not index_path.exists():
        _log(f"search_index.json not found at {index_path}; skip")
        return

    try:
        entries = _fetch_hoki_entries()
    except (urlerror.URLError, TimeoutError, OSError) as e:
        _log(f"WARN: failed to fetch hoki index ({e!r}); preserving existing search index")
        return
    except (json.JSONDecodeError, RuntimeError) as e:
        _log(f"WARN: failed to parse hoki index ({e!r}); preserving existing search index")
        return

    if len(entries) < EXPECTED_MIN_ENTRIES:
        _log(f"FATAL: fetched {len(entries)} entries (expected >= {EXPECTED_MIN_ENTRIES})")
        sys.exit(1)

    with index_path.open("r", encoding="utf-8") as f:
        index = json.load(f)
    if "docs" not in index or not isinstance(index["docs"], list):
        _log("FATAL: search_index.json missing 'docs' array")
        sys.exit(1)

    new_docs = [_build_doc(e) for e in entries]
    index["docs"].extend(new_docs)

    with index_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False)

    _log(f"injected {len(new_docs)} hoki entries into {index_path}")
