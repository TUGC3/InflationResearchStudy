"""
Sephora Product Data Extraction Module
======================================

Fetches product listings page-by-page from a Sephora Türkiye category
URL and normalises them into flat dictionaries suitable for CSV export.

Public Interface
----------------
fetch_products_for_category(category, session=None, delay=<config>, page_limit=0) -> list[dict]
    Extracts every product reachable via the category's pagination.

Data Extraction Strategy
------------------------
Sephora uses Salesforce Commerce Cloud (Demandware).  Each product tile
on a category page is rendered as an HTML ``<div>`` carrying an
attribute called ``data-tcproduct`` whose value is an **HTML-escaped
JSON blob** with the full product record::

    {
      "product_pid":            "P10060056",
      "product_sku":            "614310",
      "product_pid_name":       "cream lip stain ...",
      "product_trademark":      "sephora collection",
      "product_breadcrumb_id":  ["C302","C344","C371"],
      "product_breadcrumb_label": "makeup/dudak/lipstick",
      "product_price_ati":      "699.00",
      "product_old_price_ati":  "999.00",
      "product_discount_ati":   "300.00",
      "product_currency":       "try",
      "product_url_page":       "https://...",
      "product_instock":        "y" | "n"
    }

Pagination Strategy
-------------------
Sephora uses ``?page=N`` query-string pagination.  We iterate pages
until either no tiles are returned or ``page_limit`` is reached.

Anti-Bot Notes
--------------
Sephora sits behind Akamai Bot Manager.  We mitigate that by:

- Using ``curl_cffi`` with Safari / Chrome TLS impersonation.
- Warming the session with a homepage GET before the first category page.
- Using jittered delays between page requests.
- Rotating to a different ``impersonate`` profile on soft failures
  (HTTP 200 but bot-challenge HTML with zero tiles).
- Long ``RATE_LIMIT_BACKOFF`` sleep when HTTP 403 is returned.

Output Schema
-------------
Each returned product dict has the following fields::

    id            str   – Sephora product identifier (uppercased product_pid)
    sku           str   – Internal SKU / barcode
    name          str   – Product display name
    brand         str   – Brand / trademark
    category      str   – Breadcrumb path from the tile (e.g. "makeup/dudak/lipstick")
    category_id   str   – Category slug the tile was scraped under (e.g. "makyaj-c302")
    regular_price float – Non-discounted list price (TRY)
    sale_price    float – Currently shown price (TRY)
    discount_pct  float – Computed percentage discount (0 if none)
    currency      str   – Currency code (always "TRY")
    in_stock      bool  – True when the tile reports ``product_instock == "y"``
    url           str   – Canonical product page URL
"""

from __future__ import annotations

import html as _html
import json
import logging
import random
import re
import time
from typing import Optional

from curl_cffi import requests  # type: ignore
from lxml import html as lxml_html

import config

logger = logging.getLogger(__name__)

# Regex used to cap the maximum page number when the first page renders
# a full pagination control.  This lets us short-circuit the page loop
# when the category is exhausted.
_PAGE_RE = re.compile(r"[?&]page=(\d+)")


# ── Session helpers ──────────────────────────────────────────────────────────


def make_session(profile: Optional[str] = None) -> "requests.Session":
    """Create a curl_cffi ``Session`` pre-configured for Sephora.

    Args
    ----
    profile : str, optional
        ``curl_cffi`` impersonation target (e.g. ``"safari17_0"``,
        ``"chrome124"``).  Defaults to the first entry of
        :data:`config.IMPERSONATE_PROFILES`.
    """
    profile = profile or config.IMPERSONATE_PROFILES[0]
    session = requests.Session(impersonate=profile)
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def warm_session(session: "requests.Session") -> bool:
    """Visit the Sephora homepage to seed Akamai cookies.

    Returns ``True`` when the homepage is fetched successfully.  The
    caller is free to ignore a ``False`` return – :func:`_fetch_page`
    will rotate the session automatically when the first request fails.
    """
    try:
        resp = session.get(config.BASE_URL + "/", timeout=30)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Homepage warm-up failed: %s", exc)
        return False

    if resp.status_code != 200 or len(resp.text) < 10_000:
        logger.warning(
            "Homepage warm-up returned status=%d size=%d",
            resp.status_code, len(resp.text),
        )
        return False
    return True


# ── Parsing helpers ──────────────────────────────────────────────────────────


def _parse_tc_product(raw: str) -> dict:
    """Decode the ``data-tcproduct`` attribute into a dict.

    The raw attribute value is HTML-entity encoded JSON.  Returns ``{}``
    when decoding fails so the caller can skip malformed tiles.
    """
    if not raw:
        return {}
    try:
        return json.loads(_html.unescape(raw))
    except (json.JSONDecodeError, ValueError):
        return {}


def _to_float(value) -> float:
    """Best-effort float parsing.  Returns ``0.0`` on failure."""
    if value in (None, "", "null"):
        return 0.0
    try:
        return float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return 0.0


def _normalise(tile_data: dict, category_slug: str) -> Optional[dict]:
    """Transform a raw ``data-tcproduct`` dict into the output schema.

    Returns ``None`` when the tile lacks a product identifier (malformed
    or rendered placeholder).
    """
    pid = (tile_data.get("product_pid") or "").strip()
    if not pid:
        return None

    regular_price = _to_float(tile_data.get("product_old_price_ati")
                              or tile_data.get("product_price_ati"))
    sale_price    = _to_float(tile_data.get("product_price_ati")
                              or tile_data.get("product_old_price_ati"))
    # Sephora sometimes reports old_price == 0 when the item isn't on sale;
    # coalesce so downstream inflation maths never divides by zero.
    if regular_price <= 0:
        regular_price = sale_price

    discount_pct = 0.0
    if regular_price > 0 and sale_price < regular_price:
        discount_pct = round((1 - sale_price / regular_price) * 100, 2)

    in_stock_flag = str(tile_data.get("product_instock") or "").strip().lower() == "y"
    currency = (tile_data.get("product_currency") or "try").upper()

    return {
        "id":            pid.upper(),
        "sku":           str(tile_data.get("product_sku") or "").strip(),
        "name":          (tile_data.get("product_pid_name") or "").strip(),
        "brand":         (tile_data.get("product_trademark") or "").strip(),
        "category":      (tile_data.get("product_breadcrumb_label") or "").strip(),
        "category_id":   category_slug,
        "regular_price": round(regular_price, 2),
        "sale_price":    round(sale_price, 2),
        "discount_pct":  discount_pct,
        "currency":      currency,
        "in_stock":      in_stock_flag,
        "url":           (tile_data.get("product_url_page") or "").strip(),
    }


def _extract_tiles(page_html: str) -> list[dict]:
    """Extract all ``data-tcproduct`` payloads from a rendered HTML page."""
    if not page_html or "data-tcproduct" not in page_html:
        return []
    tree = lxml_html.fromstring(page_html)
    tiles: list[dict] = []
    for el in tree.xpath('//*[@data-tcproduct]'):
        tiles.append(_parse_tc_product(el.get("data-tcproduct", "")))
    return tiles


def _max_page_number(page_html: str) -> int:
    """Return the highest ``page=N`` number referenced on this page.

    Used as a safety bound so we stop paginating once Sephora's paginator
    has no higher page to offer.
    """
    if not page_html:
        return 1
    matches = _PAGE_RE.findall(page_html)
    if not matches:
        return 1
    return max(int(m) for m in matches)


# ── HTTP fetch with retry / back-off ─────────────────────────────────────────


def _fetch_page(
    session_box: list,
    category_url: str,
    page: int,
    referer: str,
) -> tuple[Optional[str], "requests.Session"]:
    """Fetch a single listing page.

    ``session_box`` is a single-element list so the caller can rebind to
    a freshly-impersonated session when Akamai challenges the current
    one (Python doesn't allow rebinding a caller's local from inside a
    function).  Returns ``(html_or_None, session)``.

    Soft failure ladder:
      - HTTP 403 / 429            → sleep ``RATE_LIMIT_BACKOFF`` & rotate UA
      - HTTP 200 but bot-challenge → sleep ``EMPTY_RESPONSE_BACKOFF`` & rotate UA
      - Exception                 → linear back-off ``RETRY_BACKOFF × attempt``
    """
    params = {"page": page} if page > 1 else None
    session = session_box[0]

    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            session.headers["Referer"] = referer
            resp = session.get(category_url, params=params, timeout=30)
        except Exception as exc:  # noqa: BLE001
            wait = config.RETRY_BACKOFF * attempt
            logger.warning(
                "Network error on %s page=%d (attempt %d/%d): %s – sleeping %ds",
                category_url, page, attempt, config.MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)
            continue

        status = resp.status_code

        if status == 404:
            return None, session  # category page doesn't exist

        if status in (403, 429):
            wait = config.RATE_LIMIT_BACKOFF
            logger.warning(
                "Rate-limited (HTTP %d) on %s page=%d – sleeping %ds and rotating profile.",
                status, category_url, page, wait,
            )
            time.sleep(wait)
            session = _rotate_session(session)
            session_box[0] = session
            continue

        if status != 200:
            wait = config.RETRY_BACKOFF * attempt
            logger.warning("Unexpected status %d on page=%d – sleeping %ds.", status, page, wait)
            time.sleep(wait)
            continue

        body = resp.text or ""

        # Akamai sometimes answers with HTTP 200 but serves either a tiny
        # bot-challenge stub (~2.5 KB) or an "Access Denied" notice.  A
        # legitimate Sephora category page is always > 50 KB and renders
        # the site chrome (header / footer / meta tags).  Treat anything
        # smaller or missing those markers as a soft rate-limit.
        is_bot_challenge = (
            "sec-if-cpt-container" in body
            or "Access Denied" in body
            or len(body) < 50_000
        )
        has_tiles = "data-tcproduct" in body
        has_full_layout = "sephora" in body.lower() and "</html>" in body.lower()

        if not has_tiles and (is_bot_challenge or not has_full_layout):
            wait = config.EMPTY_RESPONSE_BACKOFF
            logger.warning(
                "Bot-challenge / suspicious response on %s page=%d (size=%d) – "
                "sleeping %ds and rotating profile.",
                category_url, page, len(body), wait,
            )
            time.sleep(wait)
            session = _rotate_session(session)
            session_box[0] = session
            continue

        # Fully-rendered page without tiles = genuine empty / last page.
        return body, session

    logger.error("Giving up on %s page=%d after %d attempts.", category_url, page, config.MAX_RETRIES)
    return None, session


def _rotate_session(current: "requests.Session") -> "requests.Session":
    """Create a fresh session with a different impersonation profile
    than the one that just got blocked, then warm it with a homepage
    GET.  Falls back to reusing the input session on total failure so
    the caller never receives ``None``.
    """
    try:
        current.close()
    except Exception:  # noqa: BLE001
        pass

    profiles = list(config.IMPERSONATE_PROFILES)
    random.shuffle(profiles)
    for prof in profiles:
        new_session = make_session(prof)
        if warm_session(new_session):
            logger.info("Rotated to impersonation profile: %s", prof)
            return new_session
    logger.warning("Profile rotation failed – reusing previous session.")
    return current


# ── Public API ───────────────────────────────────────────────────────────────


def fetch_products_for_category(
    category: dict,
    session: Optional["requests.Session"] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> list[dict]:
    """Scrape every product tile from a category's paginated listing.

    Args
    ----
    category : dict
        Category dict produced by :func:`category_fetcher.fetch_categories`.
        Must contain at least ``url`` and ``slug``.
    session : curl_cffi.requests.Session, optional
        Shared session.  A new, warmed session is created when ``None``.
    delay : float
        Base per-page sleep in seconds (jittered on every page).
    page_limit : int
        Maximum number of pages to fetch (``0`` = unlimited).

    Returns
    -------
    list[dict]
        Normalised product records (see module docstring).
    """
    if session is None:
        session = make_session()
        warm_session(session)

    category_url = category["url"]
    category_slug = category["slug"]

    session_box = [session]
    all_products: list[dict] = []
    seen_ids: set[str] = set()
    page = 1
    referer = config.BASE_URL + "/"
    known_max_page: Optional[int] = None

    while True:
        if page_limit and page > page_limit:
            break
        if known_max_page is not None and page > known_max_page:
            break

        body, session_box[0] = _fetch_page(session_box, category_url, page, referer)
        if body is None:
            break

        tiles = _extract_tiles(body)
        if not tiles:
            # First empty page → we're past the end of the catalogue.
            logger.debug("  page %d returned no tiles – stopping.", page)
            break

        if page == 1:
            known_max_page = _max_page_number(body)
            logger.info(
                "  Category '%s' — detected %d page(s) of products",
                category.get("name", category_slug), known_max_page,
            )

        new_on_page = 0
        for tile in tiles:
            product = _normalise(tile, category_slug)
            if product is None:
                continue
            pid = product["id"]
            if pid in seen_ids:
                continue
            seen_ids.add(pid)
            all_products.append(product)
            new_on_page += 1

        if page % 5 == 0 or page == 1:
            logger.info(
                "  page %2d: +%d products (total so far: %d)",
                page, new_on_page, len(all_products),
            )
        else:
            logger.debug(
                "  page %2d: +%d products (total so far: %d)",
                page, new_on_page, len(all_products),
            )

        # Update the Referer like a real browser walking the paginator.
        referer = f"{category_url}?page={page}" if page > 1 else category_url
        page += 1

        time.sleep(delay * random.uniform(config.JITTER_MIN, config.JITTER_MAX))

    return all_products
