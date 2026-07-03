# Assistant Quality — Improvement Options & Tradeoffs

Working-memory analysis produced after the first **Tier-1 eval** run against the
live `optibot-kb` Assistant. It records *what the eval found*, *why each gap
exists*, and *every lever available to close it, with its tradeoff*. There is no
single "correct" fix here — the binding constraint (the verbatim system prompt)
is exactly the thing that would fix the most. So this is a menu of **precise**
answers, each honest about what it buys and what it costs. The decision is the
user's; this doc is the map for it.

Companion to `optimus-bot-pipeline-review.md` (pipeline correctness) — that file
was about the *machine*; this one is about the *output quality*.

---

## 1. What the eval found (evidence, not opinion)

Tier-1 format eval (`evals/`, 6 probe questions, deterministic checks mapped to
the system prompt). Calibrated baseline: **17/18 checks**. But the score is the
least interesting part — the run surfaced three gaps, two of them **hidden behind
green checks**:

| # | Finding | How it showed up |
|---|---|---|
| ① | **Citation format not met.** No answer emits the mandated `Article URL:` line. The model uses OpenAI's native citation token `【4:0†source】` instead — which is *not a URL* in raw text (only a clickable pill in the Playground UI). | `citation_count` passes trivially (0 ≤ 3), hiding it |
| ② | **Grounding leak.** "What is the capital of France?" → "Paris". Violates "Only answer using the uploaded docs." | Invisible to Tier-1; needs Tier-3 |
| ③ | **Brevity rule broken.** Broad asks produce 6–18 numbered points, no "link to the doc instead." | Caught as the one red check (Q4) |

### Root cause (verified, not guessed)

- **H1 (bad embedding) — ruled out.** The exact uploaded bytes (`data/chunks/*.md`)
  begin with `Article URL: https://…`. The header is present in what we sent.
- **Retrieval — working.** The answer carries a `file_citation` annotation
  pointing at our uploaded file id. `file_search` retrieves the right chunk.
- **Root cause — the model.** The deployed Assistant runs **`gpt-3.5-turbo`**
  (temperature 0.01). It emits the native citation token rather than reproducing
  the `Article URL:` line, answers out-of-scope questions, and ignores the
  5-bullet cap. Per the API docs it also gets only **5** `file_search` results
  (vs 20 for `gpt-4*`).

### A/B evidence (same Assistant, same prompt, same store — only `model` overridden per run)

| Axis | `gpt-3.5-turbo` | `gpt-4o` |
|---|---|---|
| Citation | only `【†source】` (opaque, **no URL**) | **real URL** as a markdown link + token → better |
| Out-of-scope (Paris) | answers + fabricates a citation | still answers "Paris" (no refusal), but no fake citation |
| Brevity (broad ask) | 6 bullets | **18 bullets** → **worse** |

**The counterintuitive result that justifies having an eval at all:** a "better"
model is not better on every axis. `gpt-4o` improves citation (a real URL appears)
but *regresses* brevity (smarter ⇒ more thorough ⇒ longer), and does **not** fix
grounding. Upgrading blind would trade one gap for another without noticing.

### The ceiling

Neither model refuses Paris and neither reproduces the literal `Article URL:`
line. The prompt is terse (four bullets, no imperative force, no example, no
explicit refusal clause). **A weak prompt is not rescued by a stronger model.**
And the prompt is locked "verbatim" by the assignment. That lock is the ceiling.

---

## 2. The constraint that frames every option

The assignment fixes the **system prompt verbatim**. It does **not** fix:

- the **model**,
- the **chunking / content** we upload,
- the **`file_search` settings** on the Assistant,
- how the **eval defines** "cited",
- any **code wrapper** around the Assistant.

Those five are the legal levers. Read every option below through this: the one
change that could fix all three findings at once (a stronger prompt) is the one
the constraint forbids — which is *why* there is no free fix.

---

## 3. Options (What / Why / Tradeoff / How measured)

### Option A — Upgrade the model (`gpt-3.5-turbo` → `gpt-4o` / `gpt-4o-mini` / `gpt-4.1`)
- **Why:** root cause is the weak instruction-following of `gpt-3.5`. The `gpt-4*`
  family follows literal-format and grounding instructions better and gets 20
  `file_search` results (vs 5), so richer retrieval.
- **Tradeoff:**
  - Surfaces a real URL in the citation (A/B confirmed) — the core of finding ①.
  - **Regresses brevity:** more verbose ⇒ *more* likely to blow past 5 bullets
    (measured 18 vs 6).
  - Does **not** fix the grounding leak (both models answered Paris).
  - Higher cost + latency per query. Negligible at this volume, but real.
  - `gpt-4o-mini` is a middle ground (better follower than 3.5, cheaper than 4o) —
    needs its own measurement, don't assume.
- **Measure:** re-run the eval. Caveat: the *current* strict check looks for the
  literal `Article URL:` line, so it will still read 0 citations even though a
  real URL now appears as a markdown link — which is exactly why Option A pairs
  with Option B to be visible.
- **Who does it:** you, in the Playground (code never touches the Assistant).

### Option B — Redefine what counts as "cited" (eval definition + deliverable reading)
- **Why:** the strict "literal `Article URL:` line" bar may be the wrong ruler.
  In the Playground, `【†source】` renders as a clickable source, and `gpt-4o` adds
  a real URL link. The take-home asks for a screenshot "with cited URLs" — plausibly
  satisfied by the *rendered* citation. Part of finding ① may be definitional,
  not behavioral.
- **Tradeoff:**
  - Pro: the eval then measures the *actual* deliverable, stops penalizing a
    behavior that satisfies the assignment.
  - Con: it lowers the bar relative to the prompt's literal words
    (`"Article URL:" lines`). A grader reading the prompt literally sees
    non-compliance.
  - Con: annotation tokens are **not URLs outside the Playground** (API output,
    logs) — so "screenshot passes but raw API answer has no URL" is a genuine
    limitation if the bot is ever consumed programmatically.
- **Measure:** changes the ruler, so scores before/after aren't comparable — this
  is a redefinition, not an improvement.

### Option C — Strengthen the prompt (breaks "verbatim")
- **Why:** the true ceiling. An explicit prompt (reproduce the retrieved doc's
  `Article URL:` line at the end; refuse when the docs don't cover the question;
  hard-cap at 5 points else link) is the **only** lever that can fix all three
  findings at once, and it is **model-agnostic** (helps even `gpt-3.5`).
- **Tradeoff:**
  - Pro: highest ceiling; fixes ①②③ together.
  - Con: **directly violates** the assignment's "system prompt must match
    verbatim" — a hard constraint (CLAUDE.md). Not to be done silently.
  - Nuance: the assignment *might* intend the prompt as a starting minimum, not an
    immutable string. Only the assignment/grader can resolve that ambiguity — it
    cannot be inferred. If it can bend, this becomes the recommended fix.
- **Measure:** expected largest lift across all three; eval quantifies it.

### Option D — Shape the chunk so the URL gets reproduced (content lever)
- **Why:** models echo what is salient in retrieved context. Today `Article URL:`
  is a header at the *top* of a chunk; models tend to treat leading metadata as
  context, not as text to emit. A citation-shaped hint in the chunk could nudge
  reproduction **without touching the locked prompt**.
- **Tradeoff:**
  - Pro: pure pipeline change (`chunk.py`); doesn't touch the Assistant or prompt.
  - Con: speculative — no guarantee of echo; risks the instruction text itself
    leaking verbatim into answers (ugly), and adds tokens to every chunk.
  - A weak, indirect lever. Prototype small and measure before committing.
- **Measure:** eval.

### Option E — Tune `file_search` (`max_num_results`, `ranking_options.score_threshold`)
- **Why:** retrieval quality sits upstream of everything. `gpt-3.5` caps at 5
  results; raising `max_num_results` (≤50) and/or setting a `score_threshold`
  changes which chunks — and which article URLs — reach the model.
- **Tradeoff:**
  - Pro: cheap config on the Assistant; can raise recall.
  - Con: more results = more context tokens = higher cost + more distraction
    (model may cite the wrong one of many). `score_threshold` too high misses,
    too low adds noise.
  - Con: **cannot be tuned honestly without a Tier-2 retrieval gold set** — "better"
    here is a retrieval-accuracy question Tier-1 can't see. Blind tuning is the
    guessing trap this whole exercise is meant to avoid.
- **Measure:** requires the Tier-2 gold set (deferred earlier).

### Option F — Migrate Assistants API → Responses API
- **Why:** the SDK already warns the **Assistants API is deprecated** in favor of
  the Responses API, which offers better output control (e.g. `response_format` /
  structured outputs to enforce a citation shape) and is where OpenAI is investing.
- **Tradeoff:**
  - Pro: future-proof; real control over output format could fix ① precisely.
  - Con: a larger change; the take-home is framed around a Playground **Assistant**
    (manual create + attach). This diverges from the assignment's stated shape and
    costs time.
  - Out of scope for the take-home unless deprecation forces it — worth flagging,
    not doing now.
- **Measure:** N/A near-term.

### Option G — Deterministic output guardrail (code wrapper)
- **Why:** enforce format in code *after* the model responds: truncate to 5
  points + append a doc link; and **convert `【†source】` → a real `Article URL:`
  line** by mapping the annotation's `file_id` → `article_id` (we store that in
  each file's `attributes`, and in `hash_store.json`) → the article's `html_url`.
- **Tradeoff:**
  - Pro: *guarantees* citation-format compliance regardless of model — the most
    **precise** fix for finding ① specifically, and it reuses a mapping we already
    own.
  - Con: the wrapper is **not "the Assistant"**. The take-home's product is the
    Playground Assistant; a code layer only helps a consumer going through our
    code path, not the Playground screenshot.
  - Con: cannot fix grounding (②) — no post-processor can tell a hallucination
    from a truth without judging.
- **Measure:** eval, on the wrapped output.

---

## 4. The options are not independent

- **A improves ① but regresses ③** (measured). 
- **C could fix ①②③** but breaks the constraint. 
- **B makes ① *look* fixed** by moving the ruler, without changing behavior. 
- **E is unmeasurable** without the Tier-2 work. 
- **G fixes ① precisely** but only on the code path, not the Playground.

There is no combination that fixes all three findings *and* respects *all*
constraints *and* needs no new eval. Every path drops one of those. Naming which
one it drops is the whole point — that is the "precise answer".

---

## 5. Recommended posture (not a fix — a way to decide)

1. **Establish a stable baseline first.** Output is non-deterministic (Q4 was 8
   bullets one run, 10 the next, 18 under `gpt-4o`). A single run is an anecdote.
   Run the eval **N times** and read pass-*rate*, not a single pass/fail, before
   trusting any before/after comparison.
2. **Resolve the two authoritative-input questions** — they gate half the options
   and cannot be inferred:
   - Is the verbatim prompt truly immutable, or a starting minimum? (gates C)
   - Is "cited URLs" judged on rendered Playground citations or literal text? (gates B)
3. **Then change exactly one lever, re-measure.** That is the loop that turns
   tuning from luck into progress.

Fastest pragmatic path *if* the deliverable is the Playground screenshot: **A + B**
(`gpt-4o`, accept rendered/real-URL citation). Highest-quality path *if* the prompt
can bend: **C**. Most precise fix for the literal citation format *if* the bot is
consumed via code: **G**.

---

## 6. Explicitly not worth doing (rejected)

- **Further temperature tuning** — already 0.01 (near-deterministic); not the lever.
- **Chasing the literal `Article URL:` format via chunk hacks (D) without
  measuring** — speculative; only justified if a quick prototype moves the eval.
- **Blindly raising `max_num_results` (E)** — without the Tier-2 gold set it is
  the exact guess-and-hope this project exists to avoid.
- **Migrating to the Responses API (F) for the take-home** — real long-term, but
  a scope change the assignment doesn't ask for.
