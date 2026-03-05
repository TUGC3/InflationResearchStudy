"""
Product fetcher: queries the Migros REST API to get all products for a
given category, handling pagination and retries automatically.

Subcategory filtering
---------------------
The API accepts two relevant parameters:
  - ``category-id``  : top-level category (e.g. "2" for Meyve-Sebze)
  - ``kategoriler``  : subcategory filter ID discovered from aggregationGroups
                       (e.g. "101" for Meyve within Meyve-Sebze)

When a subcategory entry has a ``parent_id``, we pass both parameters.
When it only has an ``id`` (top-level fallback), we pass just ``category-id``.
"""

import random
import time
import logging
from typing import Optional

import requests

import config

logger = logging.getLogger(__name__)


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _parse_product(raw: dict, category_name: str) -> dict:
    """
    Normalize a raw product dict from the API into a clean flat record.

    Price is in kuruş (1/100 of a TL) — converted to TL with 2 decimals.
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
    """
    Fetch ALL products for a category dict returned by ``fetch_categories()``.

    Args:
        category:   Dict with keys ``id``, ``name``, ``parent_id`` (optional).
        session:    Optional shared requests.Session.
        delay:      Seconds to wait between page requests.
        page_limit: Max pages to fetch (0 = unlimited).

    Returns:
        List of normalized product dicts.
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
    """
    GET the product search API with exponential-backoff retries.
    Returns the parsed JSON dict, or None if all retries are exhausted.
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
