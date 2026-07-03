"""Fixture tests for the client-side chunker (src/chunk.py).

This is the module the prior pipeline got wrong (a 609-chunk runaway that its
synthetic tests never caught -- prior-implementation.md §6.1/§7). The tests here
pin the properties the design relies on: bounded chunk count, atomic code
fences, and a citable header on every chunk.
"""

from src import chunk
from src.chunk import split_markdown, _ntokens
from src.config import CHUNK_BUDGET_TOKENS, STATIC_MAX_CHUNK_TOKENS

URL = "https://support.optisigns.com/hc/en-us/articles/123-example"


def _bodies(chunks):
    """Chunk text with the 'Article URL:' header line stripped back off."""
    out = []
    for c in chunks:
        assert c.text.startswith(f"Article URL: {URL}")
        out.append(c.text.split("\n\n", 1)[1] if "\n\n" in c.text else "")
    return out


# --- empties ----------------------------------------------------------------

def test_empty_returns_no_chunks():
    assert split_markdown("", URL) == []
    assert split_markdown("   \n\n  ", URL) == []


# --- header + indexing ------------------------------------------------------

def test_every_chunk_has_url_header():
    md = "\n\n".join(f"Paragraph number {i} with some words." for i in range(80))
    chunks = split_markdown(md, URL)
    assert chunks
    for c in chunks:
        assert c.text.startswith(f"Article URL: {URL}")


def test_indices_are_sequential_from_zero():
    md = "\n\n".join(f"Paragraph number {i} with some words." for i in range(80))
    chunks = split_markdown(md, URL)
    assert [c.index for c in chunks] == list(range(len(chunks)))


def test_short_article_is_one_chunk():
    chunks = split_markdown("# Title\n\nJust a short paragraph.", URL)
    assert len(chunks) == 1
    assert "Just a short paragraph." in chunks[0].text


def test_title_header_when_title_given():
    md = "\n\n".join(f"Paragraph number {i} with some words." for i in range(80))
    chunks = split_markdown(md, URL, title="Fix the Player")
    assert chunks
    for c in chunks:
        # "# <title>" then the "Article URL:" line, then a blank line, then body
        assert c.text.startswith(f"# Fix the Player\nArticle URL: {URL}\n\n")


def test_no_title_keeps_url_only_header():
    md = "Just one paragraph."
    chunks = split_markdown(md, URL)  # no title -> no "# " line
    assert chunks[0].text.startswith(f"Article URL: {URL}\n\n")
    assert not chunks[0].text.startswith("#")


# --- the regression guard: bounded chunk count ------------------------------

def test_no_runaway_chunk_count():
    # ~100 uniform paragraphs of ~12 tokens => ~1200 tokens total. At an 800
    # budget this must be a couple of chunks, NOT hundreds (the prior bug).
    md = "\n\n".join(f"This is paragraph {i} in the document body." for i in range(100))
    chunks = split_markdown(md, URL)
    total = _ntokens(md)
    expected = total / CHUNK_BUDGET_TOKENS
    # generous ceiling: never more than ~3x the theoretical minimum
    assert len(chunks) <= max(3, expected * 3)
    assert len(chunks) >= 1


def test_chunk_bodies_respect_budget_when_blocks_are_small():
    md = "\n\n".join(f"Sentence block {i} here." for i in range(200))
    for body in _bodies(split_markdown(md, URL)):
        # each chunk's body stays within the soft budget (+ tolerance for the
        # single block that tipped it over)
        assert _ntokens(body) <= CHUNK_BUDGET_TOKENS + 60


# --- code fence integrity ---------------------------------------------------

def test_code_fence_kept_intact_in_one_chunk():
    md = "Intro paragraph.\n\n```python\nprint('a')\nprint('b')\n```\n\nOutro."
    chunks = split_markdown(md, URL)
    # the fenced block lands wholly inside a single chunk
    holder = [c for c in chunks if "print('a')" in c.text]
    assert len(holder) == 1
    assert "print('b')" in holder[0].text


def test_every_chunk_has_balanced_fences():
    # a fence with a blank line inside must not be split at that blank line
    md = "Para.\n\n```\nline1\n\nline2\n```\n\nMore text after."
    for c in split_markdown(md, URL):
        assert c.text.count("```") % 2 == 0, "a code fence was split across chunks"


def test_fence_with_blank_line_is_single_block():
    blocks = chunk._split_blocks("```\nline1\n\nline2\n```")
    assert blocks == ["```\nline1\n\nline2\n```"]


# --- oversized single block -------------------------------------------------

def test_oversized_block_under_ceiling_stays_one_chunk():
    # a single paragraph between the soft budget and the hard ceiling is NOT
    # split -- it becomes its own chunk.
    big = " ".join(f"word{i}" for i in range(1500))  # ~1500+ tokens, < 4096
    assert CHUNK_BUDGET_TOKENS < _ntokens(big) < STATIC_MAX_CHUNK_TOKENS
    chunks = split_markdown(big, URL)
    assert len(chunks) == 1


def test_block_over_ceiling_is_hard_split():
    huge = "\n".join(f"line {i} with several tokens of content here" for i in range(4000))
    assert _ntokens(huge) > STATIC_MAX_CHUNK_TOKENS
    chunks = split_markdown(huge, URL)
    assert len(chunks) > 1
    for body in _bodies(chunks):
        assert _ntokens(body) <= STATIC_MAX_CHUNK_TOKENS + 60


# --- determinism ------------------------------------------------------------

def test_deterministic():
    md = "\n\n".join(f"Paragraph {i}." for i in range(120))
    assert [c.text for c in split_markdown(md, URL)] == [
        c.text for c in split_markdown(md, URL)
    ]
