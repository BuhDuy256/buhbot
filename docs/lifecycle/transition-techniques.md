# Techniques for Each Lifecycle Transition

Companion to `state-design.md`. That file says *what* the states are and *why* this
shape was chosen. This file says *how* each move from one state to the next is
actually done, and *why that method* over the other options that were considered.

Written so a future session can implement directly from this, without re-researching
the API docs from scratch.

---

## Run start (before any article): reconciliation pass

**What happens:** before touching any article, detect and delete orphaned chunk
files left in the vector store by a previous crashed run. Rationale and the crash
scenario are in `state-design.md` §10 — this section is just the mechanics.

**How:**
1. List every file currently in the vector store:
   `GET /vector_stores/{id}/files` (`docs/api/openai/vector-store-files/list-vectore-store-files.md`),
   following `has_more` / `last_id` pagination until exhausted. At ~30-60 articles ×
   a few chunks each, this is 1-3 pages of 100.
2. Build the set of *known-good* file IDs: the union of `chunk_file_ids` across every
   article in `hash_store.json` (both `CONFIRMED` and `FAILED` — a `FAILED` article's
   recorded chunks are legitimately still in the store under Lazy rollback, so they
   are not orphans).
3. Any vector-store file whose `id` is **not** in that known-good set is an orphan
   (its owning article never reached a terminal state, so its IDs were never
   recorded). Delete it:
   `DELETE /vector_stores/{id}/files/{file_id}`
   (`docs/api/openai/vector-store-files/delete-vector-store-file.md`).

**Why identify orphans by "not in the recorded set" rather than by reading each
file's `attributes.article_id`:** the local `hash_store.json` is the source of truth
for what *should* exist; a crash-orphan is defined precisely by being absent from it.
Reading `attributes.article_id` back would only tell us which article a file *claims*
to belong to — it can't tell us whether that upload was ever confirmed, which is the
actual question. The set-difference against recorded IDs answers it directly.
(`attributes.article_id` is still worth setting at upload time for dashboard
debuggability, just not load-bearing here.)

**Why this runs before `DISCOVERED`, not interleaved per-article:** it's a
whole-store consistency sweep with no dependency on which articles this run will
touch. Doing it once up front keeps it a single, auditable step and means the
per-article flow below can assume the store contains only known-good files.

**Alternative rejected:** skipping reconciliation and relying only on
`cleanup-before-reprocess` (per-article, in `PROCESSING`) to eventually remove stale
files. Rejected — that cleanup only fires for an article the local state already
knows about. A crash-orphan is invisible to local state by definition (its IDs were
never written), so nothing would ever trigger its cleanup. Reconciliation is the only
step that catches files the local state doesn't know exist.

---

## DISCOVERED → HASHED

**What happens:** fetch the article's raw content from Zendesk, clean it to
Markdown, hash the cleaned Markdown.

**How:**
1. Call `GET /api/v2/help_center/en-us/articles` (paginated) to list all articles.
   **No authentication needed** — confirmed empirically by running the old code in
   `optimus-bot-pipeline/` against the real `support.optisigns.com`: this endpoint
   returned articles successfully with no `Authorization` header sent. (The
   `/incremental/articles` endpoint was tested the same way and returned `401
   Unauthorized` — confirms the original review's decision to not use it, but that's
   a different endpoint from the one used here; the two do not share the same access
   restriction.) No `ZENDESK_EMAIL` / `ZENDESK_API_TOKEN` env vars needed.
2. For each article, keep `id`, `html_url`, `body`, `updated_at`.
3. Clean `body` (HTML) to Markdown **right away** — BeautifulSoup to strip nav/ads,
   markdownify to convert. This is moved earlier than originally drafted (was
   planned for `PROCESSING`); it has to happen here because of step 4.
4. Hash the **cleaned Markdown**, not the raw HTML.

**Why hash the cleaned Markdown, not raw HTML (corrected from an earlier version of
this document):** the prior implementation hashed the cleaned Markdown body
(`docs/prior/prior-implementation.md` §2 step 4: "MD5-hash the Markdown body"), and
this was never flagged as a defect in the review — only its chunker was. An earlier
draft of this document proposed hashing raw HTML instead, worried that a future
cleaning-library version bump could cause a false "everything changed" event across
all ~30-50 articles at once. That concern doesn't outweigh the downside:
- If the cleaning code itself gets fixed or improved (a real possibility — the old
  chunker had a confirmed bug), hashing raw HTML means already-`CONFIRMED` articles
  would never be reprocessed with the fix, because the hash never sees the cleaning
  step. They'd stay stale until Zendesk's source happens to change too, for reasons
  completely unrelated to the actual bug.
- Hashing cleaned Markdown makes *both* a real content change on Zendesk *and* a
  cleaning-code change correctly show up as "content differs" — which matches what
  "detect new/updated articles" should mean here: whatever ends up in the vector
  store changed.
- The cost (an occasional full reprocess when cleaning code changes) is small,
  one-time per code change, and only at ~30-50 articles.

**Important field to get right:** the citation requirement needs `html_url`
(the public page URL), **not** `url` (Zendesk's internal API URL for that article —
not something a user could open in a browser). Using the wrong field silently breaks
the "Article URL:" citation requirement without causing any error.

**Alternatives considered and rejected:**
- *Zendesk's `/incremental/articles?start_time=...` endpoint*, which only returns
  articles changed since a given time. Rejected in the original review
  (`docs/draft/optimus-bot-pipeline-review.md`, Rejected Ideas) — the network savings
  at ~30-50 articles/day don't justify the added complexity, and it's now confirmed
  to need its own auth handling anyway, same as the endpoint actually being used.
  Listing everything every day and comparing hashes locally is simpler and already
  required anyway (for the hash comparison itself).
- *Using Zendesk's `updated_at` timestamp instead of a content hash.* Rejected —
  `updated_at` can change for reasons that don't affect the visible article body
  (e.g. metadata edits), which would cause unnecessary re-uploads. A content hash
  only fires on actual content change.

---

## HASHED → SKIPPED / tagged "added" or "updated"

**What happens:** compare the new hash to what's on record.

**How:** look up `hash_store.json["articles"][article_id]`.
- Not present at all → tag `"added"`, proceed to `PROCESSING`.
- Present, `status: "CONFIRMED"`, hash matches → `SKIPPED`, stop here, no API calls.
- Present, `status: "CONFIRMED"`, hash differs → tag `"updated"`, proceed to
  `PROCESSING`.
- Present, `status: "FAILED"` (regardless of hash) → treat as needing reprocessing,
  proceed to `PROCESSING`. A `FAILED` article is never considered "done," even if its
  hash happens to match — it never actually finished uploading.

**Why compare only against the last `CONFIRMED` hash, never a `FAILED` one:** covered
in `state-design.md` §6 — `FAILED` never writes a hash, so there is nothing else to
compare against. No special-case code is needed for this; it falls out naturally from
the write-only-on-CONFIRMED rule.

**No alternatives considered here** — this is a direct lookup, not a design choice.

---

## PROCESSING → spawn Chunk children

**What happens:** split the already-cleaned Markdown (cleaned back in `DISCOVERED →
HASHED`, kept in memory for this run) into chunks, and — if this article has old
chunk files on record — delete those first.

**How, step by step:**

1. **Clean up old chunks first, if any exist.** If
   `hash_store.json["articles"][article_id]["chunk_file_ids"]` is non-empty (true for
   both a retried `FAILED` article and a genuinely `"updated"` article whose new
   content produces a different number of chunks), call
   `DELETE /vector_stores/{id}/files/{file_id}` (`docs/api/openai/vector-store-files/delete-vector-store-file.md`)
   for each old ID **before** uploading anything new.

   **Why this matters even for "updated" (not just "failed") articles:** this was
   almost missed. The first version of this design only thought about cleanup after a
   *failure*. But a legitimate content update can also change the chunk count (e.g.
   an article shrinks from 5 chunks to 3) — the 2 extra old chunks from before the
   edit would become orphans in exactly the same way as a failed upload's leftovers,
   just for a different reason. Same fix covers both cases: **before reprocessing any
   article that has old chunk IDs on record, delete them first.** Only a brand-new
   article (tag `"added"`) skips this step, because it has nothing to delete.

   **Alternative rejected:** searching the vector store for orphaned chunks
   dynamically (e.g. via the `search` endpoint with an `article_id` attribute
   filter) instead of tracking IDs locally. Rejected — already established in
   `state-design.md` §8 that `search` needs a semantic query and isn't reliable for
   exact lookups. Local tracking is the only dependable option.

2. **Split into chunks.** Client-side chunking with an `Article URL:` line (using
   `html_url`, per above) repeated at the top of every chunk — this part is settled
   (`docs/draft/optimus-bot-pipeline-review.md`, Settled Decisions). **The exact
   splitting algorithm is not settled** — see "Open decision: chunking algorithm"
   right after this section.

3. **Upload — one file_batch per Article, not one giant batch for the whole day.**
   Use `POST /vector_stores/{id}/file_batches` with the `files: [...]` array form
   (`docs/api/openai/vector-store-file-batches/create-vector-store-file-batch.md`), one entry per
   chunk of *this* article, each entry repeating:
   - `attributes: {"article_id": ..., "chunk_index": ..., "content_hash": ...}`
   - `chunking_strategy: {"type": "static", "max_chunk_size_tokens": 4096,
     "chunk_overlap_tokens": 0}` (the settled "neutralize server-side chunking"
     decision from the original review)

   **Why repeat `chunking_strategy` on every entry instead of setting it once:** the
   API docs state this explicitly — when using the `files` array form (needed here
   for per-chunk `attributes`), any top-level `chunking_strategy` is **ignored**; it
   must be set per file. Easy to miss, and missing it would silently re-enable
   OpenAI's default chunking (`max_chunk_size_tokens: 800`), which reintroduces the
   exact bug the original review fixed (see `docs/draft/optimus-bot-pipeline-review.md`,
   "Neutralize OpenAI's server-side chunking").

   **Why one batch per Article, not one batch for all ~30-50 articles at once:** a
   batch's status (`docs/api/openai/vector-store-file-batches/retrieve-vector-store-file-batch.md`)
   reports one aggregate `file_counts` object (`completed`, `failed`,
   `in_progress`, `total`) for the *whole* batch. If every article's chunks were
   mixed into one giant batch, that count would be meaningless per-article — a
   second lookup (matching individual files back to their article) would be needed
   anyway. One batch per article means the batch's own `file_counts` **directly
   answers** the all-or-nothing question from `state-design.md` §5: `total ==
   completed` → `CONFIRMED`; `failed > 0` → `FAILED`. No extra bookkeeping needed.

   **Alternative rejected:** calling `POST /vector_stores/{id}/files` individually
   per chunk instead of using `file_batches`. Rejected — the docs themselves say the
   batch endpoint exists specifically to reduce per-vector-store write pressure for
   multi-file uploads, and it also gives one poll target per article instead of N.

---

## Open decision: chunking algorithm

Not settled yet — needs a call before `PROCESSING` can be implemented. Three options,
in increasing order of implementation risk avoided:

**Option A — patch the old algorithm.** Keep `find_backward_safe_split`'s general
approach (search backward from a target position for a "safe" boundary — end of
sentence/paragraph), fix the one confirmed bug (`search_start` anchored to the wrong
position, causing the 609-chunk runaway — see `docs/draft/optimus-bot-pipeline-review.md`,
"Important Technical Context"). Least new code. Risk: it's a ~150-line hand-rolled
heuristic that already produced one severe bug the synthetic tests never caught
(`docs/prior/prior-implementation.md` §7 — "synthetic test fixtures hide real-world
failure modes"); fixing the one known bug doesn't rule out an unknown second one in
the same style of code.

**Option B — split along Markdown block boundaries, not arbitrary character
positions.** Parse the cleaned Markdown into its top-level blocks (paragraph,
heading, list, fenced code block), then greedily pack whole blocks into a chunk until
the token budget is reached; only split a single block if that block alone exceeds
the budget. This avoids the entire bug class from Option A — there is no backward
search for a "safe" cut point in raw text, so there's no `pos`-vs-`search_start`
relationship that can drift. It also naturally avoids cutting a fenced code block in
half, which a plain character/token-window cut (Option C) can do — relevant since the
assignment explicitly requires preserving code blocks.

**Option C — plain token-count window, no structural awareness.** Cut every N
tokens (via `tiktoken`) with a fixed overlap, ignoring Markdown structure entirely.
Simplest possible code, but can cut a code fence or a heading mid-way, producing a
chunk with broken Markdown — a real risk given the assignment's "preserve code
blocks" requirement, and a plausible source of *new*, different-looking bugs.

**Option D — use an existing text-splitter library** (e.g. `langchain-text-splitters`'
`MarkdownHeaderTextSplitter` / `RecursiveCharacterTextSplitter`) instead of hand-rolling
one. Offloads the boundary logic to maintained code instead of custom regex. Adds one
extra dependency; the assignment's own hint ("chunking strategy is up to you") does not
require a hand-rolled splitter.

Leaning towards **B or D** over **A** — patching a function that already produced one
severe, untested-for bug fixes the known instance but not the underlying risk (hand-rolled
backward-search heuristics over real-world HTML-derived Markdown). **A is the one to
avoid by default** unless there's a reason to prefer it. Final call is yours.

---

## PENDING → UPLOADING → UPLOADED / FAILED (per Chunk)

**What happens:** each chunk becomes a file, gets attached, and we wait for OpenAI
to finish processing it.

**How:**
1. Turn the chunk's Markdown text into an OpenAI File object first
   (`POST /files`, the base Files API — call shape confirmed via the prior
   `optimus-bot-pipeline/src/uploader.py:43`: `client.files.create(file=f,
   purpose="assistants")`; `docs/api/openai/files/upload-files.md` confirms
   `"assistants"` is a valid `purpose`). This has to happen before the `file_batches`
   call in the previous section, since that call needs a `file_id` to reference.
2. The `file_batches.create` call from the previous section starts all chunks of the
   article at once, each entering `UPLOADING`.
3. Poll `GET /vector_stores/{id}/file_batches/{batch_id}`
   (`docs/api/openai/vector-store-file-batches/retrieve-vector-store-file-batch.md`) until
   `status` is no longer `in_progress`.
4. If `file_counts.failed > 0`, call
   `GET /vector_stores/{id}/file_batches/{batch_id}/files?filter=failed`
   (`docs/api/openai/vector-store-file-batches/list-vector-store-files-in-a-batch.md`) to find
   exactly which chunk(s) failed and read their `last_error` for the log message.

**Why poll the batch, not each chunk file individually:** one poll target instead of
N, and the batch's own `file_counts` already gives the aggregate result needed for
the Article-level all-or-nothing rule. Only fall back to inspecting individual files
when something actually failed and a specific error message is needed for logging.

**Alternative rejected:** polling each chunk's own `GET
/vector_stores/{id}/files/{file_id}` in a loop. Rejected — more API calls for the
same information the batch status already provides in one call.

---

## PROCESSING → CONFIRMED / FAILED (the aggregate step)

**What happens:** once the batch reaches a final status, decide the Article's fate
and — only now — write to disk.

**How:**
- Batch `file_counts.total == file_counts.completed` → Article = `CONFIRMED`. Write
  `hash`, `status: "CONFIRMED"`, `confirmed_at`, and the full list of
  `chunk_file_ids` from this batch to `hash_store.json`, using an atomic write
  (write to a temp file, then rename).
- Otherwise → Article = `FAILED`. Still write `status: "FAILED"` and
  `chunk_file_ids` (whatever succeeded in *this* attempt) — needed for cleanup on
  the next run (see PROCESSING step above). Do **not** update `hash` — the old hash
  (or absence of one) must remain so the next run treats this article as still
  needing work, per the HASHED step's rule.

**Why this is the only place allowed to write `hash_store.json`:** this is the
central rule from `state-design.md` — the original bug was a write happening at the
wrong time. Making this the single write point, everywhere else in the code, is what
actually prevents that class of bug from coming back in a different form.

---

## End of run → exit code

**What happens:** after every Article has reached `SKIPPED`, `CONFIRMED`, or
`FAILED`, decide the process exit code and print the log line.

**How:**
- Count articles by tag and final state: `added`, `updated`, `skipped`, and
  `failed` (an extra bucket beyond what the assignment explicitly asks for — added
  so a failed article doesn't just silently vanish from the log; see
  `state-design.md`).
- `main.py` exits non-zero if any article ended in `FAILED`. Exits `0` only if every
  article ended in `CONFIRMED` or `SKIPPED`.

**Why per-article try/except, not one try/except around the whole run:** if one
article throws an unhandled error (bad HTML, network blip) and it's not caught at the
per-article level, the whole run stops — every article after it in the loop never
gets processed, and the log undercounts everything. Catching per-article keeps one
bad article from taking down the other 29-49.
