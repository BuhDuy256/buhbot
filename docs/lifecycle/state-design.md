# Article & Chunk State Lifecycle — Design + Reasoning

This continues from `docs/draft/optimus-bot-pipeline-review.md`. That file found the
root bug: the pipeline saved "I have seen this content" (a hash) at the wrong moment —
before upload was actually confirmed. This file is the fix, generalized into a design,
not just a one-line patch.

Written so a future session (or a future you) can pick this up without re-deriving it.

## 1. Why "state lifecycle" instead of just patching the bug

The review found **three separate problems** that all came from the same root cause:
missing state.

| Problem | Root cause |
|---|---|
| Hash saved before upload confirmed | No "confirmed" checkpoint — save happened too early |
| Upload failure doesn't fail the whole job | No way to ask "did everything finish OK?" |
| Can't tell added vs. updated vs. skipped | No record of what state each article was in before |

Patching each one separately means three unrelated pieces of code, each easy to get
wrong again later. Instead: treat every article as an **object that moves through a
fixed set of states**. Once that exists, all three problems become one rule: *only
write to disk at one specific, safe state*. This is not "add more structure for its
own sake" — it is the minimum structure needed to make all three fixes hold at once.

## 2. Two levels, not one: Article and Chunk

An article is not uploaded as one thing. It is split into multiple chunks (per
`docs/draft/optimus-bot-pipeline-review.md`, chunking must stay client-side so every
chunk can carry its own `Article URL:` line). Each chunk becomes its **own file** in
OpenAI's Files API, with its **own upload result** — one chunk can succeed while
another fails.

If we only track state at the Article level, we cannot see this. A single word like
"failed" hides the fact that 4 out of 5 chunks actually made it into the vector
store. Those 4 become invisible leftovers (see §5). So the design needs **two nested
state machines**: one for the Article, one for each Chunk it owns.

## 3. Article states

```
DISCOVERED
   |  fetch raw HTML from Zendesk (needs auth, see §9), clean it to Markdown,
   |  compute a hash of the CLEANED Markdown (not the raw HTML — see §9)
   v
HASHED  --- compare new hash against the hash from the last CONFIRMED run ---
   |
   |-- same hash --------------------------------------> SKIPPED   (done, no API calls)
   |-- never seen this article_id before --> tag "added"
   |-- seen before, hash different -------> tag "updated"
   v
PROCESSING  (split cleaned Markdown into chunks, upload chunks)
   |
   |  wait for every Chunk child to reach a final state, then:
   v
   |-- every Chunk = UPLOADED --------------------------> CONFIRMED  (write hash now)
   |-- at least one Chunk = FAILED ----------------------> FAILED    (hash NOT written)
```

Only 5 states. `SKIPPED`, `CONFIRMED`, and `FAILED` are the only ones that end a
run for that article — every article must land in exactly one of these three by the
time `main.py` exits.

## 4. Chunk states

```
PENDING     chunk text is ready, not uploaded yet
   v
UPLOADING   file created via OpenAI Files API, attached to the vector store,
            waiting for OpenAI to finish processing it
   v
   |-- OpenAI reports status = completed -----> UPLOADED
   |-- OpenAI reports status = failed/cancelled,
       or the upload call itself raised an error --> FAILED
```

This is not a made-up state machine — it mirrors the real `status` field OpenAI
already returns on a `vector_store.file` object (`in_progress / completed / cancelled
/ failed`, see `docs/api/openai/vector-store-files/list-vectore-store-files.md`). We do not invent
a parallel state; we read theirs.

## 5. The parent-child rule: all or nothing

**An Article may only become `CONFIRMED` if every one of its Chunks reached
`UPLOADED`.** If even one Chunk fails, the whole Article stays `FAILED`, and its hash
is **not** written.

**Why this exact rule, and not "confirm what succeeded, retry only the failed
chunk":** if we confirmed a partially-uploaded article, the next run would see the
hash unchanged and skip it (per §3, `HASHED` compares against the last `CONFIRMED`
hash) — the missing chunks would never be retried, and would sit permanently
incomplete. This is the same shape of bug the original review found, just moved one
level down (Article → Chunk instead of scrape → upload). All-or-nothing avoids
recreating it.

**Tradeoff, stated plainly:** if 4 of 5 chunks upload fine and 1 fails, the next run
re-uploads all 5, not just the 1. This wastes a little work. Accepted because the
article count here is small (~30-50/day) — re-uploading a whole article costs almost
nothing. If volume grows by orders of magnitude, this is the first assumption to
revisit.

## 6. What gets written to disk, and when

`hash_store.json` — one entry per article:

```json
{
  "articles": {
    "<article_id>": {
      "status": "CONFIRMED | FAILED | SKIPPED",
      "hash": "sha256:...",
      "confirmed_at": "2026-07-03T00:00:00Z",
      "chunk_file_ids": ["file_abc", "file_def", "..."]
    }
  }
}
```

Two rules that are easy to get wrong, stated explicitly so they don't get "simplified
away" later:

- **Only writing at `CONFIRMED` is not enough on its own.** `chunk_file_ids` must
  also be saved when an article ends in `FAILED` (not just `CONFIRMED`) — see §7 for
  why. An earlier version of this design said "chunk info can just live in memory
  during the run." That was wrong; it throws away exactly the information needed to
  clean up after a failure.
- **Writing the file itself must be atomic** (write to a temp file, then rename over
  the old one). The state file now lives on a real, persistent VM disk (not an
  ephemeral Docker container), so a crash mid-write can leave a **permanently
  corrupted** file instead of just "resetting to empty" like it would have in the
  old Docker-only design. Atomic writes matter more now than they used to.

## 7. Why FAILED articles must still remember their chunk_file_ids

If an Article fails after 4 of 5 chunks already uploaded successfully, those 4 chunk
files are now real, sitting in the vector store. If we forget about them (don't
persist their IDs), the next run cannot find them, cannot delete them, and just
uploads 5 brand new ones on top. Old, duplicate chunks stay in the vector store
forever, each still carrying an `Article URL:` line — the assistant can now cite the
same article's URL from two different, possibly stale, chunk texts. This directly
hurts the citation requirement in the system prompt.

This is worked out fully in `transition-techniques.md` under "cleanup before
reprocessing."

## 8. Rejected alternatives (so they aren't re-proposed later without reason)

**A flat state per Article, no separate Chunk tracking.**
Rejected — cannot detect partial upload (see §2). A single "failed" label would hide
successfully uploaded chunks.

**Store state in a database (Supabase, Postgres, etc.) instead of a JSON file.**
Rejected for this project's scale (~30-50 small records, single writer, once a day).
A database's real value — concurrent access, ad-hoc querying — is unused here.
Introduces an extra external dependency, an extra secret, and an extra failure mode
not required by the assignment. Revisit only if article volume or write concurrency
grows by orders of magnitude.

**Use OpenAI Vector Store file `attributes` as the only source of truth (no local
state file at all).**
Rejected after reading the actual API docs: the List Files endpoint
(`docs/api/openai/vector-store-files/list-vectore-store-files.md`) can only filter by `status`,
not by `attributes`. The only endpoint that filters by `attributes` is `search`
(`docs/api/openai/vector_stores/search.md`), which requires a semantic query string
and is not built for exact-match lookups. Using it as the source of truth would mean
listing every file and rebuilding state in memory on every run — more network calls,
not less complexity.

**Keep Chunk state only in memory during a run, persist nothing about chunks to
disk.**
Rejected — see §7. This was an earlier, incorrect simplification made before the
cleanup-before-reprocessing need was noticed.

## 9. Open questions carried forward

- **Hashing basis — resolved, corrected from an earlier version of this doc.**
  Hash the **cleaned Markdown**, not the raw HTML `body`. This matches what the prior
  implementation did (`docs/prior/prior-implementation.md` §2 step 4: "MD5-hash the
  Markdown body") and was never flagged as a defect in the review — only its chunker
  was. An earlier draft of this document proposed hashing raw HTML instead, reasoning
  that a cleaning-library version bump could cause false "everything changed" events.
  That reasoning didn't hold up: hashing raw HTML means a fix to the cleaning code
  itself would never cause already-`CONFIRMED` articles to be reprocessed, since the
  hash never sees the cleaning step. Hashing cleaned Markdown correctly reacts to
  *both* "Zendesk content changed" and "our own cleaning logic changed" — the second
  case matters here because the chunker has a known history of bugs (see
  `docs/prior/prior-implementation.md` §6.1).
- **Zendesk authentication — resolved, confirmed empirically against the real
  site.** Ran the old code in `optimus-bot-pipeline/` (gitignored, machine-local)
  directly against `support.optisigns.com`, no `Authorization` header sent, for
  both endpoints:
  - `GET /api/v2/help_center/incremental/articles?start_time=...` → `401
    Unauthorized`. Confirms this endpoint requires auth. Matches the original
    review's Rejected Ideas call to not use this endpoint anyway.
  - `GET /api/v2/help_center/en-us/articles` (the one the DISCOVERED step actually
    uses) → succeeded, no auth, fetched 62 articles.

  So the two endpoints do **not** share the same access restriction — the earlier
  guess that Help Center auth is a single account-wide setting applying to every
  endpoint was wrong. **The DISCOVERED step needs no Zendesk credential at all.**
  No `ZENDESK_EMAIL` / `ZENDESK_API_TOKEN` env vars needed.
- **Client-side chunking algorithm — not decided.** The review only settled that
  chunking happens client-side (vs. 1-file-per-article + server auto-chunk) and that
  server-side re-chunking is neutralized (`static`/4096/0). It did **not** settle
  *how* the client splits text into chunks. The old algorithm
  (`find_backward_safe_split`, a ~150-line regex heuristic) has a confirmed bug
  history (609-chunk runaway, `docs/prior/prior-implementation.md` §6.1). Options are
  laid out in `transition-techniques.md` under "Open decision: chunking algorithm" —
  still needs a call.
- The base OpenAI Files API `POST /files` (upload bytes → `file_id`, the step before a
  file can be attached to a vector store) has **no dedicated doc** yet. The docs folder
  was restructured: `docs/api/openai/files/` now holds the base Files API, and
  `docs/api/openai/vector-store-files/` holds the store-attach ops — but the one file
  in `files/` (`upload-files.md`) actually documents `GET /files` (List), not
  `POST /files` (Upload). **This is not blocking:** the prior `uploader.py`
  (`optimus-bot-pipeline/src/uploader.py`, line 43) shows the exact call —
  `client.files.create(file=f, purpose="assistants")` — and `upload-files.md` confirms
  `"assistants"` is a valid `purpose`. That's enough to write `uploader.py`; a formal
  `POST /files` doc would only add confirmation of size limits / return shape.

## 10. Crash recovery: reconciliation + rollback strategy

Everything above (§1-§7) handles an article that reaches a proper terminal state
(`CONFIRMED`, `FAILED`, `SKIPPED`) by the time `main.py` exits. It does **not**
handle the process being killed mid-`PROCESSING` — VM restart, out-of-memory, power
loss. Found by tracing through a concrete scenario: article 15 of 50 has 4 chunks,
2 already `UPLOADED` (real files now sitting in the vector store), chunk 3 is
mid-`UPLOADING` when the process dies. Because `write-after-confirm` (§1, §6) only
writes to disk on a terminal transition, and this article never reached one,
`hash_store.json` still shows whatever it showed *before this run started* — it has
no idea chunks 1-2 exist. `cleanup-before-reprocess` (§7) only knows to delete
`chunk_file_ids` that were actually written down, so it cannot see these two. They
become invisible, permanent orphans — still searchable, still citable, with no local
record connecting them to anything.

**Fix — a reconciliation pass, settled, no tradeoff involved:**
At the start of every run, list every file actually in the vector store
(`GET /vector_stores/{id}/files`, `docs/api/openai/vector-store-files/list-vectore-store-files.md`,
paginated). Compare against the union of `chunk_file_ids` recorded across **every**
article in `hash_store.json` — both `CONFIRMED` and `FAILED`. The `FAILED` ones must
be included: under Lazy rollback (below) a failed article's uploaded chunks are
deliberately left in the store, so they are known-good, not orphans — excluding them
here would silently delete them on the next run, turning Lazy rollback into Eager.
Any file that exists in the vector store but isn't in that recorded set is an orphan
(its owning article never reached a terminal state, so its IDs were never written) —
delete it (`DELETE /vector_stores/{id}/files/{file_id}`,
`docs/api/openai/vector-store-files/delete-vector-store-file.md`). This doesn't change the
write-after-confirm rule at all; it's a separate check layered on top, and it also
happens to catch drift from causes other than a crash (e.g. a file manually removed
from the OpenAI dashboard). Mechanics in `transition-techniques.md`, "Run start:
reconciliation pass."

**Decided: Lazy rollback, not Eager.** When an article ends `FAILED` (say 3 of 4
chunks `UPLOADED`, 1 `FAILED`), those 3 successfully-uploaded chunks are **left in
place** — not deleted immediately. They stay searchable/citable until the article is
successfully reprocessed on a later run, at which point `cleanup-before-reprocess`
(§7) removes them as part of the normal update flow. The alternative considered —
**Eager rollback**, deleting the 3 successful chunks the moment the 4th is known to
have failed, so a failed article is never partially visible — was not chosen.

*Why Lazy:* 3-of-4 correct chunks still answer most questions about that article
correctly; deleting them immediately trades a small citation-completeness risk for
losing real, correct content during the retry window. At this scale, partial
availability was judged better than strict all-or-nothing *visibility* (note: the
`CONFIRMED`/hash write itself is still strictly all-or-nothing — §5 — this decision
only concerns what stays queryable in the vector store while an article sits in
`FAILED`, waiting for retry).

**Deliberately not decided yet: in-run retry-with-backoff.** Whether a transient
failure (one network blip) should be retried a few times within the same run before
the chunk is marked `FAILED` — instead of always waiting for the next day's cron run
to retry — is left open on purpose. Plan: implement the lifecycle as designed here,
test it under normal conditions first, then stress-test it against real OS/network
failure scenarios (killed process, dropped connections, timeouts) — and let what's
actually observed during that stress test decide whether in-run retry is worth
adding, and with what parameters (attempt count, backoff timing). Deciding this
architecturally now, without that data, would be guessing.

## 11. Bootstrap, resource identity & configuration (settled Q&A round)

A batch of decisions made after the crash-recovery design, resolving how resources
are created/found and what stays configurable. Recorded with reasoning so they don't
get silently reversed.

**Vector store identity — find-or-create by name, no stored ID.**
The vector store is created via API on the very first run (never manually in the
dashboard). Its ID is **not** persisted anywhere — not in `.env`, not in code, not in
`hash_store.json`. Instead, every run lists vector stores (`GET /vector_stores`,
`docs/api/openai/vector_stores/list-a-vector-store.md` — returns each store's `name`)
and matches a fixed name constant (e.g. `"optibot-kb"`); found → reuse, not found →
create. Why: the name is a stable, code-level identifier that survives even total
loss of `hash_store.json`, and it means `VECTOR_STORE_ID` disappears as a config knob
entirely. "First run" is therefore a one-time event across the system's whole
lifetime, not per-container-start (the vector store is a durable OpenAI resource).

**Configuration — only `OPENAI_API_KEY` in `.env`; everything else is a code
constant.** This **reverses** the review's settled decision
(`docs/draft/optimus-bot-pipeline-review.md`: "Move VECTOR_STORE_ID and ENV to
environment variables") — intentional override. `VECTOR_STORE_ID` is gone (see
above); `ENV` (`development` = fetch 30 articles / `production` = full pagination)
stays a code constant. The review's actual *goal* (API-driven setup, no manual
dashboard step) is still met — just via name-discovery instead of an injected ID.
Cost of `ENV`-as-constant: switching dev↔prod needs a code edit + rebuild —
acceptable for a take-home.

**Assistant — created manually once, code never touches it.** The Assistant (with the
verbatim system prompt) is created by hand in the Playground, per the assignment's own
instruction. The API *does* support managing it in code (`create-assistant.md` /
`update-assistant.md` both accept `tool_resources.file_search.vector_store_ids`, max 1
store per assistant — verified in `docs/api/openai/assistant/`), but we deliberately
don't. Binding sequence: deploy → let the pipeline run once (creates the `optibot-kb`
store) → then in the Playground create the Assistant and attach that now-existing
store. One-time manual bind; it persists across daily runs because name-discovery
keeps the same store ID stable.
- *Known edge case (accepted, not handled):* if the store is ever deleted, the next
  run recreates it with a **new** ID, breaking the manual binding — requires a manual
  re-attach. Self-healing this would require code to call `update-assistant` every run
  (re-binding the current store ID), which contradicts "code never touches the
  Assistant." Not worth it here.

**Deleted-at-source articles — not handled, keep stale chunks (decided).** When an
article disappears from Zendesk, its chunks are **left** in the vector store rather
than detected-and-deleted. Why not handle it: we fetch the full list every run (no
incremental API), and any *incomplete* fetch — a mid-pagination network failure, or a
fetch cap — would make present articles look "missing." With delete-handling ON, one
transient fetch failure could mass-delete live chunks. The downside of not handling it
(a few orphaned chunks from genuinely-deleted articles) is far cheaper than that risk.
Note: the reconciliation pass (§10) does **not** remove these — a deleted article is
still `CONFIRMED` in `hash_store.json` with its `chunk_file_ids` recorded, so those
files count as known-good and are kept.

**Base File orphans — not cleaned (decided).** Removing a file from the vector store
(`delete-vector-store-file`) does **not** delete the underlying base File object
(`POST /files`). We accept these base-storage leftovers rather than chasing them with
a second `DELETE /files/{id}` — they don't pollute search or citations (not in the
store), only cost a little file storage.

**Single-run guarantee — lock file (decided).** A lock file (flock/PID) prevents two
overlapping runs (cron + a manual run) from writing `hash_store.json` simultaneously
and corrupting it. Cheap, and it targets exactly the kind of failure the OS
stress-test phase will probe.

**Batch poll timeout — deliberately deferred to the stress-test phase.** How long to
poll a `file_batch` before giving up on a stuck `in_progress` (interval, max wait) is
left undecided on purpose — the value should come from observed behavior during
stress-testing, not a guess now. Same posture as in-run retry (§10): understand the
problem now, pick the number later with data.
