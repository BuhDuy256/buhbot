"""Run-start reconciliation pass (state-design.md §10).

Deletes crash-orphans: files that exist in the vector store but aren't in the
recorded known-good set (the union of every article's ``chunk_file_ids``, both
CONFIRMED and FAILED). Such a file's owning article never reached a terminal
state, so its ids were never written -- the set-difference is exactly how a
crash-orphan is defined. Also catches drift from other causes (e.g. a file
removed via the dashboard).
"""

from . import vector_store


def orphans(client, store_id: str, state) -> int:
    store_files = set(vector_store.list_all_files(client, store_id))
    known_good = state.known_good_file_ids()
    orphan_ids = store_files - known_good

    deleted = 0
    for file_id in orphan_ids:
        try:
            vector_store.delete_file(client, store_id, file_id)
            deleted += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[reconcile] could not delete orphan {file_id}: {exc}")

    print(f"[reconcile] {deleted} orphan file(s) deleted ({len(store_files)} in store)")
    return deleted
