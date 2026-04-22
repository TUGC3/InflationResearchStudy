"""
Sephora Category Discovery Module
=================================

Downloads and parses Sephora Türkiye's category sitemap to build the
list of scrapable category pages.

Public Interface
----------------
fetch_categories(session=None, *, level="main") -> list[dict]
    Returns the list of categories.  ``level="main"`` (default) keeps
    only the eight top-level categories declared in
    ``config.MAIN_CATEGORY_SLUGS``; ``level="all"`` returns every
    category found in the sitemap.

Sitemap Source
--------------
``https://www.sephora.com.tr/sitemap-customsitemap_category_0.xml``
An uncompressed XML sitemap listing ~180 category URLs, e.g.:

    https://www.sephora.com.tr/makyaj-c302/
    https://www.sephora.com.tr/makyaj/yuz-c342/
    https://www.sephora.com.tr/cilt-bakimi/bakim-turu/gunduz-kremi-c299901/

Each URL ends with ``-c<numeric-id>/`` which is used as the unique slug.

Data Structure
--------------
Each returned dict has the shape::

    {
      "name":        "Cilt Bakimi",                 # Title-cased from slug
      "slug":        "cilt-bakimi-c303",            # trailing ``-c<id>`` slug
      "category_id": "303",                         # numeric id from slug
      "url":         "https://www.sephora.com.tr/cilt-bakimi-c303/",
      "parent_slug": None,                          # best-effort; may be None
    }
"""

from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from typing import Optional
from urllib.parse import urlparse

from curl_cffi import requests  # type: ignore

import config

logger = logging.getLogger(__name__)

# Category URL pattern: ends with "-c<digits>/" (slug-c<id>/)
_CATEGORY_RE = re.compile(r"-c(\d+)/?$")

# XML default namespace used by sitemaps – stripped before parsing for simplicity.
_NS_DECLARATION = 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"'


def _make_session() -> "requests.Session":
    """Return a new curl_cffi session impersonating Safari 17."""
    session = requests.Session(impersonate=config.IMPERSONATE_PROFILES[0])
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _slug_from_url(url: str) -> Optional[str]:
    """Return the category slug (``foo-c123``) or ``None`` if the URL is
    not a recognised category page."""
    path = urlparse(url).path.strip("/")
    if not path:
        return None
    last = path.split("/")[-1]
    if not _CATEGORY_RE.search(last):
        return None
    return last


def _name_from_slug(slug: str) -> str:
    """Generate a title-cased human-readable name from a slug.

    Strips the trailing ``-c<id>`` part and title-cases the remaining
    hyphen-separated words.  Example: ``cilt-bakimi-c303`` →
    ``"Cilt Bakimi"``.
    """
    base = _CATEGORY_RE.sub("", slug).strip("-")
    return " ".join(p.capitalize() for p in base.split("-") if p)


def _parent_slug_from_url(url: str) -> Optional[str]:
    """Best-effort: return the slug of the parent category if the
    category URL has a deeper path.  Example:
    ``/makyaj/yuz/fondoten-c353/`` → ``yuz-c342`` cannot be derived from
    the URL alone, so this helper only returns the parent URL *segment*
    when it looks like another category slug.
    """
    path = urlparse(url).path.strip("/")
    parts = path.split("/")
    if len(parts) < 2:
        return None
    parent = parts[-2]
    return parent if _CATEGORY_RE.search(parent) else None


def fetch_categories(
    session: Optional["requests.Session"] = None,
    *,
    level: str = "main",
) -> list[dict]:
    """Fetch Sephora categories from the XML sitemap.

    Args
    ----
    session : curl_cffi.requests.Session, optional
        Shared session to reuse.  A new Safari-17 session is created
        automatically when ``None`` is passed.
    level : str
        ``"main"`` (default) – keep only categories declared in
        :data:`config.MAIN_CATEGORY_SLUGS`.
        ``"all"`` – return every category entry found in the sitemap.

    Returns
    -------
    list[dict]
        Flat list of category dicts (see module docstring).
    """
    if session is None:
        session = _make_session()

    url = config.CATEGORY_SITEMAP_URL
    logger.info("Downloading category sitemap: %s", url)

    resp = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 200 and resp.text.strip():
                break
            logger.warning(
                "Sitemap returned status %d (attempt %d/%d)",
                resp.status_code, attempt, config.MAX_RETRIES,
            )
        except Exception as exc:  # noqa: BLE001 – curl_cffi raises various types
            logger.warning("Sitemap attempt %d failed: %s", attempt, exc)

        if attempt == config.MAX_RETRIES:
            logger.error("Failed to download sitemap after %d attempts.", config.MAX_RETRIES)
            return []
        time.sleep(config.RETRY_BACKOFF * attempt)

    if resp is None:
        return []

    xml_str = resp.text.replace(_NS_DECLARATION, "")
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        logger.error("Failed to parse sitemap XML: %s", exc)
        return []

    all_categories: list[dict] = []
    seen_slugs: set[str] = set()

    for loc in root.findall(".//loc"):
        cat_url = (loc.text or "").strip()
        if not cat_url:
            continue
        slug = _slug_from_url(cat_url)
        if not slug or slug in seen_slugs:
            continue

        match = _CATEGORY_RE.search(slug)
        cat_id = match.group(1) if match else ""

        all_categories.append({
            "name":        _name_from_slug(slug),
            "slug":        slug,
            "category_id": cat_id,
            "url":         cat_url,
            "parent_slug": _parent_slug_from_url(cat_url),
        })
        seen_slugs.add(slug)

    logger.info("Sitemap parsed: %d total categories", len(all_categories))

    if level == "all":
        return all_categories

    # level == "main": keep only the declared top-level categories
    main_set = set(config.MAIN_CATEGORY_SLUGS)
    main_categories = [c for c in all_categories if c["slug"] in main_set]

    # Preserve declared order so the scraping log reads predictably.
    order = {s: i for i, s in enumerate(config.MAIN_CATEGORY_SLUGS)}
    main_categories.sort(key=lambda c: order.get(c["slug"], 99))

    missing = [s for s in config.MAIN_CATEGORY_SLUGS if s not in seen_slugs]
    if missing:
        logger.warning("Main categories missing from sitemap: %s", ", ".join(missing))

    logger.info("Keeping %d main categories for scraping.", len(main_categories))
    return main_categories
