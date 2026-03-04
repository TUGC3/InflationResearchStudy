"""
Product fetcher: scrapes all products from a Koton category page,
handling pagination and retries automatically.

How it works
------------
Koton renders each product listing page as HTML.  Each product card
contains a hidden <div class="js-insider-product"> whose text is a
JSON-like blob with full product data (name, prices, URL, image, stock…).
The parent wrapper <div class="js-product-wrapper"> has data attributes
including the product pk and sku.

The GA4 hidden div <div class="js-ga4-product-item"> provides the brand,
category hierarchy, and the human-readable base_code (style code).

Pagination is via ?page=N.  We stop when a page returns no products.
"""

import json
import logging
import random
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

# Regex to sanitise the JSON-like blobs embedded in the page.
# Koton inlines values like: "price":  1499.99 , (extra spaces are fine
# for json.loads, but sometimes there are trailing commas before }).
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _clean_json(text: str) -> str:
    """Remove trailing commas and fix minor formatting issues."""
    # Remove trailing commas before closing braces/brackets
    text = _TRAILING_COMMA_RE.sub(r"\1", text)
    return text.strip()


def _parse_insider(raw_text: str) -> dict:
    """
    Parse the js-insider-product JSON blob.

    Returns a dict or empty dict on failure.
    Keys of interest: id, name, taxonomy, currency,
                      unit_price, unit_sale_price,
                      url, stock, color, size, product_image_url.
    """
    try:
        return json.loads(_clean_json(raw_text))
    except json.JSONDecodeError:
        return {}


def _parse_ga4(raw_text: str) -> dict:
    """
    Parse the js-ga4-product-item JSON blob.

    Keys of interest: item_name, item_id, price, item_brand,
                      item_category … item_category5, base_code.
    """
    try:
        return json.loads(_clean_json(raw_text))
    except json.JSONDecodeError:
        return {}


def _parse_product(wrapper: "BeautifulSoup", category_name: str) -> Optional[dict]:
    """
    Extract a clean product record from a .js-product-wrapper element.

    Returns None if essential data is missing.
    """
    # ── Data from the wrapper element itself ──────────────────────────────────
    pk    = wrapper.get("data-pk", "")
    sku   = wrapper.get("data-sku", "")
    price = wrapper.get("data-price", "")

    # ── Insider JSON blob ─────────────────────────────────────────────────────
    insider_div = wrapper.find("div", class_="js-insider-product")
    insider: dict = {}
    if insider_div:
        insider = _parse_insider(insider_div.get_text(strip=False))

    # ── GA4 JSON blob ─────────────────────────────────────────────────────────
    ga4_div = wrapper.find("div", class_="js-ga4-product-item")
    ga4: dict = {}
    if ga4_div:
        ga4 = _parse_ga4(ga4_div.get_text(strip=False))

    # ── Combine into a flat record ────────────────────────────────────────────
    name = insider.get("name") or ga4.get("item_name") or ""
    if not name:
        return None  # Skip malformed entries

    # Prices: prefer insider (unit_price / unit_sale_price) which are cleaner
    try:
        regular_price = float(insider.get("unit_price") or ga4.get("price") or price or 0)
    except (ValueError, TypeError):
        regular_price = 0.0
    try:
        sale_price = float(insider.get("unit_sale_price") or regular_price)
    except (ValueError, TypeError):
        sale_price = regular_price

    discount_pct = 0.0
    if regular_price and sale_price < regular_price:
        discount_pct = round((1 - sale_price / regular_price) * 100, 2)

    # Category: use taxonomy list from insider if available
    taxonomy: list = insider.get("taxonomy") or []
    category = (
        " > ".join(t for t in taxonomy if t) if taxonomy else category_name
    )

    # Brand
    brand = ga4.get("item_brand", "Koton")

    # Style/base code (e.g. "6SAK60098EW")
    base_code = ga4.get("base_code", "")

    # Stock & colour/size variant info
    stock = insider.get("stock", None)
    color = insider.get("color", "")
    size  = insider.get("size", "")

    return {
        "pk":             pk,
        "sku":            sku,
        "base_code":      base_code,
        "name":           name,
        "brand":          brand,
        "category":       category,
        "color":          color,
        "size":           size,
        "regular_price":  round(regular_price, 2),
        "sale_price":     round(sale_price, 2),
        "discount_pct":   discount_pct,
        "currency":       insider.get("currency", "TRY"),
        "stock":          stock,
    }


def _fetch_page(
    session: requests.Session,
    category_url: str,
    page: int,
) -> Optional[BeautifulSoup]:
    """
    Fetch one page of a category listing.
    Returns a BeautifulSoup object or None on permanent failure.
    """
    params = {"page": page} if page > 1 else {}
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(category_url, params=params, timeout=30)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "lxml")
        except requests.RequestException as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "All %d attempts failed for %s page %d: %s",
                    config.MAX_RETRIES, category_url, page, exc,
                )
                return None
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Attempt %d failed (%s). Retrying in %ds…", attempt, exc, wait
            )
            time.sleep(wait)
    return None


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """
    Fetch ALL products for a category dict returned by fetch_categories().

    Args:
        category:   Dict with keys ``name``, ``slug``, ``url``,
                    ``parent_name`` (optional).
        session:    Optional shared requests.Session.
        delay:      Seconds to wait between page requests.
        page_limit: Max pages to fetch (0 = unlimited).

    Returns:
        List of normalised product dicts.
    """
    if session is None:
        session = _make_session()

    category_url = category["url"]
    category_name = category["name"]
    all_products: list[dict] = []
    seen_pks: set[str] = set()
    page = 1

    while True:
        if page_limit and page > page_limit:
            break

        soup = _fetch_page(session, category_url, page)
        if soup is None:
            break

        # Find all product wrapper divs on this page
        wrappers = soup.find_all("div", class_="js-product-wrapper")
        if not wrappers:
            # Also try with the broader selector used on some pages
            wrappers = soup.find_all("div", attrs={"data-url": True, "data-price": True})

        page_count = 0
        new_on_page = 0
        for wrapper in wrappers:
            product = _parse_product(wrapper, category_name)
            if product is None:
                continue
            # Deduplicate within this category scrape by pk (variant-level key)
            pk_key = product["pk"] or product["sku"] or product["name"]
            if pk_key and pk_key in seen_pks:
                continue
            if pk_key:
                seen_pks.add(pk_key)
            all_products.append(product)
            page_count += 1
            new_on_page += 1

        # Provide feedback: log every page in DEBUG, but log every 5 pages in INFO
        # so the user knows long categories aren't stuck.
        if page % 5 == 0:
            logger.info("  %s: Scraped page %d... (total products so far: %d)", category_name, page, len(all_products))
        else:
            logger.debug("Category '%s' – page %d → %d products (total: %d)", category_name, page, page_count, len(all_products))

        # If we got fewer products than expected the page might be the last
        # but we'll keep going until a page returns 0 wrappers.
        # Alternatively, if a page returns products but NONE of them are new,
        # Koton might be repeating the last page forever (infinite scroll bug).
        if page_count == 0 or new_on_page == 0:
            logger.debug("Page %d yielded 0 new products. Ending category scrape.", page)
            break

        page += 1
        time.sleep(delay * random.uniform(0.5, 1.5))

    return all_products
