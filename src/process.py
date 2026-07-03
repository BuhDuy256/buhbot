"""Article FSM (state-design.md §3) -- the heart of the pipeline.

DISCOVERED -> HASHED -> (SKIPPED | PROCESSING) -> (CONFIRMED | FAILED). Parent of
the Chunk FSM: it calls ``uploader.upload_chunks`` and applies the all-or-nothing
rule (§5) to decide the article's fate, then writes to disk exactly once via
``state`` -- the single write point that fixes the original hash-timing bug.

On FAILED it does an *eager* rollback: the chunks that did upload are deleted
immediately so a half-indexed article is never searchable, and reconcile.orphans
is the backstop for any delete that itself failed.
"""

from . import artifacts, chunk, content, uploader, vector_store
from .config import CHUNK_TEMPLATE_VERSION
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
    # Delta key = fingerprint of EVERYTHING that lands in the uploaded bytes, not
    # just the body: the chunk-template version, title, and canonical URL all
    # appear in each chunk's header now, so a change in any of them must count as
    # an "update". A body-only hash would keep serving a stale header (or an old
    # template) forever because the body itself never changed.
    signature = f"tmpl:{CHUNK_TEMPLATE_VERSION}\n{art.title}\n{art.html_url}\n{md}"
    content_hash = content.content_hash(signature)

    verdict = _compare(state, art.id, content_hash)
    if verdict == "skip":
        print("    -> skipped (unchanged)")
        return Outcome.skipped(art.id)

    # cleanup-before-reprocess (§7): delete any chunk files this article has on
    # record BEFORE uploading new ones -- covers both retried-FAILED and
    # genuinely-updated articles whose chunk count changed.
    old_ids = state.get_chunk_ids(art.id)
    if old_ids:
        print(f"    -> {verdict}: cleaning {len(old_ids)} old chunk(s) first")
        for file_id in old_ids:
            try:
                vector_store.delete_file(client, store_id, file_id)
            except Exception as exc:  # noqa: BLE001
                print(f"    -> cleanup: could not delete {file_id}: {exc}")

    chunks = chunk.split_markdown(md, art.html_url, art.title)
    if not chunks:
        # Empty body -> nothing to upload. Confirm with no chunks so we don't
        # reprocess it every run.
        print(f"    -> {verdict}: empty body, confirming with 0 chunks")
        state.record_confirmed(art.id, content_hash, [])
        return Outcome.confirmed(art.id, verdict)

    print(f"    -> {verdict}: split into {len(chunks)} chunk(s)")
    artifacts.dump_chunks(art.id, chunks)  # inspection side-channel; no-op unless enabled
    results = uploader.upload_chunks(
        client, store_id, chunks, article_id=art.id, content_hash=content_hash
    )
    uploaded_ids = [r.file_id for r in results if r.status == UPLOADED and r.file_id]

    if all(r.status == UPLOADED for r in results):  # §5 all-or-nothing
        print(f"    -> CONFIRMED ({len(uploaded_ids)}/{len(results)} chunks uploaded)")
        state.record_confirmed(art.id, content_hash, uploaded_ids)
        return Outcome.confirmed(art.id, verdict)

    print(f"    -> FAILED ({len(uploaded_ids)}/{len(results)} chunks uploaded)")
    for r in results:
        if r.status != UPLOADED:
            print(f"       chunk {r.chunk_index}: {r.error}")
    # Eager rollback (§10): a partially-uploaded article must not stay live in the
    # store -- retrieval could otherwise serve an incomplete/half-indexed article.
    # Delete the chunks that DID upload now, then record no chunk ids and no hash
    # (record_failed enforces the no-hash rule, so the next run reprocesses). Any
    # delete that fails here is swept by reconcile.orphans() on the next run,
    # since a FAILED article no longer contributes known-good ids.
    for file_id in uploaded_ids:
        try:
            vector_store.delete_file(client, store_id, file_id)
        except Exception as exc:  # noqa: BLE001
            print(f"       rollback: could not delete {file_id}: {exc} (reconcile will sweep)")
    state.record_failed(art.id, [])
    return Outcome.failed(art.id)
