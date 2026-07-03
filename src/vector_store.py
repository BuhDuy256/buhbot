"""Vector store adapter (I/O only): identity, listing, deletion.

The store is identified by NAME, not a stored ID (state-design.md §11): every
run lists stores and matches ``STORE_NAME``; found -> reuse, missing -> create.
That makes the name a stable identifier that survives total loss of
``hash_store.json`` and removes ``VECTOR_STORE_ID`` as a config knob.
"""

from openai import OpenAI

from .config import STORE_NAME


def find_or_create(client: OpenAI, name: str = STORE_NAME) -> str:
    """Return the id of the store named ``name``, creating it on first run."""
    for store in client.vector_stores.list():  # SDK auto-paginates
        if store.name == name:
            print(f"[store] reusing '{name}' ({store.id})")
            return store.id
    store = client.vector_stores.create(name=name)
    print(f"[store] created '{name}' ({store.id})")
    return store.id


def list_all_files(client: OpenAI, store_id: str) -> list[str]:
    """Every file id currently attached to the store (all pages)."""
    return [f.id for f in client.vector_stores.files.list(vector_store_id=store_id)]


def delete_file(client: OpenAI, store_id: str, file_id: str) -> None:
    """Detach one file from the store. The underlying base File is left in
    place -- accepted (state-design.md §11, 'Base File orphans')."""
    client.vector_stores.files.delete(vector_store_id=store_id, file_id=file_id)
