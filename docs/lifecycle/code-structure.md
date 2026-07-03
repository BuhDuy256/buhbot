# Code Structure — Modules & Mapping

Third file in `docs/lifecycle/`, after `state-design.md` (what the states are + why)
and `transition-techniques.md` (how each transition is done). This file says **where
each piece lives in `src/`** and why the code is cut this way.

Written so a future session opens `src/`, reads top to bottom, and understands the
whole run without reverse-engineering it.

## Organizing principle: separate three kinds of code

The prior attempt's `scraper.py` was ~420 lines mixing fetch (I/O), clean/chunk
(pure), hashing, and disk writes all together. That mixing is *why* the 609-chunk
chunker bug hid — the chunker wasn't isolable or testable on its own
(`docs/prior/prior-implementation.md` §7). The new structure separates code by its
**nature**, so each kind can be read and tested independently:

| Kind | Property | Why separate |
|---|---|---|
| **Adapter (I/O)** | Talks to the outside world (Zendesk, OpenAI) | Only place with network; mockable in tests |
| **Pure transform** | Input → output, no I/O, no state | Testable with fixtures, no network. The bug-prone chunker lives here, isolated |
| **Orchestration (phase)** | Sequences the above per the lifecycle | Reads like the run; holds no detail logic |

## Key idea: two nested state machines → two files

The design (`state-design.md` §2) is two nested FSMs. Each gets its own home:

| FSM | Home | Responsibility |
|---|---|---|
| **Article FSM** (parent) | `process.py` | DISCOVERED→HASHED→PROCESSING→CONFIRMED/FAILED/SKIPPED; the all-or-nothing decision (§5) |
| **Chunk FSM** (child) | `uploader.py` | PENDING→UPLOADING→UPLOADED/FAILED — this *is* the upload |

`process.py` (parent) calls `uploader.py` (child), gets per-chunk results, and
aggregates them into the article's fate. Parent orchestrates; child owns the upload
mechanics.

## The tree

```
main.py                 # thin orchestrator (skeleton below)

src/
  config.py             # constants: ENV, STORE_NAME, CHUNK_BUDGET, STATIC_MAX=4096, OVERLAP=0, ZENDESK_URL
  settings.py           # read OPENAI_API_KEY from env, build OpenAI client
  lock.py               # single_run_lock() context manager — blocks overlapping runs   -> §11

  # -- adapters (I/O only) --
  zendesk.py            # fetch_all_articles() -> list[Article]                          -> DISCOVERED (fetch)
  vector_store.py       # find_or_create_by_name(), list_all_files(), delete_file()      -> §11 identity, §10 reconcile, §7 cleanup
  uploader.py           # UPLOAD — owns Chunk FSM:                                        -> PROCESSING upload, §4
                        #   upload_chunks(store_id, chunks) -> list[ChunkResult]
                        #   internally: create_base_file() + create_batch() + poll_batch() + read per-file status

  # -- pure transforms (no I/O, fixture-tested) --
  content.py            # html_to_markdown() + content_hash()                            -> DISCOVERED->HASHED
  chunk.py              # split_markdown() -> list[ChunkText]                             -> PROCESSING chunk (bug-prone, isolated)

  # -- state --
  state.py              # HashStore.load()/save() (atomic), get_status/get_hash/         -> §6 schema, write-after-confirm
                        #   get_chunk_ids, record_confirmed(), record_failed()

  # -- phases (glue the above) --
  reconcile.py          # reconcile_orphans(store, state)                                -> §10
  process.py            # process_article() — owns Article FSM                           -> §3, §5, §7
  report.py             # RunReport: tally added/updated/skipped/failed, exit_code()     -> end-of-run
```

## Granularity decisions (committed defaults)

- **Phases as separate files** (`reconcile.py` / `process.py` / `report.py`), not one
  `pipeline.py` — so `ls src/` shows the pipeline. Serves "read the directory,
  understand the run."
- **`uploader.py` split out from `vector_store.py`** — upload is a first-class concern
  (20 grading points, owns the Chunk FSM), not just another API call buried in a store
  wrapper.
- **`content.py` = clean + hash together** — both belong to the single DISCOVERED→HASHED
  transition and always run together.
- **`chunk.py` always stands alone** — it is the highest-risk, most-independently-tested
  piece; burying it is exactly what let the old bug through.

## main.py — reads as the phase list

```python
def main() -> None:
    with single_run_lock():                              # lock §11
        settings = load_settings()                       # OPENAI_API_KEY from env
        state = HashStore.load()                         # §6
        store = vector_store.find_or_create(STORE_NAME)  # §11 identity by name
        reconcile.orphans(store, state)                  # §10 crash-orphan sweep

        articles = zendesk.fetch_all_articles()          # DISCOVERED
        report = RunReport()
        for article in articles:
            report.add(process.article(article, store, state))
        report.log()                                     # counts
    sys.exit(report.exit_code())                         # non-zero if any FAILED
```

## process.py — one article's lifecycle (upload explicit)

```python
def article(art, store, state) -> Outcome:
    md   = content.html_to_markdown(art.body)            # DISCOVERED->HASHED
    h    = content.content_hash(md)

    verdict = compare(state, art.id, h)                  # HASHED
    if verdict == SKIP:      return Outcome.skipped(art.id)

    old_ids = state.get_chunk_ids(art.id)                # cleanup-before-reprocess §7
    for fid in old_ids: vector_store.delete_file(store, fid)

    chunks  = chunk.split_markdown(md, art.html_url)     # PROCESSING chunk
    results = uploader.upload_chunks(store, chunks)      # UPLOAD (Chunk FSM)

    if all(r.status == UPLOADED for r in results):       # §5 all-or-nothing
        state.record_confirmed(art.id, h, [r.file_id for r in results])
        return Outcome.confirmed(art.id, verdict)        # added / updated
    else:                                                # lazy rollback §10:
        state.record_failed(                             #   keep uploaded chunks,
            art.id,                                      #   record their ids for
            [r.file_id for r in results if r.status == UPLOADED],  # next-run cleanup
        )
        return Outcome.failed(art.id)
```

## uploader.py — upload is two API calls, not one

```python
def upload_chunks(store_id, chunks) -> list[ChunkResult]:
    file_ids = []
    for c in chunks:                                  # each chunk: PENDING -> UPLOADING
        fid = create_base_file(c.text)                # POST /files  -> file_id
        file_ids.append(fid)

    batch = create_batch(                             # POST /vector_stores/{id}/file_batches
        store_id, file_ids,
        chunking_strategy=STATIC_4096_0,              # neutralize server re-chunk (settled)
        attributes_per_file={article_id, chunk_index, content_hash},
    )
    batch = poll_batch(store_id, batch.id)            # until status != in_progress
    return read_per_file_status(store_id, batch.id)   # each chunk -> UPLOADED / FAILED
```

**Files API note (not blocking):** uploading a chunk is two calls — `POST /files`
(base Files API: bytes → `file_id`), then attach via `file_batches`. The docs are now
organised as: `docs/api/openai/files/` = base Files API,
`docs/api/openai/vector-store-files/` = store-attach ops,
`docs/api/openai/vector-store-file-batches/` = batch ops. The one file under `files/`
(`upload-files.md`) documents `GET /files` (List), **not** `POST /files` (Upload) —
so the upload endpoint has no dedicated doc. It isn't needed to proceed: the prior
`uploader.py` (`optimus-bot-pipeline/src/uploader.py:43`) shows the exact call
`client.files.create(file=f, purpose="assistants")`, and `upload-files.md` confirms
`"assistants"` is a valid `purpose`. `uploader.py` can be written from that.

## Full mapping: doc section → module

| Doc | Module |
|---|---|
| §3 Article FSM | `process.py` |
| §4 Chunk FSM | `uploader.py` |
| §5 all-or-nothing | `process.py` (aggregate) |
| §6 schema + write-after-confirm | `state.py` |
| §7 cleanup-before-reprocess | `process.py` → `vector_store.delete_file` |
| §10 reconciliation | `reconcile.py` + `vector_store.list_all_files` |
| §10 lazy rollback | `process.py` (`record_failed` keeps chunks) |
| §11 identity by name | `vector_store.find_or_create_by_name` |
| §11 lock | `lock.py` |
| DISCOVERED fetch | `zendesk.py` |
| DISCOVERED→HASHED clean+hash | `content.py` |
| PROCESSING chunk | `chunk.py` |
| PROCESSING upload | `uploader.py` |
| end-of-run counts/exit | `report.py` |

## Still open (does not block writing most modules)

- **Chunk algorithm** inside `chunk.py` — options A/B/C/D in `transition-techniques.md`.
  The module boundary is fixed (`split_markdown()`); only its internals are undecided.
- **Retry/backoff + batch poll timeout** inside `uploader.py` — deferred to the
  stress-test phase (`state-design.md` §10, §11). The function signatures don't change
  when these are added later.
- **`POST /files` formal doc** — absent but not blocking; `uploader.py` can be written
  from the prior code's confirmed call (see "Files API note" above). Add the doc later
  only if size-limit / return-shape confirmation is wanted.
