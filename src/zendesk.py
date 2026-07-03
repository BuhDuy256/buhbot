"""DISCOVERED: fetch articles from the Zendesk Help Center (I/O adapter).

No authentication -- the ``en-us/articles`` endpoint is public; confirmed
empirically against the real site (state-design.md §9). The ``/incremental``
endpoint *does* need auth and is deliberately not used.
"""

from dataclasses import dataclass

import requests

from . import artifacts
from .config import (
    ARTICLES_PER_PAGE,
    ZENDESK_ARTICLES_PATH,
    ZENDESK_BASE_URL,
    max_articles,
)

_HEADERS = {"Content-Type": "application/json", "Accept-Encoding": "gzip, deflate"}
_TIMEOUT = 30  # seconds per request


@dataclass(frozen=True)
class Article:
    id: str          # str so it maps 1:1 to hash_store.json keys
    title: str
    html_url: str    # public page URL -- the citable one, NOT the API `url`
    body: str        # raw HTML, cleaned later by content.py
    updated_at: str


def _to_article(raw: dict) -> Article:
    artifacts.dump_raw(raw)  # inspection side-channel; no-op unless enabled
    return Article(
        id=str(raw["id"]),
        title=raw.get("title", ""),
        html_url=raw.get("html_url", ""),
        body=raw.get("body") or "",
        updated_at=raw.get("updated_at", ""),
    )


def fetch_all_articles() -> list[Article]:
    """List articles as ``Article`` records, honoring the ``ENV`` cap.

    ``development`` = one capped request for a fast local run; ``production`` =
    follow ``next_page`` to exhaustion.
    """
    base = f"https://{ZENDESK_BASE_URL}{ZENDESK_ARTICLES_PATH}"
    cap = max_articles()

    if cap is not None:  # capped single-page fetch (development)
        resp = requests.get(f"{base}?per_page={cap}", headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        articles = [_to_article(a) for a in resp.json().get("articles", [])]
        print(f"[fetch] {len(articles)} article(s) (development cap={cap})")
        return articles

    url = f"{base}?per_page={ARTICLES_PER_PAGE}"  # full pagination
    articles: list[Article] = []
    while url:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        articles.extend(_to_article(a) for a in data.get("articles", []))
        url = data.get("next_page")
    print(f"[fetch] {len(articles)} article(s) (production, full pagination)")
    return articles


def fetch_all_article_ids() -> set[str]:
    """Every real article id in the full catalog, ignoring the ``ENV`` cap and
    without dumping artifacts. Used by the eval to distinguish a real cited URL
    from a hallucinated one (a cited article may be a body link outside the
    uploaded subset, so the whole catalog is the right oracle)."""
    base = f"https://{ZENDESK_BASE_URL}{ZENDESK_ARTICLES_PATH}"
    url = f"{base}?per_page={ARTICLES_PER_PAGE}"
    ids: set[str] = set()
    while url:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        ids.update(str(a["id"]) for a in data.get("articles", []))
        url = data.get("next_page")
    print(f"[eval] validating cited URLs against {len(ids)} real article(s)")
    return ids
