"""
scraper.py — Core scraping logic for Izmir.
"""

import csv
import logging
import os
import random
import re
import time

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

def setup_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={config.SELENIUM_PROFILE_DIR}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver

def _extract_total_listings(soup: BeautifulSoup) -> int | None:
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
    headers = [
        th.get_text(strip=True)
        for th in soup.select("#searchResultsTable thead th.searchResultsAttributeHeader")
    ]
    for idx, header in enumerate(headers):
        if "oda" in header.lower().replace("ı", "i"):
            return idx
    return None

def _parse_listings(soup: BeautifulSoup, rooms_idx: int | None) -> list[dict]:
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

def _wait_for_listings(driver: uc.Chrome) -> BeautifulSoup:
    time.sleep(config.PAGE_LOAD_DELAY)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

    if not listings:
        page_lower = driver.page_source.lower()
        if "ilan bulunamadı" in page_lower or "bulunamamıştır" in page_lower:
            return soup

        # GECE YAKALANIRSA KORUMA SİSTEMİ: 20 DAKİKA UYU
        logger.warning("⚠️ CAPTCHA veya Giriş Ekranı yakalandı!")
        logger.warning("Sistem gece çalışıyor olabileceği için manuel giriş beklenmiyor. IP'yi soğutmak için 20 dakika uyunacak...")
        time.sleep(1200) # 20 dakika bekle

        logger.info("20 dakika doldu. Sayfa yenileniyor...")
        driver.refresh()
        time.sleep(5)

        soup = BeautifulSoup(driver.page_source, "html.parser")

    return soup

def scrape_range(
    driver: uc.Chrome,
    min_price: int,
    max_price: int,
    done_ranges: set[tuple[int, int]],
    save_fn,
    save_checkpoint_fn,
    indent: int = 0,
) -> int:
    pad = "  " * indent

    if (min_price, max_price) in done_ranges:
        logger.info("%s↩  Skipping already-completed range %d–%d TL", pad, min_price, max_price)
        return 0

    width = max_price - min_price
    logger.info("%s▶  Checking range %d–%d TL…", pad, min_price, max_price)

    url = (
        f"https://www.sahibinden.com/kiralik/{config.CITY_URL_NAME}"
        f"?pagingSize={config.PAGE_SIZE}"
        f"&price_min={min_price}&price_max={max_price}"
    )
    driver.get(url)

    soup = _wait_for_listings(driver)
    total_listings = _extract_total_listings(soup)

    if total_listings is not None and total_listings > config.MAX_LISTINGS_PER_QUERY and width > config.MIN_BRACKET_WIDTH:
        logger.info("%s   ✂️ Range too dense (%d listings). Splitting...", pad, total_listings)
        mid = (min_price + max_price) // 2
        total_saved = 0
        total_saved += scrape_range(driver, min_price, mid, done_ranges, save_fn, save_checkpoint_fn, indent + 1)
        total_saved += scrape_range(driver, mid + 1, max_price, done_ranges, save_fn, save_checkpoint_fn, indent + 1)
        return total_saved

    elif total_listings is not None and total_listings > config.MAX_LISTINGS_PER_QUERY:
        logger.warning("%s   ⚠ Scraped up to cap.", pad)
    elif total_listings is not None:
        logger.info("%s   ✓ Safe range (%d listings). Scraping all pages.", pad, total_listings)
    else:
        logger.info("%s   ? Could not parse total count. Scraping.", pad)

    records: list[dict] = []
    rooms_idx: int | None = _resolve_rooms_index(soup)
    page_num = 1

    while True:
        page_records = _parse_listings(soup, rooms_idx)
        records.extend(page_records)

        if page_records:
            logger.info("%s      Page %2d: %2d listings (total: %d) | %d–%d TL",
                pad, page_num, len(page_records), len(records), min_price, max_price)

        has_next = bool(soup.find("a", title="Sonraki"))

        if page_num >= 20:
             break

        if has_next:
            next_btn = soup.find("a", title="Sonraki")
            next_url = "https://www.sahibinden.com" + next_btn["href"]
            driver.get(next_url)
            page_num += 1
            time.sleep(random.uniform(config.PAGE_TURN_DELAY_MIN, config.PAGE_TURN_DELAY_MAX))
            soup = _wait_for_listings(driver)
            if rooms_idx is None:
                rooms_idx = _resolve_rooms_index(soup)
        else:
            break

    if records:
        save_fn(records)
        logger.info("%s✅ Saved %d records for %d–%d TL.", pad, len(records), min_price, max_price)

    save_checkpoint_fn(min_price, max_price)
    done_ranges.add((min_price, max_price))

    return len(records)

def save_incremental(data_batch: list[dict]) -> None:
    if not data_batch:
        return

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)

    with open(config.CSV_OUTPUT_FILE, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)