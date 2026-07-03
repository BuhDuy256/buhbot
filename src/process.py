"""Article FSM (state-design.md §3) -- the heart of the pipeline.

DISCOVERED -> HASHED -> (SKIPPED | PROCESSING) -> (CONFIRMED | FAILED). Parent of
the Chunk FSM: it calls ``uploader.upload_chunks`` and applies the all-or-nothing
rule (§5) to decide the article's fate, then writes to disk exactly once via
``state`` -- the single write point that fixes the original hash-timing bug.
"""

from . import chunk, content, uploader, vector_store
from .report import Outcome
from .state import FAILED as STATE_FAILED
from .uploader import UPLOADED
from .zendesk import Article


def _compare(state, article_id: str, new_hash: str) -> str:
    """HASHED verdict: 'added' | 'updated' | 'skip' (transition-techniques.md
    'HASHED -> SKIPPED / tagged')."""
    status = state.get_status(article_id)
    if status is None:
        return "added"
    if status == STATE_FAILED:
        # A FAILED article is never "done", even if the hash matches -- it never
        # finished uploading. Reprocess it.
        return "updated" if state.get_hash(article_id) else "added"
    # status == CONFIRMED
    if state.get_hash(article_id) == new_hash:
        return "skip"
    return "updated"


def article(art: Article, client, store_id: str, state) -> Outcome:
    md = content.html_to_markdown(art.body)
    content_hash = content.content_hash(md)

    verdict = _compare(state, art.id, content_hash)
    if verdict == "skip":
        return Outcome.skipped(art.id)

    # cleanup-before-reprocess (§7): delete any chunk files this article has on
    # record BEFORE uploading new ones -- covers both retried-FAILED and
    # genuinely-updated articles whose chunk count changed.
    for file_id in state.get_chunk_ids(art.id):
        try:
            vector_store.delete_file(client, store_id, file_id)
        except Exception as exc:  # noqa: BLE001
            print(f"[cleanup] article {art.id}: could not delete {file_id}: {exc}")

    chunks = chunk.split_markdown(md, art.html_url)
    if not chunks:
        # Empty body -> nothing to upload. Confirm with no chunks so we don't
        # reprocess it every run.
        state.record_confirmed(art.id, content_hash, [])
        return Outcome.confirmed(art.id, verdict)

    results = uploader.upload_chunks(
        client, store_id, chunks, article_id=art.id, content_hash=content_hash
    )
    uploaded_ids = [r.file_id for r in results if r.status == UPLOADED and r.file_id]

    if all(r.status == UPLOADED for r in results):  # §5 all-or-nothing
        state.record_confirmed(art.id, content_hash, uploaded_ids)
        return Outcome.confirmed(art.id, verdict)

    for r in results:
        if r.status != UPLOADED:
            print(f"[fail] article {art.id} chunk {r.chunk_index}: {r.error}")
    # Lazy rollback (§10): keep the chunks that did upload, record their ids for
    # next-run cleanup; do NOT write the hash (record_failed enforces this).
    state.record_failed(art.id, uploaded_ids)
    return Outcome.failed(art.id)
