# Implementation Brief — OptiBot Pipeline (buhbot)

Entry point for the session that writes the code. The design is **complete**; this
file is the map. Read the linked docs in order — do not re-derive decisions already
settled in them.

## Mission (one paragraph)

Scrape ≥30 articles from `support.optisigns.com` (Zendesk Help Center API) → clean to
Markdown → client-side chunk with a per-chunk `Article URL:` header → upload to an
OpenAI Vector Store via API → run daily in Docker, uploading only new/changed articles
(hash-based delta), logging added/updated/skipped/failed. Full requirements:
`docs/reqs/OptiSigns_Take-Home_Test_Updated.pdf`. Hard constraints: `CLAUDE.md`.

## Read in this order

1. `CLAUDE.md` — project constraints (verbatim system prompt, uv, snake_case,
   `docker run -e API_KEY=... main.py` exits 0, cryptic repo name, `main.py` thin).
2. `docs/lifecycle/state-design.md` — the Article/Chunk state machine, every decision +
   why (§1–§11). This is the spine.
3. `docs/lifecycle/transition-techniques.md` — how each transition is implemented, and
   why each alternative was rejected. Exact API calls per step.
4. `docs/lifecycle/code-structure.md` — how it all maps to modules in `src/`. Build from
   this.
5. `docs/draft/optimus-bot-pipeline-review.md` — the review that produced the settled
   decisions (client-side chunking, neutralize server chunking, write-after-confirm,
   exit-code, `.github/workflows/` path).
6. `docs/prior/prior-implementation.md` — analysis of the prior attempt
   (`optimus-bot-pipeline/`, gitignored, machine-local). Reference only — do NOT copy;
   it has confirmed bugs. Useful as a working call-shape reference (e.g. the Files API
   upload call).
7. `docs/api/api-map.md` — API doc index (Zendesk, OpenAI vector stores / files /
   file-batches / assistants). Read the specific endpoint doc before coding each call.

## Build order (modules — see code-structure.md for the full tree)

Nothing below is blocked; build in this order so each layer can be tested before the
next depends on it:

1. `config.py`, `settings.py`, `lock.py` — constants, env (`OPENAI_API_KEY` only),
   single-run lock.
2. Pure transforms (fixture-testable, no network): `content.py` (html→md + hash),
   `chunk.py` (split — **see open decision below**).
3. Adapters: `zendesk.py` (fetch, no auth), `vector_store.py` (find-or-create by name,
   list files, delete file), `uploader.py` (Chunk FSM: `files.create` → `file_batches`
   → poll).
4. `state.py` — `hash_store.json` load/save (atomic), queries, record_confirmed/failed.
5. Phases: `reconcile.py`, `process.py` (Article FSM — the heart), `report.py`.
6. `main.py` — wire the phases (skeleton in code-structure.md).
7. `Dockerfile`, `.github/workflows/` (or VM cron — see deploy note).

## Decided (do not reopen without reason — details in state-design.md §11)

- **State lives in `hash_store.json` on the VM disk** (Pattern A: Azure B1s VM +
  crontab + `docker run -v`). Not GitHub Actions (incremental endpoint needs auth /
  managed cron platforms lack persistent volumes — Render confirmed, Railway
  undocumented). Deploy host: Azure student VM.
- **Vector store: find-or-create by NAME** (e.g. `"optibot-kb"`) each run. No stored
  ID. `VECTOR_STORE_ID` does not exist as config.
- **Config: only `OPENAI_API_KEY` in `.env`**; `ENV` (dev=30 articles / prod=full)
  and everything else are code constants.
- **Assistant: created manually once in Playground, code never touches it.** Bind the
  store to it once, after the first run creates the store.
- **Hash the cleaned Markdown** (not raw HTML). **Zendesk `en-us/articles` needs no
  auth** (verified). **Delete-at-source articles: not handled** (keep stale chunks —
  avoids mass-delete on partial fetch). **Base File orphans: not cleaned.**
- **Crash recovery: reconciliation pass** at run start (delete vector-store files not
  in recorded known-good set) + **Lazy rollback** (FAILED article keeps its uploaded
  chunks, cleaned on next reprocess). state-design.md §10.
- **Neutralize server chunking**: attach with `chunking_strategy: static,
  max_chunk_size_tokens=4096, chunk_overlap_tokens=0`. **One file_batch per article**
  (its `file_counts` answers the all-or-nothing question directly).

## Deferred — decide during implementation / stress-test, not now

- **Chunk algorithm** (`chunk.py` internals): options A–D in transition-techniques.md
  ("Open decision: chunking algorithm"). Leaning B (Markdown-block-aware) or D
  (library) over A (patch the buggy old splitter). Module boundary `split_markdown()`
  is fixed; pick the internal method when you get there.
- **In-run retry/backoff + batch poll timeout** (`uploader.py`): implement the happy
  path first, then add these based on what the OS/network stress test actually shows.

## Note on the Files API upload call

`uploader.py` needs `POST /files` (bytes → `file_id`) before attaching via
`file_batches`. There is no dedicated `POST /files` doc in the repo
(`docs/api/openai/files/upload-files.md` is actually `GET /files` List), but the call
shape is confirmed by the prior code: `client.files.create(file=f,
purpose="assistants")` (`optimus-bot-pipeline/src/uploader.py:43`), and
`upload-files.md` confirms `"assistants"` is a valid `purpose`. Not a blocker.

## How to sanity-check against reality

The prior pipeline runs locally against the real Zendesk site:
`cd optimus-bot-pipeline && uv run main.py`. Use it to confirm endpoint behavior /
article shapes — but treat its code as a buggy reference, not a template.
