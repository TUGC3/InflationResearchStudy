import csv
import os
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import WebDriverException

# =========================
# CONFIG
# =========================

CITIES: Dict[str, str] = {
    "Eskisehir": "https://www.sahibinden.com/kiralik/eskisehir",
    "Bolu": "https://www.sahibinden.com/kiralik/bolu",
    "Bartin": "https://www.sahibinden.com/kiralik/bartin",
    "Zonguldak": "https://www.sahibinden.com/kiralik/zonguldak",
}

DATA_GROUP_FOLDER = "Eskisehir_Bolu_Bartin_Zonguldak"

HEADLESS = True  # ACTION için True

SLEEP_MIN = 2
SLEEP_MAX = 4

BROWSER_MAJOR_VERSION = 145
PAGING_SIZE = 50
MAX_PAGES_PER_BRACKET = 120
MAX_RETRY = 3

PRICE_BRACKETS: List[Tuple[int, int]] = [
    (0, 7999),
    (8000, 9999),
    (10000, 11999),
    (12000, 13999),
    (14000, 15999),
    (16000, 17999),
    (18000, 19999),
    (20000, 24999),
    (25000, 34999),
    (35000, 9999999),
]

# =========================
# DRIVER
# =========================

def setup_driver() -> uc.Chrome:
    options = uc.ChromeOptions()

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1400,900")
    options.add_argument("--lang=tr-TR")
    options.add_argument("--disable-blink-features=AutomationControlled")

    if HEADLESS:
        options.add_argument("--headless=new")

    driver = uc.Chrome(
        options=options,
        version_main=BROWSER_MAJOR_VERSION,
    )

    driver.execute_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )

    return driver


def polite_sleep():
    time.sleep(random.uniform(SLEEP_MIN, SLEEP_MAX))


# =========================
# BLOCK DETECTION
# =========================

def is_block_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")

    if soup.select_one("#searchResultsTable"):
        return False

    lower = html.lower()
    signals = [
        "just a moment",
        "bir dakika lütfen",
        "cf-challenge",
        "access denied",
        "forbidden",
        "captcha",
        "robot olmadığınızı",
        "giriş yap",
    ]
    return any(s in lower for s in signals)


# =========================
# PARSING
# =========================

def extract_listings(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = soup.select("#searchResultsTable tbody tr")

    results = []

    for row in rows:
        price_elem = row.select_one(".searchResultsPriceValue")
        loc_elem = row.select_one(".searchResultsLocationValue")
        attrs = row.select(".searchResultsAttributeValue")

        price = price_elem.get_text(strip=True) if price_elem else ""
        district = " / ".join(loc_elem.stripped_strings) if loc_elem else ""
        rooms = attrs[1].get_text(strip=True) if len(attrs) > 1 else ""

        if price and district:
            results.append({
                "District": district,
                "Rooms": rooms,
                "Price": price
            })

    return results


def find_next_url(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    next_btn = soup.find("a", title="Sonraki")
    if next_btn and next_btn.get("href"):
        return "https://www.sahibinden.com" + next_btn["href"]
    return None


# =========================
# CSV
# =========================

def append_to_csv(city: str, rows: List[dict]) -> str:
    base_dir = os.path.join("Datas", "HousesRent", DATA_GROUP_FOLDER, city)
    os.makedirs(base_dir, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    file_path = os.path.join(base_dir, f"{city.lower()}_{today}.csv")

    file_exists = os.path.isfile(file_path)

    with open(file_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)

    return file_path


# =========================
# SCRAPER
# =========================

def scrape_city(driver: uc.Chrome, city: str, base_url: str):

    print(f"\n=== {city} ===")

    for min_p, max_p in PRICE_BRACKETS:

        print(f"\n--- Bracket {min_p}-{max_p} ---")

        url = f"{base_url}?pagingSize={PAGING_SIZE}&price_min={min_p}&price_max={max_p}"
        page_count = 0

        while True:
            page_count += 1

            if page_count > MAX_PAGES_PER_BRACKET:
                print("Page limit reached.")
                break

            success = False

            for attempt in range(MAX_RETRY):
                try:
                    driver.get(url)
                    polite_sleep()
                    html = driver.page_source

                    if is_block_page(html):
                        print(f"Blocked (attempt {attempt+1})")
                        time.sleep(5)
                        continue

                    rows = extract_listings(html)
                    print(f"Page {page_count}: {len(rows)} listings")

                    if len(rows) == 0:
                        print("Zero listings. Skipping page.")
                        break

                    append_to_csv(city, rows)

                    next_url = find_next_url(html)
                    if not next_url:
                        success = True
                        break

                    url = next_url
                    polite_sleep()
                    success = True
                    break

                except WebDriverException:
                    print("Driver error. Retrying...")
                    time.sleep(5)

            if not success:
                print("Skipping bracket due to repeated block/errors.")
                break


# =========================
# MAIN
# =========================

def main():
    driver = None
    try:
        driver = setup_driver()
        for city, url in CITIES.items():
            scrape_city(driver, city, url)
            time.sleep(3)
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main()
