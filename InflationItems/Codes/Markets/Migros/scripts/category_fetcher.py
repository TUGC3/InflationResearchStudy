"""
category_fetcher.py — Discovers all scrapable Migros product categories.
=========================================================================

Public API
----------
fetch_categories(session=None) -> list[dict]
    Returns the full flat list of (sub)category dicts ready for the product
    fetcher.  Each dict contains the keys ``id``, ``name``, ``parent_id``,
    ``parent_name``, and ``product_count``.

Discovery strategy
------------------
Migros exposes 13 verified top-level category IDs (see ``TOP_LEVEL_CATEGORIES``
below).  Sending a single search request for each top-level category returns
an ``aggregationGroups`` section in the JSON payload.  This section contains a
``kategoriler`` group whose ``aggregationInfos`` list every sub-category filter
available for that top-level bucket.

By harvesting those filter entries we obtain the complete, exhaustive set of
scrapable (sub)categories — the same ones a user sees when browsing the site.

Fallback behaviour
------------------
If a top-level category returns *no* sub-category filters (either the API
omits the ``kategoriler`` group or all sub-categories have ``count == 0``),
the top-level category itself is kept as a single entry with ``parent_id``
set to ``None``.  ``product_fetcher.py`` recognises this and sends only a
``category-id`` parameter (no ``kategoriler`` filter).

Deduplication
-------------
A ``seen_ids`` set prevents the same sub-category ID from appearing twice
in the final list, which can otherwise happen when a sub-category is shared
between two top-level buckets.
"""

import time
import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)

# Verified top-level category IDs — confirmed by exhaustive probe of /rest/products/search.
# IDs 2-10 are the main grocery/home sections.
# IDs 158, 160, 165, 166 are standalone sections found by probing the 11-500 range.
TOP_LEVEL_CATEGORIES = [
    {"id": "2",   "name": "Meyve, Sebze"},
    {"id": "3",   "name": "Et, Tavuk, Balık"},
    {"id": "4",   "name": "Süt, Kahvaltılık"},
    {"id": "5",   "name": "Temel Gıda"},
    {"id": "6",   "name": "İçecek"},
    {"id": "7",   "name": "Deterjan, Temizlik"},
    {"id": "8",   "name": "Kişisel Bakım, Kozmetik, Sağlık"},
    {"id": "9",   "name": "Bebek"},
    {"id": "10",  "name": "Ev, Yaşam"},
    {"id": "158", "name": "Oyuncak"},
    {"id": "160", "name": "Evcil Hayvan"},
    {"id": "165", "name": "Kitap, Dergi, Gazete"},
    {"id": "166", "name": "Elektronik"},
]


def _make_session() -> requests.Session:
    """Create a new ``requests.Session`` pre-loaded with the default headers.

    Returns
    -------
    requests.Session
        A session with ``config.DEFAULT_HEADERS`` already applied.
    """
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _fetch_subcategories(
    session: requests.Session,
    parent_id: str,
    parent_name: str,
) -> list[dict]:
    """Query the API for a top-level category and extract sub-category filters.

    Sends a page-1 search request for ``parent_id`` and parses the
    ``aggregationGroups[kategoriler].aggregationInfos`` list from the JSON
    response body.  Only entries with ``count > 0`` are returned.

    Args
    ----
    session : requests.Session
        Active session with the required headers already set.
    parent_id : str
        Top-level category ID (e.g. ``"2"`` for Meyve, Sebze).
    parent_name : str
        Human-readable label for ``parent_id`` (used in log messages and the
        returned dicts).

    Returns
    -------
    list[dict]
        Each dict has the shape::

            {
              "id":           "101",          # sub-category filter value
              "name":         "Meyve",
              "parent_id":    "2",
              "parent_name":  "Meyve, Sebze",
              "product_count": 50,
            }

        Returns an empty list if all retries are exhausted.
    """
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(
                config.PRODUCT_SEARCH_URL,
                params={
                    "category-id": parent_id,
                    "sayfa": 1,
                    "sirala": config.DEFAULT_SORT,
                },
                timeout=30,
            )
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "Failed to fetch aggregations for top-level category %s: %s",
                    parent_id, exc,
                )
                return []
            wait = config.RETRY_BACKOFF * attempt
            logger.warning("Attempt %d failed (%s). Retrying in %ds…", attempt, exc, wait)
            time.sleep(wait)

    data = resp.json().get("data", {})
    subcats = []

    for agg_group in data.get("aggregationGroups", []):
        if agg_group.get("requestParamKey") != "kategoriler":
            continue
        for item in agg_group.get("aggregationInfos", []):
            sub_id = item.get("requestParameter") or item.get("id")
            sub_name = item.get("label", "")
            count = item.get("count", 0)
            if sub_id and count > 0:
                subcats.append({
                    "id": sub_id,
                    "name": sub_name,
                    "parent_id": parent_id,
                    "parent_name": parent_name,
                    "product_count": count,
                })

    logger.debug(
        "Top-level category '%s' (id=%s): %d subcategories found.",
        parent_name, parent_id, len(subcats),
    )
    return subcats


def fetch_categories(session: Optional[requests.Session] = None) -> list[dict]:
    """Return the full flat list of scrapable (sub)categories.

    Iterates over every entry in ``TOP_LEVEL_CATEGORIES``, calls
    ``_fetch_subcategories``, and collects the results.  Duplicate IDs are
    silently skipped.  Top-level categories that expose no sub-categories are
    included as a fallback entry (see module docstring).

    Args
    ----
    session : requests.Session, optional
        Shared session to reuse.  A new session is created automatically when
        ``None`` is passed.

    Returns
    -------
    list[dict]
        Flat list of category dicts, each with the shape::

            {
              "id":            "101",         # ?kategoriler= filter value
              "name":          "Meyve",
              "parent_id":     "2",           # ?category-id= value; None for fallbacks
              "parent_name":   "Meyve, Sebze",# None for fallbacks
              "product_count": 50,            # None for fallbacks
            }

    Notes
    -----
    A 0.3-second pause is inserted between top-level requests to avoid
    triggering rate-limiting on the Migros API.
    """
    if session is None:
        session = _make_session()

    all_categories: list[dict] = []
    seen_ids: set[str] = set()

    for top in TOP_LEVEL_CATEGORIES:
        logger.info(
            "Fetching subcategories for '%s' (id=%s)…",
            top["name"], top["id"],
        )

        subcats = _fetch_subcategories(session, top["id"], top["name"])
        time.sleep(0.3)

        if subcats:
            for sc in subcats:
                if sc["id"] not in seen_ids:
                    all_categories.append(sc)
                    seen_ids.add(sc["id"])
        else:
            # Fall back: scrape the top-level directly (no sub-filter)
            entry = {
                "id": top["id"],
                "name": top["name"],
                "parent_id": None,
                "parent_name": None,
                "product_count": None,
            }
            if top["id"] not in seen_ids:
                all_categories.append(entry)
                seen_ids.add(top["id"])

    logger.info("Total scrapable categories: %d", len(all_categories))
    return all_categories
