import os
import csv
import json
import time
import random
from datetime import datetime
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Configuration
# HEAVY_BRACKETS: 17 micro-brackets for massive cities to avoid the 1,000 limit
HEAVY_BRACKETS = [
    (0, 11999), (12000, 13999), (14000, 14999), (15000, 15999), (16000, 16999),
    (17000, 17999), (18000, 18999), (19000, 19999), (20000, 20999),
    (21000, 22999), (23000, 24999), (25000, 26999),
    (27000, 29999), (30000, 34999), (35000, 39999), (40000, 49999),
    (50000, 9999999)
]

# LIGHT_BRACKETS: Just 5 wide brackets for smaller cities
LIGHT_BRACKETS = [
    (0, 10000), (10001, 15000), (15001, 20000), (20001, 25000), (25001, 9999999)
]

# Map the cities to their specific folder names AND their required bracket strategy
CITIES = {
    'bursa':   {'folder': 'Bursa',   'brackets': HEAVY_BRACKETS},
    'yalova':  {'folder': 'Yalova',  'brackets': LIGHT_BRACKETS},
    'bilecik': {'folder': 'Bilecik', 'brackets': LIGHT_BRACKETS},
    'kutahya': {'folder': 'Kütahya', 'brackets': LIGHT_BRACKETS}
}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_BASE_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../Datas/HousesRent/"))

# --- IMPROVEMENT 1: Resume tracking ---
# A JSON file tracks which (city, bracket) pairs are already done today.
# Re-running the script will skip completed brackets instantly.
PROGRESS_FILE = os.path.join(SCRIPT_DIR, "scrape_progress.json")


def load_progress():
    """Loads today's scraping progress from a JSON file."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Only reuse progress if it's from today; reset for a new day
        if data.get("date") == today_str:
            return data
    return {"date": today_str, "completed": {}}


def mark_bracket_done(progress, city_key, min_price, max_price):
    """Marks a price bracket as completed in the progress file."""
    bracket_key = f"{min_price}-{max_price}"
    if city_key not in progress["completed"]:
        progress["completed"][city_key] = []
    if bracket_key not in progress["completed"][city_key]:
        progress["completed"][city_key].append(bracket_key)
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def is_bracket_done(progress, city_key, min_price, max_price):
    """Returns True if this bracket was already scraped successfully today."""
    bracket_key = f"{min_price}-{max_price}"
    return bracket_key in progress.get("completed", {}).get(city_key, [])


def setup_driver():
    """Sets up an undetected Chrome driver with a persistent profile."""
    options = uc.ChromeOptions()
    profile_path = os.path.join(SCRIPT_DIR, "SeleniumProfile")
    options.add_argument(f"--user-data-dir={profile_path}")
    driver = uc.Chrome(options=options, version_main=145)
    return driver


def save_to_csv_incremental(folder_name, data_batch):
    """Appends a batch of scraped data to the daily CSV file to prevent data loss."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    target_dir = os.path.join(DATA_BASE_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, f"{folder_name}_{today_str}.csv")

    file_exists = os.path.isfile(file_path)

    with open(file_path, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=["District", "Rooms", "Price"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data_batch)

    print(f"✅ Appended {len(data_batch)} records to {file_path}")


# --- IMPROVEMENT 2: Smart wait helper ---
# Waits for the results table to appear (up to `timeout` seconds) instead of
# always sleeping a fixed 2.5s. On fast connections this saves ~1s per page.
def wait_for_listings(driver, timeout=10):
    """
    Waits up to `timeout` seconds for the results table to be present in the DOM.
    Falls back gracefully if the element never appears (e.g. CAPTCHA page).
    Returns True if listings are visible, False otherwise.
    """
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "#searchResultsTable tbody tr.searchResultsItem")
            )
        )
        return True
    except TimeoutException:
        return False


def scrape_city(driver, city_url_name, folder_name, brackets, progress):
    """Scrapes data by looping through dynamically assigned price brackets."""
    print(f"\n{'='*50}")
    print(f"STARTING FULL SCRAPE FOR: {folder_name}")
    print(f"{'='*50}")

    for min_price, max_price in brackets:

        # --- IMPROVEMENT 3: Skip already-completed brackets ---
        if is_bracket_done(progress, city_url_name, min_price, max_price):
            print(f"⏭️  Skipping {min_price}-{max_price} TL (already done today).")
            continue

        print(f"\n>>> Targeting Price Range: {min_price} TL to {max_price} TL")

        url = (
            f"https://www.sahibinden.com/kiralik/{city_url_name}"
            f"?pagingSize=50&price_min={min_price}&price_max={max_price}"
        )
        driver.get(url)

        bracket_data = []
        page_num = 1

        while True:
            # --- IMPROVEMENT 4: Smart wait replaces the blind 2.5s sleep ---
            listings_visible = wait_for_listings(driver, timeout=10)

            soup = BeautifulSoup(driver.page_source, 'lxml')  # IMPROVEMENT 5: lxml is 2-3x faster
            listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

            if not listings:
                page_source_lower = driver.page_source.lower()
                if "ilan bulunamadı" in page_source_lower or "bulunamamıştır" in page_source_lower:
                    print(f"No houses exist between {min_price}-{max_price} TL. Moving to next bracket.")
                    break

                print("\n" + "=" * 50)
                print("⚠️ ACTION REQUIRED: Script blocked by CAPTCHA or Login.")
                print("1. Look at the Chrome window and solve the puzzle.")
                print("2. Wait until you clearly see the list of houses.")
                print("=" * 50)
                input("Press ENTER here in the terminal ONLY AFTER you see the listings...")

                soup = BeautifulSoup(driver.page_source, 'lxml')
                listings = soup.select("#searchResultsTable tbody tr.searchResultsItem")

                if not listings:
                    print(f"Still failing to load {min_price}-{max_price} TL. Skipping bracket.")
                    break

            print(f"Scraping page {page_num} for bracket {min_price}-{max_price} TL...")

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

            # Pagination
            next_button = soup.find('a', title='Sonraki')
            if next_button and 'href' in next_button.attrs:
                next_url = "https://www.sahibinden.com" + next_button['href']
                driver.get(next_url)
                page_num += 1
                # --- IMPROVEMENT 6: Tighter inter-page delay (was 2-4s) ---
                time.sleep(random.uniform(1.2, 2.5))
            else:
                print(f"Finished gathering all houses in the {min_price}-{max_price} TL range.")
                break

        # Save this bracket's data, then mark it done so re-runs can skip it
        if bracket_data:
            save_to_csv_incremental(folder_name, bracket_data)

        mark_bracket_done(progress, city_url_name, min_price, max_price)

        # --- IMPROVEMENT 7: Tighter inter-bracket delay (was 2-4s) ---
        time.sleep(random.uniform(1.0, 2.0))


def main():
    # --- IMPROVEMENT 8: BUG FIX — no longer deletes today's CSV at startup ---
    # The original code wiped the day's data every time main() ran, which would
    # destroy partial results if the script crashed and was restarted.
    # Now we just load progress and skip what's already done.

    progress = load_progress()

    driver = setup_driver()
    try:
        for city_url_name, city_data in CITIES.items():
            scrape_city(
                driver,
                city_url_name,
                city_data['folder'],
                city_data['brackets'],
                progress
            )
            time.sleep(random.uniform(3, 5))
    finally:
        driver.quit()


if __name__ == "__main__":
    main()