import csv
import logging
import math
import os
import random
import re
import time

from bs4 import BeautifulSoup
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.keys import Keys

import config

logger = logging.getLogger(__name__)

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


def human_like_scroll(driver: WebDriver, target_duration: float = 4.0):
    """Simulates a natural scroll while collecting data on a strict time budget."""
    start_time = time.time()
    logger.info(f"      🖱️  Simulating human scroll behavior (~{int(target_duration)}s)...")

    while (time.time() - start_time) < target_duration:
        total_height = driver.execute_script("return document.body.scrollHeight")
        current_pos = driver.execute_script("return window.pageYOffset;")

        step = random.randint(200, 400)
        new_pos = current_pos + step

        if new_pos > total_height:
            new_pos = max(0, total_height - random.randint(100, 300))

        driver.execute_script(f"window.scrollTo({{top: {new_pos}, behavior: 'smooth'}});")
        time.sleep(random.uniform(0.5, 0.9))

        # 15% chance of a small "hesitation" scroll back up
        if random.random() < 0.15:
            current_pos = driver.execute_script("return window.pageYOffset;")
            new_pos = max(0, current_pos - random.randint(50, 150))
            driver.execute_script(f"window.scrollTo({{top: {new_pos}, behavior: 'smooth'}});")
            time.sleep(random.uniform(0.4, 0.7))

    driver.execute_script(f"window.scrollTo({{top: {random.randint(100, 400)}, behavior: 'smooth'}});")
    time.sleep(0.5)


def _wait_for_listings(driver: WebDriver) -> BeautifulSoup:
    """Manual intervention logic for CAPTCHAs."""
    load_delay = max(config.PAGE_LOAD_FLOOR, random.normalvariate(config.PAGE_LOAD_DELAY, config.PAGE_LOAD_STDEV))
    time.sleep(load_delay)

    while True:
        try:
            btns = driver.find_elements("xpath",
                                        "//*[contains(translate(., 'ABCÇDEFGHIİJKLMNOÖPRSŞTUÜVYZ', 'abcçdefghıijklmnoöprsştuüvyz'), 'devam et')]")
            if btns:
                logger.info("   🔵 Found 'devam et' button! Clicking...")
                driver.execute_script("arguments[0].click();", btns[0])
                time.sleep(3)
        except:
            pass

        for _ in range(6):
            soup = BeautifulSoup(driver.page_source, "lxml")
            if soup.select(
                    "#searchResultsTable tbody tr.searchResultsItem") or "ilan bulunamadı" in driver.page_source.lower():
                return soup
            time.sleep(2)

        print("\n" + "=" * 60 + "\n🛑 CAPTCHA/BOT CHECK! Solve it manually.\n" + "=" * 60)
        input("   ▶ Press ENTER after listings are visible... ")


def warmup_session(driver: WebDriver) -> None:
    """Warmup flow: Google -> Home -> Search İzmir -> District Filters."""
    logger.info("🔥 Starting organic warmup flow...")
    try:
        driver.get("https://www.google.com")
        time.sleep(2)
        try:
            driver.find_element("xpath", "//button[contains(., 'Accept') or contains(., 'Kabul')]").click()
        except:
            pass

        search_q = driver.find_element("name", "q")
        search_q.send_keys("sahibinden")
        search_q.send_keys(Keys.ENTER)
        time.sleep(3)

        driver.find_element("xpath", "//a[contains(@href, 'sahibinden.com')]").click()
        time.sleep(4)

        try:
            driver.find_element("xpath", "//button[text()='Kabul Et' or text()='Accept']").click()
        except:
            pass

        logger.info("  → Simulating 'İzmir kiralık' search...")
        search_bar = driver.find_element("id", "searchText")
        search_bar.send_keys("İzmir kiralık")
        search_bar.send_keys(Keys.ENTER)
        time.sleep(5)

        # Use scroll logic on results
        human_like_scroll(driver)

        logger.info("  → Expanding district filters...")
        ilce_filter = driver.find_elements("xpath",
                                           "//li[contains(@class, 'filter-item')]//*[contains(text(), 'İlçe')]")
        if ilce_filter:
            driver.execute_script("arguments[0].click();", ilce_filter[0])
            time.sleep(3)

        logger.info("🚀 Warmup complete!")
    except Exception as e:
        logger.warning(f"⚠️ Warmup failed: {e}. Moving to scraping.")


def load_and_bypass(driver: WebDriver, url: str) -> BeautifulSoup:
    driver.execute_script(f"window.location.href = '{url}';")
    return _wait_for_listings(driver)


def _build_page_urls(base_url: str, total_listings: int) -> list[str]:
    total_pages = min(math.ceil(total_listings / config.PAGE_SIZE), 20)
    return [f"{base_url}&pagingOffset={p * config.PAGE_SIZE}" for p in range(total_pages)]


class CategoryScanner:
    def __init__(self, driver: WebDriver):
        self.driver = driver

    def _extract_total(self, soup):
        elem = soup.select_one(".result-text")
        if elem:
            m = re.search(r"(\d+)\s*ilan", elem.get_text(strip=True).replace(".", ""), re.IGNORECASE)
            return int(m.group(1)) if m else None
        return None

    def get_district_total(self, slug):
        url = f"https://www.sahibinden.com/kiralik/{slug}?pagingSize={config.PAGE_SIZE}"
        soup = load_and_bypass(self.driver, url)
        return self._extract_total(soup) or 0

    def get_district_pages_no_price(self, slug, total):
        url = f"https://www.sahibinden.com/kiralik/{slug}?pagingSize={config.PAGE_SIZE}"
        return _build_page_urls(url, total)

    def discover_bracket(self, slug, min_p, max_p, indent=0, results=None):
        if results is None: results = []
        pad = "  " * indent
        url = f"https://www.sahibinden.com/kiralik/{slug}?pagingSize={config.PAGE_SIZE}&price_min={min_p}&price_max={max_p}"
        logger.info(f"{pad}▶ Checking {slug} | {min_p}–{max_p} TL…")
        soup = load_and_bypass(self.driver, url)
        total = self._extract_total(soup)
        if not total: return results

        if total > config.MAX_LISTINGS_PER_QUERY and (max_p - min_p) > 0:
            mid = (min_p + max_p) // 2
            self.discover_bracket(slug, min_p, mid, indent + 1, results)
            time.sleep(random.uniform(0.3, 0.6))
            self.discover_bracket(slug, mid + 1, max_p, indent + 1, results)
        else:
            results.extend(_build_page_urls(url, total))
        return results


class DataExtractor:
    def __init__(self, driver: WebDriver):
        self.driver = driver

    def extract_from_url(self, url):
        # 1. Navigate and Wait
        load_and_bypass(self.driver, url)

        # 2. Scroll while "collecting" (Strict ~4.5s budget)
        human_like_scroll(self.driver)

        # 3. Scrape
        soup = BeautifulSoup(self.driver.page_source, "lxml")
        records = []
        for row in soup.select("#searchResultsTable tbody tr.searchResultsItem"):
            try:
                price = row.select_one(".searchResultsPriceValue").text.strip()
                loc = " / ".join(row.select_one(".searchResultsLocationValue").stripped_strings)
                attrs = [a.text.strip() for a in row.select(".searchResultsAttributeValue")]
                rooms = attrs[1] if len(attrs) > 1 else "N/A"
                records.append({"Rooms": rooms, "Price": price})
            except:
                continue
        return records


def save_incremental(data_batch):
    if not data_batch: return 0
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    file_exists = os.path.isfile(config.CSV_OUTPUT_FILE)
    with open(config.CSV_OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price", "PriceInt"])
        if not file_exists: writer.writeheader()
        for r in data_batch:
            p_int = "".join(filter(str.isdigit, r["Price"]))
            writer.writerow({**r, "PriceInt": p_int})
    return len(data_batch)