"""
scraper.py — Core scraping logic for the Izmir rent scraper.

Key design: SMART ADAPTIVE BRACKETS (EARLY PEEK) + ACTIVE CLOUDFLARE BYPASS
------------------------------------------------
For any price range, the scraper loads page 1 and looks for the text telling
us the total number of listings.
- If count <= 1000: It continues and scrapes all pages.
- If count > 1000: It stops immediately, cuts the price range in half, and
  recursively tries again.

Anti-Bot Evasion & Resuming:
Actively clicks through Cloudflare Turnstile "Devam Et" buttons.
If a hard CAPTCHA or Login wall is detected, it raises a CaptchaDetectedException.
The main process deletes the profile (force-killing tasks to avoid file locks)
and restarts.
"""

import csv
import logging
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

progress_tracker = {}

# ── Custom Exception Class ────────────────────────────────────────────────────
class CaptchaDetectedException(Exception):
    """Raised when bot protection (CAPTCHA or Login wall) is detected."""
    pass

# ── Profile Cleanup ───────────────────────────────────────────────────────────
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
            shutil.rmtree(profile_dir)
            logger.info("✅ Profile deleted successfully.")
        except Exception as e:
            logger.warning(f"⚠️ First deletion attempt failed: {e}. Retrying...")
            time.sleep(2)
            try:
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

# ── Active Bypass Logic (Imported from First Script) ──────────────────────────
def handle_browser_check(driver: uc.Chrome):
    """Detects and clicks through Sahibinden's browser check page (Cloudflare Turnstile)."""
    if "tarayıcınızı kontrol ediyoruz" not in driver.page_source.lower():
        return
    logger.info("🤖 Browser check page detected, waiting for Turnstile...")
    try:
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='cf-turnstile-response']"))
        )
        time.sleep(random.uniform(4.0, 6.0))  # Wait for token to fill

        btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "btn-continue"))
        )
        btn.click()
        logger.info("✅ Clicked 'Devam Et' (Continue), loading page...")
        time.sleep(random.uniform(4.0, 6.0))
    except Exception as e:
        logger.warning(f"⚠️ Could not bypass browser check: {e}")

def is_waiting_page(page_source: str) -> bool:
    """Detects Sahibinden's Cloudflare 'please wait' challenge."""
    lower = page_source.lower()
    return any(s in lower for s in ["bir dakika lütfen", "lütfen bekleyiniz"])

def is_login_page(page_source: str) -> bool:
    """Detects if Sahibinden is showing an actual login/captcha page."""
    lower = page_source.lower()
    login_signals = ["giriş yap", "üye girişi", "captcha", "güvenlik doğrulama", "robot olmadığınızı"]
    strong_hits = sum(1 for s in login_signals if s in lower)
    return strong_hits >= 1 and "searchresultstable" not in lower

def wait_for_challenge(driver: uc.Chrome, max_wait=20) -> bool:
    """Waits for a Cloudflare-style challenge to resolve."""
    logger.info(f"⏳ Waiting for challenge page to resolve (up to {max_wait}s)...")
    for i in range(max_wait // 2):
        time.sleep(random.uniform(4.0, 6.0))
        if not is_waiting_page(driver.page_source):
            logger.info(f"✅ Challenge resolved after ~{(i + 1) * 2}s")
            return True
    logger.warning("⏰ Challenge did not resolve in time.")
    return False

def load_and_bypass(driver: uc.Chrome, url: str) -> BeautifulSoup:
    """
    Actively loads a URL and navigates Sahibinden's security checkpoints.
    Replaces the old passive _wait_for_listings function.
    """
    driver.get(url)
    time.sleep(random.uniform(4.0, 6.0))

    # STAGE 0: Turnstile Check
    handle_browser_check(driver)
    page_source = driver.page_source

    # STAGE 1: Cloudflare Auto-Wait
    if is_waiting_page(page_source):
        if wait_for_challenge(driver):
            handle_browser_check(driver)
            page_source = driver.page_source
        else:
            raise CaptchaDetectedException("Challenge stuck. Restart required.")

    # STAGE 2: Hard Block
    if is_login_page(page_source):
        raise CaptchaDetectedException("Login/CAPTCHA wall detected! Restart required.")

    # STAGE 3: Final validation that listings are visible
    start_time = time.time()
    while time.time() - start_time < 15: # 15 second timeout for DOM to render
        soup = BeautifulSoup(driver.page_source, "html.parser")
        if soup.select("#searchResultsTable tbody tr.searchResultsItem"):
            return soup

        page_lower = driver.page_source.lower()
        if "ilan bulunamadı" in page_lower or "bulunamamıştır" in page_lower:
            return soup

        time.sleep(1)

    raise CaptchaDetectedException("Page loaded but listings never appeared (Silent block).")


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

    if bracket_key in done_ranges:
        logger.info("%s↩  Skipping already-completed range %d–%d TL", pad, min_price, max_price)
        return 0

    width = max_price - min_price
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

    if start_page > 1:
        offset = (start_page - 1) * config.PAGE_SIZE
        url += f"&pagingOffset={offset}"

    # Use the active bypass loader instead of driver.get + passive wait
    soup = load_and_bypass(driver, url)

    # ── SPLIT DECISION ──
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
            save_fn(page_records)
            total_records_saved_this_run += len(page_records)
            progress_tracker[bracket_key] = current_page + 1

            logger.info("%s      Page %2d: %2d listings saved | %d–%d TL",
                pad, current_page, len(page_records), min_price, max_price)

        if current_page > 0 and current_page % 3 == 0:
            pause_time = random.uniform(3, 6)
            logger.info("%s      ⏳ Taking a human-like pause of %.2f seconds...", pad, pause_time)
            time.sleep(pause_time)

        has_next = bool(soup.find("a", title="Sonraki"))

        if current_page >= 20:
             break

        if has_next:
            next_btn = soup.find("a", title="Sonraki")
            next_url = "https://www.sahibinden.com" + next_btn["href"]

            # Use the active bypass loader for pagination as well
            soup = load_and_bypass(driver, next_url)

            current_page += 1
            if rooms_idx is None:
                rooms_idx = _resolve_rooms_index(soup)
        else:
            break

    logger.info("%s✅ Finished entirely. Saved %d records this run for %d–%d TL.", pad, total_records_saved_this_run, min_price, max_price)

    save_checkpoint_fn(min_price, max_price)
    done_ranges.add(bracket_key)

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