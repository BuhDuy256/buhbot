"""Article FSM tests (src/process.py) with the network faked out.

Covers the decisions the design is built around: write-after-confirm,
all-or-nothing (§5), lazy rollback (§10), cleanup-before-reprocess (§7), and the
HASHED verdict (added/updated/skip).
"""

import pytest

from src import process
from src.state import HashStore
from src.uploader import FAILED, UPLOADED, ChunkResult
from src.zendesk import Article


def _article(body="<p>hello world</p>", aid="1"):
    return Article(
        id=aid,
        title="T",
        html_url="https://support.optisigns.com/hc/en-us/articles/1",
        body=body,
        updated_at="2026-07-03T00:00:00Z",
    )


@pytest.fixture(autouse=True)
def _no_artifact_dump(monkeypatch):
    """Keep the debug side-channel from writing into the real data/ dir."""
    monkeypatch.setattr(process.artifacts, "dump_chunks", lambda *a, **k: None)


@pytest.fixture
def state(tmp_path):
    return HashStore(tmp_path / "hash_store.json", {})


@pytest.fixture
def deleted(monkeypatch):
    """Record vector_store.delete_file calls instead of hitting the network."""
    calls: list[str] = []
    monkeypatch.setattr(
        process.vector_store, "delete_file",
        lambda client, store_id, file_id: calls.append(file_id),
    )
    return calls


def _fake_upload(monkeypatch, statuses):
    """Make uploader.upload_chunks return one ChunkResult per chunk with the
    given statuses (ignoring how many chunks were actually produced)."""
    def fake(client, store_id, chunks, *, article_id, content_hash):
        return [
            ChunkResult(i, f"file_{article_id}_{i}", st)
            for i, st in enumerate(statuses)
        ]
    monkeypatch.setattr(process.uploader, "upload_chunks", fake)


# --- added / confirmed ------------------------------------------------------

def test_new_article_all_uploaded_is_confirmed_added(state, deleted, monkeypatch):
    _fake_upload(monkeypatch, [UPLOADED, UPLOADED])
    out = process.article(_article(), client=None, store_id="vs", state=state)

    assert out.kind == "added"
    assert state.get_status("1") == "CONFIRMED"
    assert state.get_chunk_ids("1") == ["file_1_0", "file_1_1"]
    assert deleted == []  # brand-new article has nothing to clean up


def test_unchanged_article_is_skipped_with_no_upload(state, deleted, monkeypatch):
    _fake_upload(monkeypatch, [UPLOADED])
    art = _article()
    process.article(art, None, "vs", state)  # first run -> confirmed

    # second run, same content: must skip without uploading or deleting
    def boom(*a, **k):
        raise AssertionError("upload_chunks must not be called on a skip")
    monkeypatch.setattr(process.uploader, "upload_chunks", boom)

    out = process.article(art, None, "vs", state)
    assert out.kind == "skipped"
    assert deleted == []


# --- all-or-nothing + lazy rollback -----------------------------------------

def test_partial_upload_is_failed_and_keeps_uploaded_chunks(state, deleted, monkeypatch):
    _fake_upload(monkeypatch, [UPLOADED, FAILED, UPLOADED])
    out = process.article(_article(), None, "vs", state)

    assert out.kind == "failed"
    assert state.get_status("1") == "FAILED"
    # lazy rollback: only the UPLOADED chunk ids are kept, for next-run cleanup
    assert state.get_chunk_ids("1") == ["file_1_0", "file_1_2"]
    # hash NOT written -> next run reprocesses
    assert state.get_hash("1") is None


# --- cleanup-before-reprocess -----------------------------------------------

def test_updated_article_deletes_old_chunks_first(state, deleted, monkeypatch):
    _fake_upload(monkeypatch, [UPLOADED])
    process.article(_article(body="<p>v1</p>"), None, "vs", state)
    assert state.get_chunk_ids("1") == ["file_1_0"]

    # new content -> updated -> old chunk must be deleted before new upload
    _fake_upload(monkeypatch, [UPLOADED, UPLOADED])
    out = process.article(_article(body="<p>v2 longer</p>"), None, "vs", state)

    assert out.kind == "updated"
    assert deleted == ["file_1_0"]  # the old chunk was cleaned up
    assert state.get_chunk_ids("1") == ["file_1_0", "file_1_1"]


def test_failed_article_is_reprocessed_and_old_chunks_cleaned(state, deleted, monkeypatch):
    _fake_upload(monkeypatch, [UPLOADED, FAILED])
    process.article(_article(), None, "vs", state)  # -> FAILED, keeps file_1_0
    assert state.get_status("1") == "FAILED"

    # next run: FAILED article reprocesses even if hash matches; its recorded
    # (partial) chunk ids are cleaned up first
    _fake_upload(monkeypatch, [UPLOADED, UPLOADED])
    out = process.article(_article(), None, "vs", state)

    assert out.kind in ("updated", "added")
    assert "file_1_0" in deleted
    assert state.get_status("1") == "CONFIRMED"


# --- empty body -------------------------------------------------------------

def test_empty_body_confirms_with_no_chunks(state, deleted, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("upload must not be called for an empty article")
    monkeypatch.setattr(process.uploader, "upload_chunks", boom)

    out = process.article(_article(body="   "), None, "vs", state)
    assert out.kind == "added"
    assert state.get_status("1") == "CONFIRMED"
    assert state.get_chunk_ids("1") == []
