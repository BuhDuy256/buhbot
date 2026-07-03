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


# --- citation (scope-aware, Tier-1.5) ---------------------------------------

def test_in_scope_one_real_citation_passes():
    answer = f"Here you go.\nArticle URL: {_url('111')}"
    assert checks.check_citation(answer, VALID, in_scope=True).passed


def test_in_scope_three_real_citations_pass():
    answer = "\n".join(f"Article URL: {_url(x)}" for x in ("111", "222", "333"))
    assert checks.check_citation(answer, VALID, in_scope=True).passed


def test_in_scope_zero_citations_fails():
    # this is the un-hiding of finding ①: a green check no longer masks it
    r = checks.check_citation("no citations here", VALID, in_scope=True)
    assert not r.passed


def test_in_scope_four_citations_fail():
    answer = "\n".join(f"Article URL: {_url(x)}" for x in ("111", "222", "333", "111"))
    assert not checks.check_citation(answer, VALID, in_scope=True).passed


def test_in_scope_single_fake_citation_fails():
    # a citation is present but not real -> no *real* citation -> fail
    answer = f"Article URL: {_url('999')}"
    assert not checks.check_citation(answer, VALID, in_scope=True).passed


def test_out_of_scope_zero_citations_passes():
    assert checks.check_citation("The capital is Paris.", VALID, in_scope=False).passed


def test_out_of_scope_any_citation_fails():
    answer = f"Paris.\nArticle URL: {_url('111')}"  # fabricated source on out-of-scope
    assert not checks.check_citation(answer, VALID, in_scope=False).passed


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
    results = checks.run_checks("hello", VALID, in_scope=True)
    assert {r.rule for r in results} == {"bullet_limit", "citation", "urls_real"}
