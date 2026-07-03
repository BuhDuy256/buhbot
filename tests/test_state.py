"""Tests for the single write point (src/state.py).

The original bug was a write at the wrong time. These pin the two rules that
prevent its return: FAILED never writes a hash, and both terminal states persist
chunk_file_ids for later cleanup/reconciliation.
"""

import json

from src.state import CONFIRMED, FAILED, HashStore


def _store(tmp_path):
    return HashStore(tmp_path / "hash_store.json", {})


def test_confirmed_persists_and_reloads(tmp_path):
    s = _store(tmp_path)
    s.record_confirmed("1", "sha256:aaa", ["file_a", "file_b"])

    reloaded = HashStore.load(s.path)
    assert reloaded.get_status("1") == CONFIRMED
    assert reloaded.get_hash("1") == "sha256:aaa"
    assert reloaded.get_chunk_ids("1") == ["file_a", "file_b"]


def test_failed_never_writes_hash_when_none_existed(tmp_path):
    s = _store(tmp_path)
    s.record_failed("1", ["file_a"])

    reloaded = HashStore.load(s.path)
    assert reloaded.get_status("1") == FAILED
    assert reloaded.get_hash("1") is None  # crucial: next run must reprocess
    assert reloaded.get_chunk_ids("1") == ["file_a"]


def test_failed_after_confirmed_keeps_old_hash(tmp_path):
    s = _store(tmp_path)
    s.record_confirmed("1", "sha256:old", ["old_a", "old_b"])
    s.record_failed("1", ["new_a"])  # a later update attempt failed

    reloaded = HashStore.load(s.path)
    assert reloaded.get_status("1") == FAILED
    # hash stays the OLD confirmed one -- not the new content -- so the article
    # is still seen as needing work, and won't be skipped on the new content.
    assert reloaded.get_hash("1") == "sha256:old"
    assert reloaded.get_chunk_ids("1") == ["new_a"]


def test_known_good_unions_confirmed_and_failed(tmp_path):
    s = _store(tmp_path)
    s.record_confirmed("1", "sha256:a", ["c1", "c2"])
    s.record_failed("2", ["f1"])
    assert s.known_good_file_ids() == {"c1", "c2", "f1"}


def test_saved_file_is_valid_json(tmp_path):
    s = _store(tmp_path)
    s.record_confirmed("1", "sha256:a", ["c1"])
    data = json.loads(s.path.read_text(encoding="utf-8"))
    assert data == {
        "articles": {
            "1": {
                "status": "CONFIRMED",
                "hash": "sha256:a",
                "confirmed_at": data["articles"]["1"]["confirmed_at"],
                "chunk_file_ids": ["c1"],
            }
        }
    }


def test_missing_article_queries_are_safe(tmp_path):
    s = _store(tmp_path)
    assert s.get_status("nope") is None
    assert s.get_hash("nope") is None
    assert s.get_chunk_ids("nope") == []


def test_get_chunk_ids_returns_copy(tmp_path):
    s = _store(tmp_path)
    s.record_confirmed("1", "sha256:a", ["c1"])
    ids = s.get_chunk_ids("1")
    ids.append("mutated")
    assert s.get_chunk_ids("1") == ["c1"]  # internal state not mutated
