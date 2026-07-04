"""DISCOVERED -> HASHED transform (pure, no I/O).

Two responsibilities that always run together for one article:
  1. ``html_to_markdown`` -- clean the Zendesk ``body`` HTML and convert to
     Markdown, preserving headings, code blocks, and relative links.
  2. ``content_hash`` -- hash the *cleaned Markdown* (not the raw HTML), so the
     delta check reacts to both real content changes and changes in our own
     cleaning logic. See state-design.md §9 / transition-techniques.md
     "DISCOVERED -> HASHED".

Kept free of network and disk so it is fully fixture-testable -- the isolation
the prior monolithic ``scraper.py`` lacked (code-structure.md).
"""

import hashlib
import re

from bs4 import BeautifulSoup
from markdownify import markdownify

# Tags that are never content: scripts/styles/embeds, and page chrome that can
# appear if an article body was pasted with surrounding layout. Removed by tag
# name only -- we deliberately avoid substring class/id matching (e.g. the prior
# code's ``[class*="ad"]``), which also matches innocent classes like "header"
# or "breadcrumb" and would silently delete real content.
_STRIP_TAGS = ("script", "style", "iframe", "noscript", "nav", "header", "footer")

_MULTI_BLANK_LINE = re.compile(r"\n{3,}")
_TRAILING_WS = re.compile(r"[ \t]+(?=\n)")


def clean_html(html: str) -> str:
    """Remove non-content tags, returning HTML ready for Markdown conversion."""
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(list(_STRIP_TAGS)):
        tag.decompose()
    # role="navigation" catches nav regions not marked with a <nav> tag.
    for tag in soup.select('[role="navigation"]'):
        tag.decompose()
    # Inline base64 data-URI images carry zero retrievable text but can be huge
    # (one real article embeds an 85k-token PNG). Left in, markdownify turns each
    # into a single enormous ![](data:...) line that pollutes the embedding and
    # blows past the chunk ceiling. Real http(s) image URLs are small and kept.
    for tag in soup.select('img[src^="data:"]'):
        tag.decompose()
    return str(soup)


def _normalize(md: str) -> str:
    """Make Markdown deterministic so the hash is stable across runs: strip
    trailing whitespace, collapse 3+ blank lines to one, trim the ends."""
    md = _TRAILING_WS.sub("", md)
    md = _MULTI_BLANK_LINE.sub("\n\n", md)
    return md.strip()


def html_to_markdown(html: str) -> str:
    """Clean ``html`` and convert to normalized Markdown (ATX headings)."""
    cleaned = clean_html(html)
    md = markdownify(cleaned, heading_style="ATX")
    return _normalize(md)


def content_hash(markdown: str) -> str:
    """Stable content fingerprint of the cleaned Markdown, ``sha256:<hex>``
    (state-design.md §6 schema)."""
    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
