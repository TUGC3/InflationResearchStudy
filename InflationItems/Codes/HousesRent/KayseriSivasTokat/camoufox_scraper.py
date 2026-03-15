import os
import csv
import re
import time
import random
import shutil
from datetime import datetime
from bs4 import BeautifulSoup
from camoufox.sync_api import Camoufox

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


# ============================================================
# PROTECTION HANDLERS
# ============================================================

def handle_browser_check(page):
    """Clicks through Sahibinden's Cloudflare Turnstile browser check page.

    Waits for the Turnstile widget to appear, sleeps for token population
    (shadow DOM prevents direct inspection), clicks 'Devam Et', then waits
    until the check page is fully gone before returning.
    """
    if "tarayıcınızı kontrol ediyoruz" not in page.content().lower():
        return

    print("🤖 Browser check sayfası tespit edildi, Turnstile bekleniyor...")
    try:
        # Wait for Turnstile widget container
        page.wait_for_selector("#turnStileWidget", timeout=25_000)

        # Fixed wait — token lives inside Shadow DOM, cannot be read directly
        print("   ⏳ Turnstile token bekleniyor (shadow DOM)...")
        time.sleep(random.uniform(10.0, 13.0))

        # Click the continue button
        page.wait_for_selector("#btn-continue", timeout=15_000)
        page.click("#btn-continue")
        print("✅ 'Devam Et' butonuna tıklandı, sayfa geçişi bekleniyor...")

        # Wait until the browser check page is gone
        page.wait_for_function(
            "() => !document.body.innerText.toLowerCase().includes('tarayıcınızı kontrol ediyoruz')",
            timeout=20_000
        )
    except Exception as e:
        print(f"⚠️ Browser check geçilemedi: {e}")


def is_waiting_page(html):
    lower = html.lower()
    return any(s in lower for s in ["bir dakika lütfen", "lütfen bekleyiniz"])


def is_login_page(html):
    lower = html.lower()
    login_signals = ["giriş yap", "üye girişi", "captcha", "güvenlik doğrulama", "robot olmadığınızı"]
    strong_hits = sum(1 for s in login_signals if s in lower)
    return strong_hits >= 1 and "searchresultstable" not in lower


def wait_for_challenge(page, max_wait=20):
    """Waits for a self-resolving Cloudflare challenge to clear."""
    print(f"⏳ Waiting for challenge page to resolve (up to {max_wait}s)...")
    for i in range(max_wait // 2):
        time.sleep(random.uniform(4.0, 6.0))
        if not is_waiting_page(page.content()):
            print(f"✅ Challenge resolved after ~{(i + 1) * 2}s")
            return True
    print("⏰ Challenge did not resolve in time.")
    return False


def wait_for_listings(page, timeout=15_000):
    """Waits until the search results table is present in the DOM.

    Called after every navigation to ensure listing rows are fully
    rendered before BeautifulSoup parses the HTML. Prevents empty
    extractions caused by parsing too early after a Turnstile redirect.

    Returns True if listings appeared, False if timeout was reached.
    """
    try:
        page.wait_for_selector(
            "#searchResultsTable tbody tr.searchResultsItem",
            timeout=timeout
        )
        return True
    except Exception:
        return False


def safe_goto(page, url):
    """Navigates to a URL and handles all Sahibinden protection layers.

    Returns True on success. On success, the listing table is guaranteed
    to be present in the DOM. Unlike the Selenium version, we do not need
    to restart the browser — camoufox handles fingerprint rotation
    automatically, so a simple re-navigation is sufficient on blocks.
    """
    page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    time.sleep(random.uniform(3.0, 5.0))

    # Layer 0: Browser check (Turnstile)
    handle_browser_check(page)

    html = page.content()

    # After Turnstile, sahibinden may redirect to login if it suspects a bot
    if is_login_page(html):
        print("🔄 Browser check sonrası login sayfasına yönlendirildi! Tekrar deneniyor...")
        time.sleep(random.uniform(8, 12))
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(random.uniform(4, 7))
        handle_browser_check(page)
        html = page.content()

    # Layer 1: Cloudflare waiting page (self-resolving)
    if is_waiting_page(html):
        resolved = wait_for_challenge(page)
        if resolved:
            handle_browser_check(page)
            html = page.content()
        else:
            print("🔄 Challenge stuck. Re-navigating...")
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            time.sleep(random.uniform(4, 7))
            handle_browser_check(page)
            html = page.content()
            if is_waiting_page(html):
                wait_for_challenge(page)
                handle_browser_check(page)
                html = page.content()

    # Layer 2: Login / CAPTCHA wall
    if is_login_page(html):
        print("🔄 Login/CAPTCHA page detected! Re-navigating...")
        time.sleep(random.uniform(5, 10))
        page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        time.sleep(random.uniform(4, 7))
        handle_browser_check(page)
        html = page.content()

        if is_waiting_page(html):
            wait_for_challenge(page)
            handle_browser_check(page)
            html = page.content()

        if is_login_page(html):
            print("❌ Still blocked after re-navigation.")
            return False

    # Wait for the listings table to be fully rendered in the DOM
    wait_for_listings(page)
    return True


# ============================================================
# PRICE NORMALIZATION
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
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 1 and all(p.isdigit() for p in parts):
            if all(len(p) == 3 for p in parts[1:]):
                cleaned = "".join(parts)

    try:
        return float(cleaned)
    except ValueError:
        return None


# ============================================================
# COMPONENT 1: LINK DISCOVERY
# Scans all bracket + pagination combinations and returns a
# flat list of (url, page_html, min_price, max_price).
# HTML is cached here so Component 2 needs zero extra requests.
# ============================================================

def discover_pages(page, city_url_name, brackets):
    """Collects all search result page URLs + their HTML for a city.

    Iterates over price brackets and follows pagination. The page HTML
    is saved alongside each URL so the extraction component can reuse
    it directly — eliminating the double-request problem that previously
    caused Sahibinden to block the scraper.

    Returns:
        discovered: list of (url, page_html, min_price, max_price)
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
            success = safe_goto(page, current_url)
            if not success:
                print(f"   ⚠️ Could not access page {page_num}, stopping discovery for this bracket.")
                break

            # Cache HTML — extraction will reuse this, no second request needed
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                html_lower = html.lower()
                if "ilan bulunamadı" in html_lower or "bulunamamıştır" in html_lower:
                    print(f"   No listings exist in {min_price}-{max_price} TL range.")
                else:
                    print(f"   No listings on page {page_num}, stopping.")
                break

            discovered.append((current_url, html, min_price, max_price))
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
    return discovered


# ============================================================
# COMPONENT 2: DATA EXTRACTION
# Parses listing data from the HTML collected during discovery.
# Makes zero additional network requests.
# ============================================================

def extract_page(html):
    """Parses a single search results page and returns listing records.

    Uses the HTML snapshot saved during discovery — no network request.
    Price values are normalized to plain floats via normalize_price().

    Returns a list of {"District", "Rooms", "Price"} dicts.
    """
    soup = BeautifulSoup(html, 'html.parser')
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


def extract_all_pages(discovered_pages, folder_name):
    """Extracts listing data from all pages discovered in Component 1.

    Parses from cached HTML — zero additional network requests made.
    """
    print(f"\n{'=' * 50}")
    print(f"EXTRACTING DATA FOR: {folder_name.upper()}")
    print(f"{'=' * 50}")

    for i, (url, html, min_price, max_price) in enumerate(discovered_pages, 1):
        print(f"\n[{i}/{len(discovered_pages)}] Extracting: bracket {min_price}-{max_price} TL")

        records = extract_page(html)

        if records:
            save_to_csv_incremental(folder_name, records)
            print(f"   ✅ Saved {len(records)} records.")
        else:
            print(f"   ⚠️ No records extracted from this page.")


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
    with Camoufox(headless=False) as browser:
        page = browser.new_page()

        for city_url_name, city_data in CITIES.items():
            print(f"\n{'=' * 50}")
            print(f"CITY: {city_data['folder'].upper()}")
            print(f"{'=' * 50}")

            # COMPONENT 1: Discover all pages + cache their HTML
            discovered_pages = discover_pages(
                page,
                city_url_name,
                city_data['brackets']
            )

            # COMPONENT 2: Extract from cached HTML — zero extra requests
            extract_all_pages(discovered_pages, city_data['folder'])

            time.sleep(random.uniform(4.0, 6.0))


if __name__ == "__main__":
    main()