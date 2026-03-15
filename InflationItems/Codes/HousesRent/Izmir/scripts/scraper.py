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

import config

logger = logging.getLogger(__name__)

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
    if "tarayıcınızı" not in driver.page_source.lower():
        return

    logger.info("🤖 Browser check page detected. Waiting for it to resolve...")
    start_time = time.time()

    while time.time() - start_time < 30:
        page_source = driver.page_source.lower()

        if "tarayıcınızı" not in page_source and "bekleyiniz" not in page_source:
            logger.info("✅ Browser check resolved automatically!")
            time.sleep(3)
            return

        try:
            btn = WebDriverWait(driver, 1).until(
                EC.element_to_be_clickable((By.ID, "btn-continue"))
            )
            reaction_time = random.uniform(7.0, 11.5)
            logger.info(f"🛑 Button found! Staring at it for {reaction_time:.2f} seconds to let background JS finish...")
            time.sleep(reaction_time)

            logger.info("🖱️ Clicking 'Devam Et' button...")
            btn.click()
            time.sleep(8)
            return
        except Exception:
            pass

        time.sleep(1)

    logger.warning("⚠️ Browser check timed out after 30 seconds.")

def load_and_bypass(driver: uc.Chrome, url: str) -> BeautifulSoup:
    if driver.current_url in ["data:,", "about:blank"]:
        logger.info("🔥 Warming up fresh browser on homepage...")
        driver.get("https://www.sahibinden.com/")
        time.sleep(random.uniform(4.0, 7.0))
        handle_browser_check(driver)

    driver.get(url)
    time.sleep(random.uniform(4.0, 6.0))

    handle_browser_check(driver)
    page_source = driver.page_source.lower()

    if "bir dakika lütfen" in page_source or "lütfen bekleyiniz" in page_source:
        logger.info("⏳ Hit the 'Please Wait' page. Waiting 15s...")
        time.sleep(15)
        handle_browser_check(driver)

    start_time = time.time()
    while time.time() - start_time < 20:
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if soup.select("#searchResultsTable tbody tr.searchResultsItem") or "ilan bulunamadı" in driver.page_source.lower():
            return soup
        time.sleep(1.5)

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
            time.sleep(random.uniform(config.BETWEEN_BRACKET_DELAY_MIN, config.BETWEEN_BRACKET_DELAY_MAX))
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