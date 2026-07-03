"""Unit tests for the Tier-1 eval checkers (evals/checks.py).

The checkers are the deterministic core of the eval -- if THEY are wrong, the
whole scorecard lies. Fixtures pin each system-prompt rule.
"""

from evals import checks

VALID = {"111", "222", "333"}


def _url(article_id: str) -> str:
    return f"https://support.optisigns.com/hc/en-us/articles/{article_id}-some-slug"


# --- bullet limit -----------------------------------------------------------

def test_five_bullets_pass():
    answer = "\n".join(f"- point {i}" for i in range(5))
    assert checks.check_bullet_limit(answer).passed


def test_six_bullets_without_link_fail():
    answer = "\n".join(f"- point {i}" for i in range(6))
    assert not checks.check_bullet_limit(answer).passed


def test_six_bullets_with_doc_link_pass():
    answer = "\n".join(f"- point {i}" for i in range(6)) + f"\nSee {_url('111')}"
    assert checks.check_bullet_limit(answer).passed


def test_numbered_bullets_are_counted():
    answer = "\n".join(f"{i}. step" for i in range(1, 7))
    assert checks.count_bullets(answer) == 6


def test_horizontal_rule_is_not_a_bullet():
    assert checks.count_bullets("some text\n\n---\n\nmore text") == 0


# --- citation count ---------------------------------------------------------

def test_three_citations_pass():
    answer = "\n".join(f"Article URL: {_url(x)}" for x in ("111", "222", "333"))
    assert checks.check_citation_count(answer).passed


def test_four_citations_fail():
    answer = "\n".join(f"Article URL: {_url(x)}" for x in ("111", "222", "333", "111"))
    assert not checks.check_citation_count(answer).passed


def test_zero_citations_allowed():
    assert checks.check_citation_count("no citations here").passed  # "up to 3"


# --- real URLs --------------------------------------------------------------

def test_real_cited_url_passes():
    answer = f"Here you go.\nArticle URL: {_url('222')}"
    assert checks.check_urls_real(answer, VALID).passed


def test_hallucinated_url_fails():
    answer = f"Article URL: {_url('999')}"  # 999 not in the known set
    r = checks.check_urls_real(answer, VALID)
    assert not r.passed
    assert "999" in r.detail


def test_real_check_scans_urls_outside_citation_lines():
    answer = f"As explained in {_url('999')} you should reboot."
    assert not checks.check_urls_real(answer, VALID).passed


def test_markdown_link_trailing_paren_not_swallowed():
    # a real id inside a markdown link must not fail just because of the ")"
    answer = "See the [Whitelist Article](https://support.optisigns.com/hc/en-us/articles/111)."
    r = checks.check_urls_real(answer, VALID)
    assert r.passed, r.detail


def test_run_checks_returns_all_three_rules():
    results = checks.run_checks("hello", VALID)
    assert {r.rule for r in results} == {"bullet_limit", "citation_count", "urls_real"}
