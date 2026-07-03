"""hash_store.json -- the ONLY place that writes delta-detection state.

The prior bug was a write at the wrong time (hash saved before upload was
confirmed). The fix is to make this the single write point: ``record_confirmed``
and ``record_failed`` are the only methods that touch disk, and they are only
called at an Article's terminal transition (state-design.md §6,
transition-techniques.md "PROCESSING -> CONFIRMED/FAILED").

Two rules that must not be "simplified away":
  * A FAILED article still persists its ``chunk_file_ids`` (whatever uploaded
    this attempt) but NOT its hash -- so the next run both cleans those chunks
    and reprocesses the article (§6, §7).
  * Writes are atomic (temp file + ``os.replace``) -- the state file lives on a
    persistent VM disk now, so a crash mid-write could otherwise corrupt it
    permanently (§6).

On-disk ``status`` is only ever CONFIRMED or FAILED. SKIPPED is a runtime
outcome (unchanged article) and by definition writes nothing.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .config import HASH_STORE_PATH

CONFIRMED = "CONFIRMED"
FAILED = "FAILED"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class HashStore:
    def __init__(self, path: Path, articles: dict[str, dict]):
        self.path = path
        self.articles = articles

    # --- load -----------------------------------------------------------
    @classmethod
    def load(cls, path: Path = HASH_STORE_PATH) -> "HashStore":
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(path, data.get("articles", {}))
        return cls(path, {})

    # --- queries (read-only) --------------------------------------------
    def get_status(self, article_id: str) -> str | None:
        entry = self.articles.get(article_id)
        return entry.get("status") if entry else None

    def get_hash(self, article_id: str) -> str | None:
        entry = self.articles.get(article_id)
        return entry.get("hash") if entry else None

    def get_chunk_ids(self, article_id: str) -> list[str]:
        entry = self.articles.get(article_id)
        return list(entry.get("chunk_file_ids", [])) if entry else []

    def known_good_file_ids(self) -> set[str]:
        """Union of ``chunk_file_ids`` across ALL articles (CONFIRMED and
        FAILED). Used by reconciliation to tell real files from crash-orphans;
        FAILED entries must be included, else Lazy rollback becomes Eager
        (state-design.md §10)."""
        ids: set[str] = set()
        for entry in self.articles.values():
            ids.update(entry.get("chunk_file_ids", []))
        return ids

    # --- the single write point -----------------------------------------
    def record_confirmed(
        self, article_id: str, content_hash: str, chunk_file_ids: list[str]
    ) -> None:
        self.articles[article_id] = {
            "status": CONFIRMED,
            "hash": content_hash,
            "confirmed_at": _now_iso(),
            "chunk_file_ids": list(chunk_file_ids),
        }
        self._save_atomic()

    def record_failed(self, article_id: str, chunk_file_ids: list[str]) -> None:
        entry = dict(self.articles.get(article_id, {}))
        entry["status"] = FAILED
        entry["failed_at"] = _now_iso()
        entry["chunk_file_ids"] = list(chunk_file_ids)
        # Deliberately do NOT set/overwrite "hash": the next run must treat this
        # article as still needing work (state-design.md §6).
        self.articles[article_id] = entry
        self._save_atomic()

    # --- atomic persistence ---------------------------------------------
    def _save_atomic(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"articles": self.articles}, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)  # atomic on the same filesystem
