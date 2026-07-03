"""Tier-1 format checks -- pure, deterministic, no ground truth, no network.

Each check maps to one line of the verbatim OptiBot system prompt:

    • Max 5 bullet points; else link to the doc.   -> check_bullet_limit
    • Cite up to 3 "Article URL:" lines per reply. -> check_citation_count
    (cited URLs must be real OptiSigns articles)   -> check_urls_real

These catch format regressions with zero labeling: an "improvement" that
silently starts citing hallucinated URLs or spilling past 5 bullets fails here.
Grounding/retrieval quality is Tier 2/3 and needs a gold set -- out of scope.
"""

import re
from dataclasses import dataclass

MAX_BULLETS = 5
MAX_CITATIONS = 3

# A markdown bullet: -, *, • or "N." at line start, followed by whitespace+text.
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+\.)\s+\S", re.MULTILINE)
# The citation format the prompt mandates.
_ARTICLE_URL_LINE = re.compile(r"^\s*Article URL:\s*(\S+)", re.MULTILINE | re.IGNORECASE)
# Any OptiSigns help-article URL anywhere in the answer. The id may be followed
# by a slug of word chars / hyphens; stop there so trailing markdown punctuation
# like a closing ")" is not swallowed into the URL.
_OPTISIGNS_ARTICLE_URL = re.compile(
    r"https?://support\.optisigns\.com/hc/\S*?/articles/\d+[\w-]*"
)
_ARTICLE_ID = re.compile(r"/articles/(\d+)")


@dataclass(frozen=True)
class CheckResult:
    rule: str
    passed: bool
    detail: str


def count_bullets(answer: str) -> int:
    return len(_BULLET.findall(answer))


def citation_lines(answer: str) -> list[str]:
    """URLs on the mandated ``Article URL:`` lines."""
    return _ARTICLE_URL_LINE.findall(answer)


def all_article_urls(answer: str) -> list[str]:
    """Every OptiSigns article URL anywhere in the answer (for the 'real' check)."""
    return _OPTISIGNS_ARTICLE_URL.findall(answer)


def check_bullet_limit(answer: str) -> CheckResult:
    n = count_bullets(answer)
    if n <= MAX_BULLETS:
        return CheckResult("bullet_limit", True, f"{n} bullet(s) <= {MAX_BULLETS}")
    # Over the limit is only allowed if it instead links to the doc.
    has_link = bool(_OPTISIGNS_ARTICLE_URL.search(answer))
    return CheckResult(
        "bullet_limit",
        has_link,
        f"{n} bullet(s) > {MAX_BULLETS}; doc link present={has_link}",
    )


def check_citation_count(answer: str) -> CheckResult:
    n = len(citation_lines(answer))
    return CheckResult(
        "citation_count", n <= MAX_CITATIONS, f"{n} 'Article URL:' line(s) <= {MAX_CITATIONS}"
    )


def check_urls_real(answer: str, valid_ids: set[str]) -> CheckResult:
    """Every cited OptiSigns article URL must resolve to a real article id we
    actually fetched -- catches hallucinated / stale URLs."""
    bad: list[str] = []
    for url in all_article_urls(answer):
        m = _ARTICLE_ID.search(url)
        if not m or m.group(1) not in valid_ids:
            bad.append(url)
    return CheckResult(
        "urls_real",
        not bad,
        "all cited URLs are real" if not bad else f"unreal URL(s): {bad}",
    )


def run_checks(answer: str, valid_ids: set[str]) -> list[CheckResult]:
    return [
        check_bullet_limit(answer),
        check_citation_count(answer),
        check_urls_real(answer, valid_ids),
    ]
