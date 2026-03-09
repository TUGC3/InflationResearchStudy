"""
product_fetcher.py — Fetches all products for a single Migros category.
=======================================================================

Public API
----------
fetch_products_for_category(category, session=None, delay=…, page_limit=0)
    Paginates through the Migros search API for the given category dict
    (as returned by ``category_fetcher.fetch_categories``) and returns
    every product as a normalised flat dict.

API parameter mapping
---------------------
The Migros REST search endpoint accepts two category-selection parameters:

``category-id`` (required)
    The top-level category bucket.  Passed as ``parent_id`` when the
    category has a parent, or as ``id`` for top-level fallback entries.

``kategoriler`` (optional)
    A sub-category filter discovered by the category fetcher from the API's
    own ``aggregationGroups``.  Omitted when ``parent_id`` is ``None``.

Normalised product record
-------------------------
Every raw product dict from the API is converted into a flat, consistent
record by ``_parse_product``.  Prices are converted from kuruş (1/100 TL)
to TL with two decimal places.  The image URL is resolved by priority:
``PRODUCT_LIST`` > ``PRODUCT_DETAIL`` > ``PRODUCT_HD`` > first available.
"""

import random
import time
import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    """Create a new ``requests.Session`` pre-loaded with the required default headers.

    Returns
    -------
    requests.Session
        A session with ``config.DEFAULT_HEADERS`` already applied.
    """
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _parse_product(raw: dict, category_name: str) -> dict:
    """Normalise a raw product dict from the Migros API into a clean flat record.

    Args
    ----
    raw : dict
        A single product entry as returned by the ``storeProductInfos`` or
        ``products`` array in the API response JSON.
    category_name : str
        Display name of the category being scraped, used as a fallback when
        the product itself does not carry a ``category.name`` field.

    Returns
    -------
    dict
        Flat record with the following keys (all strings / float / int)::

            id, sku, name, brand, category,
            regular_price, shown_price, discount_rate,
            unit, status, image_url, product_url

    Notes
    -----
    - Prices are stored in kuruş (integer, 1/100 TL) by the API.  They are
      divided by 100 and rounded to 2 decimal places here.
    - ``regular_price`` is the original shelf price; ``shown_price`` is the
      currently displayed price (may differ during campaigns/discounts).
    - Image type priority: ``PRODUCT_LIST`` → ``PRODUCT_DETAIL`` →
      ``PRODUCT_HD`` → first image in the list → ``""`` if none.
    """
    regular_price = raw.get("regularPrice") or raw.get("shownPrice") or 0
    shown_price   = raw.get("shownPrice")   or raw.get("regularPrice") or 0

    def to_tl(k: int) -> float:
        return round(k / 100, 2) if k else 0.0

    # Images: API returns a list [{url: ..., imageType: "PRODUCT_LIST"}, ...]
    images_raw: list = raw.get("images") or []
    image_url = None
    priority = ["PRODUCT_LIST", "PRODUCT_DETAIL", "PRODUCT_HD"]
    image_map = {
        img.get("imageType"): img.get("url")
        for img in images_raw
        if isinstance(img, dict)
    }
    for img_type in priority:
        if img_type in image_map:
            image_url = image_map[img_type]
            break
    if image_url is None and images_raw:
        first = images_raw[0]
        image_url = first.get("url") if isinstance(first, dict) else None

    # Brand and category are nested dicts
    brand_raw = raw.get("brand") or {}
    brand = brand_raw.get("name", "") if isinstance(brand_raw, dict) else str(brand_raw)

    category_raw = raw.get("category") or {}
    product_category = (
        category_raw.get("name", category_name)
        if isinstance(category_raw, dict)
        else category_name
    )

    # Product page URL is already encoded in prettyName
    pretty_name = raw.get("prettyName") or ""
    product_id  = raw.get("id") or raw.get("sku") or ""
    product_url = f"{config.BASE_URL}/{pretty_name}" if pretty_name else ""

    return {
        "id":            str(product_id),
        "sku":           str(raw.get("sku") or ""),
        "name":          raw.get("name") or "",
        "brand":         brand,
        "category":      product_category or category_name,
        "regular_price": to_tl(regular_price),
        "shown_price":   to_tl(shown_price),
        "discount_rate": raw.get("discountRate") or 0,
        "unit":          raw.get("unit") or "",
        "status":        raw.get("status") or raw.get("saleStatus") or "",
        "image_url":     image_url or "",
        "product_url":   product_url,
    }


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """Fetch ALL products for a category dict returned by ``fetch_categories()``.

    Sends paginated GET requests to ``config.PRODUCT_SEARCH_URL`` using the
    ``sayfa`` (page number) query parameter, incrementing page by one after
    each successful response.  Stops when a page returns an empty product list
    or all retries for a page are exhausted.

    A jitter-randomised delay (``delay × uniform(JITTER_MIN, JITTER_MAX)``)
    is inserted between every page request to reduce the risk of triggering
    rate limiting.

    Args
    ----
    category : dict
        Category dict as returned by ``fetch_categories``.  Must contain at
        least ``"id"`` and ``"name"``; ``"parent_id"`` is optional.
    session : requests.Session, optional
        Shared session with the required headers already set.  A new session
        is created automatically when ``None`` is passed.
    delay : float
        Base number of seconds to sleep between page requests.  Actual sleep
        time is ``delay × uniform(JITTER_MIN, JITTER_MAX)``.
    page_limit : int
        Maximum number of pages to fetch per category.  ``0`` (default) means
        unlimited — all pages are scraped.

    Returns
    -------
    list[dict]
        List of normalised product records (see ``_parse_product``) for every
        product found across all fetched pages.  Returns an empty list if the
        first page request fails.
    """
    if session is None:
        session = _make_session()

    parent_id = category.get("parent_id")
    sub_id    = category["id"]
    name      = category["name"]

    # Determine the API params:
    # - If the category has a parent, filter by (parent category-id) + (sub kategoriler)
    # - If it IS the top-level (parent_id is None), just use category-id
    if parent_id:
        base_params: dict = {
            "category-id": parent_id,
            "kategoriler":  sub_id,
            "sirala":       config.DEFAULT_SORT,
        }
    else:
        base_params = {
            "category-id": sub_id,
            "sirala":      config.DEFAULT_SORT,
        }

    all_products: list[dict] = []
    page = 1

    while True:
        if page_limit and page > page_limit:
            break

        params = {**base_params, "sayfa": page}
        data = _fetch_with_retry(session, params)

        if data is None:
            break

        products_raw = (
            data.get("data", {}).get("storeProductInfos")
            or data.get("storeProductInfos")
            or data.get("data", {}).get("products")
            or data.get("products")
            or []
        )

        if not products_raw:
            break

        for raw in products_raw:
            all_products.append(_parse_product(raw, name))

        logger.debug(
            "Category '%s' – page %d → %d products (total: %d)",
            name, page, len(products_raw), len(all_products),
        )
        page += 1
        time.sleep(delay * random.uniform(config.JITTER_MIN, config.JITTER_MAX))

    return all_products


def _fetch_with_retry(
    session: requests.Session,
    params: dict,
) -> Optional[dict]:
    """GET the product search API with exponential-backoff retries.

    Args
    ----
    session : requests.Session
        Active session with the required headers already set.
    params : dict
        Query parameters forwarded verbatim to the GET request (e.g.
        ``{"category-id": "2", "kategoriler": "101", "sayfa": 1, "sirala": "onerilenler"}``).

    Returns
    -------
    dict or None
        Parsed JSON response body on success.  ``None`` when:
        - A 403 Forbidden response is received (the caller should slow down
          requests or increase ``--delay``).
        - All ``config.MAX_RETRIES`` attempts raise a ``RequestException``.

    Notes
    -----
    Retry wait time follows a linear back-off:
    ``config.RETRY_BACKOFF × attempt`` seconds (1×, 2×, 3×, …).
    """
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = session.get(
                config.PRODUCT_SEARCH_URL,
                params=params,
                timeout=30,
            )

            if response.status_code == 403:
                logger.warning(
                    "403 Forbidden for params %s — try increasing --delay.", params
                )
                return None

            response.raise_for_status()
            return response.json()

        except requests.RequestException as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "All %d attempts failed for params %s: %s",
                    config.MAX_RETRIES, params, exc,
                )
                return None
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Attempt %d failed (%s). Retrying in %ds…", attempt, exc, wait
            )
            time.sleep(wait)

    return None
