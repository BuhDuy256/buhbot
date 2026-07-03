# Working Memory — optimus-bot-pipeline Review & Rebuild Direction

Snapshot of a completed architectural review of the prior take-home attempt
(`optimus-bot-pipeline/`, gitignored, reference-only) against the OptiBot
requirements in the project's root `CLAUDE.md`. This document is the
authoritative continuation point — it supersedes the reasoning trail that
produced it.

## 1. Current Project State

`buhbot/` (this repo) has not started implementation yet. `src/` is empty
except `__init__.py`; `main.py` does not exist yet at repo root. The only
concrete artifacts so far are documentation: requirements PDF, prior-attempt
analysis, OpenAI/Zendesk API reference docs, and this review.

A prior, non-final attempt at the same task exists on disk at
`optimus-bot-pipeline/` (gitignored — not part of this repo, machine-local
only, gone if not read now). It is a full working pipeline: Zendesk fetch →
BeautifulSoup clean → markdownify → custom token-window chunker → per-chunk
`.md` files with title/URL header → OpenAI Files API upload → vector store
file_batches → `hash_store.json` as the only persistence layer. It has real,
confirmed bugs (below) but its core shape — client-side chunking with a
per-chunk citation header — has been re-validated as architecturally correct
for this project's specific citation requirement, not something to discard.

**Shape assessed as reusable, not requiring redesign:** review concluded the
overall pipeline shape (fetch → clean → chunk-with-header → upload →
hash_store) is architecturally sound for this project's requirements. The
defects identified below (Settled Decisions, Current Risks) are localized —
tied to specific functions/timing, not the overall design. This is a
characterization of what was found, not a plan for what to build first or
in what order — that sequencing is not yet decided.

## 2. Settled Decisions

**Keep client-side chunking with per-chunk `Article URL:` header (do not
switch to "1 file per article, let OpenAI auto-chunk").**
- Why: the assistant system prompt requires citing up to 3 "Article URL:"
  lines per reply. OpenAI's server-side chunker (`static` or `auto`) is a
  pure token-window slicer over the raw file bytes — it does not duplicate
  a header into every derived sub-chunk. If the URL header exists only once
  at the top of a multi-chunk article file, only the *first* server-derived
  chunk carries it; any other chunk retrieved by search has no
  "Article URL:" text for the model to cite. This is a functional
  regression against an explicit, verbatim requirement, not a style
  preference.
- Alternative rejected: uploading one file per article and letting OpenAI's
  `chunking_strategy` do all splitting (this was the initial recommendation,
  inherited from `docs/prior/prior-implementation.md` — see Rejected Ideas).
- Revisit if: the system prompt's citation requirement changes, or if
  citation is implemented via file-level `attributes`/metadata instead of
  in-body text (not currently planned).

**Neutralize OpenAI's server-side chunking instead of syncing it to the
client's chunk size.**
- Decision: when uploading, set `chunking_strategy: static` with
  `max_chunk_size_tokens: 4096` (the documented ceiling) and
  `chunk_overlap_tokens: 0`, instead of trying to keep a second constant
  (previously `MAX_CHUNK_TOKENS = CHUNK_BODY_TOKENS + 100 = 900`) in sync
  with the client chunk budget.
- Why: client-produced chunks run ~800–950 tokens. With the server ceiling
  at 4096 (documented max in `docs/api/openai/vector_stores/create-a-vector-store.md`),
  there's a ~4.5x margin — server-side splitting never triggers, so 1
  uploaded file = 1 stored chunk, guaranteed structurally rather than by
  keeping two numbers manually synchronized. This also resolves the
  "double chunking drift" risk (two chunk-size knobs that could silently
  diverge) by making the server number stop being a real second chunker.
- Residual uncertainty: OpenAI does not document which tokenizer it uses
  server-side to measure `max_chunk_size_tokens`, so client `tiktoken`
  counts (gpt-4o encoding) may not be bit-identical to server counts. Not
  a practical risk here given the ~4.5x margin, but flagged as an assumption,
  not a documented guarantee.
- Revisit if: client chunk budget (`CHUNK_BODY_TOKENS`) is ever raised close
  to 4096 (unlikely — would defeat the point of chunking at all).

**Delta-detection hash must only be persisted after upload for that article
is confirmed successful — not at scrape time.**
- Why: in the prior implementation, `hash_store["articles"][id]["hash"]` is
  computed and written to disk inside `scraper()`, which runs to completion
  and saves the file *before* `uploader()` is even invoked (`main.py` calls
  them sequentially, not atomically). If upload subsequently fails, is never
  reached, or the process is interrupted between the two calls, the content
  hash is already persisted. On the next run, since the source content on
  Zendesk hasn't changed, the hash comparison matches → the article is
  classified `HASH_SKIPPED` → it is **never retried**, even though it was
  never actually uploaded. This was independently reproduced by the user
  manually interrupting a run mid-pipeline — confirms the failure mode is
  real, not theoretical.
- Alternative rejected: leaving hash-write timing as-is and only fixing the
  upload-failure visibility (exit code) — insufficient, because even a
  loudly-failed upload leaves the hash already committed, so the article
  still can't self-heal on the next run.
- Revisit: not applicable — this is a correctness requirement, not a
  judgment call.

**Upload failures must propagate to a non-zero process exit code.**
- Why: currently every upload exception is caught and only `print`ed, at
  both the per-file level and the batch level; nothing re-raises; `main.py`
  has no try/except around either `scraper()` or `uploader()`. The Docker
  `CMD` therefore exits 0 unconditionally, even on a fully failed upload —
  confirmed against real on-disk data where all 50 articles in a snapshot
  had `openai_file_ids: []` despite `num_chunks` being populated (i.e.
  scrape succeeded, upload path was never confirmed to complete).
  `docker run ... main.py` "must run once and exit 0" only means something
  if failure can produce a non-zero exit.
- Revisit: not applicable — required by the project's own success criteria.

**Move `VECTOR_STORE_ID` and `ENV` to environment variables.**
- Why: currently hardcoded literals in `config.py`; only `OPENAI_API_KEY`
  is read from env. Requirements emphasize API-driven setup, not manual
  dashboard/config edits. Switching dev↔prod or vector stores currently
  requires a source edit and rebuild.
- Revisit: not applicable.

**Daily-job workflow file must live at `.github/workflows/`, not
`github/workflow/`.**
- Why: confirmed directly — the prior attempt has a fully-written, correct
  `daily-sync.yml` (schedule, artifact download/upload for state
  persistence, secrets) but it sits at `github/workflow/daily-sync.yml`
  (no dot, singular "workflow"). GitHub Actions only auto-discovers
  `.github/workflows/*.yml`. The workflow logic itself does not need
  rewriting — only relocation. This corrects a factual error in
  `docs/prior/prior-implementation.md`, which claimed no workflow file
  exists anywhere in the old repo at all; it does exist, just undiscoverable
  by GitHub due to path.
- Revisit: not applicable.

## 3. Rejected Ideas

**"Drop the custom chunker entirely; upload 1 file per article and let
OpenAI's server-side chunking_strategy handle all splitting."**
- Proposed initially by `docs/prior/prior-implementation.md` and repeated
  by this reviewer as an early recommendation.
- Rejected because: it breaks the citation requirement (see Settled
  Decisions above — header wouldn't appear in every server-derived
  sub-chunk). Also rejected the premise that OpenAI's chunker is an
  uncontrollable "black box" — verified against `docs/api/openai/vector_stores/create-a-vector-store.md`
  that `static` (and even `auto`) is just a token-window slicer with two
  explicit, documented parameters, functionally the same idea as the
  custom chunker, just server-side.
- Do not re-suggest unless the citation mechanism changes to something that
  doesn't depend on in-body text.

**Framing `BATCH_SIZE = 500` as "required by OpenAI's API limits."**
- Checked `docs/api/openai/file_batches/create-vector-store-file-batch.md`:
  actual documented limit is 2000 files per batch, not 500. `BATCH_SIZE=500`
  in the prior code has no documented justification — it's an arbitrary,
  more conservative choice (possibly for progress-logging granularity or
  smaller blast radius per batch failure).
- Not necessarily wrong to keep, but must not be justified as "OpenAI's
  limit" in code comments or README — that claim is false. If kept, document
  it as a deliberate conservative choice.

**Treating "Layer 1" (`updated_at` pre-filter) as a network-cost
optimization.**
- The Zendesk incremental-articles endpoint that would actually reduce
  network calls is present in code but commented out, and no request in
  the codebase ever sends an `Authorization` header — so "unauthorized"
  for that endpoint was never actually tested, only assumed.
- Rejected as a priority fix for this project: at ≥30 articles run once
  daily, the network-call savings are negligible. Not worth spending
  take-home time on. Would only be worth revisiting if article volume grew
  by orders of magnitude.

## 4. Open Questions

**Does OpenAI's server-side tokenizer for `max_chunk_size_tokens` match
`tiktoken`'s gpt-4o encoding used client-side?**
- Known: not documented in `docs/api/openai/vector_stores/create-a-vector-store.md`.
- Evidence: none directly; inferred safety comes only from the ~4.5x margin
  between client chunk size (~900 tokens) and the server ceiling (4096),
  not from any confirmed tokenizer match.
- Missing: no way to verify without hitting the live API with a
  near-boundary test file.
- Next step if it matters: not urgent given the margin; only worth testing
  empirically once API access is available, by uploading a chunk near
  900–1000 tokens and inspecting the returned `chunking_strategy`/chunk
  count on the vector store file object.

**Whether the Zendesk incremental-articles endpoint is actually reachable
with proper auth.**
- Known: code has it written but commented out; no `Authorization` header
  ever sent anywhere in the old codebase.
- Evidence: none — never tested. The old code's "unauthorized" assumption
  is unverified, not confirmed.
- Missing: an actual authenticated request against
  `/api/v2/help_center/incremental/articles`.
- Next step: low priority per Rejected Ideas above; only test if fetch
  volume/cost becomes a real constraint.

**No live OpenAI/Zendesk API access in this review session** (explicitly
stated by the user) — every conclusion above about API *behavior* (token
limits, batch limits, chunking_strategy semantics) comes from reading the
static docs in `docs/api/openai/` and `docs/api/zendesk/`, not from live
calls. Treat these as "per documentation," not "empirically confirmed,"
until the new implementation actually runs against real endpoints.

## 5. Important Technical Context

**Two-write hash_store problem is structural, not incidental.** The prior
code's `scraper()` function both computes new content hashes *and* persists
them to disk in the same call, before returning control to `main.py` for the
upload step. Any fix must either (a) move the hash write to happen only
after a per-article upload confirmation, or (b) merge scrape+upload into a
single per-article unit of work so there's no window where "seen" and
"stored" can diverge. Partial fixes (e.g. only adding better error logging)
do not close this gap.

**Root cause of the historical 609-chunk runaway bug (for context, not
current work — this bug lived in `find_backward_safe_split`'s
`search_start = target_pos * 0.5` calculation, which is anchored to the
absolute end-of-chunk position rather than the current chunk's start
(`pos`). Algebraically, from roughly the 3rd chunk onward, `search_start`
falls behind `pos`, letting the "safe split point" search return a position
earlier than the chunk's own start — producing a negative/empty chunk and
forcing the `max(pos+1, ...)` fallback, which advances 1 character per
iteration. This explains why the bug was systemic (609/777 chunks, 78%) once
an article exceeded ~2 chunks, not an occasional edge case. If client-side
chunking is retained (per Settled Decisions), this is the exact function/line
of logic that needs a `pos`-anchored lower bound before reuse — not a
rewrite of the whole chunker.

**Citation mechanism depends on literal in-body text, not file metadata.**
The `Article URL:` line must physically be part of whatever text chunk gets
retrieved and shown to the model — there is no indication in the API docs
reviewed that vector store `attributes`/metadata get surfaced to the model
as citable text automatically. This is why per-chunk header duplication (not
just per-file) is load-bearing for the system prompt's citation requirement.

**`optimus-bot-pipeline/` is gitignored and machine-local only.** It will
not be visible to a future session unless `docs/prior/prior-implementation.md`
is read first (per the project's root `CLAUDE.md`, item 6). That analysis
document itself was found to contain at least one factual error (claimed no
GitHub Actions workflow file exists at all in the old repo; one exists, just
at the wrong path) — treat its claims as a starting hypothesis to verify
against actual source, not as ground truth.

## 6. Current Risks

**State persistence under the literal required Docker invocation.**
CLAUDE.md specifies the run command as `docker run -e API_KEY=... main.py`
— no volume mount. The prior Dockerfile bakes an empty `hash_store.json`
into the image at build time. If the new implementation is run with exactly
that literal command (no `-v` mount), every container start is a fresh
state, and "upload only the delta" cannot function across separate `docker
run` invocations — every run would look like a first run. The old
`daily-sync.yml` workaround (download/upload the `data/` directory as a
CI artifact between scheduled runs) only works once that file is moved to
the correct `.github/workflows/` path. Mitigation: either document the
volume-mount requirement explicitly in the new README, or rely on the
CI-artifact pattern and make clear that a bare `docker run` without state
injection is expected to behave as a first run — this is acceptable for a
take-home as long as it's stated, not silently broken.

**Tokenizer mismatch between client chunk-sizing and server chunk ceiling**
(see Open Questions) — currently judged low-risk given the margin, but
unverified. Acceptable to proceed without live-testing this immediately;
worth a quick empirical check once API access exists, before considering
the pipeline done.

**Batch-size/error-handling changes are not yet implemented anywhere** —
everything in sections 2–5 is analysis and agreed direction, not code. The
actual `buhbot/src/` implementation has not started. Do not assume any of
the described fixes exist in code yet.

## 7. Sequencing / Next Steps

Not decided yet. Sections 2–6 above are the full set of findings and
settled reasoning from the review; no implementation order, prioritization,
or "what to build first" call has been made. That decision belongs to the
user and should be made explicitly in conversation, not inferred or
defaulted to by whichever session reads this file next.
