"""Optional debug artifacts for manual data validation.

A side-channel ONLY: when ``config.DUMP_ARTIFACTS`` is on, dumps the raw fetched
article JSON and the exact chunk Markdown to disk so the output can be inspected.
The upload path (uploader.py) still sends in-memory bytes and never reads these
files -- writing them does NOT re-couple upload to disk the way the prior
pipeline did. No-ops cleanly when the flag is off.

Layout under ``data/``:
    raw/<article_id>.json               -- the article exactly as fetched
    chunks/<article_id>-chunk-<i>.md    -- each chunk's uploaded text (incl. header)
"""

import json

from .config import CHUNK_DIR, DUMP_ARTIFACTS, RAW_DIR


def dump_raw(raw: dict) -> None:
    """Write one fetched article's raw JSON (called per article at fetch time)."""
    if not DUMP_ARTIFACTS:
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{raw.get('id')}.json"
    path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")


def dump_chunks(article_id: str, chunks) -> None:
    """Write one article's chunk Markdown files (called after split, before upload).

    Stale chunk files for this article are cleared first, so an article that
    shrinks from 5 chunks to 3 doesn't leave 2 misleading leftovers on disk.
    """
    if not DUMP_ARTIFACTS:
        return
    CHUNK_DIR.mkdir(parents=True, exist_ok=True)
    for old in CHUNK_DIR.glob(f"{article_id}-chunk-*.md"):
        old.unlink()
    for c in chunks:
        path = CHUNK_DIR / f"{article_id}-chunk-{c.index}.md"
        path.write_text(c.text, encoding="utf-8")
