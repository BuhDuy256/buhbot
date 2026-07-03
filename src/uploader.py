"""UPLOAD -- owns the Chunk FSM (state-design.md §4).

Per chunk: PENDING -> UPLOADING -> UPLOADED | FAILED. Uploading one chunk is two
API calls:
  1. ``POST /files`` (base Files API) turns the chunk text into a File -> file_id
     (call shape from the prior code: ``files.create(file=..., purpose="assistants")``).
  2. ``POST /vector_stores/{id}/file_batches`` attaches every chunk of THIS
     article in one batch, then we poll it.

One batch per Article (not one giant daily batch) so the batch's own
``file_counts`` directly answers the all-or-nothing question the Article FSM
asks -- ``total == completed`` -> CONFIRMED, any failure -> FAILED
(transition-techniques.md "PROCESSING -> spawn Chunk children").

Server-side re-chunking is neutralized with a per-file ``static`` strategy at
4096/0: the ``files[]`` form ignores any top-level ``chunking_strategy``, so it
MUST be set on every entry (transition-techniques.md).
"""

import time
from dataclasses import dataclass

from openai import OpenAI

from .chunk import ChunkText
from .config import (
    BATCH_POLL_INTERVAL_SECONDS,
    CHUNK_OVERLAP_TOKENS,
    STATIC_MAX_CHUNK_TOKENS,
)

UPLOADED = "UPLOADED"
FAILED = "FAILED"

# Neutralize OpenAI's server chunker: one uploaded file == one stored chunk.
_STATIC_STRATEGY = {
    "type": "static",
    "static": {
        "max_chunk_size_tokens": STATIC_MAX_CHUNK_TOKENS,
        "chunk_overlap_tokens": CHUNK_OVERLAP_TOKENS,
    },
}


@dataclass(frozen=True)
class ChunkResult:
    chunk_index: int
    file_id: str | None  # base File id; None only if the base-file upload failed
    status: str          # UPLOADED | FAILED
    error: str | None = None


def upload_chunks(
    client: OpenAI,
    store_id: str,
    chunks: list[ChunkText],
    *,
    article_id: str,
    content_hash: str,
) -> list[ChunkResult]:
    """Upload every chunk of one article; return a result per chunk in order."""
    if not chunks:
        return []

    results: dict[int, ChunkResult] = {}
    entries: list[dict] = []
    file_to_index: dict[str, int] = {}

    # Phase 1: base files (PENDING -> UPLOADING).
    print(f"       uploading {len(chunks)} file(s) to Files API...")
    for c in chunks:
        try:
            file_id = _create_base_file(client, article_id, c)
        except Exception as exc:  # noqa: BLE001 -- one bad chunk must not sink the article
            print(f"       chunk {c.index}: base-file upload failed: {exc}")
            results[c.index] = ChunkResult(c.index, None, FAILED, str(exc))
            continue
        file_to_index[file_id] = c.index
        entries.append(
            {
                "file_id": file_id,
                "attributes": {
                    "article_id": article_id,
                    "chunk_index": c.index,
                    "content_hash": content_hash,
                },
                "chunking_strategy": _STATIC_STRATEGY,
            }
        )

    # Phase 2: attach as one batch, poll to terminal (UPLOADING -> UPLOADED/FAILED).
    if entries:
        try:
            batch = client.vector_stores.file_batches.create(
                vector_store_id=store_id, files=entries
            )
            print(f"       batch {batch.id} created; embedding {len(entries)} file(s)...")
            batch = _poll_batch(client, store_id, batch.id)
            _resolve_batch(client, store_id, batch, file_to_index, results)
        except Exception as exc:  # noqa: BLE001 -- attach/poll failure fails these chunks
            for file_id, idx in file_to_index.items():
                results[idx] = ChunkResult(idx, file_id, FAILED, str(exc))

    return [results[c.index] for c in chunks]


def _create_base_file(client: OpenAI, article_id: str, chunk: ChunkText) -> str:
    filename = f"{article_id}-chunk-{chunk.index}.md"
    obj = client.files.create(
        file=(filename, chunk.text.encode("utf-8")), purpose="assistants"
    )
    return obj.id


def _poll_batch(client: OpenAI, store_id: str, batch_id: str):
    """Poll until the batch leaves ``in_progress``.

    Retry/backoff and a max-wait timeout are intentionally NOT here yet -- happy
    path only, with this function as the clean seam to add them once the
    stress-test phase shows what's needed (state-design.md §10/§11).
    """
    start = time.monotonic()
    batch = client.vector_stores.file_batches.retrieve(batch_id, vector_store_id=store_id)
    while batch.status == "in_progress":
        time.sleep(BATCH_POLL_INTERVAL_SECONDS)
        batch = client.vector_stores.file_batches.retrieve(
            batch_id, vector_store_id=store_id
        )
        counts = batch.file_counts
        elapsed = int(time.monotonic() - start)
        print(
            f"       ...embedding {counts.completed}/{counts.total} "
            f"done, {counts.in_progress} in progress ({elapsed}s)"
        )
    print(f"       batch {batch.status} after {int(time.monotonic() - start)}s")
    return batch


def _resolve_batch(client, store_id, batch, file_to_index, results) -> None:
    """Turn the finished batch into per-chunk UPLOADED/FAILED results."""
    counts = batch.file_counts
    if (
        batch.status == "completed"
        and counts.failed == 0
        and counts.completed == counts.total
    ):
        for file_id, idx in file_to_index.items():
            results[idx] = ChunkResult(idx, file_id, UPLOADED)
        return

    # Something didn't complete: read each file's real status + error message.
    per_file = _batch_file_status(client, store_id, batch.id)
    for file_id, idx in file_to_index.items():
        status, error = per_file.get(file_id, ("failed", "file missing from batch"))
        if status == "completed":
            results[idx] = ChunkResult(idx, file_id, UPLOADED)
        else:
            results[idx] = ChunkResult(idx, file_id, FAILED, error or status)


def _batch_file_status(client: OpenAI, store_id: str, batch_id: str) -> dict:
    """``{file_id: (status, error_message|None)}`` for every file in the batch."""
    out: dict[str, tuple[str, str | None]] = {}
    for f in client.vector_stores.file_batches.list_files(
        batch_id, vector_store_id=store_id
    ):
        last_error = getattr(f, "last_error", None)
        out[f.id] = (f.status, last_error.message if last_error else None)
    return out
