"""Fixture tests for the client-side chunker (src/chunk.py).

This is the module the prior pipeline got wrong (a 609-chunk runaway that its
synthetic tests never caught -- prior-implementation.md §6.1/§7). The tests here
pin the properties the design relies on: a hard per-chunk token cap (with code
fences the one documented exception), a citable header on every chunk, bounded
chunk count, and a token-budgeted look-back overlap.
"""

import re

from src import chunk
from src.chunk import split_markdown, _ntokens
from src.config import (
    CHUNK_LOOKBACK_TOKENS,
    CHUNK_MAX_TOKENS,
    FENCE_MAX_TOKENS,
    STATIC_MAX_CHUNK_TOKENS,
)

URL = "https://support.optisigns.com/hc/en-us/articles/123-example"


def _body(text):
    """A chunk's text with the leading provenance header stripped off (returns
    the look-back overlap + body that follow the first blank line)."""
    return text.split("\n\n", 1)[1] if "\n\n" in text else ""


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
    chunks = split_markdown(md, URL)  # no title -> no "# " line, no headings
    assert chunks[0].text.startswith(f"Article URL: {URL}\n\n")
    assert not chunks[0].text.startswith("#")
    assert "Section Path:" not in chunks[0].text


# --- section path (contextual breadcrumb) -----------------------------------

def test_section_path_reflects_heading_hierarchy():
    heading = "# Setup\n\n## Network Settings\n\n"
    body = "\n\n".join(f"Paragraph {i} " + "word " * 50 for i in range(20))
    chunks = split_markdown(heading + body, URL, title="Doc")
    # some chunk starts under the H1>H2 section and must carry that breadcrumb
    assert any("Section Path: Setup > Network Settings" in c.text for c in chunks)


def test_section_path_ignores_hashes_inside_code_fence():
    # a big paragraph after the fence is windowed into its own chunks; their
    # Section Path must be the real heading, never the "# comment" inside the fence.
    md = "# Real Heading\n\n```\n# not a heading\ncode\n```\n\n" + "word " * 900
    chunks = split_markdown(md, URL)
    tail = [c for c in chunks if c.text.rstrip().endswith("word")][-1]
    header_block = tail.text.split("\n\n", 1)[0]
    assert "Section Path: Real Heading" in header_block
    assert "not a heading" not in header_block


# --- look-back overlap ------------------------------------------------------

def test_lookback_overlap_repeats_previous_tail():
    # many small, uniquely-numbered blocks force several chunks
    blocks = [f"Para{i} " + "filler " * 20 for i in range(60)]
    chunks = split_markdown("\n\n".join(blocks), URL)
    assert len(chunks) >= 2

    def para_ids(text):
        return re.findall(r"Para(\d+)", text)

    # look-back: chunk 1 re-opens INSIDE chunk 0's range and carries its tail --
    # the shared run is a suffix of chunk 0 sitting at the head of chunk 1.
    ids0, ids1 = para_ids(chunks[0].text), para_ids(chunks[1].text)
    assert ids1[0] in ids0, "chunk 1 should open with look-back from chunk 0"
    assert ids0[-1] in ids1, "chunk 0's last paragraph should reappear in chunk 1"


def test_lookback_never_exceeds_its_budget():
    # each chunk's overlap (head up to where new content begins) is bounded; a
    # simple proxy: the overlap can never be so large it breaches the hard cap.
    blocks = [f"Para{i} " + "filler " * 20 for i in range(60)]
    for c in split_markdown("\n\n".join(blocks), URL):
        assert _ntokens(c.text) <= CHUNK_MAX_TOKENS


def test_first_chunk_has_no_overlap():
    # nothing precedes chunk 0, so its body must start at the article's first block
    blocks = [f"Para{i} " + "filler " * 20 for i in range(60)]
    chunks = split_markdown("\n\n".join(blocks), URL)
    assert _body(chunks[0].text).startswith("Para0 ")


# --- the regression guard: bounded chunk count ------------------------------

def test_no_runaway_chunk_count():
    # ~100 uniform paragraphs -> a handful of chunks, NOT hundreds (the prior bug)
    md = "\n\n".join(f"This is paragraph {i} in the document body." for i in range(100))
    chunks = split_markdown(md, URL)
    expected = _ntokens(md) / CHUNK_MAX_TOKENS
    assert len(chunks) <= max(4, expected * 4)  # generous ceiling
    assert len(chunks) >= 1


# --- the core invariant: normal chunk.text <= hard cap ----------------------

def test_normal_chunks_within_hard_cap():
    md = "\n\n".join(f"Sentence block {i} here with a few words." for i in range(200))
    for c in split_markdown(md, URL):
        assert _ntokens(c.text) <= CHUNK_MAX_TOKENS


def test_oversized_prose_block_is_windowed_under_cap():
    # a single paragraph well over the cap is NOT kept whole (that was the old
    # design) -- it is windowed into several chunks, each within the hard cap.
    big = " ".join(f"word{i}" for i in range(900))  # ~2000 tokens
    assert _ntokens(big) > CHUNK_MAX_TOKENS
    chunks = split_markdown(big, URL)
    assert len(chunks) > 1
    for c in chunks:
        assert _ntokens(c.text) <= CHUNK_MAX_TOKENS


def test_space_less_monster_blob_within_cap():
    huge = "word" * 85000  # one space-less token blob, ~85k tokens
    chunks = split_markdown(huge, URL)
    assert len(chunks) > 1
    for c in chunks:
        assert _ntokens(c.text) <= CHUNK_MAX_TOKENS


def test_no_chunk_ever_exceeds_openai_ceiling():
    # a long URL + title maximise the header cost; every case must stay under the
    # OpenAI 4096 upload ceiling (our fence backstop already guarantees this).
    long_url = "https://support.optisigns.com/hc/en-us/articles/999999999-" + "x" * 90
    long_title = "A Fairly Long Support Article Title That Eats Header Tokens"
    cases = [
        "word " * 4080,
        "word" * 85000,
        ("para " * 700) + "\n\n" + ("word " * 3900),
    ]
    assert FENCE_MAX_TOKENS < STATIC_MAX_CHUNK_TOKENS  # our backstop is below OpenAI's
    for md in cases:
        chunks = split_markdown(md, long_url, long_title)
        assert chunks
        for c in chunks:
            assert _ntokens(c.text) <= STATIC_MAX_CHUNK_TOKENS


# --- code fence integrity ---------------------------------------------------

def test_code_fence_kept_intact_in_one_chunk():
    md = "Intro paragraph.\n\n```python\nprint('a')\nprint('b')\n```\n\nOutro."
    chunks = split_markdown(md, URL)
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


def test_big_fence_is_exempt_and_stays_whole():
    # a single fence larger than the normal cap is kept atomic in one chunk, and
    # is allowed to ride above CHUNK_MAX_TOKENS -- up to the fence backstop.
    code = "\n".join(f"code_line_{i} = compute(value_{i}, factor_{i})" for i in range(140))
    md = f"```python\n{code}\n```"
    fence_tokens = _ntokens(md)
    assert CHUNK_MAX_TOKENS < fence_tokens < FENCE_MAX_TOKENS
    chunks = split_markdown(md, URL)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.text.count("```") == 2  # whole, balanced fence
    assert CHUNK_MAX_TOKENS < _ntokens(c.text) <= FENCE_MAX_TOKENS


# --- determinism ------------------------------------------------------------

def test_deterministic():
    md = "\n\n".join(f"Paragraph {i}." for i in range(120))
    assert [c.text for c in split_markdown(md, URL)] == [
        c.text for c in split_markdown(md, URL)
    ]
