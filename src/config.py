"""Static configuration for the OptiBot pipeline.

Everything here is a code-level constant on purpose. The only value that is read
from the environment is ``OPENAI_API_KEY`` (see ``settings.py``); see
``docs/lifecycle/state-design.md`` §11 for why ``ENV`` and the vector-store
identity are constants rather than env vars.
"""

from pathlib import Path

# --- run mode ---------------------------------------------------------------
# "development" caps how many articles are fetched so a local run is fast; the
# assignment requires >= 30, so the dev cap stays at or above that. Switching to
# "production" enables full pagination. Changing this needs a code edit + rebuild
# (accepted trade-off for a take-home -- state-design.md §11).
ENV: str = "development"
MAX_ARTICLES_DEV: int = 30

# --- Zendesk (no auth needed for this endpoint -- state-design.md §9) --------
ZENDESK_BASE_URL: str = "support.optisigns.com"
ZENDESK_ARTICLES_PATH: str = "/api/v2/help_center/en-us/articles"
ARTICLES_PER_PAGE: int = 100  # production pagination page size

# --- vector store identity (find-or-create by name -- state-design.md §11) ---
STORE_NAME: str = "optibot-kb"

# --- chunking ----------------------------------------------------------------
# CHUNK_BUDGET_TOKENS is the client-side per-chunk body budget. STATIC_* are
# passed to OpenAI to *neutralize* its server-side re-chunking: at 4096 vs a
# ~800-token client chunk there is a ~5x margin, so 1 uploaded file == 1 stored
# chunk. See optimus-bot-pipeline-review.md "Neutralize server-side chunking".
CHUNK_BUDGET_TOKENS: int = 800
STATIC_MAX_CHUNK_TOKENS: int = 4096
CHUNK_OVERLAP_TOKENS: int = 0
TOKENIZER_MODEL: str = "gpt-4o"  # tiktoken encoding used for client token counts

# Bumped whenever the per-chunk header TEMPLATE changes (e.g. adding the title
# line). It is folded into the delta hash so an existing deployment re-uploads
# every article once to pick up the new format -- a body-only hash would keep
# serving the old header forever because the body is unchanged. v1 = URL-only
# header; v2 = "# <title>" + "Article URL:" header.
CHUNK_TEMPLATE_VERSION: int = 2

# --- upload ------------------------------------------------------------------
# How often to re-poll a file_batch while it is still in_progress. A max-wait
# timeout is deliberately NOT set yet -- deferred to the stress-test phase
# (state-design.md §11 "Batch poll timeout").
BATCH_POLL_INTERVAL_SECONDS: float = 2.0

# --- state on disk (persistent VM volume -- state-design.md §11) -------------
REPO_ROOT: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = REPO_ROOT / "data"
HASH_STORE_PATH: Path = DATA_DIR / "hash_store.json"
LOCK_PATH: Path = DATA_DIR / ".run.lock"

# --- debug artifacts (inspection only, NOT on the upload path) ----------------
# When on, each run dumps the raw fetched JSON and the exact chunk Markdown to
# disk so the data can be eyeballed. The uploader still sends in-memory bytes --
# these files are never read back (see artifacts.py). Auto-on in development.
DUMP_ARTIFACTS: bool = ENV == "development"
RAW_DIR: Path = DATA_DIR / "raw"      # raw/<article_id>.json
CHUNK_DIR: Path = DATA_DIR / "chunks"  # chunks/<article_id>-chunk-<i>.md


def max_articles() -> int | None:
    """Fetch cap for the current ``ENV``. ``None`` means full pagination."""
    return MAX_ARTICLES_DEV if ENV == "development" else None
