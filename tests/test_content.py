"""Fixture tests for the DISCOVERED -> HASHED transform (src/content.py).

The prior pipeline's bug hid because clean/hash/chunk were never isolable or
tested. These pin the behavior the design depends on: stripping non-content,
preserving headings/code/links, and a *stable* hash over cleaned Markdown.
"""

from src import content


# --- cleaning ---------------------------------------------------------------

def test_strips_script_and_style():
    html = "<p>keep this</p><script>evil()</script><style>.x{}</style>"
    md = content.html_to_markdown(html)
    assert "keep this" in md
    assert "evil" not in md
    assert ".x{}" not in md


def test_strips_nav_header_footer():
    html = "<nav>menu</nav><header>top</header><p>body text</p><footer>bottom</footer>"
    md = content.html_to_markdown(html)
    assert "body text" in md
    assert "menu" not in md
    assert "top" not in md
    assert "bottom" not in md


def test_strips_base64_data_uri_image():
    # a real article embeds an 85k-token base64 PNG; it must not survive cleaning.
    html = '<p>keep this</p><img src="data:image/png;base64,AAAABBBBCCCCDDDD">'
    md = content.html_to_markdown(html)
    assert "keep this" in md
    assert "data:image" not in md
    assert "base64" not in md


def test_keeps_http_image_urls():
    # only data: URIs are junk; a real attachment URL is small and preserved.
    html = '<img src="https://support.optisigns.com/hc/article_attachments/42.png">'
    md = content.html_to_markdown(html)
    assert "article_attachments/42.png" in md


def test_does_not_overstrip_classes_containing_ad_or_header():
    # "breadcrumb" contains "ad"; a <div class="header-note"> is real content
    # here. The conservative tag-only strip must keep both.
    html = '<div class="breadcrumb">Read more</div><div class="header-note">important</div>'
    md = content.html_to_markdown(html)
    assert "Read more" in md
    assert "important" in md


# --- structure preservation (assignment requirements) -----------------------

def test_preserves_headings_as_atx():
    md = content.html_to_markdown("<h1>Title</h1><h2>Sub</h2><p>text</p>")
    assert "# Title" in md
    assert "## Sub" in md


def test_preserves_code_block():
    html = "<pre><code>print('hello')</code></pre>"
    md = content.html_to_markdown(html)
    assert "print('hello')" in md


def test_preserves_relative_links():
    html = '<p>See <a href="/hc/en-us/articles/123">this</a>.</p>'
    md = content.html_to_markdown(html)
    assert "/hc/en-us/articles/123" in md
    assert "this" in md


# --- hashing ----------------------------------------------------------------

def test_hash_is_prefixed_sha256():
    h = content.content_hash("some markdown")
    assert h.startswith("sha256:")
    assert len(h) == len("sha256:") + 64


def test_hash_is_deterministic():
    assert content.content_hash("abc") == content.content_hash("abc")


def test_hash_differs_on_different_content():
    assert content.content_hash("abc") != content.content_hash("abd")


def test_same_html_hashes_equal_across_calls():
    html = "<h1>OptiBot</h1><p>Docs about <a href='/x'>signage</a>.</p>"
    assert content.content_hash(content.html_to_markdown(html)) == content.content_hash(
        content.html_to_markdown(html)
    )


def test_normalization_collapses_blank_lines():
    # Cosmetic whitespace differences in source HTML must not change the hash.
    a = content.html_to_markdown("<p>one</p><p>two</p>")
    b = content.html_to_markdown("<p>one</p>\n\n\n<p>two</p>")
    assert a == b
