"""PROCESSING: split cleaned Markdown into upload chunks (pure, no I/O).

Block-aware, hand-rolled -- chosen over the prior backward-search splitter, whose
``search_start`` drift caused a 609-chunk runaway (optimus-bot-pipeline-review.md
§5). The failure class there came from a drifting index into raw text that ALSO
fed forward progress. This algorithm has no such index in its control loop: it
pre-splits the Markdown into whole blocks, then *greedily packs whole blocks
forward* until a token budget is hit. There is no position to drift.

Guarantees that matter for the assignment:
  * Fenced code blocks (``` / ~~~) are treated as atomic -- never cut mid-fence.
    A fence larger than a normal chunk is kept whole and rides ABOVE
    CHUNK_MAX_TOKENS up to FENCE_MAX_TOKENS (the one documented exception to the
    cap); only a fence past that backstop is ever split.
  * Every emitted chunk carries a data-only provenance header at the top --
    ``# <title>``, ``Article URL: <url>``, and (when the chunk sits under one or
    more Markdown headings) a ``Section Path: H1 > H2 > H3`` breadcrumb -- so any
    chunk retrieved by search is independently citable AND knows where in the
    article it came from even when its own heading was packed into an earlier
    chunk. The header is provenance only: no imperative "cite this" prose lives in
    the corpus, because that text would pollute the chunk's embedding and dilute
    retrieval. Citation behavior is the system prompt's job; the corpus only has
    to make the exact ``Article URL:`` string it asks for present in every chunk.

Overlap (look-back, token-budgeted -- CHUNK_LOOKBACK_TOKENS):
  Every chunk after the first repeats up to CHUNK_LOOKBACK_TOKENS of the previous
  chunk's tail at its own head, so an answer that straddles a chunk boundary is
  fully present in the later chunk. The overlap is whole trailing LINES (never
  starts mid-line) and is fence-balanced (a partial fence is dropped, never
  emitted broken). It is counted INSIDE the cap: the cap always wins, so the
  overlap shrinks -- down to zero -- rather than push a chunk over CHUNK_MAX_TOKENS.

Budgets (see config.py):
  * CHUNK_MAX_TOKENS (~800) is the HARD cap on a normal emitted ``chunk.text``
    (header + overlap + body). Body packing reserves room for the header and a
    full look-back, so a normal chunk lands at or below it. An oversized non-fence
    block is windowed into cap-sized pieces (with look-back stitched between
    them); an oversized fence is kept whole and exempted up to FENCE_MAX_TOKENS.
  * FENCE_MAX_TOKENS (~3000) is the backstop for an exempt fence, kept far below
    OpenAI's 4096 upload ceiling so the gap absorbs any tokenizer divergence and
    the file is never re-chunked server-side (which would separate the URL header
    from the body -- the exact bug we neutralize).
"""

import re
from dataclasses import dataclass

import tiktoken

from .config import (
    CHUNK_LOOKBACK_TOKENS,
    CHUNK_MAX_TOKENS,
    FENCE_MAX_TOKENS,
    TOKENIZER_MODEL,
)

_encoder = tiktoken.encoding_for_model(TOKENIZER_MODEL)

# An ATX heading line: 1-6 '#' then space then text. Used to reconstruct the
# section breadcrumb for the Section Path header.
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")

_FENCE = ("```", "~~~")


@dataclass(frozen=True)
class ChunkText:
    """One upload unit. ``index`` is the per-article ``chunk_index`` that
    ``uploader.py`` attaches as a file attribute; ``text`` already includes the
    provenance header (``# <title>`` + ``Article URL:``)."""

    index: int
    text: str


def _ntokens(text: str) -> int:
    return len(_encoder.encode(text))


def _is_fence(block: str) -> bool:
    """True if a block is a fenced code block (opens with ``` or ~~~)."""
    return block.lstrip().startswith(_FENCE)


def _fences_balanced(text: str) -> bool:
    """True if ``text`` opens exactly as many code fences as it closes -- i.e. it
    does not start or end in the middle of a fence."""
    return sum(1 for ln in text.split("\n") if ln.strip().startswith(_FENCE)) % 2 == 0


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
        is_fence = line.strip().startswith(_FENCE)
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


def _slice_tokens(text: str, limit: int) -> list[str]:
    """Last resort: cut a space-less blob into <= ``limit``-token slices."""
    toks = _encoder.encode(text)
    return [_encoder.decode(toks[i : i + limit]) for i in range(0, len(toks), limit)]


def _split_long_line(line: str, limit: int) -> list[str]:
    """Split one over-long line into pieces of <= ``limit`` tokens: on spaces
    first, then by raw token slices for a space-less blob. Token counts are
    measured on the actual joined piece (not summed per word) so a piece fills the
    budget -- summing per-word overcounts, because tokenization is not additive."""
    if _ntokens(line) <= limit:
        return [line]
    pieces: list[str] = []
    cur: list[str] = []
    for word in line.split(" "):
        if _ntokens(word) > limit:  # a single space-less token-blob past the limit
            if cur:
                pieces.append(" ".join(cur))
                cur = []
            pieces.extend(_slice_tokens(word, limit))
            continue
        if cur and _ntokens(" ".join(cur) + " " + word) > limit:
            pieces.append(" ".join(cur))
            cur = []
        cur.append(word)
    if cur:
        pieces.append(" ".join(cur))
    return pieces


def _window(block: str, limit: int) -> list[str]:
    """Cut a single block larger than ``limit`` tokens into consecutive pieces,
    each <= ``limit``, on line boundaries first; a lone line over the limit is
    itself split (words, then raw tokens). Used to window an oversized non-fence
    block -- Phase 2 stitches the look-back overlap between the pieces."""
    pieces: list[str] = []
    cur: list[str] = []
    for line in block.split("\n"):
        if _ntokens(line) > limit:  # one line alone is too big -> split the line itself
            if cur:
                pieces.append("\n".join(cur))
                cur = []
            pieces.extend(_split_long_line(line, limit))
            continue
        if cur and _ntokens("\n".join(cur) + "\n" + line) > limit:
            pieces.append("\n".join(cur))
            cur = []
        cur.append(line)
    if cur:
        pieces.append("\n".join(cur))
    return pieces


def _overlap_tail(prev_body: str, n_tokens: int) -> str:
    """The longest run of WHOLE trailing lines of ``prev_body`` that fits in
    ``n_tokens`` AND leaves no code fence half-open.

    Whole-line granularity means the look-back never starts mid-line; the
    fence-balance check means a partial code fence is dropped rather than emitted
    broken (look-back that would cut into a fence is skipped, not sliced -- the
    fence stays atomic). Returns "" when nothing safe fits (e.g. the tail is a
    single over-long line, or ends inside a large fence)."""
    if n_tokens <= 0:
        return ""
    lines = prev_body.split("\n")
    best = ""
    acc: list[str] = []
    for line in reversed(lines):
        acc.insert(0, line)
        cand = "\n".join(acc)
        if _ntokens(cand) > n_tokens:
            break
        if _fences_balanced(cand):
            best = cand
    return best


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
        if not first.startswith(_FENCE):
            m = _HEADING.match(first)
            if m:
                depth = len(m.group(1))
                levels = {k: v for k, v in levels.items() if k < depth}
                levels[depth] = m.group(2).strip()
        paths.append(" > ".join(levels[k] for k in sorted(levels)))
    return paths


def _header(title: str, article_url: str, path: str) -> str:
    """The provenance header block (no trailing blank line)."""
    lines = [f"# {title}"] if title else []
    lines.append(f"Article URL: {article_url}")
    if path:
        lines.append(f"Section Path: {path}")
    return "\n".join(lines)


def split_markdown(md: str, article_url: str, title: str = "") -> list[ChunkText]:
    """Split cleaned Markdown into chunks, each prefixed with a provenance header.

    The header is ``# <title>`` (omitted when empty), an ``Article URL:`` line,
    and a ``Section Path:`` breadcrumb (omitted when the chunk sits under no
    heading), then a blank line, then an optional look-back overlap, then the
    chunk body. All header lines are data only -- see the module docstring.

    Every normal chunk.text (header + overlap + body) stays <= CHUNK_MAX_TOKENS;
    the only exception is a single oversized code fence, kept atomic and allowed
    up to FENCE_MAX_TOKENS.
    """
    md = md.strip()
    if not md:
        return []

    blocks = _split_blocks(md)
    paths = _heading_paths(blocks)

    # Reserve the most expensive header any chunk of this article could carry
    # (longest section path) so every budget below is safe for every chunk.
    max_header = max(_ntokens(_header(title, article_url, p) + "\n\n") for p in set(paths))
    content_budget = CHUNK_MAX_TOKENS - max_header  # overlap + body in a normal chunk
    body_budget = content_budget - CHUNK_LOOKBACK_TOKENS  # new content, reserving overlap
    fence_ceiling = FENCE_MAX_TOKENS - max_header  # a whole atomic fence may ride this high

    # Phase 1: build the NEW content of each chunk (no overlap yet). Each entry is
    # (body_text, start_block_index, fence_exempt). A block too big to be a normal
    # body is either kept whole (fence -> exempt from the cap) or windowed into
    # body_budget pieces (non-fence).
    bodies: list[tuple[str, int, bool]] = []
    cur: list[str] = []
    cur_tokens = 0
    cur_start = 0

    def flush() -> None:
        nonlocal cur, cur_tokens
        if cur:
            bodies.append(("\n\n".join(cur), cur_start, False))
            cur, cur_tokens = [], 0

    for i, block in enumerate(blocks):
        bt = _ntokens(block)
        if bt > content_budget:  # too big to be a normal chunk body
            flush()
            if _is_fence(block):
                # Keep the fence atomic; it is exempt from CHUNK_MAX_TOKENS up to
                # the backstop. Only a fence past the backstop is ever split.
                if bt <= fence_ceiling:
                    bodies.append((block, i, True))
                else:
                    for piece in _window(block, fence_ceiling):
                        bodies.append((piece, i, True))
            else:
                # Window oversized prose/lists into cap-sized pieces; Phase 2
                # stitches CHUNK_LOOKBACK_TOKENS of look-back between them.
                for piece in _window(block, body_budget):
                    bodies.append((piece, i, False))
            continue
        # A lone block between body_budget and content_budget still fits a chunk;
        # it just leaves little room for overlap (which will yield in Phase 2).
        if cur and cur_tokens + bt > body_budget:
            flush()
        if not cur:
            cur_start = i
        cur.append(block)
        cur_tokens += bt
    flush()

    # Phase 2: prepend look-back overlap, honouring the hard cap (cap wins, overlap
    # yields). A fence-exempt body carries no overlap: it is already at/over the
    # normal cap, and a fence cannot be cleanly overlapped into anyway.
    out: list[ChunkText] = []
    prev_body: str | None = None
    for k, (body, start, exempt) in enumerate(bodies):
        header = _header(title, article_url, paths[start])
        text = f"{header}\n\n{body}"
        if k > 0 and not exempt and prev_body is not None:
            room = CHUNK_MAX_TOKENS - _ntokens(text) - 2  # 2 ~ the "\n\n" joiner
            overlap = _overlap_tail(prev_body, min(CHUNK_LOOKBACK_TOKENS, room))
            if overlap:
                cand = f"{header}\n\n{overlap}\n\n{body}"
                if _ntokens(cand) <= CHUNK_MAX_TOKENS:
                    text = cand
        out.append(ChunkText(index=k, text=text))
        prev_body = body
    return out
