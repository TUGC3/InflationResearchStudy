"""
scraper.py — Core scraping logic for the Izmir rent scraper.

Key design: SMART ADAPTIVE BRACKETS (EARLY PEEK)
------------------------------------------------
For any price range, the scraper loads page 1 and looks for the text telling
us the total number of listings.
- If count <= 1000: It continues and scrapes all pages.
- If count > 1000: It stops immediately, cuts the price range in half, and
  recursively tries again.

Anti-Bot Evasion & Resuming:
If a CAPTCHA or Login wall is detected, it raises a CaptchaDetectedException.
The main process deletes the profile (force-killing tasks to avoid file locks)
and restarts. The scraper remembers exactly which page it was on and resumes
without duplicating data.
"""

import csv
import logging
import os
import random
import re
import time
import shutil
import subprocess  # Added to resolve locked files (taskkill)

import undetected_chromedriver as uc
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

# Global dictionary to remember the page we left off on (kept in memory)
# Format: {(min_price, max_price): last_attempted_page_number}
progress_tracker = {}

# ── Custom Exception Class ────────────────────────────────────────────────────
class CaptchaDetectedException(Exception):
    """Raised when bot protection (CAPTCHA or Login wall) is detected."""
    pass

# ── Profile Cleanup ───────────────────────────────────────────────────────────
def delete_selenium_profile():
    """Completely deletes the existing Selenium profile directory (resets cookies and history).
       Force-closes the browser to prevent Windows file lock issues.
    """
    profile_dir = getattr(config, 'SELENIUM_PROFILE_DIR', None)

    if profile_dir and os.path.exists(profile_dir):
        logger.info("🗑️ Deleting old Selenium profile (Resetting identity)...")

        # 1. Force kill hanging Chrome tasks in the background on Windows
        if os.name == 'nt':
            try:
                subprocess.call("taskkill /F /IM chrome.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.call("taskkill /F /IM chromedriver.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

        # 2. Wait a short time for the OS to release file locks
        time.sleep(3)

        # 3. Attempt to delete the directory
        try:
            shutil.rmtree(profile_dir)
            logger.info("✅ Profile deleted successfully.")
        except Exception as e:
            logger.warning(f"⚠️ First deletion attempt failed: {e}. Retrying...")
            time.sleep(2)
            try:
                # Force delete the directory, ignoring stubborn locked files
                shutil.rmtree(profile_dir, ignore_errors=True)
                logger.info("✅ Profile force-deleted.")
            except Exception as final_e:
                logger.error(f"❌ Profile could not be permanently deleted: {final_e}")

# ── Driver Setup ──────────────────────────────────────────────────────────────
def setup_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    if hasattr(config, 'SELENIUM_PROFILE_DIR') and config.SELENIUM_PROFILE_DIR:
        options.add_argument(f"--user-data-dir={config.SELENIUM_PROFILE_DIR}")

    options.add_argument("--disable-blink-features=AutomationControlled")

    is_github_actions = os.environ.get("HEADLESS") == "true"
    if is_github_actions:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")

    driver = uc.Chrome(options=options, version_main=145)
    return driver

# ── HTML Helpers ──────────────────────────────────────────────────────────────
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

        logger.warning("🚨 CAPTCHA or Login screen detected!")
        raise CaptchaDetectedException("Hit the bot protection wall.")

    return soup


# ── Core: Adaptive Scrape ─────────────────────────────────────────────────────
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
    bracket_key = (min_price, max_price)

    # Skip if the range is marked as "completely done" in the JSON file
    if bracket_key in done_ranges:
        logger.info("%s↩  Skipping already-completed range %d–%d TL", pad, min_price, max_price)
        return 0

    width = max_price - min_price

    # Check if there's a page we previously left off on for this range
    start_page = progress_tracker.get(bracket_key, 1)

    if start_page == 1:
        logger.info("%s▶  Checking range %d–%d TL…", pad, min_price, max_price)
    else:
        logger.info("%s⏩ Resuming range %d–%d TL directly from Page %d...", pad, min_price, max_price, start_page)

    url = (
        f"https://www.sahibinden.com/kiralik/{config.CITY_URL_NAME}"
        f"?pagingSize={config.PAGE_SIZE}"
        f"&price_min={min_price}&price_max={max_price}"
    )

    # If not starting from page 1, add an Offset to the URL to go directly to that page
    if start_page > 1:
        offset = (start_page - 1) * config.PAGE_SIZE
        url += f"&pagingOffset={offset}"

    driver.get(url)
    soup = _wait_for_listings(driver)

    # ── SPLIT DECISION (We only make split decisions if we are on page 1) ──
    if start_page == 1:
        total_listings = _extract_total_listings(soup)

        if total_listings is not None and total_listings > config.MAX_LISTINGS_PER_QUERY and width > config.MIN_BRACKET_WIDTH:
            logger.info("%s   ✂️ Range too dense (%d listings). Splitting...", pad, total_listings)
            mid = (min_price + max_price) // 2
            total_saved = 0
            total_saved += scrape_range(driver, min_price, mid, done_ranges, save_fn, save_checkpoint_fn, indent + 1)
            time.sleep(random.uniform(config.BETWEEN_BRACKET_DELAY_MIN, config.BETWEEN_BRACKET_DELAY_MAX))
            total_saved += scrape_range(driver, mid + 1, max_price, done_ranges, save_fn, save_checkpoint_fn, indent + 1)
            return total_saved

        elif total_listings is not None and total_listings > config.MAX_LISTINGS_PER_QUERY:
             logger.warning("%s   ⚠ Scraped up to cap.", pad)
        elif total_listings is not None:
             logger.info("%s   ✓ Safe range (%d listings). Scraping all pages.", pad, total_listings)
        else:
             logger.info("%s   ? Could not parse total count. Scraping.", pad)

    # ── PERFORM ACTUAL SCRAPE ──
    rooms_idx: int | None = _resolve_rooms_index(soup)
    current_page = start_page
    total_records_saved_this_run = 0

    while True:
        page_records = _parse_listings(soup, rooms_idx)

        if page_records:
            # 1. Save data IMMEDIATELY (So data isn't lost if the next page crashes)
            save_fn(page_records)
            total_records_saved_this_run += len(page_records)

            # 2. Save the successfully completed page to the tracker
            progress_tracker[bracket_key] = current_page + 1

            logger.info("%s      Page %2d: %2d listings saved | %d–%d TL",
                pad, current_page, len(page_records), min_price, max_price)

        has_next = bool(soup.find("a", title="Sonraki"))

        if current_page >= 20:
             break

        if has_next:
            next_btn = soup.find("a", title="Sonraki")
            next_url = "https://www.sahibinden.com" + next_btn["href"]
            driver.get(next_url)
            time.sleep(random.uniform(config.PAGE_TURN_DELAY_MIN, config.PAGE_TURN_DELAY_MAX))

            # This might throw a CAPTCHA. If it does, the while loop breaks,
            # and 'current_page + 1' saved in progress_tracker stays in memory!
            soup = _wait_for_listings(driver)

            current_page += 1
            if rooms_idx is None:
                rooms_idx = _resolve_rooms_index(soup)
        else:
            break

    logger.info("%s✅ Finished entirely. Saved %d records this run for %d–%d TL.", pad, total_records_saved_this_run, min_price, max_price)

    # Save to JSON if the entire range finished completely
    save_checkpoint_fn(min_price, max_price)
    done_ranges.add(bracket_key)

    # Clear the record in the tracker since the range is done
    if bracket_key in progress_tracker:
        del progress_tracker[bracket_key]

    return total_records_saved_this_run


# ── CSV Output ────────────────────────────────────────────────────────────────
def save_incremental(data_batch: list[dict]) -> None:
    if not data_batch:
        return

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)

    with open(config.CSV_OUTPUT_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)