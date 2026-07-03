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
    ``# <title>`` then ``Article URL: <url>`` -- so any chunk retrieved by search
    is independently citable AND topically anchored (the whole reason chunking
    stays client-side -- optimus-bot-pipeline-review.md §2). The header is
    provenance only: no imperative "cite this" prose lives in the corpus, because
    that text would pollute the chunk's embedding and dilute retrieval. Citation
    behavior is the system prompt's job; the corpus only has to make the exact
    ``Article URL:`` string it asks for present in every retrieved chunk.

Budgets:
  * CHUNK_BUDGET_TOKENS (~800) is a *soft* target for retrieval granularity:
    packing stops adding blocks once it would exceed this.
  * A single block larger than the soft target still becomes its own chunk (no
    splitting) as long as it stays under STATIC_MAX_CHUNK_TOKENS (4096). Only a
    lone block past *that* ceiling is hard-split -- because 4096 is where
    OpenAI's server-side re-chunker would otherwise kick in and slice the file,
    separating the URL header from the body (the exact bug we neutralize).
"""

from dataclasses import dataclass

import tiktoken

from .config import CHUNK_BUDGET_TOKENS, STATIC_MAX_CHUNK_TOKENS, TOKENIZER_MODEL

_encoder = tiktoken.encoding_for_model(TOKENIZER_MODEL)


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


def split_markdown(md: str, article_url: str, title: str = "") -> list[ChunkText]:
    """Split cleaned Markdown into chunks, each prefixed with a provenance header.

    The header is ``# <title>`` (omitted when ``title`` is empty) followed by an
    ``Article URL:`` line, then a blank line, then the chunk body. Both lines are
    data only -- see the module docstring for why no imperative citation prose
    goes here.
    """
    md = md.strip()
    if not md:
        return []

    bodies: list[str] = []
    cur: list[str] = []
    cur_tokens = 0

    def flush() -> None:
        nonlocal cur, cur_tokens
        if cur:
            bodies.append("\n\n".join(cur))
            cur, cur_tokens = [], 0

    for block in _split_blocks(md):
        bt = _ntokens(block)
        if bt > STATIC_MAX_CHUNK_TOKENS:
            flush()
            bodies.extend(_hard_split(block, STATIC_MAX_CHUNK_TOKENS))
            continue
        if cur and cur_tokens + bt > CHUNK_BUDGET_TOKENS:
            flush()
        cur.append(block)
        cur_tokens += bt
    flush()

    header_lines = [f"# {title}"] if title else []
    header_lines.append(f"Article URL: {article_url}")
    header = "\n".join(header_lines)
    return [
        ChunkText(index=i, text=f"{header}\n\n{body}")
        for i, body in enumerate(bodies)
    ]
