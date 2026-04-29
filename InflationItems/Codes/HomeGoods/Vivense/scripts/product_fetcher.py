"""
Vivense Product Data Extraction Module
======================================

Scrapes every product in a Vivense category by walking ``?page=N`` until
an empty page is returned, and emits a list of normalised flat dicts
ready for CSV export / downstream inflation calculations.

Public Interface
----------------
fetch_products_for_category(category, session=None, delay=1.0, page_limit=0) -> list[dict]
    Iterates through all paginated category pages for ``category["url"]``
    and returns the combined product list.

Data Source
-----------
Vivense renders each product card with the relevant metadata embedded as
``data-*`` attributes on a ``<div class="product-card product-content parent">``
element.  The fields we care about are:

- ``data-product-sku``    → unique product identifier
- ``data-product-name``   → display name (Turkish)
- ``data-product-price``  → currently displayed (final) price in TRY
- ``data-discount-rate``  → discount percent (empty string → 0)
- ``data-product-brand``  → brand / collection
- ``data-category``       → most-specific sub-category (e.g. "Köşe Koltuk")
- ``data-list``           → top-level category (e.g. "Oturma Odası")
- ``data-url``            → canonical product page path
- ``span.psf-price``      → original / regular price (only present when
                             a discount is active)
- ``img.main_image``      → product image URL (``data-main-img``)

Pagination
----------
URL parameter ``?page=N`` (1-indexed).  An empty product grid signals
the end of the category.  We also stop on consecutive duplicate pages
as a defensive guard against the site silently clamping ``page`` values
back to the last valid page.

Output Schema
-------------
Each normalised product dict matches the schema used by the other
scrapers in this repository::

    {
      "id":            "HU3-1637",
      "sku":           "HU3-1637",
      "name":          "Silva Bohem Koltuk",
      "brand":         "Vivense Collection",
      "category":      "Oturma Odası",       # top-level (per scraper)
      "sub_category":  "Kanepe + Koltuk",     # data-category
      "regular_price": 23090.0,
      "shown_price":   23090.0,
      "discount_rate": 0,
      "unit":          "PIECE",
      "status":        "IN_SALE",
      "image_url":     "https://img.vivense.com/.../foo.jpg",
      "product_url":   "https://www.vivense.com/silva-bohem-ikili-koltuk-modeli.html",
    }
"""

import logging
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)


# ── Session / HTTP helpers ──────────────────────────────────────────────────

def _make_session() -> requests.Session:
    """Create a fresh ``requests.Session`` pre-loaded with default headers.

    Each worker thread calls this to obtain its own independent session,
    preventing cross-thread state sharing on the connection pool.

    Returns
    -------
    requests.Session
        A session with :data:`config.DEFAULT_HEADERS` already applied.
    """
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _fetch_page_html(
    session: requests.Session,
    url: str,
    page: int,
) -> Optional[str]:
    """GET a single category page with retries and 403-aware backoff.

    Builds the paginated URL ``"{url}?page={page}"`` and dispatches up to
    :data:`config.MAX_RETRIES` attempts.  Retry wait time follows a
    linear back-off: ``config.RETRY_BACKOFF × attempt`` seconds.

    A 403 Forbidden response triggers the same backoff but does not count
    as a hard failure on the first attempt — Vivense occasionally returns
    transient 403s under heavy concurrency, and a short sleep usually
    clears them.

    Args
    ----
    session : requests.Session
        Active session with the required browser headers already set.
    url : str
        Absolute category URL (without query parameters).
    page : int
        1-indexed page number to request.

    Returns
    -------
    str or None
        The HTML response body on success.  ``None`` when every retry
        attempt fails (network error or repeated 403/4xx/5xx).
    """
    target = f"{url}?page={page}"
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            resp = session.get(target, timeout=30)

            if resp.status_code == 403:
                logger.warning(
                    "403 Forbidden for %s — backing off (attempt %d/%d).",
                    target, attempt, config.MAX_RETRIES,
                )
                time.sleep(config.RETRY_BACKOFF * attempt)
                continue

            resp.raise_for_status()
            return resp.text

        except requests.RequestException as exc:
            if attempt == config.MAX_RETRIES:
                logger.error(
                    "All %d attempts failed for %s: %s",
                    config.MAX_RETRIES, target, exc,
                )
                return None
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Attempt %d failed (%s). Retrying in %ds...",
                attempt, exc, wait,
            )
            time.sleep(wait)

    return None


# ── Price parsing ────────────────────────────────────────────────────────────

def _clean_price(price_str: str) -> float:
    """Convert a Turkish-formatted price string into a numeric ``float``.

    Vivense renders prices with a Turkish thousands separator (``.``)
    and a comma decimal separator (e.g. ``"23.090,00 TL"``).  This helper
    strips the currency suffix and any non-breaking spaces, then
    converts the locale formatting to a plain ``float``.

    Args
    ----
    price_str : str
        Raw price text extracted from the HTML (e.g. ``"23.090,00 TL"``).
        ``None`` and empty strings are tolerated.

    Returns
    -------
    float
        Numeric price in TRY.  Returns ``0.0`` on empty input or when
        the string cannot be parsed as a float.

    Examples
    --------
    >>> _clean_price("23.090,00 TL")
    23090.0
    >>> _clean_price("19.199 TL")
    19199.0
    >>> _clean_price("")
    0.0
    """
    if not price_str:
        return 0.0
    cleaned = (
        price_str.replace("TL", "")
        .replace("\xa0", "")
        .strip()
        .replace(".", "")
        .replace(",", ".")
    )
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


# ── Card → record normalisation ──────────────────────────────────────────────

def _parse_card(card, category_name: str) -> Optional[dict]:
    """Convert a single ``product-card`` BeautifulSoup element to a flat record.

    Reads the ``data-*`` attributes embedded on the card by Vivense and,
    where required, falls back to inner-element text (e.g. parsing
    ``span.last-price`` if ``data-product-price`` is missing).

    Pricing logic
    -------------
    Vivense exposes two prices per card:

    - ``data-product-price`` / ``span.last-price`` → the **shown** price
      (post-discount, what the customer actually pays).
    - ``span.psf-price``                            → the **regular** /
      list price.  Only present when a discount is currently active;
      when absent, ``regular_price`` is set equal to ``shown_price``.

    The ``data-discount-rate`` attribute carries the discount percentage
    as a string (``""`` → 0).

    Brand handling
    --------------
    Vivense places ``data-product-brand`` on the inner
    ``<input class="favorite-checkbox">`` element instead of the parent
    card div, so we look there as a fallback.  An empty brand is normal
    for some third-party-sourced products.

    Args
    ----
    card : bs4.element.Tag
        A ``<div class="product-card product-content parent">`` element
        as returned by :func:`BeautifulSoup.select`.
    category_name : str
        Human-readable name of the top-level category currently being
        scraped (used as the ``category`` field in the output record so
        the value is always consistent with the curated taxonomy).

    Returns
    -------
    dict or None
        A flat product record with the schema documented at the top of
        this module.  ``None`` is returned when the element is missing
        a SKU or any usable price (e.g. placeholder cards).
    """
    sku = (card.get("data-product-sku") or "").strip()
    if not sku:
        return None

    # ``data-product-price`` is the displayed (post-discount) price.
    price_attr = card.get("data-product-price") or ""
    try:
        shown_price = float(price_attr) if price_attr else 0.0
    except ValueError:
        shown_price = _clean_price(price_attr)

    if not shown_price:
        # Fall back to parsing the inline ``last-price`` span.
        last = card.select_one("span.last-price")
        if last:
            shown_price = _clean_price(last.get_text(" ", strip=True))

    if not shown_price:
        return None

    # ``psf-price`` is the original / list price; only present when a
    # discount is active.  When absent, the regular price equals the
    # shown price (the catalogue is currently at "no discount").
    psf = card.select_one("span.psf-price")
    regular_price = (
        _clean_price(psf.get_text(" ", strip=True)) if psf else shown_price
    )
    if not regular_price:
        regular_price = shown_price

    discount_raw = (card.get("data-discount-rate") or "").strip()
    try:
        discount_rate = int(discount_raw) if discount_raw else 0
    except ValueError:
        try:
            discount_rate = round(float(discount_raw))
        except ValueError:
            discount_rate = 0

    name = (card.get("data-product-name") or "").strip()
    if not name:
        h3 = card.select_one("h3.product-name")
        name = h3.get_text(strip=True) if h3 else ""

    # Vivense places the brand on the inner ``<input class="favorite-checkbox">``
    # element, not on the parent card div.  Fall back to the card attribute
    # for forward compatibility in case the markup ever changes.
    brand = (card.get("data-product-brand") or "").strip()
    if not brand:
        fav = card.select_one("input.favorite-checkbox[data-product-brand]")
        if fav:
            brand = (fav.get("data-product-brand") or "").strip()

    sub_category = (card.get("data-category") or "").strip()

    # Image URL — prefer the high-quality main image.
    image_url = ""
    img = card.select_one("img.main_image, img.active-img")
    if img:
        image_url = (
            img.get("data-main-img")
            or img.get("data-original")
            or img.get("src")
            or ""
        )
        if image_url.startswith("//"):
            image_url = "https:" + image_url

    # Product page URL.
    rel_url = (card.get("data-url") or "").strip()
    if not rel_url:
        a = card.select_one("a.product-link[href]")
        if a:
            rel_url = a.get("href", "")
    product_url = (
        config.BASE_URL + rel_url
        if rel_url.startswith("/")
        else rel_url
    )

    return {
        "id":            sku,
        "sku":           sku,
        "name":          name,
        "brand":         brand,
        "category":      category_name,
        "sub_category":  sub_category,
        "regular_price": round(regular_price, 2),
        "shown_price":   round(shown_price, 2),
        "discount_rate": discount_rate,
        "unit":          "PIECE",
        "status":        "IN_SALE",
        "image_url":     image_url,
        "product_url":   product_url,
    }


# ── Main entry point ─────────────────────────────────────────────────────────

def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """Return every product in ``category`` by iterating ``?page=N`` pages.

    Args
    ----
    category : dict
        Category dict as produced by ``category_fetcher.fetch_categories``.
        Must contain ``id``, ``name`` and ``url``.
    session : requests.Session, optional
        Shared session with the required headers.  Created lazily when ``None``.
    delay : float
        Base inter-page sleep in seconds (multiplied by a uniform jitter in
        ``[config.JITTER_MIN, config.JITTER_MAX]`` for each page).
    page_limit : int
        Maximum pages to fetch per category.  ``0`` (default) → unlimited
        (still capped by :data:`config.PAGE_HARD_LIMIT` for safety).

    Returns
    -------
    list[dict]
        Normalised product records (see ``_parse_card``).  An empty list is
        returned when the very first page request fails.
    """
    if session is None:
        session = _make_session()

    cat_name = category["name"]
    cat_url  = category["url"]

    # Per-category dedup: Vivense occasionally injects related-product
    # carousels into category pages; using the SKU set guarantees we don't
    # double-count those.
    seen_skus: set[str] = set()
    products: list[dict] = []
    last_page_skus: frozenset[str] = frozenset()

    page = 1
    hard_limit = page_limit if page_limit and page_limit > 0 else config.PAGE_HARD_LIMIT

    logger.info("[%s] Starting scrape (url=%s)", cat_name, cat_url)

    while page <= hard_limit:
        html = _fetch_page_html(session, cat_url, page)
        if html is None:
            logger.warning("[%s] Page %d fetch failed — aborting category.",
                           cat_name, page)
            break

        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("div.product-card.product-content.parent")

        if not cards:
            logger.info("[%s] No product cards on page %d — end of catalogue.",
                        cat_name, page)
            break

        page_skus: set[str] = set()
        new_count = 0
        for card in cards:
            record = _parse_card(card, cat_name)
            if record is None:
                continue
            sku = record["sku"]
            if sku in seen_skus:
                continue
            seen_skus.add(sku)
            page_skus.add(sku)
            products.append(record)
            new_count += 1

        logger.debug(
            "[%s] page %d → %d cards, %d new (running total: %d)",
            cat_name, page, len(cards), new_count, len(products),
        )

        # Defensive: if Vivense returns the exact same set of SKUs as the
        # previous page (e.g. when ``page`` exceeds the real maximum), stop.
        page_sku_set = frozenset(page_skus)
        if new_count == 0 or page_sku_set == last_page_skus:
            logger.info(
                "[%s] Page %d is a duplicate of page %d — stopping.",
                cat_name, page, page - 1,
            )
            break
        last_page_skus = page_sku_set

        page += 1
        time.sleep(delay * random.uniform(config.JITTER_MIN, config.JITTER_MAX))

    logger.info("[%s] Completed: %d products across %d page(s).",
                cat_name, len(products), page - 1)
    return products
