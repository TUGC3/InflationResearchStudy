"""Product extraction for the Karaca scraper."""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

try:
    from . import config
except ImportError:
    import config

logger = logging.getLogger(__name__)

TOTAL_PRODUCTS_RE = re.compile(r"window\.totalProduct\s*=\s*(?P<count>\d+)\s*;")
TOTAL_PAGES_RE = re.compile(r"window\.totalPage\s*=\s*(?P<count>\d+)\s*;")
PAGE_SIZE_RE = re.compile(r"window\.catalogPaginateLimit\s*=\s*(?P<count>\d+)\s*;")
VISIBLE_TOTAL_RE = re.compile(r"(?P<count>\d+)\s*Ürün var", re.IGNORECASE)


@dataclass
class CategoryFetchResult:
    products: list[dict]
    total_products: Optional[int]
    total_pages: Optional[int]
    complete: bool


def _make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(config.DEFAULT_HEADERS)
    return session


def _clean_text(value: str) -> str:
    return " ".join((value or "").split())


def _normalise_product_url(value: str) -> str:
    cleaned = _clean_text(value)
    if not cleaned:
        return ""
    absolute = urljoin(config.HOME_URL, cleaned)
    if absolute.rstrip("/") == config.BASE_URL:
        return ""
    return absolute


def _is_placeholder_image(value: str) -> bool:
    lowered = (value or "").strip().lower()
    return "no-image" in lowered


def _as_float(value) -> float:
    if value in (None, ""):
        return 0.0
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    text = str(value).strip().replace(".", "").replace(",", ".")
    try:
        return round(float(text), 2)
    except ValueError:
        return 0.0


def _extract_json_literal(html: str, variable_name: str) -> Optional[str]:
    marker = variable_name
    start_index = html.find(marker)
    if start_index == -1:
        return None

    equals_index = html.find("=", start_index)
    if equals_index == -1:
        return None

    cursor = equals_index + 1
    while cursor < len(html) and html[cursor].isspace():
        cursor += 1

    if cursor >= len(html) or html[cursor] not in "[{":
        return None

    opening = html[cursor]
    closing = "]" if opening == "[" else "}"
    depth = 0
    in_string = False
    escape = False

    for index in range(cursor, len(html)):
        char = html[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == opening:
            depth += 1
            continue
        if char == closing:
            depth -= 1
            if depth == 0:
                return html[cursor : index + 1]

    return None


def _pick_first_image_url(card) -> str:
    for image in card.select(".swiper-container-product-preview .swiper-slide img"):
        srcset = (image.get("srcset") or "").strip()
        if srcset:
            first = srcset.split(",")[0].strip().split(" ")[0].strip()
            if first:
                return first

        src = (image.get("src") or "").strip()
        if src:
            if "," in src:
                src = src.split(",")[0].strip().split(" ")[0].strip()
            if src:
                return src

    return ""


def parse_card_fallbacks_from_html(html: str) -> dict[str, dict]:
    """Parse rendered product-card metadata as a fallback for malformed JSON rows."""
    soup = BeautifulSoup(html, "html.parser")
    fallbacks: dict[str, dict] = {}

    for card in soup.select(".plpProduct[data-productid]"):
        product_id = _clean_text(card.get("data-productid") or "")
        if not product_id:
            continue

        link = card.select_one("a.plp-url[href]")
        if link is None:
            continue

        href = _normalise_product_url(link.get("href") or "")
        data_url = _normalise_product_url(link.get("data-product-url") or "")
        image_url = _pick_first_image_url(card)
        if not image_url:
            image_url = _clean_text(link.get("data-product-image-url") or "")

        name = _clean_text(
            link.get("data-productname")
            or link.get("title")
            or ""
        )

        fallbacks[product_id] = {
            "Product Name": name,
            "Product URL": href or data_url,
            "Image URL": image_url,
            "Stock Quantity": _clean_text(link.get("data-stock") or ""),
            "Color": _clean_text(link.get("data-variant") or ""),
        }

    return fallbacks


def build_page_url(category_url: str, page: int) -> str:
    """Build a category page URL with Karaca's `page` pagination parameter."""
    if page <= 1:
        return category_url

    parsed = urlparse(category_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["page"] = str(page)
    updated = parsed._replace(query=urlencode(query))
    return urlunparse(updated)


def extract_total_products(html: str) -> Optional[int]:
    """Extract the total product count from a category page if present."""
    match = TOTAL_PRODUCTS_RE.search(html)
    if match:
        return int(match.group("count"))

    match = VISIBLE_TOTAL_RE.search(html)
    if match:
        return int(match.group("count"))

    return None


def extract_total_pages(html: str) -> Optional[int]:
    """Extract the total number of pages from a category page if present."""
    match = TOTAL_PAGES_RE.search(html)
    if match:
        return int(match.group("count"))
    return None


def extract_page_size(html: str) -> Optional[int]:
    """Extract the server-rendered page size from a category page if present."""
    match = PAGE_SIZE_RE.search(html)
    if match:
        return int(match.group("count"))
    return None


def parse_category_metadata_from_html(html: str) -> dict:
    """Extract Karaca category metadata from the page's datalayer object."""
    payload = _extract_json_literal(html, "window.datalayer_category")
    if payload is None:
        return {}
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def normalize_product_record(
    raw: dict,
    source_category: dict,
    category_meta: dict,
    fallback: Optional[dict] = None,
) -> dict:
    """Normalise one Karaca catalog payload into CSV-ready fields."""
    fallback = fallback or {}
    regular_price = _as_float(raw.get("unit_price") or raw.get("unit_sale_price"))
    shown_price = _as_float(raw.get("unit_sale_price") or raw.get("unit_price"))
    if shown_price == 0:
        shown_price = regular_price
    if regular_price == 0:
        regular_price = shown_price

    discount_amount = round(max(0.0, regular_price - shown_price), 2)
    discount_rate = round((discount_amount / regular_price) * 100, 2) if regular_price else 0.0

    stock_value = raw.get("stock")
    if stock_value in (None, ""):
        stock_value = fallback.get("Stock Quantity") or 0
    stock_quantity = int(float(stock_value or 0))
    main_category = source_category.get("main_category", "")
    top_category = source_category.get("name", "")
    category_path = " > ".join(part for part in (main_category, top_category) if part)
    product_name = _clean_text(raw.get("name") or fallback.get("Product Name") or "")
    product_url = _normalise_product_url(raw.get("url") or "")
    if not product_url:
        product_url = _normalise_product_url(fallback.get("Product URL") or "")
    image_url = _clean_text(raw.get("product_image_url") or "")
    if not image_url or _is_placeholder_image(image_url):
        image_url = _clean_text(fallback.get("Image URL") or image_url)

    return {
        "Product Name": product_name,
        "Product Cost": shown_price,
        "Product Original Cost": regular_price,
        "Discount Amount": discount_amount,
        "Discount Rate": discount_rate,
        "Currency": _clean_text(raw.get("currency") or "TRY"),
        "Product ID": str(raw.get("id") or ""),
        "Stock Quantity": stock_quantity,
        "In Stock": "Yes" if stock_quantity > 0 else "No",
        "Main Category": main_category,
        "Top Category": top_category,
        "Category ID": str(category_meta.get("categoryid") or ""),
        "Category Path": category_path,
        "Source Category": top_category,
        "Source Category URL": source_category.get("url", ""),
        "Product URL": product_url,
        "Image URL": image_url,
        "Color": _clean_text(raw.get("color") or fallback.get("Color") or ""),
        "Size": _clean_text(raw.get("size") or ""),
    }


def _is_valid_product_record(record: dict) -> bool:
    product_id = _clean_text(record.get("Product ID") or "")
    product_name = _clean_text(record.get("Product Name") or "")
    product_url = _clean_text(record.get("Product URL") or "")
    if not product_id or not product_name or not product_url:
        return False
    if product_url.rstrip("/") == config.BASE_URL:
        return False
    return True


def parse_product_records_from_html(
    html: str,
    source_category: dict,
    category_meta: Optional[dict] = None,
) -> list[dict]:
    """Parse Karaca `window.catalog_products` records from a category page."""
    payload = _extract_json_literal(html, "window.catalog_products")
    if payload is None:
        return []

    raw_records = json.loads(payload)
    if not isinstance(raw_records, list):
        return []

    if category_meta is None:
        category_meta = parse_category_metadata_from_html(html)
    card_fallbacks = parse_card_fallbacks_from_html(html)

    records: list[dict] = []
    for raw in raw_records:
        if not isinstance(raw, dict):
            continue
        product_id = str(raw.get("id") or "").strip()
        fallback = card_fallbacks.get(product_id, {})
        record = normalize_product_record(raw, source_category, category_meta, fallback)
        if not _is_valid_product_record(record):
            logger.warning(
                "Dropping malformed Karaca product row in '%s': id=%s name=%r url=%r",
                source_category.get("name", ""),
                record.get("Product ID", ""),
                record.get("Product Name", ""),
                record.get("Product URL", ""),
            )
            continue
        records.append(record)
    return records


def _fetch_page_html(session: requests.Session, url: str) -> str:
    last_error: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt == config.MAX_RETRIES:
                break
            time.sleep(config.RETRY_BACKOFF * attempt)
    raise RuntimeError(f"Karaca category page could not be fetched: {url} ({last_error})")


def fetch_products_for_category(
    category: dict,
    session: Optional[requests.Session] = None,
    delay: float = config.REQUEST_DELAY,
    page_limit: int = 0,
) -> CategoryFetchResult:
    """Fetch every page for one Karaca category."""
    if session is None:
        session = _make_session()

    all_products: list[dict] = []
    seen_page_signatures: set[tuple[str, ...]] = set()
    total_products: Optional[int] = None
    total_pages: Optional[int] = None
    page_size: Optional[int] = None
    page = 1
    complete = True

    while True:
        if page_limit and page > page_limit:
            if total_products is None or len(all_products) < total_products:
                complete = False
            break
        if total_pages is not None and page > total_pages:
            break

        page_url = build_page_url(category["url"], page)
        html = _fetch_page_html(session, page_url)

        if total_products is None:
            total_products = extract_total_products(html)
        if total_pages is None:
            total_pages = extract_total_pages(html)
        if page_size is None:
            page_size = extract_page_size(html)

        category_meta = parse_category_metadata_from_html(html)
        page_products = parse_product_records_from_html(html, category, category_meta)
        if not page_products:
            if page == 1:
                logger.warning(
                    "Category '%s' returned no Karaca products on its first page.",
                    category["name"],
                )
            break

        signature = tuple(item["Product ID"] for item in page_products)
        if signature in seen_page_signatures:
            logger.warning(
                "Category '%s' page %d repeated a previous page payload. Stopping pagination.",
                category["name"],
                page,
            )
            complete = False
            break
        seen_page_signatures.add(signature)

        all_products.extend(page_products)
        logger.info(
            "  %s page %d -> %d products (running total: %d/%s)",
            category["name"],
            page,
            len(page_products),
            len(all_products),
            total_products if total_products is not None else "?",
        )

        if total_products is not None and len(all_products) >= total_products:
            break
        if total_pages is None and page_size is not None and len(page_products) < page_size:
            break

        page += 1
        if delay:
            time.sleep(delay)

    return CategoryFetchResult(
        products=all_products,
        total_products=total_products,
        total_pages=total_pages,
        complete=complete,
    )
