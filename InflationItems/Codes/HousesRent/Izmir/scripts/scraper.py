"""
scraper.py — Core scraping logic for the Izmir rent scraper.
Components:
  1. CategoryScanner  — discovers and generates target URLs
  2. DataExtractor    — visits URLs and extracts listing data
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

progress_tracker = {}

IZMIR_DISTRICT_SLUGS = [
    "izmir-aliaga", "izmir-balcova", "izmir-bayindir", "izmir-bayrakli",
    "izmir-bergama", "izmir-beydag", "izmir-bornova", "izmir-buca",
    "izmir-cesme", "izmir-cigli", "izmir-dikili", "izmir-foca",
    "izmir-gaziemir", "izmir-guzelbahce", "izmir-karabaglar", "izmir-karaburun",
    "izmir-karsiyaka", "izmir-kemalpasa", "izmir-kinik", "izmir-kiraz",
    "izmir-konak", "izmir-menderes", "izmir-menemen", "izmir-narlidere",
    "izmir-odemis", "izmir-seferihisar", "izmir-selcuk", "izmir-tire",
    "izmir-torbali", "izmir-urla",
]

IZMIR_SLUG_TO_DISTRICT = {
    "izmir-aliaga": "Aliağa", "izmir-balcova": "Balçova", "izmir-bayindir": "Bayındır",
    "izmir-bayrakli": "Bayraklı", "izmir-bergama": "Bergama", "izmir-beydag": "Beydağ",
    "izmir-bornova": "Bornova", "izmir-buca": "Buca", "izmir-cesme": "Çeşme",
    "izmir-cigli": "Çiğli", "izmir-dikili": "Dikili", "izmir-foca": "Foça",
    "izmir-gaziemir": "Gaziemir", "izmir-guzelbahce": "Güzelbahçe", "izmir-karabaglar": "Karabağlar",
    "izmir-karaburun": "Karaburun", "izmir-karsiyaka": "Karşıyaka", "izmir-kemalpasa": "Kemalpaşa",
    "izmir-kinik": "Kınık", "izmir-kiraz": "Kiraz", "izmir-konak": "Konak",
    "izmir-menderes": "Menderes", "izmir-menemen": "Menemen", "izmir-narlidere": "Narlıdere",
    "izmir-odemis": "Ödemiş", "izmir-seferihisar": "Seferihisar", "izmir-selcuk": "Selçuk",
    "izmir-tire": "Tire", "izmir-torbali": "Torbalı", "izmir-urla": "Urla"
}


class CaptchaDetectedException(Exception):
    pass


# ── Browser lifecycle ─────────────────────────────────────────────────────────

def delete_selenium_profile() -> None:
    profile_dir = getattr(config, "SELENIUM_PROFILE_DIR", None)
    if profile_dir and os.path.exists(profile_dir):
        logger.info("🗑️ Deleting old Selenium profile (resetting identity)...")
        if os.name == "nt":
            try:
                subprocess.call("taskkill /F /IM chrome.exe /T",       shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.call("taskkill /F /IM chromedriver.exe /T", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass
        time.sleep(3)
        shutil.rmtree(profile_dir, ignore_errors=True)


def setup_driver() -> uc.Chrome:
    options = uc.ChromeOptions()
    options.page_load_strategy = "eager"

    # Disable image loading — pages load faster, less bandwidth.
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option("prefs", prefs)

    if hasattr(config, "SELENIUM_PROFILE_DIR") and config.SELENIUM_PROFILE_DIR:
        options.add_argument(f"--user-data-dir={config.SELENIUM_PROFILE_DIR}")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if os.environ.get("HEADLESS") == "true":
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

    return uc.Chrome(
        options=options,
        driver_executable_path=config.CHROMEDRIVER_PATH,
        version_main=147,
    )


# ── Page loading & bot-check handling ────────────────────────────────────────

def _find_accessibility_circle(driver: uc.Chrome):
    """
    Finds the circular accessibility icon button on the Sahibinden check screen.
    This is the grey circle with the person/wheelchair icon (NOT the blue button).
    It is typically an <img> or <svg> wrapped in a clickable container, OR
    an element whose tag/class references accessibility/check concepts.
    Returns the element or None.
    """
    # Priority selectors — from most specific to broadest.
    # The circle icon is separate from the blue "Lütfen bekleyin"/"Tekrar basın" button.
    selectors = [
        # DataDome / Sahibinden known selectors for the icon circle
        "input#icon",
        "input[type='image']",
        "#icon",
        "[id*='icon']",
        "[class*='icon']",
        # SVG or img inside a wrapper
        "svg",
        "img[src*='access']",
        "img[alt*='access']",
        # Generic: any element that is NOT the blue button
    ]

    for sel in selectors:
        try:
            elems = driver.find_elements(By.CSS_SELECTOR, sel)
            for e in elems:
                txt = (e.text or "").strip().lower()
                # Skip the blue button
                if "bekleyin" in txt or "tekrar" in txt or "basın" in txt:
                    continue
                if e.is_displayed():
                    return e
        except Exception:
            continue

    # Fallback: use JavaScript to find the element by its visual position.
    # The circle is always to the LEFT of the blue button on this page.
    # Find all visible interactive-ish elements and return the leftmost one.
    try:
        elems = driver.find_elements(By.XPATH,
            "//*[self::button or self::input or self::a or self::svg or self::img]"
            "[not(contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'bekle'))]"
            "[not(contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'),'tekrar'))]"
        )
        visible = [e for e in elems if e.is_displayed()]
        if visible:
            # Return the leftmost visible element (the circle is on the left)
            visible.sort(key=lambda e: e.location.get("x", 9999))
            return visible[0]
    except Exception:
        pass

    return None


def _try_click_hold_button(driver: uc.Chrome) -> bool:
    """
    Clicks the circular accessibility icon (the grey circle the user circled in red),
    waits for the page to show 'Tekrar basın', then clicks that blue button.
    Returns True if the full sequence succeeded.
    """
    try:
        logger.info("🔍 Looking for the accessibility circle icon...")

        # Wait up to 8s for the circle to be present
        circle = None
        deadline = time.time() + 8
        while time.time() < deadline:
            circle = _find_accessibility_circle(driver)
            if circle:
                break
            time.sleep(0.5)

        if not circle:
            logger.warning("⚠️ Could not locate the accessibility circle icon.")
            return False

        logger.info(f"🖱️  Found circle element: <{circle.tag_name}> — clicking it...")
        # Move naturally to the element, then click
        ActionChains(driver) \
            .move_to_element(circle) \
            .pause(random.uniform(0.4, 0.9)) \
            .click(circle) \
            .perform()
        logger.info("✅ Circle clicked. Waiting for 'Tekrar basın'...")

        time.sleep(random.uniform(1.0, 2.0))

        # Now wait for and click 'Tekrar basın'
        clicked = _try_click_tekrar_basin(driver)
        return clicked

    except Exception as e:
        logger.debug(f"_try_click_hold_button error: {e}")
        return False


def _try_click_tekrar_basin(driver: uc.Chrome) -> bool:
    """
    Waits for the blue 'Tekrar basın' button to appear and clicks it.
    Tries ActionChains first, falls back to JS click.
    Returns True on success.
    """
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            src = driver.page_source.lower()
            if "tekrar" in src:
                # Find the blue button — it contains "Tekrar basın" text
                for selector in ["button", "a", "[role='button']", "input[type='submit']"]:
                    elems = driver.find_elements(By.CSS_SELECTOR, selector)
                    for e in elems:
                        txt = (e.text or e.get_attribute("value") or "").lower()
                        if "tekrar" in txt and e.is_displayed():
                            try:
                                # Try natural mouse click first
                                ActionChains(driver) \
                                    .move_to_element(e) \
                                    .pause(random.uniform(0.3, 0.7)) \
                                    .click() \
                                    .perform()
                            except Exception:
                                # Fallback: JavaScript click (works even if element is covered)
                                driver.execute_script("arguments[0].click();", e)
                            logger.info("🎯 Clicked 'Tekrar basın'.")
                            time.sleep(random.uniform(2.5, 4.0))
                            return True
        except Exception:
            pass
        time.sleep(0.4)
    logger.debug("'Tekrar basın' button not found within timeout.")
    return False


def handle_browser_check(driver: uc.Chrome) -> None:
    page_source = driver.page_source.lower()
    if "tarayıcınızı" not in page_source and "kontrol ediliyor" not in page_source:
        return

    logger.info("🤖 Browser check detected. Attempting automated bypass...")
    start_time = time.time()

    while time.time() - start_time < 120:
        page_source = driver.page_source.lower()

        # ── Fully resolved ───────────────────────────────────────────────────
        if ("tarayıcınızı" not in page_source
                and "bekleyiniz" not in page_source
                and "kontrol ediliyor" not in page_source):
            logger.info("✅ Browser check resolved!")
            time.sleep(1.5)
            return

        # ── Press-and-Hold / Basılı Tut screen ──────────────────────────────
        if "basılı tutun" in page_source or "bağlantınız kontrol ediliyor" in page_source:
            logger.info("🖱️  'Press & Hold' screen detected — attempting auto-click...")
            success = _try_click_hold_button(driver)
            if success:
                # Give the page time to transition after the hold
                time.sleep(random.uniform(3.0, 5.0))
                continue  # Re-check page state
            else:
                # Auto-click failed; fall back to manual wait with shorter timeout
                logger.warning("⚠️  Auto-click failed. Waiting for manual intervention (2 min)...")
                manual_start = time.time()
                while time.time() - manual_start < 120:
                    src = driver.page_source.lower()
                    if "basılı tutun" not in src and "bağlantınız kontrol ediliyor" not in src:
                        logger.info("✅ Manually passed! Resuming automation...")
                        time.sleep(3)
                        return
                    time.sleep(2)
                logger.error("❌ Manual timeout reached.")
                return

        # ── Tekrar basın appeared without prior hold (edge case) ─────────────
        if "tekrar" in page_source:
            logger.info("🖱️  'Tekrar basın' detected — clicking...")
            _try_click_tekrar_basin(driver)
            time.sleep(random.uniform(2.0, 3.0))
            continue

        # ── Devam Et screen ──────────────────────────────────────────────────
        if "tarayıcınızı kontrol ediyoruz" in page_source and "devam et" in page_source:
            try:
                wait_time = random.uniform(25.0, 30.0)
                logger.info(f"⚠️ 'Devam Et' screen. Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                btn = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "btn-continue"))
                )
                ActionChains(driver).move_to_element(btn).pause(0.5).click().perform()
                logger.info("🎯 Clicked 'Devam Et'.")
                time.sleep(5)
                return
            except Exception as e:
                logger.error(f"❌ 'Devam Et' bypass error: {e}")
                time.sleep(2)
                continue

        time.sleep(1)

    logger.warning("⚠️ Browser check timed out after 120s.")


def accept_cookies(driver: uc.Chrome) -> None:
    try:
        btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "onetrust-accept-btn-handler"))
        )
        ActionChains(driver).move_to_element(btn).pause(random.uniform(0.5, 1.0)).click().perform()
        logger.info("✅ Cookies accepted.")
        time.sleep(random.uniform(1.0, 2.0))
    except Exception:
        logger.debug("Cookie banner not found or already accepted.")


def load_and_bypass(driver: uc.Chrome, url: str) -> BeautifulSoup:
    if "sahibinden.com" not in driver.current_url:
        logger.info("🔥 Establishing Sahibinden session via homepage first...")
        driver.get("https://www.sahibinden.com/")
        time.sleep(random.uniform(2.0, 4.0))
        handle_browser_check(driver)
        accept_cookies(driver)

    driver.get(url)
    time.sleep(random.uniform(0.5, 1.0))
    handle_browser_check(driver)

    page_source = driver.page_source.lower()
    if "bir dakika lütfen" in page_source or "lütfen bekleyiniz" in page_source:
        logger.info("⏳ 'Please Wait' page detected. Waiting 15s...")
        time.sleep(15)
        handle_browser_check(driver)

    start_time = time.time()
    while time.time() - start_time < 20:
        soup = BeautifulSoup(driver.page_source, "lxml")
        src = driver.page_source.lower()

        # CONDITION 1: Listings successfully loaded
        if soup.select("#searchResultsTable tbody tr.searchResultsItem"):
            return soup

        # CONDITION 2: Sahibinden explicitly says there are no listings here
        if any(phrase in src for phrase in ["ilan bulunamadı", "aradığınız kriterlere", "sonuç bulunamadı"]):
            return soup

        # CONDITION 3: The table frame loaded but it is completely empty (Last page scenario)
        if soup.select_one("#searchResultsTable") and "giriş yap" not in src:
            return soup

        # Re-check for bot walls that might have popped up dynamically
        if "tarayıcınızı" in src or "kontrol ediliyor" in src:
            handle_browser_check(driver)
            start_time = time.time()

        time.sleep(0.3)

    # If 20 seconds pass and none of the success conditions are met:
    driver.save_screenshot("debug_silent_block.png")
    final = driver.page_source.lower()
    if "giriş yap" in final and "searchresultstable" not in final:
        raise CaptchaDetectedException("Login wall detected — saved debug_silent_block.png.")
    raise CaptchaDetectedException("Listings never appeared — saved debug_silent_block.png.")


# ── URL helpers ───────────────────────────────────────────────────────────────

def _build_page_urls(base_url: str, total_listings: int) -> list[str]:
    total_pages = min(math.ceil(total_listings / config.PAGE_SIZE), 20)
    return [f"{base_url}&pagingOffset={p * config.PAGE_SIZE}" for p in range(total_pages)]


# ── COMPONENT 1: Scanner ──────────────────────────────────────────────────────

class CategoryScanner:
    def __init__(self, driver: uc.Chrome):
        self.driver = driver

    def _extract_total_listings(self, soup: BeautifulSoup) -> int | None:
        elem = soup.select_one(".result-text")
        if elem:
            m = re.search(r"(\d+)\s*ilan", elem.get_text(strip=True).replace(".", ""), re.IGNORECASE)
            if m:
                return int(m.group(1))
        return None

    def get_district_total(self, slug: str) -> int:
        """Returns the total number of listings for a bare district."""
        url = f"https://www.sahibinden.com/kiralik/{slug}?pagingSize={config.PAGE_SIZE}"
        logger.info(f"Checking total listings for district: {slug}...")
        soup = load_and_bypass(self.driver, url)
        return self._extract_total_listings(soup) or 0

    def get_district_pages_no_price(self, slug: str, total: int) -> list[str]:
        """Returns paginated URLs for a district when it's under the 1000 limit."""
        url = f"https://www.sahibinden.com/kiralik/{slug}?pagingSize={config.PAGE_SIZE}"
        return _build_page_urls(url, total)

    def discover_bracket(
        self,
        slug: str,
        min_price: int,
        max_price: int,
        indent: int = 0,
        results: list | None = None,
    ) -> list[str]:
        """
        Recursively discovers all page URLs for a specific district and price range.
        `results` is mutated in-place so partial progress survives a CAPTCHA.
        """
        if results is None:
            results = []

        pad = "  " * indent
        url = (
            f"https://www.sahibinden.com/kiralik/{slug}"
            f"?pagingSize={config.PAGE_SIZE}&price_min={min_price}&price_max={max_price}"
        )

        logger.info(f"{pad}▶ Checking {slug} | {min_price}–{max_price} TL…")
        soup  = load_and_bypass(self.driver, url)
        total = self._extract_total_listings(soup)

        if not total:
            logger.info(f"{pad}  📭 0 listings or unreadable. Skipping.")
            return results

        width = max_price - min_price

        if total > config.MAX_LISTINGS_PER_QUERY:
            if width > 0:
                logger.info(f"{pad}  ✂️ Too dense ({total} listings). Splitting...")
                mid = (min_price + max_price) // 2

                if mid == min_price:
                    self.discover_bracket(slug, min_price, min_price, indent + 1, results)
                    # SPEED UP: Slightly faster recursion delays
                    time.sleep(random.uniform(0.2, 0.4))
                    self.discover_bracket(slug, max_price, max_price, indent + 1, results)
                else:
                    self.discover_bracket(slug, min_price, mid, indent + 1, results)
                    time.sleep(random.uniform(0.2, 0.4))
                    self.discover_bracket(slug, mid + 1, max_price, indent + 1, results)

                return results
            else:
                logger.warning(
                    f"{pad}  ⚠️ Massive cluster at exactly {min_price} TL in {slug}! "
                    f"Capping at 1000 listings to prevent infinite loops."
                )
                page_urls = _build_page_urls(url, total)
                results.extend(page_urls)
                return results

        # Safe range
        page_urls = _build_page_urls(url, total)
        results.extend(page_urls)
        logger.info(f"{pad}  ✓ Safe ({total} listings) → {len(page_urls)} pages")
        return results

# ── COMPONENT 2: Extractor ────────────────────────────────────────────────────

class DataExtractor:
    def __init__(self, driver: uc.Chrome):
        self.driver = driver

    def _resolve_rooms_index(self, soup: BeautifulSoup) -> int | None:
        headers = [
            th.get_text(strip=True)
            for th in soup.select("#searchResultsTable thead th.searchResultsAttributeHeader")
        ]
        for idx, header in enumerate(headers):
            if "oda" in header.lower().replace("ı", "i"):
                return idx
        return None

    def extract_from_url(self, url: str) -> list[dict]:
        soup      = load_and_bypass(self.driver, url)
        rooms_idx = self._resolve_rooms_index(soup)
        records   = []

        for row in soup.select("#searchResultsTable tbody tr.searchResultsItem"):
            try:
                price_elem = row.select_one(".searchResultsPriceValue")
                loc_elem   = row.select_one(".searchResultsLocationValue")
                attrs      = row.select(".searchResultsAttributeValue")

                price    = price_elem.text.strip() if price_elem else None
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


import re


# ── Data cleaning & persistence ───────────────────────────────────────────────

def clean_new_batch(data_batch: list[dict]) -> list[dict]:
    cleaned = []

    for row in data_batch:
        price = row.get("Price", "N/A")

        # Strip everything EXCEPT numbers
        digits_only = re.sub(r'\D', '', price)
        price_int = int(digits_only) if digits_only else ""

        # Keep both District and Neighborhood
        cleaned.append({
            "District": row.get("District", "N/A"),
            "Neighborhood": row.get("Neighborhood", "N/A"),
            "Rooms": row.get("Rooms", "N/A"),
            "Price": price,
            "PriceInt": price_int
        })

    return cleaned


def save_incremental(data_batch: list[dict]) -> int:
    if not data_batch:
        return 0

    cleaned = clean_new_batch(data_batch)
    if not cleaned:
        return 0

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)

    with open(config.CSV_OUTPUT_FILE, mode="a", newline="", encoding="utf-8-sig") as f:
        # Added Neighborhood to the CSV columns!
        writer = csv.DictWriter(f, fieldnames=["District", "Neighborhood", "Rooms", "Price", "PriceInt"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(cleaned)

    return len(cleaned)