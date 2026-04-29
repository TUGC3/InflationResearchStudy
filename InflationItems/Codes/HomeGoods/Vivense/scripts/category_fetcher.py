"""
Vivense Category Discovery Module
=================================

Returns the list of top-level Vivense navigation categories that the
product fetcher will iterate through.

Public Interface
----------------
fetch_categories(session=None) -> list[dict]
    Returns the curated list of categories defined in
    ``config.TOP_LEVEL_CATEGORIES``.  Each dict has the shape::

        {
          "id":          "oturma-odasi-mobilyalari",
          "name":        "Oturma Odası",
          "url":         "https://www.vivense.com/oturma-odasi-mobilyalari.html",
          "parent_id":   None,
          "parent_name": None,
          "product_count": None,   # not exposed by the public site
        }

Discovery Strategy
------------------
Vivense renders all product cards directly into category HTML; there is
no public API to enumerate categories.  Rather than scraping the home-page
mega-menu (which mixes campaign / promo links with real categories), we
use a small hard-coded list of the top-level navigation buckets that map
1-to-1 to URLs of the form ``/<slug>.html``.

The same approach is used by the Rossmann scraper, which also relies on
a curated ``TOP_LEVEL_CATEGORIES`` list in its config module.
"""

import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    """Create a fresh ``requests.Session`` pre-loaded with default headers.

    Provided for API parity with the other category fetchers in this
    repository (e.g. Migros, Rossmann) — Vivense's curated category
    list does not actually require any HTTP calls, but the session
    parameter is kept on :func:`fetch_categories` for symmetry.

    Returns
    -------
    requests.Session
        A session with :data:`config.DEFAULT_HEADERS` already applied.
    """
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def fetch_categories(
    session: Optional[requests.Session] = None,
) -> list[dict]:
    """Return the list of Vivense top-level categories to scrape.

    Reads :data:`config.TOP_LEVEL_CATEGORIES` (a curated list) and returns
    one dict per category in the canonical scraper schema.

    Args
    ----
    session : requests.Session, optional
        Accepted for API compatibility with the other scrapers in this
        repository — not used because no network call is required to
        enumerate the curated list.

    Returns
    -------
    list[dict]
        One dict per category with keys ``id``, ``name``, ``url``,
        ``parent_id``, ``parent_name`` and ``product_count``.
    """
    # ``session`` accepted for cross-scraper API parity; not used here.
    del session

    categories: list[dict] = []
    for top in config.TOP_LEVEL_CATEGORIES:
        categories.append(
            {
                "id":            top["id"],
                "name":          top["name"],
                "url":           top["url"],
                "parent_id":     None,
                "parent_name":   None,
                "product_count": None,
            }
        )

    logger.info("Discovered %d top-level Vivense categories.", len(categories))
    return categories


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    for c in fetch_categories():
        print(f"{c['id']:<40} {c['name']}")
