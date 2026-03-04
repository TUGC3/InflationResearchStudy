"""
Category fetcher: discovers all Koton product categories by parsing
the gzip XML category sitemap.

Strategy
--------
Koton provides a comprehensive sitemap of all its categories:
https://s3.eu-central-1.amazonaws.com/f58f3a/sitemaps/sitemaps/sitemap-categories-1.xml.gz

This file contains over 2,500 <loc> URLs. By downloading and parsing this
sitemap, we guarantee 100% coverage of all scrapable categories, including
deeply nested or newly added sections that might not be visible in the
top-level HTML navigation.
"""

import gzip
import io
import logging
import time
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def fetch_categories(session: Optional[requests.Session] = None) -> list[dict]:
    """
    Return the definitive list of all Koton categories from the XML sitemap.

    Downloads the .xml.gz sitemap, decompresses it, parses the XML, and
    extracts all <loc> URLs.

    Returns a list of category dicts:
        [
            {
                "name": "Kadin Giyim",   # Title-cased from slug
                "slug": "kadin-giyim",
                "url":  "https://www.koton.com/kadin-giyim/",
                "parent_name": None,
                "parent_slug": None,
            },
            ...
        ]
    """
    if session is None:
        session = _make_session()

    url = config.CATEGORY_SITEMAP_URL
    logger.info("Downloading category sitemap: %s", url)

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            break
        except requests.RequestException as exc:
            if attempt == config.MAX_RETRIES:
                logger.error("Failed to download sitemap: %s", exc)
                return []
            wait = config.RETRY_BACKOFF * attempt
            logger.warning("Attempt %d failed (%s). Retrying in %ds…", attempt, exc, wait)
            time.sleep(wait)

    try:
        # requests automatically handles gzip decompression if headers are right.
        # But if it's raw we just use resp.content.
        try:
            content = gzip.decompress(resp.content)
        except gzip.BadGzipFile:
            content = resp.content
            
        # Parse the XML
        root = ET.fromstring(content)
    except Exception as exc:
        logger.error("Failed to parse sitemap: %s", exc)
        return []

    # The sitemap XML uses namespaces, typically:
    # xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
    # To avoid xpath/namespace issues in Python 3.9, we strip namespaces or
    # search using a generic string replacement.
    xml_str = content.decode("utf-8", errors="ignore")
    # Replace the default namespace declaration so ET parses it without namespaces
    xml_str = xml_str.replace('xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"', '')
    
    try:
        root = ET.fromstring(xml_str)
    except Exception as exc:
        logger.error("Failed to parse sitemap XML: %s", exc)
        return []

    # Now we can just use a simple findall for 'loc'
    loc_elements = root.findall(".//loc")
    
    if not loc_elements:
        # Fallback to wildcard namespace search if the string replace failed
        loc_elements = root.findall(".//{*}loc")

    all_categories: list[dict] = []
    seen_slugs: set[str] = set()

    for loc in loc_elements:
        cat_url = loc.text
        if not cat_url:
            continue

        # Extract the slug from the URL path
        parsed = urlparse(cat_url)
        path = parsed.path.strip("/")
        
        # Some URLs might be the root or non-category paths
        if not path or path == "list":
            continue

        # We take the last segment of the path as the primary slug
        segments = path.split("/")
        slug = segments[-1]
        
        if slug in seen_slugs:
            continue

        seen_slugs.add(slug)
        
        # Generate a fallback readable name from the slug (e.g. kiz-cocuk -> Kiz Cocuk)
        name = " ".join(part.capitalize() for part in slug.split("-"))

        # Try to infer a parent from the slug prefix if it's obvious,
        # but the product fetcher taxonomy will supersede this anyway.
        parent_slug = None
        if "-" in slug:
            parts = slug.split("-")
            if parts[0] in ("kadin", "erkek", "cocuk", "kiz", "erkek"):
                parent_slug = f"{parts[0]}-giyim"

        all_categories.append(
            {
                "name":        name,
                "slug":        slug,
                "url":         cat_url,
                "parent_name": None,
                "parent_slug": parent_slug,
            }
        )

    logger.info("Sitemap parsed successfully. Found %d categories.", len(all_categories))
    return all_categories
