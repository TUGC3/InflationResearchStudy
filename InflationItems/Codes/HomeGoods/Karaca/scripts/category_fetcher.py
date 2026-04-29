"""Category discovery for the Karaca scraper."""

from __future__ import annotations

import logging
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

try:
    from . import config
except ImportError:
    import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _main_category_priority(name: str) -> int:
    return config.MAIN_CATEGORY_PRIORITY.get(name, 999)


def _normalise_url(href: str) -> str:
    url = urljoin(config.HOME_URL, href)
    parsed = urlparse(url)
    return parsed._replace(fragment="").geturl().rstrip("/")


def _category_score(name: str, main_category: str) -> int:
    score = len(name)
    if not name.startswith("Tüm "):
        score += 100
    if name != main_category:
        score += 50
    return score


def parse_categories_from_html(
    html: str,
    *,
    include_promotional: bool = False,
) -> list[dict]:
    """Parse top-level navigation categories from the Karaca homepage."""
    soup = BeautifulSoup(html, "html.parser")
    links = soup.select('a[data-track="track-navbar"][data-main-category][href]')
    if not links:
        raise RuntimeError("Karaca navbar category links could not be found.")

    by_url: dict[str, dict] = {}
    order = 0

    for link in links:
        href = (link.get("href") or "").strip()
        name = _clean_text(link.get_text(" ", strip=True))
        main_category = _clean_text(link.get("data-main-category") or "")
        sub_category = _clean_text(link.get("data-sub-category") or "")
        if not href or href == "javascript:;" or not name or not main_category:
            continue
        if sub_category:
            continue
        is_promotional = main_category in config.PROMOTIONAL_MAIN_CATEGORIES
        if href in config.NON_LISTING_PATHS:
            continue
        if name.startswith("Tüm ") and not is_promotional:
            continue
        if name == main_category and not is_promotional:
            continue
        if not include_promotional and is_promotional:
            continue

        url = _normalise_url(href)
        slug = urlparse(url).path.rstrip("/").split("/")[-1]
        candidate = {
            "id": slug,
            "name": name,
            "url": url,
            "main_category": main_category,
            "main_priority": _main_category_priority(main_category),
            "priority": order,
            "nav_id": str(link.get("data-id") or ""),
            "is_promotional": is_promotional,
        }
        order += 1

        existing = by_url.get(url)
        if existing is None or _category_score(name, main_category) > _category_score(
            existing["name"],
            existing["main_category"],
        ):
            by_url[url] = candidate

    categories = sorted(
        by_url.values(),
        key=lambda item: (item["main_priority"], item["priority"], item["name"].casefold()),
    )
    if not categories:
        raise RuntimeError("No Karaca top-level categories were discovered.")
    return categories


def fetch_categories(
    session: Optional[requests.Session] = None,
    *,
    include_promotional: bool = False,
) -> list[dict]:
    """Fetch and parse Karaca top-level catalog categories."""
    if session is None:
        session = _make_session()

    last_error: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = session.get(config.HOME_URL, timeout=30)
            response.raise_for_status()
            categories = parse_categories_from_html(
                response.text,
                include_promotional=include_promotional,
            )
            logger.info("Discovered %d top-level Karaca categories.", len(categories))
            return categories
        except requests.RequestException as exc:
            last_error = exc
            if attempt == config.MAX_RETRIES:
                break
            time.sleep(config.RETRY_BACKOFF * attempt)

    raise RuntimeError(f"Karaca homepage could not be fetched: {last_error}")
