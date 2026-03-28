"""
scraper.py — Core scraping logic for the Izmir rent scraper.
Refactored into a two-component architecture:
1. CategoryScanner: Discovers and generates target URLs.
2. DataExtractor: Visits generated URLs and extracts the data.
"""

import csv
import logging
import math
import os
import random
import re
import time
import shutil
import subprocess

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

import config

logger = logging.getLogger(__name__)

# Dictionary needed for main.py to remember where it left off
progress_tracker = {}

class CaptchaDetectedException(Exception):
    pass

def delete_selenium_profile():
    profile_dir = getattr(config, 'SELENIUM_PROFILE_DIR', None)
    if profile_dir and os.path.exists(profile_dir):
        logger.info("🗑️ Deleting old Selenium profile (Resetting identity)...")
        if os.name == 'nt':
            try:
                subprocess.call("taskkill /F /IM chrome.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.call("taskkill /F /IM chromedriver.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        time.sleep(3)
        try:
            shutil.rmtree(profile_dir, ignore_errors=True)
        except Exception:
            pass

def setup_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    if hasattr(config, 'SELENIUM_PROFILE_DIR') and config.SELENIUM_PROFILE_DIR:
        options.add_argument(f"--user-data-dir={config.SELENIUM_PROFILE_DIR}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if os.environ.get("HEADLESS") == "true":
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    return uc.Chrome(options=options, version_main=145)


def handle_browser_check(driver: uc.Chrome):
    page_source = driver.page_source.lower()

    if "tarayıcınızı" not in page_source and "kontrol ediliyor" not in page_source:
        return

    logger.info("🤖 Browser check page detected. Waiting for it to resolve...")
    start_time = time.time()

    while time.time() - start_time < 90:
        page_source = driver.page_source.lower()

        if "tarayıcınızı" not in page_source and "bekleyiniz" not in page_source and "kontrol ediliyor" not in page_source:
            logger.info("✅ Browser check resolved automatically!")
            time.sleep(1.5)
            return

        # --- NEW MANUAL "Click and Hold" Screen ---
        if "basılı tutun" in page_source or "bağlantınız kontrol ediliyor" in page_source:
            logger.warning("🚨 USER ACTION REQUIRED: 'Basılı Tutun' screen detected!")
            logger.warning("👉 Please go to the Chrome window and MANUALLY CLICK AND HOLD the button. The bot is waiting for you to pass...")

            manual_wait_start = time.time()
            # Waits here for 5 minutes (300 seconds) until you pass
            while time.time() - manual_wait_start < 300:
                current_source = driver.page_source.lower()
                # If the "click and hold" text on the screen disappears, it means you bypassed the block
                if "basılı tutun" not in current_source and "bağlantınız kontrol ediliyor" not in current_source:
                    logger.info("✅ Great! You manually bypassed the block. Automation is continuing...")
                    time.sleep(3) # Short head start to allow the site to load the new page
                    return
                time.sleep(2) # Check the page every 2 seconds

            logger.error("❌ No action taken for 5 minutes. Timeout!")
            return

        # --- Standard Automatic "Continue" Screen ---
        if "tarayıcınızı kontrol ediyoruz" in page_source and "devam et" in page_source:
            try:
                # Reduced wait time on the standard button to 15-20 seconds range (A bit faster)
                wait_time = random.uniform(15.0, 20.0)
                logger.info(f"⚠️ Standard 'Devam Et' screen detected. Waiting {wait_time:.2f}s before interaction...")
                time.sleep(wait_time)

                logger.info("✅ Wait complete. Locating 'Devam Et' button...")
                btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "btn-continue"))
                )

                actions = ActionChains(driver)
                actions.move_to_element(btn).pause(0.5).click().perform()
                logger.info("🎯 Clicked 'Devam Et' button.")

                time.sleep(5)
                return
            except Exception as e:
                logger.error(f"❌ Standard bypass error: {e}")
                time.sleep(2)
                continue

        time.sleep(1)

    logger.warning("⚠️ Browser check timed out after 90 seconds.")

def load_and_bypass(driver: uc.Chrome, url: str) -> BeautifulSoup:
    if driver.current_url in ["data:,", "about:blank"]:
        logger.info("🔥 Warming up fresh browser on homepage...")
        driver.get("https://www.sahibinden.com/")
        time.sleep(random.uniform(2.0, 4.0))
        handle_browser_check(driver)

    driver.get(url)

    # SPEEDUP 1: Fixed wait time reduced to 1-2 seconds
    time.sleep(random.uniform(1.0, 2.0))

    handle_browser_check(driver)
    page_source = driver.page_source.lower()

    if "bir dakika lütfen" in page_source or "lütfen bekleyiniz" in page_source:
        logger.info("⏳ Hit the 'Please Wait' page. Waiting 15s...")
        time.sleep(15)
        handle_browser_check(driver)

    start_time = time.time()
    # SPEEDUP 2: Reduced timeout limit from 30 to 20
    while time.time() - start_time < 20:
        soup = BeautifulSoup(driver.page_source, "html.parser")

        # If there are listings in the table, return the data INSTANTLY, don't waste time
        if soup.select("#searchResultsTable tbody tr.searchResultsItem") or "ilan bulunamadı" in driver.page_source.lower():
            return soup

        current_source = driver.page_source.lower()
        if "tarayıcınızı" in current_source or "kontrol ediliyor" in current_source:
            handle_browser_check(driver)
            start_time = time.time()

        # SPEEDUP 3: Frequency of checking listings reduced from 1.5s to 0.5s
        time.sleep(0.5)

    driver.save_screenshot("debug_silent_block.png")
    final_source = driver.page_source.lower()
    if "giriş yap" in final_source and "searchresultstable" not in final_source:
        raise CaptchaDetectedException("Login/CAPTCHA wall detected! Saved 'debug_silent_block.png'.")

    raise CaptchaDetectedException("Page loaded but listings never appeared. Saved 'debug_silent_block.png'.")

# ── COMPONENT 1: Scanner ──────────────────────────────────────────────────────
class CategoryScanner:
    def __init__(self, driver: uc.Chrome):
        self.driver = driver

    def _extract_total_listings(self, soup: BeautifulSoup) -> int | None:
        res_elem = soup.select_one(".result-text")
        if res_elem:
            match = re.search(r"(\d+)\s*ilan", res_elem.get_text(strip=True).replace(".", ""), re.IGNORECASE)
            if match: return int(match.group(1))
        return None

    def discover_bracket(self, min_price: int, max_price: int, indent: int = 0) -> list[str]:
        pad = "  " * indent
        url = (f"https://www.sahibinden.com/kiralik/{config.CITY_URL_NAME}"
               f"?pagingSize={config.PAGE_SIZE}&price_min={min_price}&price_max={max_price}")

        logger.info(f"{pad}▶ Checking range {min_price}–{max_price} TL…")
        soup = load_and_bypass(self.driver, url)
        total_listings = self._extract_total_listings(soup)

        width = max_price - min_price

        if total_listings and total_listings > config.MAX_LISTINGS_PER_QUERY and width > config.MIN_BRACKET_WIDTH:
            logger.info(f"{pad}  ✂️ Range too dense ({total_listings} listings). Splitting...")
            mid = (min_price + max_price) // 2
            left_urls = self.discover_bracket(min_price, mid, indent + 1)

            # SPEEDUP 4: Wait time during search split is greatly shortened
            time.sleep(random.uniform(0.5, 1.0))

            right_urls = self.discover_bracket(mid + 1, max_price, indent + 1)
            return left_urls + right_urls

        bracket_urls = []
        if total_listings:
            total_pages = math.ceil(total_listings / config.PAGE_SIZE)
            total_pages = min(total_pages, 20) # HARD CAP AT 20 PAGES

            for page in range(total_pages):
                offset = page * config.PAGE_SIZE
                page_url = f"{url}&pagingOffset={offset}"
                bracket_urls.append(page_url)

            logger.info(f"{pad}  ✓ Safe range ({total_listings} listings). Generated {len(bracket_urls)} page URLs.")
        else:
            logger.warning(f"{pad}  ? Could not parse total count. Appending base URL only.")
            bracket_urls.append(url)

        return bracket_urls

# ── COMPONENT 2: Extractor ────────────────────────────────────────────────────
class DataExtractor:
    def __init__(self, driver: uc.Chrome):
        self.driver = driver

    def _resolve_rooms_index(self, soup: BeautifulSoup) -> int | None:
        headers = [th.get_text(strip=True) for th in soup.select("#searchResultsTable thead th.searchResultsAttributeHeader")]
        for idx, header in enumerate(headers):
            if "oda" in header.lower().replace("ı", "i"):
                return idx
        return None

    def extract_from_url(self, url: str) -> list[dict]:
        soup = load_and_bypass(self.driver, url)
        rooms_idx = self._resolve_rooms_index(soup)
        records = []

        for row in soup.select("#searchResultsTable tbody tr.searchResultsItem"):
            try:
                price_elem = row.select_one(".searchResultsPriceValue")
                loc_elem = row.select_one(".searchResultsLocationValue")
                attrs = row.select(".searchResultsAttributeValue")

                price = price_elem.text.strip() if price_elem else None
                district = " / ".join(loc_elem.stripped_strings) if loc_elem else "N/A"

                if rooms_idx is not None and len(attrs) > rooms_idx:
                    rooms = attrs[rooms_idx].text.strip()
                elif len(attrs) > 1:
                    rooms = attrs[1].text.strip()
                else:
                    rooms = "N/A"

                if price:
                    records.append({"District": district, "Rooms": rooms, "Price": price})
            except Exception as exc:
                logger.debug(f"Row parse error: {exc}")

        return records

    @staticmethod
    def save_to_csv(data_batch: list[dict]):
        if not data_batch: return
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)

        with open(config.CSV_OUTPUT_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
            if not file_exists:
                writer.writeheader()
            writer.writerows(data_batch)


# ── ADAPTER: Bridge for main.py ───────────────────────────────────────────────
def scrape_range(driver: uc.Chrome, min_price: int, max_price: int, done_ranges: set, save_fn, save_checkpoint_fn, indent: int = 0) -> int:
    """Connects the Scanner and Extractor to the main execution loop."""
    bracket_key = (min_price, max_price)

    if bracket_key in done_ranges:
        logger.info(f"↩  Skipping already-completed range {min_price}–{max_price} TL")
        return 0

    scanner = CategoryScanner(driver)
    extractor = DataExtractor(driver)

    # 1. Discover all URLs for this bracket
    urls_to_scrape = scanner.discover_bracket(min_price, max_price)

    total_saved_this_run = 0
    start_index = progress_tracker.get(bracket_key, 0)

    # 2. Extract data from each URL sequentially
    for i in range(start_index, len(urls_to_scrape)):
        url = urls_to_scrape[i]
        logger.info(f"  📄 Scraping page {i + 1}/{len(urls_to_scrape)} for {min_price}-{max_price} TL...")

        page_records = extractor.extract_from_url(url)

        if page_records:
            save_fn(page_records)
            total_saved_this_run += len(page_records)

        progress_tracker[bracket_key] = i + 1

        # SPEEDUP 5: Human-like wait reduced to once every 5 pages, duration set to 2-4 seconds
        if i > 0 and i % 5 == 0:
            pause_time = random.uniform(2, 4)
            logger.info(f"  ⏳ Taking a brief human-like pause of {pause_time:.2f} seconds...")
            time.sleep(pause_time)

    save_checkpoint_fn(min_price, max_price)
    done_ranges.add(bracket_key)

    if bracket_key in progress_tracker:
        del progress_tracker[bracket_key]

    return total_saved_this_run


def save_incremental(data_batch: list[dict]) -> None:
    """Appends data to the CSV file. Required by main.py."""
    if not data_batch: return
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)

    with open(config.CSV_OUTPUT_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)