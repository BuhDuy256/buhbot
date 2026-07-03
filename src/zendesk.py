"""DISCOVERED: fetch articles from the Zendesk Help Center (I/O adapter).

No authentication -- the ``en-us/articles`` endpoint is public; confirmed
empirically against the real site (state-design.md §9). The ``/incremental``
endpoint *does* need auth and is deliberately not used.
"""

from dataclasses import dataclass

import requests

from .config import (
    ARTICLES_PER_PAGE,
    ENV,
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
    return Article(
        id=str(raw["id"]),
        title=raw.get("title", ""),
        html_url=raw.get("html_url", ""),
        body=raw.get("body") or "",
        updated_at=raw.get("updated_at", ""),
    )


def fetch_all_articles() -> list[Article]:
    """List every article (or the dev cap). Returns them as ``Article`` records.

    In ``development`` a single request with ``per_page`` capped to
    ``MAX_ARTICLES_DEV`` keeps local runs fast; in ``production`` it follows
    ``next_page`` until exhausted.
    """
    base = f"https://{ZENDESK_BASE_URL}{ZENDESK_ARTICLES_PATH}"
    cap = max_articles()

    if ENV == "development":
        url = f"{base}?per_page={cap}" if cap else base
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        raw = resp.json().get("articles", [])
        articles = [_to_article(a) for a in raw]
        print(f"[fetch] {len(articles)} article(s) (development cap={cap})")
        return articles

    url = f"{base}?per_page={ARTICLES_PER_PAGE}"
    articles: list[Article] = []
    while url:
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        articles.extend(_to_article(a) for a in data.get("articles", []))
        url = data.get("next_page")
    print(f"[fetch] {len(articles)} article(s) (production, full pagination)")
    return articles
