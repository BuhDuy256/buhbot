Implement the OptiBot daily-sync pipeline for this repo (buhbot). The full design is
already done and written down — your job is to build it, not redesign it.

Read these first, in this order (they contain every settled decision and why):
@docs/lifecycle/IMPLEMENTATION-BRIEF.md
@CLAUDE.md
@docs/lifecycle/state-design.md
@docs/lifecycle/transition-techniques.md
@docs/lifecycle/code-structure.md
@docs/draft/optimus-bot-pipeline-review.md

IMPLEMENTATION-BRIEF.md is the map: it gives the reading order, the module build order,
what's decided, and what's deliberately deferred. It also points to
@docs/prior/prior-implementation.md (buggy reference, do NOT copy) and
@docs/api/api-map.md (read the specific endpoint doc before coding each API call).

Ground rules:
- The module layout in code-structure.md is pre-approved — build exactly that tree in
  src/, keep main.py a thin orchestrator.
- Honor every "Decided" item in the brief. Do not reopen them.
- For the two "Deferred" items (chunk algorithm, retry/backoff+poll timeout): for the
  chunk algorithm, stop and confirm the approach with me before writing chunk.py
  internals (I'm leaning option B or D from transition-techniques.md, not A). For
  retry/backoff, build the happy path now and leave a clean seam.
- Use uv (pyproject.toml + uv.lock), snake_case, only OPENAI_API_KEY in .env.
- Verbatim assistant system prompt and constraints are in CLAUDE.md.
- The prior pipeline at optimus-bot-pipeline/ (gitignored) runs against the real
  Zendesk site via `uv run main.py` — use it to verify endpoint behavior, not as a
  code template.

Start by: (1) confirming the build order back to me in one short list, (2) building the
non-blocked layers first — config/settings/lock, then the pure transforms (content.py,
chunk.py) with fixture tests, since the old chunker's bug was never caught by tests.
Then adapters, state, phases, main.py, Dockerfile.
