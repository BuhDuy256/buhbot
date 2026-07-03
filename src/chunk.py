"""PROCESSING: split cleaned Markdown into upload chunks (pure, no I/O).

Option B (block-aware, hand-rolled) -- chosen over patching the prior
backward-search splitter, whose ``search_start`` drift caused a 609-chunk
runaway (optimus-bot-pipeline-review.md §5). The failure class there came from a
drifting index into raw text. This algorithm has no such index: it pre-splits
the Markdown into whole blocks, then *greedily packs whole blocks forward* until
a token budget is hit. There is no position to drift.

Guarantees that matter for the assignment:
  * Fenced code blocks (``` / ~~~) are treated as atomic -- never cut mid-fence
    (unless a single fence alone exceeds the hard limit; see ``_hard_split``).
  * Every emitted chunk carries a data-only provenance header at the top --
    ``# <title>``, ``Article URL: <url>``, and (when the chunk sits under one or
    more Markdown headings) a ``Section Path: H1 > H2 > H3`` breadcrumb -- so any
    chunk retrieved by search is independently citable AND knows where in the
    article it came from even when its own heading was packed into an earlier
    chunk (the whole reason chunking stays client-side --
    optimus-bot-pipeline-review.md §2). The header is provenance only: no
    imperative "cite this" prose lives in the corpus, because that text would
    pollute the chunk's embedding and dilute retrieval. Citation behavior is the
    system prompt's job; the corpus only has to make the exact ``Article URL:``
    string it asks for present in every retrieved chunk.
  * Optional one-block overlap (``CHUNK_OVERLAP_BLOCKS``): the last whole block of
    a chunk is repeated at the head of the next, so an answer that straddles a
    chunk boundary is still fully present in the second chunk. Block-level, not a
    token %, to avoid minting near-duplicate chunks.

Budgets:
  * CHUNK_BUDGET_TOKENS (~800) is a *soft* target for retrieval granularity:
    packing stops adding blocks once it would exceed this.
  * A single block larger than the soft target still becomes its own chunk (no
    splitting) as long as it stays under STATIC_MAX_CHUNK_TOKENS (4096). Only a
    lone block past *that* ceiling is hard-split -- because 4096 is where
    OpenAI's server-side re-chunker would otherwise kick in and slice the file,
    separating the URL header from the body (the exact bug we neutralize).
"""

import re
from dataclasses import dataclass

import tiktoken

from .config import (
    CHUNK_BUDGET_TOKENS,
    CHUNK_OVERLAP_BLOCKS,
    STATIC_MAX_CHUNK_TOKENS,
    TOKENIZER_MODEL,
)

_encoder = tiktoken.encoding_for_model(TOKENIZER_MODEL)

# An ATX heading line: 1-6 '#' then space then text. Used to reconstruct the
# section breadcrumb for the Section Path header.
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass(frozen=True)
class ChunkText:
    """One upload unit. ``index`` is the per-article ``chunk_index`` that
    ``uploader.py`` attaches as a file attribute; ``text`` already includes the
    provenance header (``# <title>`` + ``Article URL:``)."""

    index: int
    text: str


def _ntokens(text: str) -> int:
    return len(_encoder.encode(text))


def _split_blocks(md: str) -> list[str]:
    """Split Markdown into top-level blocks separated by blank lines, keeping a
    fenced code block (from its opening ``` to its closing fence) as one block
    even though it contains blank lines."""
    blocks: list[str] = []
    cur: list[str] = []
    in_fence = False

    def flush() -> None:
        nonlocal cur
        if cur:
            blocks.append("\n".join(cur))
            cur = []

    for line in md.split("\n"):
        is_fence = line.strip().startswith(("```", "~~~"))
        if in_fence:
            cur.append(line)
            if is_fence:  # closing fence -> the code block is a complete block
                in_fence = False
                flush()
        elif is_fence:  # opening fence -> start a fresh block
            flush()
            cur.append(line)
            in_fence = True
        elif line.strip() == "":  # blank line -> block boundary
            flush()
        else:
            cur.append(line)
    flush()  # trailing block (or an unclosed fence)
    return blocks


def _hard_split(block: str, limit: int) -> list[str]:
    """Best-effort fallback for a single block larger than ``limit`` tokens
    (~16k chars -- essentially only a pathological code dump). Split on line
    boundaries so we never cut mid-line. A single line over the limit is left
    whole; that's vanishingly rare for support articles."""
    pieces: list[str] = []
    cur: list[str] = []
    cur_tokens = 0
    for line in block.split("\n"):
        lt = _ntokens(line + "\n")
        if cur and cur_tokens + lt > limit:
            pieces.append("\n".join(cur))
            cur, cur_tokens = [], 0
        cur.append(line)
        cur_tokens += lt
    if cur:
        pieces.append("\n".join(cur))
    return pieces


def _heading_paths(blocks: list[str]) -> list[str]:
    """For each block, the ``H1 > H2 > H3`` breadcrumb in effect at its start.

    A block whose first line is an ATX heading contributes that heading to its
    OWN path (so a chunk that opens on a heading shows it) and clears any deeper
    levels. Code fences are skipped so a ``# comment`` line inside a fence is not
    mistaken for a heading."""
    levels: dict[int, str] = {}
    paths: list[str] = []
    for block in blocks:
        first = block.split("\n", 1)[0].strip()
        if not first.startswith(("```", "~~~")):
            m = _HEADING.match(first)
            if m:
                depth = len(m.group(1))
                levels = {k: v for k, v in levels.items() if k < depth}
                levels[depth] = m.group(2).strip()
        paths.append(" > ".join(levels[k] for k in sorted(levels)))
    return paths


def split_markdown(md: str, article_url: str, title: str = "") -> list[ChunkText]:
    """Split cleaned Markdown into chunks, each prefixed with a provenance header.

    The header is ``# <title>`` (omitted when empty), an ``Article URL:`` line,
    and a ``Section Path:`` breadcrumb (omitted when the chunk sits under no
    heading), then a blank line, then the chunk body. All header lines are data
    only -- see the module docstring. When ``CHUNK_OVERLAP_BLOCKS`` > 0 the tail
    block(s) of the previous chunk are repeated at the head of this one.
    """
    md = md.strip()
    if not md:
        return []

    blocks = _split_blocks(md)
    paths = _heading_paths(blocks)

    # Phase 1: greedy-pack whole blocks into chunks. Track each chunk as its list
    # of blocks plus the index of its first block (for the Section Path).
    chunk_blocks: list[list[str]] = []
    chunk_start: list[int] = []
    cur: list[str] = []
    cur_tokens = 0
    cur_start = 0

    def flush() -> None:
        nonlocal cur, cur_tokens
        if cur:
            chunk_blocks.append(cur)
            chunk_start.append(cur_start)
            cur, cur_tokens = [], 0

    for i, block in enumerate(blocks):
        bt = _ntokens(block)
        if bt > STATIC_MAX_CHUNK_TOKENS:
            flush()
            for piece in _hard_split(block, STATIC_MAX_CHUNK_TOKENS):
                chunk_blocks.append([piece])
                chunk_start.append(i)
            continue
        if cur and cur_tokens + bt > CHUNK_BUDGET_TOKENS:
            flush()
        if not cur:
            cur_start = i
        cur.append(block)
        cur_tokens += bt
    flush()

    # Phase 2: assemble bodies, prepending one-block overlap from the previous
    # chunk. An oversized block (from a hard split) is never carried as overlap:
    # the budget guard keeps overlap from bloating a chunk.
    out: list[ChunkText] = []
    for k, blks in enumerate(chunk_blocks):
        prefix: list[str] = []
        if CHUNK_OVERLAP_BLOCKS and k > 0:
            cand = chunk_blocks[k - 1][-CHUNK_OVERLAP_BLOCKS:]
            if sum(_ntokens(b) for b in cand) <= CHUNK_BUDGET_TOKENS:
                prefix = cand
        body = "\n\n".join(prefix + blks)

        header_lines = [f"# {title}"] if title else []
        header_lines.append(f"Article URL: {article_url}")
        path = paths[chunk_start[k]]
        if path:
            header_lines.append(f"Section Path: {path}")
        header = "\n".join(header_lines)
        out.append(ChunkText(index=k, text=f"{header}\n\n{body}"))
    return out
