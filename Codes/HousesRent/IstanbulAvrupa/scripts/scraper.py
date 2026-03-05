"""
scraper.py — Core scraping logic for the Istanbul Avrupa rent scraper.
======================================================================

Adaptive bracket splitting
--------------------------
Sahibinden.com caps search results at 1 000 listings per query. To capture
all data, the scraper works with price-range brackets:

  scrape_and_resolve()  peeks at the total listing count for a given range.
  If the count exceeds 1 000, it splits the range in half and recurses. When
  the count is safe, it scrapes all pages immediately using the already-loaded
  page 1 — so every URL is fetched exactly once.

  scrape_leaf_bracket()  scrapes a single bracket whose price bounds are
  already known to be safe (used on --resume when the bracket list has been
  cached from a previous run, avoiding any resolution overhead).
"""

import csv
import logging
import os
import random
import re
import threading
import time

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

# One CAPTCHA prompt at a time — prevents interleaved terminal output if the
# scraper is ever adapted for concurrent use.
_captcha_lock = threading.Lock()


# ── Driver factory ────────────────────────────────────────────────────────────

def setup_driver(profile_dir: str | None = None) -> uc.Chrome:
    """Create and return a uc.Chrome driver.

    Args
    ----
    profile_dir : str | None
        Path to the Chrome user-data-dir. Defaults to config.SELENIUM_PROFILE_DIR

    Returns
    -------
    uc.Chrome
        Chrome driver instance tailored to bypass basic Selenium detection.
    """
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={profile_dir or config.SELENIUM_PROFILE_DIR}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver


# ── HTML helpers ──────────────────────────────────────────────────────────────

def _extract_total_listings(soup: BeautifulSoup) -> int | None:
    """Finds the total number of listings from the summary text.

    Example: '"İstanbul Kiralık Ev"aramanızda3.193 ilanbulundu.' -> 3193

    Args
    ----
    soup : BeautifulSoup
        Parsed HTML of the sahibinden.com page.

    Returns
    -------
    int | None
        Total listing integer if found, None otherwise.
    """
    res_elem = soup.select_one(".result-text")
    if res_elem:
        text = res_elem.get_text(strip=True)
        clean_text = text.replace(".", "")
        match = re.search(r"(\d+)\s*ilan", clean_text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    for tag in soup.find_all(string=lambda t: t and "ilan" in t.lower()):
        parent = tag.parent
        if parent and parent.name not in ["script", "style", "title"]:
            text = tag.strip()
            clean_text = text.replace(".", "")
            match = re.search(r"(\d+)\s*ilan\s*(?:bulundu|var)", clean_text, re.IGNORECASE)
            if match:
                return int(match.group(1))

    return None


def _resolve_rooms_index(soup: BeautifulSoup) -> int | None:
    """Identifies the index of the "Rooms" column in the search results table.

    Args
    ----
    soup : BeautifulSoup
        Parsed HTML of the sahibinden.com page.

    Returns
    -------
    int | None
        0-based index of the "Oda" column, or None if not located.
    """
    headers = [
        th.get_text(strip=True)
        for th in soup.select(
            "#searchResultsTable thead th.searchResultsAttributeHeader"
        )
    ]
    for idx, header in enumerate(headers):
        if "oda" in header.lower().replace("ı", "i"):
            return idx
    return None


def _parse_listings(soup: BeautifulSoup, rooms_idx: int | None) -> list[dict]:
    """Extracts listing metrics from the page's search results table.

    Args
    ----
    soup : BeautifulSoup
        Parsed HTML of the sahibinden.com page.
    rooms_idx : int | None
        The column index containing the rooms data.

    Returns
    -------
    list[dict]
        A list of dictionaries containing District, Rooms, and Price keys.
    """
    records = []
    for row in soup.select("#searchResultsTable tbody tr.searchResultsItem"):
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            price = price_elem.text.strip() if price_elem else None

            loc_elem = row.select_one(".searchResultsLocationValue")
            district = " / ".join(loc_elem.stripped_strings) if loc_elem else "N/A"

            attrs = row.select(".searchResultsAttributeValue")
            if rooms_idx is not None and len(attrs) > rooms_idx:
                rooms = attrs[rooms_idx].text.strip()
            elif len(attrs) > 1:
                rooms = attrs[1].text.strip()
            else:
                rooms = "N/A"

            if price:
                records.append({"District": district, "Rooms": rooms, "Price": price})
        except Exception as exc:
            logger.debug("Row parse error: %s", exc)

    return records


def _build_url(min_price: int, max_price: int, page: int = 1) -> str:
    """Constructs the sahibinden.com search URL query string.

    Args
    ----
    min_price : int
        Minimum price bound limitation.
    max_price : int
        Maximum price bound limitation.
    page : int
        The pagination number to view.

    Returns
    -------
    str
        Full URL to the search results page.
    """
    url = (
        f"https://www.sahibinden.com/kiralik/{config.CITY_URL_NAME}"
        f"?pagingSize={config.PAGE_SIZE}"
        f"&price_min={min_price}&price_max={max_price}"
    )
    if page > 1:
        url += f"&pagingOffset={(page - 1) * config.PAGE_SIZE}"
    return url


def _wait_for_listings(driver: uc.Chrome) -> BeautifulSoup:
    """Wait for the page to settle, then return its parsed soup.

    If no listing rows are found and the page does not show a "no results"
    message, a CAPTCHA or login wall is assumed. The scraper pauses and
    prompts the user interactively, then re-parses once a successful page
    is confirmed. Loops until the page is conclusively resolved.

    Args
    ----
    driver : uc.Chrome
        Active Chrome driver instance.

    Returns
    -------
    BeautifulSoup
        Parsed HTML soup of the driver's current active page.
    """
    time.sleep(config.PAGE_LOAD_DELAY)
    soup = BeautifulSoup(driver.page_source, "lxml")
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

    if listings:
        return soup

    page_lower = driver.page_source.lower()
    if "ilan bulunamadı" in page_lower or "bulunamamıştır" in page_lower:
        return soup

    # CAPTCHA / login wall — prompt the user and keep retrying until the
    # listing table is visible or the page clearly shows no results.
    with _captcha_lock:
        while True:
            print("\n" + "=" * 55)
            print("⚠️  ACTION REQUIRED: CAPTCHA or Login wall detected.")
            print("   1. Look at the Chrome window and solve the puzzle.")
            print("   2. Wait until you clearly see the list of houses.")
            print("=" * 55)
            input("   ▶ Press ENTER here ONLY AFTER you see the listings… ")

            time.sleep(2.0)
            soup = BeautifulSoup(driver.page_source, "lxml")
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if listings:
                break

            page_lower = driver.page_source.lower()
            if "ilan bulunamadı" in page_lower or "bulunamamıştır" in page_lower:
                break

            print("   ⚠  No listings visible yet. Please wait a moment longer.")

    return soup


# ── Shared page-scraping helper ───────────────────────────────────────────────

def _scrape_pages_from_soup(
    driver: uc.Chrome,
    soup: BeautifulSoup,
    min_price: int,
    max_price: int,
    delay: float,
    pad: str = "",
) -> list[dict]:
    """Scrape all pages of a bracket, starting from an already-loaded soup.

    page 1 soup is passed in directly (already fetched by the caller) so no
    additional request is made for the first page. Subsequent pages are
    navigated using the "Sonraki" (Next) button. Stops at page 20, which is
    the hard cap imposed by sahibinden.com (20 pages × 50 listings = 1 000).

    Args
    ----
    driver : uc.Chrome
        Active Chrome driver instance.
    soup : BeautifulSoup
        The fetched page 1 HTML data for iterative processing.
    min_price : int
        Minimum price limit for logs.
    max_price : int
        Maximum price limit for logs.
    delay : float
        Base delay value between pagination shifts.
    pad : str
        Padding for console display visuals.

    Returns
    -------
    list[dict]
        Complete list of collected row dictionaries spanning all accessible pages.
    """
    records: list[dict] = []
    rooms_idx: int | None = _resolve_rooms_index(soup)
    page_num = 1

    while True:
        page_records = _parse_listings(soup, rooms_idx)
        records.extend(page_records)

        if page_records:
            logger.info(
                "%s  Page %2d: %2d listings (total: %d) | %d–%d TL",
                pad, page_num, len(page_records), len(records),
                min_price, max_price,
            )

        # Sahibinden hard cap: 20 pages × 50 = 1 000 listings
        if page_num >= 20:
            break

        has_next_btn = soup.find("a", title="Sonraki")
        if not has_next_btn:
            break

        next_url = "https://www.sahibinden.com" + has_next_btn["href"]
        driver.get(next_url)
        page_num += 1
        time.sleep(delay * random.uniform(0.5, 1.5))
        soup = _wait_for_listings(driver)

        if rooms_idx is None:
            rooms_idx = _resolve_rooms_index(soup)

    return records


# ── Adaptive resolve + scrape ─────────────────────────────────────────────────

def scrape_and_resolve(
    driver: uc.Chrome,
    min_price: int,
    max_price: int,
    done_ranges: set[tuple[int, int]],
    save_fn,
    mark_done_fn,
    bracket_cache: list | None = None,
    delay: float = config.PAGE_LOAD_DELAY,
    indent: int = 0,
) -> int:
    """Recursively resolves and scrapes the price range [min_price, max_price].

    On the first page load, peeks at the total listing count:
      - If count > MAX_LISTINGS_PER_QUERY: splits the range and recurses.
      - If count is safe: scrapes all pages immediately, reusing the already
        loaded page 1 soup (no duplicate request).

    Each resolved leaf bracket is appended to bracket_cache (if provided) so
    main.py can persist the bracket list for faster future --resume runs.
    Brackets already in done_ranges are skipped without a page load.

    Args
    ----
    driver : uc.Chrome
        Active Selenium worker instance.
    min_price : int
        Current testing minimum bound in TL.
    max_price : int
        Current testing maximum bound in TL.
    done_ranges : set[tuple[int, int]]
        Set of recorded (already-completed) bounds.
    save_fn : Callable
        Function pointing to the data persistence orchestrator.
    mark_done_fn : Callable
        Function pointing to checkpoint persistence logical flow.
    bracket_cache : list | None
        Active list tracking leaf brackets as they emerge from recursion.
    delay : float
        Configured base latency limit payload to stagger query speeds.
    indent : int
        Padding tracker to provide tree structured logs on the terminal.

    Returns
    -------
    int
        The total number of records successfully captured and saved by leaf logic.
    """
    pad = "  " * indent

    if (min_price, max_price) in done_ranges:
        logger.info("%s↩  Skipping completed: %d–%d TL", pad, min_price, max_price)
        return 0

    width = max_price - min_price
    logger.info("%s▶  Checking range %d–%d TL…", pad, min_price, max_price)

    url = _build_url(min_price, max_price, page=1)
    driver.get(url)
    soup = _wait_for_listings(driver)
    total_listings = _extract_total_listings(soup)

    # ── Split decision ────────────────────────────────────────────────────────
    if (
        total_listings is not None
        and total_listings > config.MAX_LISTINGS_PER_QUERY
        and width > config.MIN_BRACKET_WIDTH
    ):
        logger.info(
            "%s   ✂️ Range too dense (%d listings). Splitting…",
            pad, total_listings,
        )
        mid = (min_price + max_price) // 2
        time.sleep(random.uniform(
            config.BETWEEN_BRACKET_DELAY_MIN,
            config.BETWEEN_BRACKET_DELAY_MAX,
        ))
        total = scrape_and_resolve(
            driver, min_price, mid,
            done_ranges, save_fn, mark_done_fn, bracket_cache, delay, indent + 1,
        )
        total += scrape_and_resolve(
            driver, mid + 1, max_price,
            done_ranges, save_fn, mark_done_fn, bracket_cache, delay, indent + 1,
        )
        return total

    elif total_listings is not None and total_listings > config.MAX_LISTINGS_PER_QUERY:
        logger.warning(
            "%s   ⚠ Min width (%d TL) reached but count (%d) still over cap. "
            "Scraping up to the 1000-listing limit only.",
            pad, width, total_listings,
        )
    elif total_listings is not None:
        logger.info(
            "%s   ✓ Safe range (%d listings). Scraping now…",
            pad, total_listings,
        )
    else:
        logger.info("%s   ? Could not parse count (likely 0). Scraping.", pad)

    # ── Scrape this safe bracket (page 1 already loaded — no extra request) ──
    if bracket_cache is not None:
        bracket_cache.append([min_price, max_price])

    records = _scrape_pages_from_soup(driver, soup, min_price, max_price, delay, pad)

    if records:
        save_fn(records)
        logger.info(
            "%s✅ Saved %d records for %d–%d TL.",
            pad, len(records), min_price, max_price,
        )

    mark_done_fn(min_price, max_price)
    done_ranges.add((min_price, max_price))
    return len(records)


# ── Direct leaf-bracket scrape ────────────────────────────────────────────────

def scrape_leaf_bracket(
    driver: uc.Chrome,
    min_price: int,
    max_price: int,
    save_fn,
    mark_done_fn,
    delay: float = config.PAGE_LOAD_DELAY,
) -> int:
    """Scrape a single price bracket whose bounds are already known to be safe.

    Used on --resume when the complete bracket list has been cached in the
    checkpoint from a previous run. Skips peeking at the listing count,
    loading page 1 directly and scraping all pages from there.

    Args
    ----
    driver : uc.Chrome
        Active driver proxy.
    min_price : int
        Lowest listing criteria price.
    max_price : int
        Highest listing criteria price.
    save_fn : Callable
        Function appending collected records.
    mark_done_fn : Callable
        Function for updating ongoing progress logs.
    delay : float
        Pre-configured sleep buffer limit.

    Returns
    -------
    int
        Valid records generated through iteration over accessible pages.
    """
    logger.info("▶  Scraping bracket %d–%d TL…", min_price, max_price)
    url = _build_url(min_price, max_price, page=1)
    driver.get(url)
    soup = _wait_for_listings(driver)

    records = _scrape_pages_from_soup(driver, soup, min_price, max_price, delay)

    if records:
        save_fn(records)
        logger.info("✅ Saved %d records for %d–%d TL.", len(records), min_price, max_price)

    mark_done_fn(min_price, max_price)
    return len(records)


# ── CSV output ────────────────────────────────────────────────────────────────

def save_incremental(data_batch: list[dict]) -> None:
    """Append a batch of records to the shared CSV.
    
    Args
    ----
    data_batch : list[dict]
        The newly validated chunk of dictionary records.
    """
    if not data_batch:
        return

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)

    with open(config.CSV_OUTPUT_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)
