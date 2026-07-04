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

# --- Assistant identity (eval-only; the pipeline never touches the Assistant) --
# The deployed Assistant is created BY HAND in the Playground (state-design.md
# §11), so its id isn't known until after that one-time setup. It is a plain
# identifier, not a secret, so it lives here as a constant -- keeping the pipeline
# to a single env var (OPENAI_API_KEY) as the assignment requires, instead of
# adding OPTIBOT_ASSISTANT_ID. Paste the `asst_...` id here once, then run the
# eval. Empty until then; evals/run_eval.py fails loudly if it is still blank.
ASSISTANT_ID: str = ""

# --- chunking ----------------------------------------------------------------
# The chunker (chunk.py) packs whole Markdown blocks into chunks, then prepends a
# fixed token budget of LOOK-BACK overlap taken from the previous chunk. Two
# ceilings govern size:
#
# CHUNK_MAX_TOKENS is the HARD cap on a normal emitted chunk.text (header +
# look-back overlap + body). Every ordinary chunk stays at or below it, so chunk
# size is directly controlled and predictable. The cap always wins: when a body is
# large the look-back overlap shrinks (down to zero) rather than push the chunk
# over. STATIC_* below is passed to OpenAI to *neutralize* its server-side
# re-chunking -- at 4096 vs an 800-token client chunk there is a ~5x margin, so 1
# uploaded file == 1 stored chunk.
CHUNK_MAX_TOKENS: int = 800

# Target size of the LOOK-BACK overlap repeated at the head of each chunk: the
# whole trailing lines of the previous chunk, up to this many tokens. Counted
# INSIDE CHUNK_MAX_TOKENS -- a chunk carries ~CHUNK_LOOKBACK_TOKENS of overlap plus
# the remaining budget of new content. Token-budgeted (not "N whole blocks") so a
# fat trailing block can no longer make two neighbours near-duplicates.
CHUNK_LOOKBACK_TOKENS: int = 200

# The ONE documented exception to CHUNK_MAX_TOKENS: a single code fence larger than
# a normal chunk is kept ATOMIC (the assignment requires preserving code blocks)
# and may ride above CHUNK_MAX_TOKENS up to here. Kept far below OpenAI's 4096
# upload ceiling so even an exempt fence is never re-chunked server-side (which
# would strip the Article URL header off the tail pieces). A fence larger than this
# backstop -- pathological -- is the only case a fence is ever split.
FENCE_MAX_TOKENS: int = 3000

# The static max_chunk_size_tokens handed to OpenAI at upload (uploader.py). Set
# to the API maximum (4096) -- the ceiling ABOVE which OpenAI slices a file. We
# always stay under FENCE_MAX_TOKENS, so the gap to this ceiling is the safety
# buffer against any divergence between our tiktoken count and OpenAI's server
# tokenizer. Raising OpenAI's side is impossible (4096 is the API max); the buffer
# must come from OUR cap being lower, never from lowering this.
STATIC_MAX_CHUNK_TOKENS: int = 4096
CHUNK_OVERLAP_TOKENS: int = 0  # server-side static-strategy overlap (kept 0)
TOKENIZER_MODEL: str = "gpt-4o"  # tiktoken encoding used for client token counts

# Bumped whenever the per-chunk header TEMPLATE or the chunk *bodies* change, so
# an existing deployment re-uploads every article once to pick up the new format
# (a body-only hash would keep serving the old chunks forever). v1 = URL-only
# header; v2 = "# <title>" + "Article URL:"; v3 = + "Section Path:" breadcrumb
# and one-block overlap; v4 = token-budgeted look-back overlap + hard 800-token
# per-chunk cap (fences exempt).
CHUNK_TEMPLATE_VERSION: int = 4

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
