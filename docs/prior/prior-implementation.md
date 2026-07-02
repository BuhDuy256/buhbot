# Prior Implementation Analysis — `optimus-bot-pipeline`

## Status of this document

This document analyzes a **previous, non-final attempt** at this take-home test, located in
`optimus-bot-pipeline/` at the repo root. That folder is git-ignored — it exists only on this
machine, is not committed, and future sessions (human or AI) will not have file access to it
unless this document is read first.

**This is a reference, not a spec.** Do not copy the previous implementation's code or
structure by default. Where this document recommends a change, treat that as the current
guidance for the new implementation — it supersedes what the old code did.

Everything below was derived by reading the old codebase and probing its actual on-disk
output (`data/hash_store.json`, `data/raw/*.json`, `data/markdown/*.md`) — not just its
README. Two of the "known limitations" below are empirically confirmed bugs, not guesses.

---

## 1. Overall Architecture

```
Zendesk Help Center API (support.optisigns.com)
        │
        ▼
  src/scraper.py ──► clean_html() ──► markdownify() ──► chunk_text()
        │                                                    │
        │                                                    ▼
        │                                     data/markdown/<slug>-part<N>.md
        ▼                                     data/raw/<slug>.json
  data/hash_store.json  ◄────────────────────────────┘
  (delta-detection state: content hash, updated_at, openai_file_ids, num_chunks)
        │
        ▼
  src/uploader.py ──► OpenAI Files API ──► OpenAI Vector Store (file_batches.create_and_poll)
        │
        ▼
  data/hash_store.json updated with new openai_file_ids
```

`main.py` is a two-line orchestrator: `scraper()` then `uploader(changed_articles=...)`.
There is no CLI, no logging framework (plain `print`), no retry/backoff layer.

## 2. End-to-End Workflow

1. Load `data/hash_store.json` (creates an empty one if missing: `{last_fetching_time: None, articles: {}}`).
2. **First run** (`last_fetching_time is None`): fetch up to `MAX_ARTICLES_IN_DEVELOPMENT`
   articles (dev mode) or all pages (prod mode) via `GET /api/v2/help_center/en-us/articles`.
3. **Subsequent runs**: fetch the same full article list again, then filter client-side to
   articles whose `updated_at` is newer than `last_fetching_time` ("Layer 1").
4. For each candidate article: strip nav/ads/scripts with BeautifulSoup, convert to Markdown
   with `markdownify`, MD5-hash the Markdown body, and compare against the stored hash
   ("Layer 2"). Unchanged → `HASH_SKIPPED`. New → `ADDED`. Changed → `UPDATED` (old chunk
   files for that article are deleted from disk first).
5. Each surviving article is split into multiple `.md` chunk files by a hand-written
   token-aware splitter (`chunk_text`, ~150 lines of regex heuristics for paragraph/list/
   heading/code-block/sentence boundaries), each wrapped with a title + `Article URL:`
   header and footer.
6. `hash_store.json` is written with the new hash, `updated_at`, and `num_chunks`; then
   `scraper()` returns `{"added": {article_id: [chunk_paths]}, "updated": {...}}`.
7. `uploader()` uploads every chunk file for added/updated articles via `client.files.create`,
   batches them (500/batch) into the vector store via
   `client.vector_stores.file_batches.create_and_poll` — passing an **additional** server-side
   `chunking_strategy: static` — then, for updated articles, deletes the article's previous
   `openai_file_ids` from both the vector store and file storage.
8. `hash_store.json` is rewritten with the new `openai_file_ids` per article.

## 3. Component Responsibilities

| File | Responsibility |
|---|---|
| `main.py` | Orchestration only: `scraper()` → `uploader()`. No error boundary. |
| `src/config.py` | Constants: chunk sizes, batch size, `VECTOR_STORE_ID`, `ENV`. **Not environment-driven** — see §6. |
| `src/helper.py` | MD5 hashing + hash-store JSON load/save. |
| `src/scraper.py` | Fetch, clean, convert, chunk, hash, and persist articles. The bulk of the logic (~420 lines) and all the custom chunking heuristics live here. |
| `src/uploader.py` | Upload chunk files to OpenAI, manage vector-store file batches, delete stale files on update. |
| `tests/` | pytest suite; good unit coverage of pure functions (slug, hash, chunk boundaries), integration tests mock the OpenAI client and Zendesk API entirely. |
| `CHUNKING_STRATEGY.md`, `DELTA_DETECTION.md`, `DEPLOY.md`, `TESTING.md` | Design-rationale docs the author wrote per-topic instead of one long README. |

## 4. Data Flow & On-Disk Artifacts

- `data/raw/<slug>.json` — the raw Zendesk article object, one file per article, overwritten on update.
- `data/markdown/<slug>-part<N>.md` — one file per chunk. On update, old `part*.md` files for
  that article are deleted by filename glob before new ones are written.
- `data/hash_store.json` — the only persistent state between runs:
  ```json
  {
    "last_fetching_time": 1769601452,
    "articles": {
      "<article_id>": {
        "hash": "<md5 of markdown body>",
        "openai_file_ids": ["file-..."],
        "updated_at": "<zendesk updated_at>",
        "num_chunks": 2
      }
    }
  }
  ```
  This file is the delta-detection source of truth *and* the mapping needed to clean up
  vector-store files on update/delete. Losing it (e.g. a bad CI cache) forces a full
  re-upload with no way to delete the orphaned old files, since the old `openai_file_ids`
  would no longer be known.

## 5. Design Decisions & Rationale (from the old docs, condensed)

- **Manual chunking instead of relying on OpenAI's auto-split**: motivated by cost
  predictability (`CHUNK_BODY_TOKENS=800` → ~$0.05/query ceiling at 5 search results) and by
  wanting each chunk to carry the article title/URL for citation. See §6 for why this
  reasoning doesn't fully hold up.
- **Two-layer delta detection** (`updated_at` filter, then content hash): the `updated_at`
  field on Zendesk articles changes for metadata edits too, so it's a cheap-but-noisy
  pre-filter; the hash is the real "did the body change" check, applied only to the
  pre-filtered candidates. Sound idea in principle — see §6 for why Layer 1 currently buys
  nothing.
- **GitHub Actions instead of DigitalOcean**: the take-home explicitly allows any
  cloud/public host; the author chose GitHub Actions because DigitalOcean required credit
  card verification with a $24 minimum deposit they didn't have. Documented in the README —
  a reasonable, honestly-stated constraint, not a shortcut.
- **`.md` chunk files are the upload unit, not the article**: one file per chunk means the
  vector store ends up with N files per article instead of 1, which is what makes the
  chunker bug in §6 so costly (609 files from one article, not 609 chunks inside one file).

## 6. Known Limitations (empirically confirmed, not speculative)

### 6.1 Chunker runaway bug — confirmed, high severity

`data/hash_store.json` (a real dev run, `ENV=development`, 50 articles) shows one article
(`48241081473043`, "Operational Schedule Troubleshooting", 12,542 raw characters — should be
~4-5 chunks at `CHUNK_BODY_TOKENS=800`) produced **609 chunk files**. Reading
`...part1.md`, `...part2.md`, `...part3.md` directly shows each chunk advancing by only a
handful of characters past the previous one — near-total content duplication between
consecutive chunks. Those 609 chunks account for **609 of 777 total chunks (78%)** across
all 50 articles combined in that snapshot.

Root-cause hypothesis (from reading `chunk_text`/`find_backward_safe_split` in
`src/scraper.py`): the fallback `pos = max(pos + 1, end_pos - overlap_chars)` means that if
`find_backward_safe_split` returns a split point close to the current position (which this
article's mixed table/link/heading Markdown seems to trigger), the loop advances by as
little as 1 character per iteration instead of by a full chunk-width. The synthetic test
fixtures (`long_text_with_headings`, `text_with_lists` in `conftest.py`) are clean lorem-ipsum
text and never exercise this path — **no test caught this**, and it directly contradicts the
cost-predictability claim in `CHUNKING_STRATEGY.md`/README (5,000 tokens / $0.05 per query
assumes ~1 chunk ≈ 1 semantic unit, not 609 near-duplicates for one article).

### 6.2 Infra config hardcoded in source, not environment-driven

`VECTOR_STORE_ID` and `ENV` (`"development"` / `"production"`) live as literals in
`src/config.py`, not as environment variables. Only `OPENAI_API_KEY` is read from the
environment. This means:
- Switching dev → prod requires editing source and redeploying, not setting a flag.
- The README instructs manually creating the vector store via the OpenAI dashboard UI and
  pasting the ID into `config.py` — a manual step for something that could be fully
  API-driven and env-injected.

### 6.3 Daily job deployment is documented but not present in the repo

`DEPLOY.md` describes a `daily-sync.yml` GitHub Actions workflow in detail (schedule, data
artifact caching, secrets setup). No `.github/workflows/` directory or any `.yml`/`.yaml`
file exists anywhere in `optimus-bot-pipeline/`. The only evidence the daily job ever ran is
a screenshot (`docs/images/daily-job-logs.png`). This is the single biggest gap against the
grading rubric's "Daily job deployment & logs" criterion (15 pts) — the deployment isn't
reproducible from the code as committed.

### 6.4 Upload success is unverifiable from the persisted state

In the same `hash_store.json` snapshot, **all 50 articles have `openai_file_ids: []`** —
zero evidence any upload ever completed successfully against this data, despite `num_chunks`
being populated (which only requires `scraper()`, not `uploader()`). Either `uploader()` was
never run to completion with a valid key against this snapshot, or a failure there is
silently swallowed (`upload_added_articles` catches and prints per-file exceptions but never
raises, so a fully-failed upload still returns a hash_store update marking articles as
processed). Either way, the file on disk cannot currently prove the vector store upload path
was ever exercised end-to-end.

### 6.5 "Layer 1" delta filter fetches everything anyway

The Zendesk incremental articles endpoint
(`/api/v2/help_center/incremental/articles?start_time=...`) is present in the code but
commented out with the note `# API is authorized`, and the code falls back to fetching the
**entire** article list every run (paginated at 100/page in prod) before filtering
client-side by `updated_at`. So "Layer 1" reduces hashing work, but does not reduce API
calls/network I/O — the "fast, filters out 99% instantly" claim in `DELTA_DETECTION.md`
only applies to the hashing step, not the fetch step. No `Authorization` header is sent on
any request, suggesting authenticated access to the incremental endpoint was never actually
attempted.

### 6.6 Double chunking: two chunking layers must be kept in sync manually

Files are pre-chunked client-side (`CHUNK_BODY_TOKENS=800`, `+100` metadata budget), then
uploaded with an *additional* server-side `chunking_strategy: {type: "static",
max_chunk_size_tokens: MAX_CHUNK_TOKENS}`. In the common case each file is already under
`MAX_CHUNK_TOKENS` so the server-side chunker is a no-op — but nothing enforces that
invariant, and the two knobs (`CHUNK_BODY_TOKENS` vs `MAX_CHUNK_TOKENS`) can drift out of
sync, silently re-introducing exactly the "unpredictable auto-split" problem the manual
chunker was built to avoid.

## 7. Lessons Learned

- **A working design doc is not evidence of a working system.** `CHUNKING_STRATEGY.md` and
  `DELTA_DETECTION.md` describe sound designs; the actual on-disk output shows the
  chunking implementation violates its own design in a specific, measurable way (§6.1).
  Trust generated artifacts over prose descriptions when auditing.
- **Synthetic test fixtures hide real-world failure modes.** All chunking tests use clean,
  short, hand-written text. The one bug that matters was only visible in real Zendesk HTML
  (a table + inline links + short paragraphs) — content shapes the fixtures never modeled.
- **Constraints documented honestly are still constraints.** The DigitalOcean → GitHub
  Actions pivot (due to a card-verification requirement) was a reasonable call, but the
  actual workflow file was never committed, so the pivot's outcome can't be verified from
  the repo alone. Documenting a decision isn't the same as shipping its artifact.
- **Silent exception handling hides upload failures.** Catching and printing exceptions
  per-file in `upload_added_articles` without ever surfacing failure at the `uploader()` or
  `main.py` level means a fully-broken upload path still looks like a successful run from
  the process exit code / hash_store state.

## 8. Recommendations for the New Implementation

These are opinionated, not just observations — treat them as the current default plan
unless you decide otherwise.

1. **Seriously consider dropping the custom chunker entirely.** OpenAI's vector store
   `chunking_strategy: static` already gives token-budget control (the main stated reason
   for hand-rolling a splitter). The only thing the custom splitter adds beyond that is
   embedding title/URL into each chunk — which can be achieved more simply by uploading
   **one file per article** with a title/URL header (and letting OpenAI's server-side
   static chunker do all splitting). This also eliminates the class of bug in §6.1 outright
   (no custom split-point search = no runaway loop), and it shrinks the vector store to
   1 file per article instead of N, which simplifies delta-detection cleanup (1
   `openai_file_id` per article, not a list). Trade-off: less fine-grained control over
   exact split boundaries and overlap — acceptable given the take-home's own hint says
   "chunking strategy is up to you," and simplicity + reliability should outweigh
   marginal control here.
2. **Move all deployment-relevant config to environment variables** (`ENV`,
   `VECTOR_STORE_ID`, not just `OPENAI_API_KEY`), with the vector store created
   programmatically on first run if the env var is unset, rather than requiring a manual
   dashboard step. This matches the take-home's own emphasis on API-driven setup.
3. **Actually commit the daily-job deployment config** (GitHub Actions workflow file, or
   whatever platform is chosen) — a screenshot of past logs doesn't substitute for a
   reproducible, reviewable deployment definition in the repo.
4. **Fail loudly on upload failure.** `uploader()` should raise (or return a non-zero exit
   from `main.py`) if any file fails to upload, rather than silently persisting a
   hash_store that claims the article was processed. This is also what makes
   `docker run ... main.py` exiting 0 actually mean something.
5. **Add at least one regression test against real scraped content** (a captured HTML
   fixture with a table + inline links, similar to the article that broke chunking here),
   not just synthetic lorem-ipsum text — this is the one thing that would have caught
   §6.1 before it reached `data/`.
6. **Re-attempt the Zendesk incremental endpoint with proper auth** before assuming it's
   unavailable — the old code never sent an `Authorization` header, so "unauthorized" was
   never actually tested. If it works, Layer 1 becomes a real network-cost reduction, not
   just a hashing-cost reduction.
