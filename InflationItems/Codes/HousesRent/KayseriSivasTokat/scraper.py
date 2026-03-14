import os
import csv
import re
import time
import random
import shutil
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ============================================================
# Per-city price brackets, calibrated from real data (2026-02-27)
# Each bracket targets ~200-250 listings to stay well under
# Sahibinden's 1,000 listing cap per search page.
# ============================================================

KAYSERI_BRACKETS = [
    (0, 19_999),
    (20_000, 39_999),
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999)
]

SIVAS_BRACKETS = [
    (0, 19_999),
    (20_000, 39_999),
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999)
]

TOKAT_BRACKETS = [
    (0, 19_999),
    (20_000, 39_999),
    (40_000, 59_999),
    (60_000, 99_999),
    (100_000, 9_999_999)
]

CITIES = {
    'kayseri': {'folder': 'Kayseri', 'brackets': KAYSERI_BRACKETS},
    'sivas':   {'folder': 'Sivas',   'brackets': SIVAS_BRACKETS},
    'tokat':   {'folder': 'Tokat',   'brackets': TOKAT_BRACKETS}
}

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/"))

_profile_counter = 0


# ============================================================
# DRIVER UTILITIES
# ============================================================

def setup_driver():
    """Creates a fresh Chrome instance with a brand new profile."""
    global _profile_counter
    _profile_counter += 1

    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, f"SeleniumProfile_{_profile_counter}")
    options.add_argument(f"--user-data-dir={profile_path}")
    if os.environ.get('HEADLESS', '').lower() in ('1', 'true', 'yes'):
        options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

    driver = uc.Chrome(options=options, version_main=145)
    return driver


def close_driver(driver):
    try:
        driver.quit()
    except Exception:
        pass
    print("🔒 Chrome instance closed.")


def cleanup_profiles():
    for item in os.listdir(SCRIPT_DIR):
        if item.startswith("SeleniumProfile_"):
            path = os.path.join(SCRIPT_DIR, item)
            try:
                shutil.rmtree(path)
                print(f"🧹 Cleaned up profile: {item}")
            except Exception:
                pass


# ============================================================
# PROTECTION HANDLERS
# ============================================================

def handle_browser_check(driver):
    """Clicks through Sahibinden's Cloudflare Turnstile browser check page.

    Waits for the Turnstile widget container to appear, pauses for the token
    to populate (shadow DOM prevents direct value inspection), then clicks
    'Devam Et'. After clicking, waits until the check page is gone instead
    of using a fixed sleep — this avoids both premature parsing and wasted
    time when the page resolves quickly.
    """
    if "tarayıcınızı kontrol ediyoruz" not in driver.page_source.lower():
        return
    print("🤖 Browser check sayfası tespit edildi, Turnstile bekleniyor...")
    try:
        # Wait for Turnstile widget container to appear
        WebDriverWait(driver, 25).until(
            EC.presence_of_element_located((By.ID, "turnStileWidget"))
        )

        # Fixed wait — token lives inside Shadow DOM, cannot be read directly
        print("   ⏳ Turnstile token bekleniyor (shadow DOM)...")
        time.sleep(random.uniform(10.0, 13.0))

        btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.ID, "btn-continue"))
        )
        btn.click()
        print("✅ 'Devam Et' butonuna tıklandı, sayfa geçişi bekleniyor...")

        # Wait until the browser check page disappears instead of fixed sleep
        WebDriverWait(driver, 20).until(
            lambda d: "tarayıcınızı kontrol ediyoruz" not in d.page_source.lower()
        )
    except Exception as e:
        print(f"⚠️ Browser check geçilemedi: {e}")


def is_waiting_page(page_source):
    lower = page_source.lower()
    return any(s in lower for s in ["bir dakika lütfen", "lütfen bekleyiniz"])


def is_login_page(page_source):
    lower = page_source.lower()
    login_signals = ["giriş yap", "üye girişi", "captcha", "güvenlik doğrulama", "robot olmadığınızı"]
    strong_hits = sum(1 for s in login_signals if s in lower)
    return strong_hits >= 1 and "searchresultstable" not in lower


def wait_for_challenge(driver, url, max_wait=20):
    print(f"⏳ Waiting for challenge page to resolve (up to {max_wait}s)...")
    for i in range(max_wait // 2):
        time.sleep(random.uniform(4.0, 6.0))
        if not is_waiting_page(driver.page_source):
            print(f"✅ Challenge resolved after ~{(i + 1) * 2}s")
            return True
    print("⏰ Challenge did not resolve in time.")
    return False


def wait_for_listings(driver, timeout=15):
    """Waits for the search results table to be present in the DOM.

    Called after every page navigation to ensure the listing rows are
    actually rendered before BeautifulSoup parses the HTML. Fixes the
    'No records extracted' issue that occurs when the DOM is parsed
    immediately after a Turnstile redirect before the table has loaded.

    Returns True if listings are visible, False if timeout is reached.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#searchResultsTable tbody tr.searchResultsItem")
            )
        )
        return True
    except Exception:
        return False


def safe_get(driver, url):
    """Navigates to a URL and handles all Sahibinden protection layers.

    Returns (driver, success). Driver may be a new instance if Chrome
    was restarted. On success, the listing table is guaranteed to be
    present in the DOM before this function returns.
    """
    driver.get(url)
    time.sleep(random.uniform(4.0, 6.0))

    # Layer 0: Browser check (Turnstile)
    handle_browser_check(driver)

    # After Turnstile, sahibinden may redirect to login if it suspects a bot
    if is_login_page(driver.page_source):
        print("🔄 Browser check sonrası login sayfasına yönlendirildi! Chrome yeniden başlatılıyor...")
        close_driver(driver)
        time.sleep(random.uniform(8, 12))
        driver = setup_driver()
        driver.get(url)
        time.sleep(random.uniform(4, 7))
        handle_browser_check(driver)

    page_source = driver.page_source

    # Layer 1: Cloudflare waiting page (self-resolving)
    if is_waiting_page(page_source):
        resolved = wait_for_challenge(driver, url)
        if resolved:
            handle_browser_check(driver)
            page_source = driver.page_source
        else:
            print("🔄 Challenge stuck. Restarting Chrome...")
            close_driver(driver)
            time.sleep(random.uniform(5, 10))
            driver = setup_driver()
            driver.get(url)
            time.sleep(random.uniform(4, 7))
            handle_browser_check(driver)
            page_source = driver.page_source
            if is_waiting_page(page_source):
                wait_for_challenge(driver, url)
                handle_browser_check(driver)
                page_source = driver.page_source

    # Layer 2: Login / CAPTCHA wall
    if is_login_page(page_source):
        print("🔄 Login/CAPTCHA page detected! Restarting Chrome...")
        close_driver(driver)
        time.sleep(random.uniform(5, 10))
        driver = setup_driver()
        driver.get(url)
        time.sleep(random.uniform(4, 7))
        handle_browser_check(driver)
        page_source = driver.page_source

        if is_waiting_page(page_source):
            wait_for_challenge(driver, url)
            handle_browser_check(driver)
            page_source = driver.page_source

        if is_login_page(page_source):
            print("❌ Still blocked after Chrome restart.")
            return driver, False

    # Wait for the listings table to be fully rendered in the DOM
    wait_for_listings(driver)

    return driver, True


# ============================================================
# PRICE NORMALIZATION  (adapted from Ankara scraper)
# Converts raw price strings like "15.000 TL" → 15000.0
# ============================================================

def normalize_price(price_text):
    """Cleans raw price strings from sahibinden into a plain float.

    Handles formats: "15.000 TL", "15,000", "1.500.000 TL", etc.
    Returns None for unparseable values so they can be filtered out.
    """
    if not price_text or price_text == "N/A":
        return None
    cleaned = price_text.lower()
    cleaned = cleaned.replace("tl", "").replace("₺", "").strip()
    cleaned = re.sub(r"[^\d,\.]", "", cleaned)
    if not cleaned:
        return None

    if "." in cleaned and "," in cleaned:
        # e.g. "1.500,00" → European decimal format
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        # "15.000" → thousands separator, not decimal
        if len(parts) > 1 and all(p.isdigit() for p in parts):
            if all(len(p) == 3 for p in parts[1:]):
                cleaned = "".join(parts)

    try:
        return float(cleaned)
    except ValueError:
        return None


# ============================================================
# COMPONENT 1: LINK DISCOVERY
# Scans all bracket + pagination combinations for a city and
# returns a flat list of (url, page_source, min_price, max_price).
# Page HTML is saved here so Component 2 can reuse it without
# making a second request for the same page.
# ============================================================

def discover_pages(driver, city_url_name, brackets):
    """Collects all search result page URLs for a city.

    Iterates over price brackets and follows pagination. For every page
    visited, the HTML is saved alongside the URL so that the extraction
    component can reuse it directly — eliminating the double-request
    problem that previously caused Sahibinden to block the scraper.

    Returns:
        driver: possibly restarted Chrome instance
        discovered: list of (url, page_source, min_price, max_price)
    """
    discovered = []

    for min_price, max_price in brackets:
        print(f"\n🔍 Discovering pages for bracket {min_price}-{max_price} TL...")
        page_num = 1

        base_url = (
            f"https://www.sahibinden.com/kiralik/{city_url_name}"
            f"?pagingSize=50&price_min={min_price}&price_max={max_price}"
        )
        current_url = base_url

        while True:
            driver, success = safe_get(driver, current_url)
            if not success:
                print(f"   ⚠️ Could not access page {page_num}, stopping discovery for this bracket.")
                break

            # Save HTML now — extraction will reuse this, no second request needed
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                page_source_lower = page_source.lower()
                if "ilan bulunamadı" in page_source_lower or "bulunamamıştır" in page_source_lower:
                    print(f"   No listings exist in {min_price}-{max_price} TL range.")
                else:
                    print(f"   No listings on page {page_num}, stopping.")
                break

            # Store URL + HTML together
            discovered.append((current_url, page_source, min_price, max_price))
            print(f"   ✔ Page {page_num} queued ({len(listings)} listings found)")

            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                current_url = "https://www.sahibinden.com" + next_button['href']
                page_num += 1
                time.sleep(random.uniform(4.0, 6.0))
            else:
                print(f"   Last page reached for bracket {min_price}-{max_price} TL.")
                break

    print(f"\n📋 Discovery complete. {len(discovered)} pages queued in total.")
    return driver, discovered


# ============================================================
# COMPONENT 2: DATA EXTRACTION
# Parses listing data from the HTML already collected during
# discovery. Makes zero additional network requests.
# ============================================================

def extract_page(page_source):
    """Parses a single search results page and returns listing records.

    Uses the HTML snapshot saved during discovery — no network request.
    Price values are normalized to plain floats via normalize_price().

    Returns a list of {"District", "Rooms", "Price"} dicts.
    """
    soup = BeautifulSoup(page_source, 'html.parser')
    listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")
    results = []

    for row in listings:
        try:
            price_elem = row.select_one(".searchResultsPriceValue")
            raw_price  = price_elem.text.strip() if price_elem else None
            price      = normalize_price(raw_price)

            location_elem = row.select_one(".searchResultsLocationValue")
            district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

            attributes = row.select(".searchResultsAttributeValue")
            rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

            if price is not None and district != "N/A":
                results.append({"District": district, "Rooms": rooms, "Price": price})
        except Exception as e:
            print(f"   ⚠️ Error parsing row: {e}")
            continue

    return results


def extract_all_pages(driver, discovered_pages, folder_name):
    """Extracts listing data from all pages discovered in Component 1.

    Each entry in discovered_pages already contains the page HTML so no
    additional requests are made. The driver is only used if an entry
    somehow has no cached HTML (should not happen in normal operation).
    """
    print(f"\n{'=' * 50}")
    print(f"EXTRACTING DATA FOR: {folder_name.upper()}")
    print(f"{'=' * 50}")

    for i, (url, page_source, min_price, max_price) in enumerate(discovered_pages, 1):
        print(f"\n[{i}/{len(discovered_pages)}] Extracting: bracket {min_price}-{max_price} TL")

        records = extract_page(page_source)

        if records:
            save_to_csv_incremental(folder_name, records)
            print(f"   ✅ Saved {len(records)} records.")
        else:
            print(f"   ⚠️ No records extracted from this page.")

    return driver


# ============================================================
# CSV HELPER
# ============================================================

def save_to_csv_incremental(folder_name, data_batch):
    today_str  = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path  = os.path.join(target_dir, f"{today_str}.csv")

    file_exists = os.path.isfile(file_path)
    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)

    print(f"   💾 Appended {len(data_batch)} records to {file_path}")


# ============================================================
# MAIN
# ============================================================

def main():
    driver = setup_driver()
    try:
        for city_url_name, city_data in CITIES.items():
            print(f"\n{'=' * 50}")
            print(f"CITY: {city_data['folder'].upper()}")
            print(f"{'=' * 50}")

            # COMPONENT 1: Discover all pages + cache their HTML
            driver, discovered_pages = discover_pages(
                driver,
                city_url_name,
                city_data['brackets']
            )

            # COMPONENT 2: Extract from cached HTML — zero extra requests
            driver = extract_all_pages(driver, discovered_pages, city_data['folder'])

            time.sleep(random.uniform(4.0, 6.0))
    finally:
        close_driver(driver)
        cleanup_profiles()


if __name__ == "__main__":
    main()