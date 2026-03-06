import os
import csv
import time
import random
import shutil
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc

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
    'sivas': {'folder': 'Sivas', 'brackets': SIVAS_BRACKETS},
    'tokat': {'folder': 'Tokat', 'brackets': TOKAT_BRACKETS}
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../Datas/HousesRent/"))

_profile_counter = 0


def _detect_chrome_version():
    """Auto-detect installed Chrome major version to avoid driver mismatch."""
    import subprocess
    for cmd in [
        ["google-chrome", "--version"],
        ["google-chrome-stable", "--version"],
        ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--version"],
        ["chromium-browser", "--version"],
    ]:
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode().strip()
            # e.g. "Google Chrome 145.0.7632.116"
            ver = int(out.split()[-1].split(".")[0])
            print(f"🔍 Detected Chrome version: {ver}")
            return ver
        except Exception:
            continue
    print("⚠️ Could not detect Chrome version, letting UC auto-detect.")
    return None


def setup_driver():
    """Creates a fresh Chrome instance with a brand new profile to avoid login locks."""
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
    """Safely closes a Chrome instance."""
    try:
        driver.quit()
    except Exception:
        pass
    print("🔒 Chrome instance closed.")


def is_waiting_page(page_source):
    """Detects Sahibinden's Cloudflare 'please wait' challenge (resolves itself)."""
    lower = page_source.lower()
    wait_signals = [
        "bir dakika lütfen",  # "Please wait a moment"
        "lütfen bekleyiniz",  # "Please wait"
    ]
    return any(s in lower for s in wait_signals)


def is_login_page(page_source):
    """Detects if Sahibinden is showing an actual login/captcha page (needs Chrome restart)."""
    lower = page_source.lower()
    login_signals = [
        "giriş yap",  # "Log in" button/page
        "üye girişi",  # "Member login"
        "captcha",
        "güvenlik doğrulama",  # "Security verification"
        "robot olmadığınızı",  # "Verify you're not a robot"
    ]
    # Make sure the page is actually a login form, not just a normal page with a login link
    # Check for multiple strong signals or a dedicated login form
    strong_hits = sum(1 for s in login_signals if s in lower)
    return strong_hits >= 1 and "searchresultstable" not in lower


def wait_for_challenge(driver, url, max_wait=20):
    """Waits for a Cloudflare-style challenge to resolve. Returns True if resolved."""
    print(f"⏳ Waiting for challenge page to resolve (up to {max_wait}s)...")
    for i in range(max_wait // 2):
        time.sleep(2)
        page = driver.page_source
        if not is_waiting_page(page):
            print(f"✅ Challenge resolved after ~{(i + 1) * 2}s")
            return True
    print("⏰ Challenge did not resolve in time.")
    return False


def save_to_csv_incremental(folder_name, data_batch):
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{today_str}.csv")

    file_exists = os.path.isfile(file_path)

    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)

    print(f"✅ Appended {len(data_batch)} records to {file_path}")


def scrape_city(driver, city_url_name, folder_name, brackets):
    print(f"\n{'=' * 50}")
    print(f"STARTING FULL SCRAPE FOR: {folder_name.upper()}")
    print(f"{'=' * 50}")

    for min_price, max_price in brackets:
        print(f"\n>>> Targeting Price Range: {min_price} TL to {max_price} TL")

        bracket_data = []
        page_num = 1

        url = f"https://www.sahibinden.com/kiralik/{city_url_name}?pagingSize=50&price_min={min_price}&price_max={max_price}"
        driver.get(url)

        while True:
            time.sleep(random.uniform(2.5, 4.5))

            page_source = driver.page_source

            # --- STAGE 1: Handle Cloudflare waiting page (resolves itself) ---
            if is_waiting_page(page_source):
                resolved = wait_for_challenge(driver, url)
                if resolved:
                    page_source = driver.page_source
                else:
                    # Challenge didn't resolve, restart Chrome
                    print("🔄 Challenge stuck. Restarting Chrome...")
                    close_driver(driver)
                    time.sleep(random.uniform(5, 10))
                    driver = setup_driver()
                    driver.get(url)
                    time.sleep(random.uniform(4, 7))
                    page_source = driver.page_source
                    if is_waiting_page(page_source):
                        wait_for_challenge(driver, url)
                        page_source = driver.page_source

            # --- STAGE 2: Handle actual login/captcha walls ---
            if is_login_page(page_source):
                print("🔄 Login/CAPTCHA page detected! Restarting Chrome...")
                close_driver(driver)
                time.sleep(random.uniform(5, 10))
                driver = setup_driver()
                driver.get(url)
                time.sleep(random.uniform(4, 7))
                page_source = driver.page_source

                # Wait out any challenge on the new instance
                if is_waiting_page(page_source):
                    wait_for_challenge(driver, url)
                    page_source = driver.page_source

                # If still blocked after restart, skip this bracket
                if is_login_page(page_source):
                    print("❌ Still blocked after Chrome restart. Skipping this bracket.")
                    break

            soup = BeautifulSoup(page_source, 'html.parser')
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                page_source_lower = page_source.lower()
                if "ilan bulunamadı" in page_source_lower or "bulunamamıştır" in page_source_lower:
                    print(f"No houses exist between {min_price}-{max_price} TL.")
                else:
                    print("⚠️ No listings found on this page. Moving to next bracket.")
                break

            print(f"Scraping page {page_num} for bracket {min_price}-{max_price} TL... ({len(listings)} listings)")

            for row in listings:
                try:
                    price_elem = row.select_one(".searchResultsPriceValue")
                    price = price_elem.text.strip() if price_elem else "N/A"

                    location_elem = row.select_one(".searchResultsLocationValue")
                    district = " / ".join(location_elem.stripped_strings) if location_elem else "N/A"

                    attributes = row.select(".searchResultsAttributeValue")
                    rooms = attributes[1].text.strip() if len(attributes) > 1 else "N/A"

                    if price != "N/A" and district != "N/A":
                        bracket_data.append({
                            "District": district,
                            "Rooms": rooms,
                            "Price": price
                        })
                except Exception as e:
                    print(f"Error parsing a row: {e}")
                    continue

            if bracket_data:
                save_to_csv_incremental(folder_name, bracket_data)
                bracket_data = []  # clear for next page

            # Pagination
            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                next_url = "https://www.sahibinden.com" + next_button['href']
                driver.get(next_url)
                page_num += 1
                time.sleep(random.uniform(2, 4))
            else:
                print(f"Finished gathering all houses in the {min_price}-{max_price} TL range.")
                break

    return driver  # Return the (possibly new) driver instance


def cleanup_profiles():
    """Remove all temporary Selenium profile directories."""
    for item in os.listdir(SCRIPT_DIR):
        if item.startswith("SeleniumProfile_"):
            path = os.path.join(SCRIPT_DIR, item)
            try:
                shutil.rmtree(path)
                print(f"🧹 Cleaned up profile: {item}")
            except Exception:
                pass


def main():
    driver = setup_driver()
    try:
        # Loop through the cities
        for city_url_name, city_data in CITIES.items():
            driver = scrape_city(driver, city_url_name, city_data['folder'], city_data['brackets'])
            time.sleep(3)
    finally:
        close_driver(driver)
        cleanup_profiles()


if __name__ == "__main__":
    main()