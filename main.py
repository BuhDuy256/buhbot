"""OptiBot daily-sync entry point -- thin orchestrator only (code-structure.md).

Reads as the phase list: lock -> settings -> load state -> find/create store ->
reconcile orphans -> fetch -> process each article -> report -> exit code.
All detail logic lives in ``src/``.
"""

import sys

from src import process, reconcile, vector_store, zendesk
from src.config import STORE_NAME
from src.lock import AlreadyRunningError, single_run_lock
from src.report import Outcome, RunReport
from src.settings import load_settings
from src.state import HashStore


def run() -> int:
    settings = load_settings()          # OPENAI_API_KEY from env
    client = settings.client()
    state = HashStore.load()            # §6 delta-detection state
    store_id = vector_store.find_or_create(client, STORE_NAME)  # §11 identity by name
    reconcile.orphans(client, store_id, state)                  # §10 crash-orphan sweep

    articles = zendesk.fetch_all_articles()                     # DISCOVERED
    report = RunReport()
    for art in articles:
        # Per-article guard: one bad article must not take down the other 29-49
        # (transition-techniques.md "Why per-article try/except").
        try:
            report.add(process.article(art, client, store_id, state))
        except Exception as exc:  # noqa: BLE001
            print(f"[error] article {art.id} crashed: {exc}")
            report.add(Outcome.failed(art.id))
    report.log()
    return report.exit_code()


def main() -> None:
    try:
        with single_run_lock():
            code = run()
    except AlreadyRunningError as exc:
        print(f"[lock] {exc}")
        sys.exit(1)
    sys.exit(code)


if __name__ == "__main__":
    main()
